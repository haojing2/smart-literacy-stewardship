from __future__ import annotations

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.assistants.base import ResearchAssistantProvider
from app.models.course_design import (
    DesignEvidenceLink,
    ProjectActivity,
    ProjectAssessment,
    ProjectObjective,
    ProjectPedagogy,
)
from app.models.course_project import CourseProject
from app.repositories.evidence_card_repository import EvidenceCardRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.course_design import (
    CourseActivityProposal,
    CourseActivityRegenerationRequest,
    CourseActivityTransformRequest,
    CourseActivityUpdateRequest,
    CourseBlueprintGenerationRequest,
    CourseBlueprintGenerationResult,
)
from app.services.project_service import ProjectNotFoundError
from app.services.workflow_service import WorkflowService


class CourseActivityNotFoundError(LookupError):
    pass


class CourseBlueprintWorkflowError(ValueError):
    pass


class CourseBlueprintDurationError(ValueError):
    pass


class CourseBlueprintService:
    """Generate an evidence-backed activity chain and edit one activity at a time."""

    _PROMPT = """基于教学情境、最终目标、最终教学策略、最终评价任务和研究证据，生成恰好 4 个连续教学活动。
每项仅输出 name、duration、coreTask、teacherAction、studentAction、aiRole、assessment、scaffolds、objectiveRefs。
活动时长总和不得超过课时；活动须覆盖目标和评价，并体现前后衔接。不要输出完整教案之外的解释。"""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.projects = ProjectRepository(db)
        self.evidence_cards = EvidenceCardRepository(db)

    async def generate(
        self, *, current_user_id: int, project_id: int, provider: ResearchAssistantProvider
    ) -> dict[str, object]:
        project = self._owned_project(current_user_id=current_user_id, project_id=project_id)
        objectives, pedagogy, assessments = self._generation_basis(project)
        request = self._generation_request(project, objectives, pedagogy, assessments)
        result = await self._generate_valid_blueprint(provider, request, project.lesson_minutes)
        try:
            self._remove_current_blueprint(project.id)
            activities = self._persist_activities(project, result.activities)
            self._link_evidence(project.id, activities)
            project.workflow_state = "ACTIVITY_READY"
            project.stale_sections_json = self._activity_change_stale_sections(project)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {
            "activities": [self._view(activity) for activity in activities],
            "totalDuration": sum(item.duration for item in activities),
        }

    def revise(
        self, *, current_user_id: int, project_id: int, activity_id: int,
        payload: CourseActivityUpdateRequest,
    ) -> dict[str, object]:
        project, activity = self._owned_activity(current_user_id, project_id, activity_id)
        self._require_activity_ready(project)
        try:
            for field, value in (
                ("name", payload.name),
                ("duration", payload.duration),
                ("core_task", payload.core_task),
                ("teacher_action", payload.teacher_action),
                ("student_action", payload.student_action),
                ("ai_role", payload.ai_role),
                ("assessment_note", payload.assessment),
                ("scaffolds_json", payload.scaffolds),
            ):
                if value is not None:
                    setattr(activity, field, value)
            self._ensure_duration_within_lesson(project)
            activity.version += 1
            project.stale_sections_json = self._activity_change_stale_sections(project)
            self.db.commit()
            self.db.refresh(activity)
        except Exception:
            self.db.rollback()
            raise
        return {"activity": self._view(activity), "totalDuration": self._total_duration(project.id)}

    async def regenerate(
        self, *, current_user_id: int, project_id: int, activity_id: int,
        provider: ResearchAssistantProvider,
    ) -> dict[str, object]:
        project, activity = self._owned_activity(current_user_id, project_id, activity_id)
        self._require_activity_ready(project)
        request = self._activity_regeneration_request(project, activity)
        try:
            proposal = CourseActivityProposal.model_validate(
                await provider.regenerate_course_activity(request)
            )
        except ValueError as exc:
            raise CourseBlueprintWorkflowError("活动重新生成结果不符合结构要求") from exc
        try:
            self._apply_proposal(activity, proposal)
            self._ensure_duration_within_lesson(project)
            activity.version += 1
            project.stale_sections_json = self._activity_change_stale_sections(project)
            self.db.commit()
            self.db.refresh(activity)
        except Exception:
            self.db.rollback()
            raise
        return {"activity": self._view(activity), "totalDuration": self._total_duration(project.id)}

    def transform(
        self, *, current_user_id: int, project_id: int, activity_id: int,
        payload: CourseActivityTransformRequest,
    ) -> dict[str, object]:
        project, activity = self._owned_activity(current_user_id, project_id, activity_id)
        self._require_activity_ready(project)
        try:
            if payload.action == "SHORTEN":
                if activity.duration <= 1:
                    raise CourseBlueprintDurationError("Activity duration cannot be shortened further")
                activity.duration -= max(1, activity.duration // 4)
                activity.core_task = f"{activity.core_task}（压缩为核心步骤）"
            elif payload.action == "INCREASE_DIFFICULTY":
                activity.core_task = f"{activity.core_task}（增加跨来源比较与理由说明）"
                activity.scaffolds_json = list(activity.scaffolds_json or []) + ["挑战问题：比较证据冲突时如何判断"]
            elif payload.action == "DECREASE_DIFFICULTY":
                activity.core_task = f"{activity.core_task}（先完成单一来源的示范核验）"
                activity.scaffolds_json = list(activity.scaffolds_json or []) + ["分步核验提示"]
            else:  # ADD_SCAFFOLD
                activity.scaffolds_json = list(activity.scaffolds_json or []) + ["核验步骤清单"]
            self._ensure_duration_within_lesson(project)
            activity.version += 1
            project.stale_sections_json = self._activity_change_stale_sections(project)
            self.db.commit()
            self.db.refresh(activity)
        except Exception:
            self.db.rollback()
            raise
        return {
            "activity": self._view(activity),
            "action": payload.action,
            "totalDuration": self._total_duration(project.id),
        }

    async def _generate_valid_blueprint(
        self, provider: ResearchAssistantProvider, request: CourseBlueprintGenerationRequest,
        lesson_minutes: int | None,
    ) -> CourseBlueprintGenerationResult:
        if not lesson_minutes:
            raise CourseBlueprintWorkflowError("Lesson minutes are required before generating a blueprint")
        if lesson_minutes < 4:
            raise CourseBlueprintDurationError("Lesson minutes must allow four non-empty activities")
        last_error: CourseBlueprintDurationError | None = None
        for _ in range(2):
            try:
                result = CourseBlueprintGenerationResult.model_validate(
                    await provider.generate_course_blueprint(request)
                )
                self._validate_generated_duration(result.activities, lesson_minutes)
                return result
            except CourseBlueprintDurationError as exc:
                last_error = exc
            except ValueError as exc:
                raise CourseBlueprintWorkflowError("课程蓝图生成结果不符合结构要求") from exc
        raise last_error or CourseBlueprintDurationError("Generated blueprint duration is invalid")

    def _generation_basis(
        self, project: CourseProject,
    ) -> tuple[list[ProjectObjective], ProjectPedagogy, list[ProjectAssessment]]:
        if project.workflow_state != "ASSESSMENT_CONFIRMED":
            raise CourseBlueprintWorkflowError("Assessments must be confirmed before generating a blueprint")
        objectives = self._confirmed_objectives(project.id)
        pedagogy = self.db.scalar(
            select(ProjectPedagogy)
            .where(ProjectPedagogy.project_id == project.id, ProjectPedagogy.confirmed.is_(True))
            .order_by(ProjectPedagogy.id.desc())
            .limit(1)
        )
        assessments = list(
            self.db.scalars(
                select(ProjectAssessment)
                .where(ProjectAssessment.project_id == project.id, ProjectAssessment.confirmed.is_(True))
                .order_by(ProjectAssessment.id)
            ).all()
        )
        if not objectives or pedagogy is None or not assessments:
            raise CourseBlueprintWorkflowError("Confirmed objectives, pedagogy, and assessments are required")
        return objectives, pedagogy, assessments

    def _generation_request(
        self, project: CourseProject, objectives: list[ProjectObjective],
        pedagogy: ProjectPedagogy, assessments: list[ProjectAssessment],
    ) -> CourseBlueprintGenerationRequest:
        evidence = self.evidence_cards.list_confirmed_by_project(project_id=project.id)
        return CourseBlueprintGenerationRequest(
            project_id=project.id,
            context={
                "grade": project.grade, "topic": project.topic,
                "lessonMinutes": project.lesson_minutes, "classSize": project.class_size,
                "studentExperience": project.student_experience or "",
                "deviceCondition": str((project.devices_json or [""])[0]),
                "additionalRequirements": project.additional_requirements or "",
            },
            objectives=[{"id": item.id, "content": item.content} for item in objectives],
            pedagogy={
                "primaryMethodId": pedagogy.primary_method_id,
                "customName": pedagogy.custom_name,
                "description": pedagogy.custom_description or pedagogy.rationale or "",
            },
            assessments=[
                {
                    "objectiveId": item.objective_id,
                    "taskContent": item.task_content,
                    "studentEvidence": item.student_evidence_json or [],
                    "criteria": item.criteria_json or [],
                }
                for item in assessments
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

    def _activity_regeneration_request(
        self, project: CourseProject, activity: ProjectActivity,
    ) -> CourseActivityRegenerationRequest:
        objectives, pedagogy, assessments = self._activity_generation_basis(project)
        activities = self._activities(project.id)
        position = next(index for index, item in enumerate(activities) if item.id == activity.id)
        return CourseActivityRegenerationRequest(
            blueprint=self._generation_request(project, objectives, pedagogy, assessments),
            activity=self._proposal_from_activity(activity),
            previous_activity=(
                self._proposal_from_activity(activities[position - 1]) if position else None
            ),
            next_activity=(
                self._proposal_from_activity(activities[position + 1])
                if position + 1 < len(activities) else None
            ),
        )

    def _activity_generation_basis(
        self, project: CourseProject,
    ) -> tuple[list[ProjectObjective], ProjectPedagogy, list[ProjectAssessment]]:
        objectives = self._confirmed_objectives(project.id)
        pedagogy = self.db.scalar(
            select(ProjectPedagogy)
            .where(ProjectPedagogy.project_id == project.id, ProjectPedagogy.confirmed.is_(True))
            .order_by(ProjectPedagogy.id.desc())
            .limit(1)
        )
        assessments = list(
            self.db.scalars(
                select(ProjectAssessment)
                .where(ProjectAssessment.project_id == project.id, ProjectAssessment.confirmed.is_(True))
                .order_by(ProjectAssessment.id)
            ).all()
        )
        if not objectives or pedagogy is None or not assessments:
            raise CourseBlueprintWorkflowError("Confirmed design basis is required for activity regeneration")
        return objectives, pedagogy, assessments

    def _persist_activities(
        self, project: CourseProject, proposals: list[CourseActivityProposal],
    ) -> list[ProjectActivity]:
        activities = []
        for sequence_no, proposal in enumerate(proposals, start=1):
            activity = ProjectActivity(
                project_id=project.id, sequence_no=sequence_no, name=proposal.name,
                duration=proposal.duration, core_task=proposal.core_task,
                teacher_action=proposal.teacher_action, student_action=proposal.student_action,
                ai_role=proposal.ai_role, dominant_actor="STUDENT",
                assessment_note=proposal.assessment, scaffolds_json=proposal.scaffolds,
                objective_refs_json=proposal.objective_refs, version=1,
            )
            self.db.add(activity)
            self.db.flush()
            activities.append(activity)
        return activities

    def _remove_current_blueprint(self, project_id: int) -> None:
        activity_ids = list(
            self.db.scalars(
                select(ProjectActivity.id).where(ProjectActivity.project_id == project_id)
            ).all()
        )
        if activity_ids:
            self.db.execute(
                delete(DesignEvidenceLink).where(
                    DesignEvidenceLink.project_id == project_id,
                    DesignEvidenceLink.biz_type == "ACTIVITY",
                    DesignEvidenceLink.biz_id.in_(activity_ids),
                )
            )
        self.db.execute(delete(ProjectActivity).where(ProjectActivity.project_id == project_id))

    def _link_evidence(self, project_id: int, activities: list[ProjectActivity]) -> None:
        evidence = self.evidence_cards.list_confirmed_by_project(project_id=project_id)
        if not evidence:
            return
        selected = evidence[0]
        for activity in activities:
            self.db.add(
                DesignEvidenceLink(
                    project_id=project_id, biz_type="ACTIVITY", biz_id=activity.id,
                    evidence_id=selected.id,
                    principle=selected.teaching_implication or selected.main_finding,
                    decision_text=activity.core_task, support_level="SUPPORTED",
                )
            )

    def _owned_project(self, *, current_user_id: int, project_id: int) -> CourseProject:
        project = self.projects.get_by_id_and_user(project_id=project_id, user_id=current_user_id)
        if project is None:
            raise ProjectNotFoundError("Project was not found for the current user")
        return project

    def _owned_activity(
        self, current_user_id: int, project_id: int, activity_id: int,
    ) -> tuple[CourseProject, ProjectActivity]:
        project = self._owned_project(current_user_id=current_user_id, project_id=project_id)
        activity = self.db.scalar(
            select(ProjectActivity).where(
                ProjectActivity.id == activity_id, ProjectActivity.project_id == project.id
            )
        )
        if activity is None:
            raise CourseActivityNotFoundError("Activity was not found")
        return project, activity

    def _confirmed_objectives(self, project_id: int) -> list[ProjectObjective]:
        return list(
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

    def _activities(self, project_id: int) -> list[ProjectActivity]:
        return list(
            self.db.scalars(
                select(ProjectActivity)
                .where(ProjectActivity.project_id == project_id)
                .order_by(ProjectActivity.sequence_no, ProjectActivity.id)
            ).all()
        )

    def _ensure_duration_within_lesson(self, project: CourseProject) -> None:
        lesson_minutes = project.lesson_minutes
        if not lesson_minutes:
            raise CourseBlueprintDurationError("Lesson minutes are required")
        total = self._total_duration(project.id)
        if total > lesson_minutes:
            raise CourseBlueprintDurationError(
                f"Activity duration total ({total}) exceeds lesson minutes ({lesson_minutes})"
            )

    @staticmethod
    def _validate_generated_duration(
        activities: list[CourseActivityProposal], lesson_minutes: int,
    ) -> None:
        total = sum(item.duration for item in activities)
        minimum_meaningful_duration = max(1, int(lesson_minutes * 0.6))
        if total > lesson_minutes or total < minimum_meaningful_duration:
            raise CourseBlueprintDurationError(
                f"Generated activity duration total ({total}) is invalid for lesson minutes ({lesson_minutes})"
            )

    def _total_duration(self, project_id: int) -> int:
        return sum(item.duration for item in self._activities(project_id))

    @staticmethod
    def _apply_proposal(activity: ProjectActivity, proposal: CourseActivityProposal) -> None:
        activity.name = proposal.name
        activity.duration = proposal.duration
        activity.core_task = proposal.core_task
        activity.teacher_action = proposal.teacher_action
        activity.student_action = proposal.student_action
        activity.ai_role = proposal.ai_role
        activity.assessment_note = proposal.assessment
        activity.scaffolds_json = proposal.scaffolds
        activity.objective_refs_json = proposal.objective_refs

    @staticmethod
    def _proposal_from_activity(activity: ProjectActivity) -> CourseActivityProposal:
        return CourseActivityProposal(
            name=activity.name, duration=activity.duration,
            core_task=activity.core_task or activity.name,
            teacher_action=activity.teacher_action or "组织活动",
            student_action=activity.student_action or "完成任务",
            ai_role=activity.ai_role, assessment=activity.assessment_note or "观察学习表现",
            scaffolds=activity.scaffolds_json or [], objective_refs=activity.objective_refs_json or [],
        )

    @staticmethod
    def _activity_change_stale_sections(project: CourseProject) -> list:
        old_stale_sections = [
            section for section in (project.stale_sections_json or [])
            if section != "ACTIVITY"
        ]
        return WorkflowService.stale_sections_after_activity_change(
            project.workflow_state, old_stale_sections
        )

    @staticmethod
    def _require_activity_ready(project: CourseProject) -> None:
        if project.workflow_state != "ACTIVITY_READY":
            raise CourseBlueprintWorkflowError("Generate a course blueprint before editing activities")

    @staticmethod
    def _view(item: ProjectActivity) -> dict[str, object]:
        return {
            "activityId": item.id, "sequenceNo": item.sequence_no, "name": item.name,
            "duration": item.duration, "coreTask": item.core_task,
            "teacherAction": item.teacher_action, "studentAction": item.student_action,
            "aiRole": item.ai_role, "dominantActor": item.dominant_actor,
            "assessment": item.assessment_note, "scaffolds": item.scaffolds_json or [],
            "objectiveRefs": item.objective_refs_json or [], "version": item.version,
        }
