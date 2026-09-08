from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.assistants.base import ResearchAssistantProvider
from app.models.course_design import (
    AiLiteracyItem,
    CurriculumStandard,
    DecisionLog,
    DesignEvidenceLink,
    ProjectObjective,
)
from app.models.course_project import CourseProject
from app.repositories.evidence_card_repository import EvidenceCardRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.course_design import (
    CourseContextDiagnosis,
    CourseObjectiveCreateRequest,
    CourseObjectiveGenerationRequest,
    CourseObjectiveGenerationResult,
    CourseObjectiveProposal,
    CourseObjectiveUpdateRequest,
)
from app.services.project_service import ProjectNotFoundError
from app.services.workflow_service import WorkflowService


class CourseObjectiveNotFoundError(LookupError):
    pass


class CourseObjectiveWorkflowError(ValueError):
    pass


class CourseObjectiveConfirmationError(ValueError):
    pass


class CourseObjectiveService:
    """Generate and manage teacher-owned decisions for learning objectives."""

    _GENERATABLE_STATES = {"CONTEXT_READY", "RESEARCH_READY", "OBJECTIVE_PENDING"}
    _PROMPT = """根据教学情境、情境诊断、已确认研究证据、课程标准和 AI 素养条目生成 2 至 4 个学习目标。
仅输出 JSON，格式为 {\"objectives\":[{\"content\":\"...\",\"rationale\":\"...\",\"standardRefs\":[],\"literacyRefs\":[]}]}。
目标必须可观察、可评价、适合当前年级，使用行为动词；禁止使用“了解”或“掌握”。不要生成教学策略或完整教案。"""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.projects = ProjectRepository(db)
        self.evidence_cards = EvidenceCardRepository(db)

    async def generate(
        self, *, current_user_id: int, project_id: int, provider: ResearchAssistantProvider
    ) -> list[dict[str, object]]:
        project = self._owned_project(current_user_id=current_user_id, project_id=project_id)
        if project.workflow_state not in self._GENERATABLE_STATES:
            raise CourseObjectiveWorkflowError("Teaching context must be confirmed before generating objectives")
        if not project.context_diagnosis_json:
            raise CourseObjectiveWorkflowError("Teaching-context diagnosis is required before generating objectives")

        try:
            request, evidence_cards = self._generation_request(project)
        except ValueError as exc:
            raise CourseObjectiveWorkflowError("Teaching context or diagnosis is incomplete") from exc
        generated = CourseObjectiveGenerationResult.model_validate(
            await provider.generate_course_objectives(request)
        )
        proposals = [CourseObjectiveProposal.model_validate(item) for item in generated.objectives]
        if not 2 <= len(proposals) <= 4:
            raise CourseObjectiveWorkflowError("Objective generation must return 2 to 4 objectives")

        try:
            next_sequence = self._next_sequence(project.id)
            objectives: list[ProjectObjective] = []
            for offset, proposal in enumerate(proposals):
                objective = ProjectObjective(
                    project_id=project.id,
                    content=proposal.content,
                    sequence_no=next_sequence + offset,
                    standard_refs_json=proposal.standard_refs,
                    literacy_refs_json=proposal.literacy_refs,
                    rationale=proposal.rationale,
                    source_type="AI",
                    teacher_action=None,
                    confirmed=False,
                    version=1,
                )
                self.db.add(objective)
                self.db.flush()
                objectives.append(objective)
                self._link_evidence(project.id, objective, evidence_cards, offset)
            project.workflow_state = "OBJECTIVE_PENDING"
            project.stale_sections_json = WorkflowService.stale_sections_after_objective_change(
                project.workflow_state, project.stale_sections_json
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return [self._objective_view(item) for item in objectives]

    def revise(
        self, *, current_user_id: int, project_id: int, objective_id: int, payload: CourseObjectiveUpdateRequest
    ) -> dict[str, object]:
        project, objective = self._owned_objective(current_user_id, project_id, objective_id)
        try:
            objective.content = payload.content
            objective.teacher_action = "REVISE"
            objective.confirmed = False
            objective.version += 1
            self._mark_objective_change(project)
            self.db.commit()
            self.db.refresh(objective)
        except Exception:
            self.db.rollback()
            raise
        return self._objective_view(objective)

    def keep(self, *, current_user_id: int, project_id: int, objective_id: int) -> dict[str, object]:
        project, objective = self._owned_objective(current_user_id, project_id, objective_id)
        try:
            objective.teacher_action = "ACCEPT"
            objective.confirmed = False
            self._mark_objective_change(project)
            self.db.commit()
            self.db.refresh(objective)
        except Exception:
            self.db.rollback()
            raise
        return self._objective_view(objective)

    def reject(self, *, current_user_id: int, project_id: int, objective_id: int) -> None:
        project, objective = self._owned_objective(current_user_id, project_id, objective_id)
        try:
            objective.teacher_action = "REJECT"
            objective.confirmed = False
            self._mark_objective_change(project)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def add_teacher_objective(
        self, *, current_user_id: int, project_id: int, payload: CourseObjectiveCreateRequest
    ) -> dict[str, object]:
        project = self._owned_project(current_user_id=current_user_id, project_id=project_id)
        try:
            objective = ProjectObjective(
                project_id=project.id,
                content=payload.content,
                sequence_no=self._next_sequence(project.id),
                standard_refs_json=[],
                literacy_refs_json=[],
                rationale=None,
                source_type="TEACHER",
                teacher_action="ACCEPT",
                confirmed=False,
                version=1,
            )
            self.db.add(objective)
            self.db.flush()
            project.workflow_state = "OBJECTIVE_PENDING"
            self._mark_objective_change(project)
            self.db.commit()
            self.db.refresh(objective)
        except Exception:
            self.db.rollback()
            raise
        return self._objective_view(objective)

    def confirm(self, *, current_user_id: int, project_id: int) -> list[dict[str, object]]:
        project = self._owned_project(current_user_id=current_user_id, project_id=project_id)
        objectives = self.db.scalars(
            select(ProjectObjective).where(ProjectObjective.project_id == project.id).order_by(ProjectObjective.sequence_no, ProjectObjective.id)
        ).all()
        effective = [item for item in objectives if item.teacher_action != "REJECT"]
        if not effective:
            raise CourseObjectiveConfirmationError("At least one non-rejected objective is required")
        if project.workflow_state == "OBJECTIVE_CONFIRMED":
            return [self._objective_view(item) for item in effective]
        if project.workflow_state != "OBJECTIVE_PENDING":
            raise CourseObjectiveWorkflowError("Generate objectives before confirming them")
        try:
            for objective in objectives:
                objective.confirmed = objective in effective
            for objective in effective:
                self.db.add(
                    DecisionLog(
                        project_id=project.id,
                        decision_type="OBJECTIVE",
                        biz_id=objective.id,
                        ai_proposal_json={"content": objective.content} if objective.source_type == "AI" else None,
                        teacher_action=objective.teacher_action or "ACCEPT",
                        teacher_revision_json={"content": objective.content} if objective.teacher_action == "REVISE" else None,
                    )
                )
            project.workflow_state = "OBJECTIVE_CONFIRMED"
            project.stale_sections_json = WorkflowService.stale_sections_after_objective_change(
                project.workflow_state, project.stale_sections_json
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return [self._objective_view(item) for item in effective]

    def _generation_request(self, project: CourseProject) -> tuple[CourseObjectiveGenerationRequest, list]:
        diagnosis = CourseContextDiagnosis.model_validate(project.context_diagnosis_json)
        standards = self._standards_for_grade(project.grade or 0)
        literacy_items = self._literacy_for_grade(project.grade or 0)
        evidence_cards = self.evidence_cards.list_confirmed_by_project(project_id=project.id)
        return (
            CourseObjectiveGenerationRequest(
                project_id=project.id,
                grade=project.grade or 0,
                topic=project.topic,
                context_diagnosis=diagnosis,
                evidence=[{"id": str(card.id), "finding": card.main_finding or "", "implication": card.teaching_implication or ""} for card in evidence_cards],
                curriculum_standards=[{"id": item.id, "content": item.content, "performance": item.performance or ""} for item in standards],
                ai_literacy_items=[{"id": item.id, "dimension": item.dimension, "performance": item.performance or "", "description": item.description or ""} for item in literacy_items],
                prompt=self._PROMPT,
            ),
            evidence_cards,
        )

    def _standards_for_grade(self, grade: int) -> list[CurriculumStandard]:
        return list(self.db.scalars(select(CurriculumStandard).where(or_(CurriculumStandard.grade_min.is_(None), CurriculumStandard.grade_min <= grade), or_(CurriculumStandard.grade_max.is_(None), CurriculumStandard.grade_max >= grade)).order_by(CurriculumStandard.id)).all())

    def _literacy_for_grade(self, grade: int) -> list[AiLiteracyItem]:
        return list(self.db.scalars(select(AiLiteracyItem).where(or_(AiLiteracyItem.grade_min.is_(None), AiLiteracyItem.grade_min <= grade), or_(AiLiteracyItem.grade_max.is_(None), AiLiteracyItem.grade_max >= grade)).order_by(AiLiteracyItem.id)).all())

    def _owned_project(self, *, current_user_id: int, project_id: int) -> CourseProject:
        project = self.projects.get_by_id_and_user(project_id=project_id, user_id=current_user_id)
        if project is None:
            raise ProjectNotFoundError("Project was not found for the current user")
        return project

    def _owned_objective(self, current_user_id: int, project_id: int, objective_id: int) -> tuple[CourseProject, ProjectObjective]:
        project = self._owned_project(current_user_id=current_user_id, project_id=project_id)
        objective = self.db.scalar(select(ProjectObjective).where(ProjectObjective.id == objective_id, ProjectObjective.project_id == project.id))
        if objective is None:
            raise CourseObjectiveNotFoundError("Objective was not found")
        return project, objective

    def _next_sequence(self, project_id: int) -> int:
        return (self.db.scalar(select(func.max(ProjectObjective.sequence_no)).where(ProjectObjective.project_id == project_id)) or 0) + 1

    def _link_evidence(self, project_id: int, objective: ProjectObjective, evidence_cards: list, offset: int) -> None:
        if not evidence_cards:
            return
        evidence = evidence_cards[offset % len(evidence_cards)]
        objective_principle = evidence.teaching_implication or evidence.main_finding
        self.db.add(DesignEvidenceLink(project_id=project_id, biz_type="OBJECTIVE", biz_id=objective.id, evidence_id=evidence.id, principle=objective_principle, decision_text=objective.content, support_level="SUPPORTED"))

    @staticmethod
    def _mark_objective_change(project: CourseProject) -> None:
        project.stale_sections_json = WorkflowService.stale_sections_after_objective_change(project.workflow_state, project.stale_sections_json)

    @staticmethod
    def _objective_view(item: ProjectObjective) -> dict[str, object]:
        return {"objectiveId": item.id, "content": item.content, "sequenceNo": item.sequence_no, "standardRefs": item.standard_refs_json or [], "literacyRefs": item.literacy_refs_json or [], "rationale": item.rationale, "sourceType": item.source_type, "teacherAction": item.teacher_action, "confirmed": item.confirmed, "version": item.version}
