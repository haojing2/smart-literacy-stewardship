from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.assistants.base import ResearchAssistantProvider
from app.models.course_design import (
    AiLiteracyItem,
    DecisionLog,
    ProjectAssessment,
    ProjectObjective,
    ProjectPedagogy,
)
from app.models.course_project import CourseProject
from app.repositories.evidence_card_repository import EvidenceCardRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.course_design import (
    CourseAssessmentGenerationRequest,
    CourseAssessmentGenerationResult,
    CourseAssessmentProposal,
    CourseAssessmentUpdateRequest,
)
from app.services.project_service import ProjectNotFoundError
from app.services.workflow_service import WorkflowService


class CourseAssessmentNotFoundError(LookupError):
    pass


class CourseAssessmentWorkflowError(ValueError):
    pass


class CourseAssessmentAlignmentError(ValueError):
    pass


class CourseAssessmentService:
    """Generate and confirm objective-aligned assessments before activities."""

    _PROMPT = """根据教学情境、已确认目标、已确认教学策略、AI 素养和研究证据，为每个目标生成至少一个评价任务。
仅输出 JSON：{\"assessments\":[{\"objectiveId\":1,\"taskContent\":\"...\",\"studentEvidence\":[],\"criteria\":[],\"rationale\":\"...\"}]}。
评价必须直接测量目标要求的可观察行为，不能以概念记忆题替代实践性评价。不要生成教学活动或完整教案。"""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.projects = ProjectRepository(db)
        self.evidence_cards = EvidenceCardRepository(db)

    async def generate(self, *, current_user_id: int, project_id: int, provider: ResearchAssistantProvider) -> dict[str, object]:
        project = self._owned_project(current_user_id=current_user_id, project_id=project_id)
        objectives, pedagogy = self._generation_basis(project)
        try:
            generated = CourseAssessmentGenerationResult.model_validate(
                await provider.generate_course_assessments(self._generation_request(project, objectives, pedagogy))
            )
        except ValueError as exc:
            raise CourseAssessmentWorkflowError("评价生成结果不符合结构要求") from exc
        self._validate_coverage(generated.assessments, objectives)
        try:
            assessments = self._persist_proposals(project, generated.assessments)
            project.workflow_state = "ASSESSMENT_PENDING"
            project.stale_sections_json = self._assessment_change_stale_sections(project)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {"assessments": [self._view(item) for item in assessments], "aligned": self._aligned(project.id, objectives)}

    def revise(self, *, current_user_id: int, project_id: int, assessment_id: int, payload: CourseAssessmentUpdateRequest) -> dict[str, object]:
        project, assessment = self._owned_assessment(current_user_id, project_id, assessment_id)
        try:
            if payload.task_content is not None:
                assessment.task_content = payload.task_content
            if payload.student_evidence is not None:
                assessment.student_evidence_json = payload.student_evidence
            if payload.criteria is not None:
                assessment.criteria_json = payload.criteria
            assessment.teacher_action = "REVISE"
            assessment.confirmed = False
            assessment.version += 1
            project.workflow_state = "ASSESSMENT_PENDING"
            project.stale_sections_json = self._assessment_change_stale_sections(project)
            self.db.commit()
            self.db.refresh(assessment)
        except Exception:
            self.db.rollback()
            raise
        return {"assessment": self._view(assessment), "aligned": self._aligned(project.id, self._confirmed_objectives(project.id))}

    async def regenerate(self, *, current_user_id: int, project_id: int, assessment_id: int, provider: ResearchAssistantProvider) -> dict[str, object]:
        project, assessment = self._owned_assessment(current_user_id, project_id, assessment_id)
        objectives, pedagogy = self._generation_basis(project, allow_assessment_pending=True)
        target = next((item for item in objectives if item.id == assessment.objective_id), None)
        if target is None:
            raise CourseAssessmentWorkflowError("Assessment objective is no longer confirmed")
        try:
            generated = CourseAssessmentGenerationResult.model_validate(
                await provider.generate_course_assessments(self._generation_request(project, [target], pedagogy))
            )
        except ValueError as exc:
            raise CourseAssessmentWorkflowError("评价重新生成结果不符合结构要求") from exc
        proposals = [CourseAssessmentProposal.model_validate(item) for item in generated.assessments if item.objective_id == target.id]
        if not proposals:
            raise CourseAssessmentWorkflowError("Regeneration did not return an assessment for the current objective")
        proposal = proposals[0]
        try:
            assessment.task_content = proposal.task_content
            assessment.student_evidence_json = proposal.student_evidence
            assessment.criteria_json = proposal.criteria
            assessment.rationale = proposal.rationale
            assessment.teacher_action = None
            assessment.confirmed = False
            assessment.version += 1
            project.workflow_state = "ASSESSMENT_PENDING"
            project.stale_sections_json = self._assessment_change_stale_sections(project)
            self.db.commit()
            self.db.refresh(assessment)
        except Exception:
            self.db.rollback()
            raise
        return {"assessment": self._view(assessment), "aligned": self._aligned(project.id, objectives)}

    def confirm(self, *, current_user_id: int, project_id: int) -> dict[str, object]:
        project = self._owned_project(current_user_id=current_user_id, project_id=project_id)
        objectives = self._confirmed_objectives(project.id)
        if not objectives or not self._aligned(project.id, objectives):
            raise CourseAssessmentAlignmentError("Every confirmed objective requires at least one valid assessment")
        assessments = self.db.scalars(select(ProjectAssessment).where(ProjectAssessment.project_id == project.id)).all()
        if project.workflow_state == "ASSESSMENT_CONFIRMED":
            return {"assessments": [self._view(item) for item in assessments if item.confirmed], "aligned": True}
        if project.workflow_state != "ASSESSMENT_PENDING":
            raise CourseAssessmentWorkflowError("Generate assessments before confirming them")
        try:
            confirmed_ids = {item.id for item in objectives}
            valid_assessments = [item for item in assessments if item.objective_id in confirmed_ids and item.task_content.strip()]
            for assessment in assessments:
                assessment.confirmed = assessment in valid_assessments
            for assessment in valid_assessments:
                self.db.add(DecisionLog(project_id=project.id, decision_type="ASSESSMENT", biz_id=assessment.id, ai_proposal_json={"taskContent": assessment.task_content}, teacher_action=assessment.teacher_action or "ACCEPT", teacher_revision_json={"taskContent": assessment.task_content} if assessment.teacher_action == "REVISE" else None))
            project.workflow_state = "ASSESSMENT_CONFIRMED"
            project.stale_sections_json = self._assessment_change_stale_sections(project)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {"assessments": [self._view(item) for item in valid_assessments], "aligned": True}

    def _generation_basis(
        self,
        project: CourseProject,
        *,
        allow_assessment_pending: bool = False,
    ) -> tuple[list[ProjectObjective], ProjectPedagogy]:
        permitted_states = {"PEDAGOGY_CONFIRMED"}
        if allow_assessment_pending:
            permitted_states.add("ASSESSMENT_PENDING")
        if project.workflow_state not in permitted_states:
            raise CourseAssessmentWorkflowError("Pedagogy must be confirmed before generating assessments")
        objectives = self._confirmed_objectives(project.id)
        pedagogy = self.db.scalar(select(ProjectPedagogy).where(ProjectPedagogy.project_id == project.id, ProjectPedagogy.confirmed.is_(True)).order_by(ProjectPedagogy.id.desc()).limit(1))
        if not objectives or pedagogy is None:
            raise CourseAssessmentWorkflowError("Confirmed objectives and pedagogy are required")
        return objectives, pedagogy

    def _generation_request(self, project: CourseProject, objectives: list[ProjectObjective], pedagogy: ProjectPedagogy) -> CourseAssessmentGenerationRequest:
        evidence = self.evidence_cards.list_confirmed_by_project(project_id=project.id)
        literacy = self._literacy_for_grade(project.grade or 0)
        return CourseAssessmentGenerationRequest(
            project_id=project.id,
            context={"grade": project.grade, "topic": project.topic, "lessonMinutes": project.lesson_minutes, "classSize": project.class_size, "studentExperience": project.student_experience or ""},
            objectives=[{"id": item.id, "content": item.content, "rationale": item.rationale or ""} for item in objectives],
            pedagogy={"primaryMethodId": pedagogy.primary_method_id, "customName": pedagogy.custom_name, "description": pedagogy.custom_description or pedagogy.rationale or ""},
            ai_literacy_items=[{"id": item.id, "dimension": item.dimension, "performance": item.performance or ""} for item in literacy],
            evidence=[{"id": str(item.id), "finding": item.main_finding or "", "implication": item.teaching_implication or ""} for item in evidence],
            prompt=self._PROMPT,
        )

    def _persist_proposals(self, project: CourseProject, proposals: list[CourseAssessmentProposal]) -> list[ProjectAssessment]:
        assessments: list[ProjectAssessment] = []
        for proposal in proposals:
            assessment = ProjectAssessment(project_id=project.id, objective_id=proposal.objective_id, task_content=proposal.task_content, student_evidence_json=proposal.student_evidence, criteria_json=proposal.criteria, rationale=proposal.rationale, teacher_action=None, confirmed=False, version=1)
            self.db.add(assessment)
            self.db.flush()
            assessments.append(assessment)
        return assessments

    def _owned_project(self, *, current_user_id: int, project_id: int) -> CourseProject:
        project = self.projects.get_by_id_and_user(project_id=project_id, user_id=current_user_id)
        if project is None:
            raise ProjectNotFoundError("Project was not found for the current user")
        return project

    def _owned_assessment(self, current_user_id: int, project_id: int, assessment_id: int) -> tuple[CourseProject, ProjectAssessment]:
        project = self._owned_project(current_user_id=current_user_id, project_id=project_id)
        assessment = self.db.scalar(select(ProjectAssessment).where(ProjectAssessment.id == assessment_id, ProjectAssessment.project_id == project.id))
        if assessment is None:
            raise CourseAssessmentNotFoundError("Assessment was not found")
        return project, assessment

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

    def _literacy_for_grade(self, grade: int) -> list[AiLiteracyItem]:
        return list(self.db.scalars(select(AiLiteracyItem).where(or_(AiLiteracyItem.grade_min.is_(None), AiLiteracyItem.grade_min <= grade), or_(AiLiteracyItem.grade_max.is_(None), AiLiteracyItem.grade_max >= grade)).order_by(AiLiteracyItem.id)).all())

    @staticmethod
    def _validate_coverage(proposals: list[CourseAssessmentProposal], objectives: list[ProjectObjective]) -> None:
        proposal_objective_ids = {item.objective_id for item in proposals}
        required_ids = {item.id for item in objectives}
        if not required_ids.issubset(proposal_objective_ids):
            raise CourseAssessmentWorkflowError("Generation must include an assessment for every confirmed objective")

    def _aligned(self, project_id: int, objectives: list[ProjectObjective]) -> bool:
        if not objectives:
            return False
        covered_ids = set(self.db.scalars(select(ProjectAssessment.objective_id).where(ProjectAssessment.project_id == project_id, ProjectAssessment.task_content != "")).all())
        return all(item.id in covered_ids for item in objectives)

    @staticmethod
    def _assessment_change_stale_sections(project: CourseProject) -> list:
        previous_stale_sections = [
            section
            for section in (project.stale_sections_json or [])
            if section != "ASSESSMENT"
        ]
        return WorkflowService.stale_sections_after_assessment_change(
            project.workflow_state,
            previous_stale_sections,
        )

    @staticmethod
    def _view(item: ProjectAssessment) -> dict[str, object]:
        return {"assessmentId": item.id, "objectiveId": item.objective_id, "taskContent": item.task_content, "studentEvidence": item.student_evidence_json or [], "criteria": item.criteria_json or [], "rationale": item.rationale, "teacherAction": item.teacher_action, "confirmed": item.confirmed, "version": item.version}
