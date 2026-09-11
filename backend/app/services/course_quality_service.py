from __future__ import annotations

import re

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.assistants.base import ResearchAssistantProvider
from app.models.course_design import (
    ProjectActivity,
    ProjectAssessment,
    ProjectObjective,
    ProjectPedagogy,
    QualityCheck,
)
from app.models.course_project import CourseProject
from app.repositories.evidence_card_repository import EvidenceCardRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.course_design import (
    CourseQualityCheckProposal,
    CourseQualityCheckRequest,
    CourseQualityCheckResult,
)
from app.services.project_service import ProjectNotFoundError
from app.services.workflow_service import WorkflowService


class CourseQualityCheckNotFoundError(LookupError):
    pass


class CourseQualityWorkflowError(ValueError):
    pass


class CourseQualityApplyError(ValueError):
    pass


class CourseQualityService:
    """Run deterministic and AI-assisted quality checks on a completed blueprint."""

    _PROMPT = """检查当前课程设计，不生成或改写课程内容。针对认知负荷、活动复杂度、支架充分性、
过程性评价、目标—活动一致性、目标—评价一致性和 Evidence Fidelity，输出结构化检查项。
仅依据输入的研究证据，不得编造文献、作者、年份或页码。需要教师可应用的建议时，checkType
仅用于系统执行；evidence.target 仅保存 type、id、scaffold、studentEvidence 等机器参数。
suggestion 必须是面向教师的简洁自然中文，禁止出现 ADD_SCAFFOLD、ADD_PROCESS_EVIDENCE、
id:、type:、content: 等内部字段。"""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.projects = ProjectRepository(db)
        self.evidence_cards = EvidenceCardRepository(db)

    async def run(
        self, *, current_user_id: int, project_id: int, provider: ResearchAssistantProvider,
    ) -> dict[str, object]:
        project = self._owned_project(current_user_id=current_user_id, project_id=project_id)
        self._require_activity_ready(project)
        objectives, pedagogy, assessments, activities = self._design_basis(project.id)
        rule_checks = self._rule_checks(project, objectives, pedagogy, assessments, activities)
        try:
            ai_result = CourseQualityCheckResult.model_validate(
                await provider.check_course_quality(
                    self._quality_request(project, objectives, pedagogy, assessments, activities)
                )
            )
        except ValueError as exc:
            raise CourseQualityWorkflowError("质量检查结果不符合结构要求") from exc
        try:
            self.db.execute(delete(QualityCheck).where(QualityCheck.project_id == project.id))
            records = [
                self._new_record(project.id, check)
                for check in [*rule_checks, *ai_result.checks]
            ]
            self.db.add_all(records)
            project.workflow_state = "QUALITY_CHECKED"
            project.stale_sections_json = self._quality_checked_stale_sections(project)
            self.db.commit()
            for record in records:
                self.db.refresh(record)
        except Exception:
            self.db.rollback()
            raise
        return self._result(records)

    def get(self, *, current_user_id: int, project_id: int) -> dict[str, object]:
        project = self._owned_project(current_user_id=current_user_id, project_id=project_id)
        checks = list(
            self.db.scalars(
                select(QualityCheck)
                .where(QualityCheck.project_id == project.id)
                .order_by(QualityCheck.id)
            ).all()
        )
        return self._result(checks)

    def apply(
        self, *, current_user_id: int, project_id: int, check_id: int,
    ) -> dict[str, object]:
        project = self._owned_project(current_user_id=current_user_id, project_id=project_id)
        check = self.db.scalar(
            select(QualityCheck).where(
                QualityCheck.id == check_id, QualityCheck.project_id == project.id
            )
        )
        if check is None:
            raise CourseQualityCheckNotFoundError("Quality check was not found")
        target = check.evidence_json.get("target") if isinstance(check.evidence_json, dict) else None
        if not isinstance(target, dict):
            raise CourseQualityApplyError("This quality suggestion has no applicable target")
        try:
            if check.check_type == "ADD_SCAFFOLD":
                affected_type, affected_id = self._apply_scaffold(project, target)
            elif check.check_type == "ADD_PROCESS_EVIDENCE":
                affected_type, affected_id = self._apply_process_evidence(project, target)
            else:
                raise CourseQualityApplyError("This quality suggestion cannot be applied automatically")
            project.stale_sections_json = self._quality_stale_after_apply(
                project, affected_type
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {"applied": True, "affectedType": affected_type, "affectedId": affected_id}

    def _rule_checks(
        self, project: CourseProject, objectives: list[ProjectObjective],
        pedagogy: ProjectPedagogy | None, assessments: list[ProjectAssessment],
        activities: list[ProjectActivity],
    ) -> list[CourseQualityCheckProposal]:
        context_fields = [
            project.grade, project.topic, project.lesson_minutes, project.class_size,
            project.student_experience, project.devices_json,
        ]
        assessment_objective_ids = {
            item.objective_id for item in assessments if item.task_content.strip()
        }
        activity_objective_ids = {
            objective_id
            for activity in activities
            for objective_id in (activity.objective_refs_json or [])
            if isinstance(objective_id, int)
        }
        total_duration = sum(item.duration for item in activities)
        lesson_minutes = project.lesson_minutes or 0
        rules = [
            ("CONTEXT_COMPLETE", all(context_fields), "教学情境字段不完整", "补充年级、主题、课时、班级规模、学习经验和设备条件。"),
            ("OBJECTIVE_CONFIRMED", bool(objectives), "没有已确认的学习目标", "至少确认一个可观察、可评价的学习目标。"),
            ("PEDAGOGY_CONFIRMED", pedagogy is not None, "没有已确认的教学策略", "确认教学策略后再进行质量检查。"),
            ("OBJECTIVE_ASSESSMENT_ALIGNMENT", all(item.id in assessment_objective_ids for item in objectives), "存在目标缺少评价任务", "为每个目标补充至少一个有效评价任务。"),
            ("OBJECTIVE_ACTIVITY_ALIGNMENT", all(item.id in activity_objective_ids for item in objectives), "存在目标未被活动覆盖", "在相应活动的 objectiveRefs 中关联该目标。"),
            ("ACTIVITY_DURATION", bool(lesson_minutes) and total_duration <= lesson_minutes, "活动总时长超过课时或课时未设置", "调整活动时长，使总时长不超过课程时长。"),
            ("AI_ROLE_DEFINED", bool(activities) and all(bool(item.ai_role and item.ai_role.strip()) for item in activities), "存在活动未明确 AI 角色", "为每个活动填写明确的 AI 角色。"),
        ]
        return [
            CourseQualityCheckProposal(
                check_type=check_type,
                status="PASS" if passed else "WARNING",
                issue=None if passed else issue,
                reason="确定性完整性与对齐规则检查。",
                suggestion=None if passed else suggestion,
                evidence={},
            )
            for check_type, passed, issue, suggestion in rules
        ]

    def _quality_request(
        self, project: CourseProject, objectives: list[ProjectObjective],
        pedagogy: ProjectPedagogy | None, assessments: list[ProjectAssessment],
        activities: list[ProjectActivity],
    ) -> CourseQualityCheckRequest:
        evidence = self.evidence_cards.list_confirmed_by_project(project_id=project.id)
        return CourseQualityCheckRequest(
            project_id=project.id,
            context={
                "grade": project.grade, "topic": project.topic,
                "lessonMinutes": project.lesson_minutes,
                "studentExperience": project.student_experience or "",
                "deviceCondition": str((project.devices_json or [""])[0]),
            },
            objectives=[{"id": item.id, "content": item.content} for item in objectives],
            pedagogy={
                "id": pedagogy.id if pedagogy else None,
                "description": (
                    pedagogy.custom_description or pedagogy.rationale or ""
                    if pedagogy else ""
                ),
            },
            assessments=[
                {
                    "id": item.id, "objectiveId": item.objective_id,
                    "taskContent": item.task_content,
                    "studentEvidence": item.student_evidence_json or [],
                }
                for item in assessments
            ],
            activities=[
                {
                    "id": item.id, "name": item.name, "duration": item.duration,
                    "coreTask": item.core_task or "", "aiRole": item.ai_role,
                    "scaffolds": item.scaffolds_json or [],
                    "objectiveRefs": item.objective_refs_json or [],
                }
                for item in activities
            ],
            evidence=[
                {
                    "id": str(item.id), "finding": item.main_finding or "",
                    "implication": item.teaching_implication or "",
                }
                for item in evidence
            ],
            prompt=self._PROMPT,
        )

    def _design_basis(
        self, project_id: int,
    ) -> tuple[list[ProjectObjective], ProjectPedagogy | None, list[ProjectAssessment], list[ProjectActivity]]:
        objectives = list(
            self.db.scalars(
                select(ProjectObjective)
                .where(
                    ProjectObjective.project_id == project_id,
                    ProjectObjective.confirmed.is_(True),
                    or_(
                        ProjectObjective.teacher_action.is_(None),
                        ProjectObjective.teacher_action != "REJECT",
                    ),
                )
                .order_by(ProjectObjective.sequence_no, ProjectObjective.id)
            ).all()
        )
        pedagogy = self.db.scalar(
            select(ProjectPedagogy)
            .where(ProjectPedagogy.project_id == project_id, ProjectPedagogy.confirmed.is_(True))
            .order_by(ProjectPedagogy.id.desc())
            .limit(1)
        )
        assessments = list(
            self.db.scalars(
                select(ProjectAssessment)
                .where(ProjectAssessment.project_id == project_id, ProjectAssessment.confirmed.is_(True))
                .order_by(ProjectAssessment.id)
            ).all()
        )
        activities = list(
            self.db.scalars(
                select(ProjectActivity)
                .where(ProjectActivity.project_id == project_id)
                .order_by(ProjectActivity.sequence_no, ProjectActivity.id)
            ).all()
        )
        return objectives, pedagogy, assessments, activities

    def _apply_scaffold(
        self, project: CourseProject, target: dict[str, object],
    ) -> tuple[str, int]:
        if target.get("type") != "ACTIVITY" or not isinstance(target.get("id"), int):
            raise CourseQualityApplyError("ADD_SCAFFOLD requires an ACTIVITY target")
        scaffold = target.get("scaffold")
        if not isinstance(scaffold, str) or not scaffold.strip():
            raise CourseQualityApplyError("ADD_SCAFFOLD requires scaffold content")
        activity = self.db.scalar(
            select(ProjectActivity).where(
                ProjectActivity.id == target["id"], ProjectActivity.project_id == project.id
            )
        )
        if activity is None:
            raise CourseQualityApplyError("Suggestion target activity was not found")
        activity.scaffolds_json = list(activity.scaffolds_json or [])
        if scaffold not in activity.scaffolds_json:
            activity.scaffolds_json = [*activity.scaffolds_json, scaffold]
        activity.version += 1
        return "ACTIVITY", activity.id

    def _apply_process_evidence(
        self, project: CourseProject, target: dict[str, object],
    ) -> tuple[str, int]:
        if target.get("type") != "ASSESSMENT" or not isinstance(target.get("id"), int):
            raise CourseQualityApplyError("ADD_PROCESS_EVIDENCE requires an ASSESSMENT target")
        evidence = target.get("studentEvidence")
        if not isinstance(evidence, str) or not evidence.strip():
            raise CourseQualityApplyError("ADD_PROCESS_EVIDENCE requires studentEvidence content")
        assessment = self.db.scalar(
            select(ProjectAssessment).where(
                ProjectAssessment.id == target["id"],
                ProjectAssessment.project_id == project.id,
            )
        )
        if assessment is None:
            raise CourseQualityApplyError("Suggestion target assessment was not found")
        assessment.student_evidence_json = list(assessment.student_evidence_json or [])
        if evidence not in assessment.student_evidence_json:
            assessment.student_evidence_json = [*assessment.student_evidence_json, evidence]
        assessment.version += 1
        return "ASSESSMENT", assessment.id

    def _owned_project(self, *, current_user_id: int, project_id: int) -> CourseProject:
        project = self.projects.get_by_id_and_user(project_id=project_id, user_id=current_user_id)
        if project is None:
            raise ProjectNotFoundError("Project was not found for the current user")
        return project

    @staticmethod
    def _new_record(project_id: int, proposal: CourseQualityCheckProposal) -> QualityCheck:
        return QualityCheck(
            project_id=project_id, check_type=proposal.check_type,
            status=proposal.status, issue=proposal.issue, reason=proposal.reason,
            suggestion=CourseQualityService._sanitize_suggestion(
                proposal.check_type, proposal.suggestion, proposal.evidence
            ), evidence_json=proposal.evidence,
        )

    @staticmethod
    def _sanitize_suggestion(
        check_type: str, suggestion: str | None, evidence: dict[str, object],
    ) -> str | None:
        if not suggestion:
            return suggestion
        internal_pattern = re.compile(
            r"ADD_SCAFFOLD|ADD_PROCESS_EVIDENCE|(?:^|[,，;；]\s*)(?:id|type|content)\s*:",
            re.IGNORECASE,
        )
        if not internal_pattern.search(suggestion):
            return suggestion

        target = evidence.get("target") if isinstance(evidence, dict) else None
        if isinstance(target, dict):
            scaffold = target.get("scaffold")
            student_evidence = target.get("studentEvidence")
            if check_type == "ADD_SCAFFOLD" and isinstance(scaffold, str) and scaffold.strip():
                return f"建议在相应教学活动中增加学习支架：{scaffold.strip()}"
            if (
                check_type == "ADD_PROCESS_EVIDENCE"
                and isinstance(student_evidence, str)
                and student_evidence.strip()
            ):
                return f"建议在相应评价任务中补充过程性评价证据：{student_evidence.strip()}"

        content_match = re.search(r"content\s*:\s*(.+)$", suggestion, re.IGNORECASE)
        if content_match and content_match.group(1).strip():
            return content_match.group(1).strip()
        cleaned = re.sub(r"ADD_SCAFFOLD|ADD_PROCESS_EVIDENCE", "", suggestion, flags=re.IGNORECASE)
        cleaned = re.sub(r"(?:id|type)\s*:\s*[^,，;；]+[,，;；]?", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"content\s*:\s*", "", cleaned, flags=re.IGNORECASE)
        return cleaned.strip(" ：:,，;；") or "请根据该检查项完善课程设计。"

    @staticmethod
    def _quality_checked_stale_sections(project: CourseProject) -> list:
        return [
            section for section in (project.stale_sections_json or [])
            if section != "QUALITY"
        ]

    @staticmethod
    def _quality_stale_after_apply(project: CourseProject, affected_type: str) -> list:
        if affected_type == "ACTIVITY":
            return WorkflowService.stale_sections_after_activity_change(
                project.workflow_state, project.stale_sections_json
            )
        return WorkflowService.stale_sections_after_change(
            changed_section="ASSESSMENT",
            workflow_state=project.workflow_state,
            stale_sections=project.stale_sections_json,
        )

    @staticmethod
    def _require_activity_ready(project: CourseProject) -> None:
        if project.workflow_state != "ACTIVITY_READY" and not (
            project.workflow_state == "QUALITY_CHECKED"
            and "QUALITY" in (project.stale_sections_json or [])
        ):
            raise CourseQualityWorkflowError("Course blueprint must be ready before quality checking")

    @staticmethod
    def _result(checks: list[QualityCheck]) -> dict[str, object]:
        views = [
            {
                "qualityCheckId": item.id, "checkType": item.check_type,
                "status": item.status, "issue": item.issue, "reason": item.reason,
                "suggestion": CourseQualityService._sanitize_suggestion(
                    item.check_type, item.suggestion, item.evidence_json or {}
                ), "evidence": item.evidence_json or {},
            }
            for item in checks
        ]
        completion_checks = [
            item for item in views
            if item["checkType"] in {
                "CONTEXT_COMPLETE", "OBJECTIVE_CONFIRMED", "PEDAGOGY_CONFIRMED",
                "OBJECTIVE_ASSESSMENT_ALIGNMENT", "OBJECTIVE_ACTIVITY_ALIGNMENT",
                "ACTIVITY_DURATION", "AI_ROLE_DEFINED",
            }
        ]
        suggestions = [
            item for item in views if item["status"] == "WARNING" and item["suggestion"]
        ]
        return {
            "completionChecks": completion_checks,
            "qualitySummary": {
                "total": len(views),
                "passed": sum(item["status"] == "PASS" for item in views),
                "warnings": sum(item["status"] == "WARNING" for item in views),
            },
            "suggestions": suggestions,
        }
