from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.assistants.base import ResearchAssistantProvider
from app.models.course_design import (
    DecisionLog,
    DesignEvidenceLink,
    PedagogyMethod,
    ProjectObjective,
    ProjectPedagogy,
)
from app.models.course_project import CourseProject
from app.repositories.evidence_card_repository import EvidenceCardRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.course_design import (
    CoursePedagogyCustomRequest,
    CoursePedagogyRecommendation,
    CoursePedagogyRecommendationRequest,
    CoursePedagogyRecommendationResult,
    CoursePedagogySelectRequest,
)
from app.services.project_service import ProjectNotFoundError
from app.services.workflow_service import WorkflowService


class CoursePedagogyNotFoundError(LookupError):
    pass


class CoursePedagogyWorkflowError(ValueError):
    pass


class CoursePedagogyService:
    """Create project-level pedagogy recommendations and teacher decisions."""

    _PROMPT = """基于教学情境、已确认目标、已确认研究证据和提供的教学法知识库，推荐一个教学策略并给出备选。
仅输出 JSON：recommended 和 alternatives；每项必须含 methodId、name、rationale、components。
允许组合已有教学法形成项目级策略，但不得创建或修改全局 pedagogy_method。不要生成完整教案。"""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.projects = ProjectRepository(db)
        self.evidence_cards = EvidenceCardRepository(db)

    async def recommend(self, *, current_user_id: int, project_id: int, provider: ResearchAssistantProvider) -> dict[str, object]:
        project = self._owned_project(current_user_id=current_user_id, project_id=project_id)
        if project.workflow_state != "OBJECTIVE_CONFIRMED":
            raise CoursePedagogyWorkflowError("Objectives must be confirmed before recommending pedagogy")
        objectives = self._confirmed_objectives(project.id)
        if not objectives:
            raise CoursePedagogyWorkflowError("At least one confirmed objective is required")
        methods = list(self.db.scalars(select(PedagogyMethod).order_by(PedagogyMethod.id)).all())
        if not methods:
            raise CoursePedagogyWorkflowError("Pedagogy method knowledge base is unavailable")

        request, evidence_cards = self._recommendation_request(project, objectives, methods)
        recommendation = CoursePedagogyRecommendationResult.model_validate(
            await provider.recommend_course_pedagogy(request)
        )
        self._validate_recommendation_methods(recommendation, methods)
        try:
            pedagogy = self._draft_for_project(project.id)
            if pedagogy is None:
                pedagogy = ProjectPedagogy(
                    project_id=project.id,
                    primary_method_id=recommendation.recommended.method_id,
                    secondary_method_id=None,
                    rationale=recommendation.recommended.rationale,
                    suitable_for_json=[item.id for item in objectives],
                    risk_note=None,
                    alternative_json={},
                    teacher_action=None,
                    confirmed=False,
                    version=1,
                    custom_name=None,
                    custom_description=None,
                    source_type="AI",
                )
                self.db.add(pedagogy)
            else:
                pedagogy.primary_method_id = recommendation.recommended.method_id
                pedagogy.secondary_method_id = None
                pedagogy.rationale = recommendation.recommended.rationale
                pedagogy.suitable_for_json = [item.id for item in objectives]
                pedagogy.custom_name = None
                pedagogy.custom_description = None
                pedagogy.source_type = "AI"
                pedagogy.teacher_action = None
                pedagogy.confirmed = False
                pedagogy.version += 1
            pedagogy.alternative_json = recommendation.model_dump(by_alias=True, mode="json")
            self.db.flush()
            self._link_evidence(project.id, pedagogy, evidence_cards, recommendation.recommended)
            project.workflow_state = "PEDAGOGY_PENDING"
            project.stale_sections_json = WorkflowService.stale_sections_after_pedagogy_change(project.workflow_state, project.stale_sections_json)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return recommendation.model_dump(by_alias=True, mode="json")

    def select(self, *, current_user_id: int, project_id: int, payload: CoursePedagogySelectRequest) -> dict[str, object]:
        project = self._owned_project(current_user_id=current_user_id, project_id=project_id)
        self._require_editable_workflow(project)
        method = self.db.get(PedagogyMethod, payload.method_id)
        if method is None:
            raise CoursePedagogyNotFoundError("Pedagogy method was not found")
        pedagogy = self._draft_for_project(project.id)
        if pedagogy is None:
            raise CoursePedagogyWorkflowError("Request pedagogy recommendations before selecting a method")
        try:
            pedagogy.primary_method_id = method.id
            pedagogy.secondary_method_id = None
            pedagogy.rationale = method.description or pedagogy.rationale
            pedagogy.custom_name = None
            pedagogy.custom_description = None
            pedagogy.source_type = "AI"
            pedagogy.teacher_action = "SELECT"
            pedagogy.confirmed = False
            pedagogy.version += 1
            project.workflow_state = "PEDAGOGY_PENDING"
            project.stale_sections_json = WorkflowService.stale_sections_after_pedagogy_change(project.workflow_state, project.stale_sections_json)
            self.db.commit()
            self.db.refresh(pedagogy)
        except Exception:
            self.db.rollback()
            raise
        return self._view(pedagogy)

    def custom(self, *, current_user_id: int, project_id: int, payload: CoursePedagogyCustomRequest) -> dict[str, object]:
        project = self._owned_project(current_user_id=current_user_id, project_id=project_id)
        self._require_editable_workflow(project)
        try:
            pedagogy = self._draft_for_project(project.id)
            if pedagogy is None:
                pedagogy = ProjectPedagogy(
                    project_id=project.id, primary_method_id=None, secondary_method_id=None,
                    rationale=payload.description, suitable_for_json=[], risk_note=None,
                    alternative_json=None, teacher_action="CUSTOM", confirmed=False,
                    version=1, custom_name=payload.name,
                    custom_description=payload.description, source_type="TEACHER",
                )
                self.db.add(pedagogy)
            else:
                pedagogy.primary_method_id = None
                pedagogy.secondary_method_id = None
                pedagogy.rationale = payload.description
                pedagogy.custom_name = payload.name
                pedagogy.custom_description = payload.description
                pedagogy.source_type = "TEACHER"
                pedagogy.teacher_action = "CUSTOM"
                pedagogy.confirmed = False
                pedagogy.version += 1
            project.workflow_state = "PEDAGOGY_PENDING"
            project.stale_sections_json = WorkflowService.stale_sections_after_pedagogy_change(project.workflow_state, project.stale_sections_json)
            self.db.commit()
            self.db.refresh(pedagogy)
        except Exception:
            self.db.rollback()
            raise
        return self._view(pedagogy)

    def confirm(self, *, current_user_id: int, project_id: int) -> dict[str, object]:
        project = self._owned_project(current_user_id=current_user_id, project_id=project_id)
        self._require_editable_workflow(project)
        pedagogy = self._draft_for_project(project.id)
        if pedagogy is None or (pedagogy.primary_method_id is None and not pedagogy.custom_name):
            raise CoursePedagogyWorkflowError("Select or define a pedagogy before confirmation")
        if project.workflow_state == "PEDAGOGY_CONFIRMED" and pedagogy.confirmed:
            return self._view(pedagogy)
        if project.workflow_state != "PEDAGOGY_PENDING":
            raise CoursePedagogyWorkflowError("Generate or select pedagogy before confirming it")
        try:
            pedagogy.confirmed = True
            pedagogy.teacher_action = "ACCEPT" if pedagogy.source_type == "AI" else "CUSTOM"
            self.db.add(DecisionLog(
                project_id=project.id, decision_type="PEDAGOGY", biz_id=pedagogy.id,
                ai_proposal_json=pedagogy.alternative_json if pedagogy.source_type == "AI" else None,
                teacher_action=pedagogy.teacher_action,
                teacher_revision_json={"name": pedagogy.custom_name, "description": pedagogy.custom_description} if pedagogy.source_type == "TEACHER" else None,
            ))
            project.workflow_state = "PEDAGOGY_CONFIRMED"
            project.stale_sections_json = WorkflowService.stale_sections_after_pedagogy_change(project.workflow_state, project.stale_sections_json)
            self.db.commit()
            self.db.refresh(pedagogy)
        except Exception:
            self.db.rollback()
            raise
        return self._view(pedagogy)

    def _recommendation_request(self, project: CourseProject, objectives: list[ProjectObjective], methods: list[PedagogyMethod]) -> tuple[CoursePedagogyRecommendationRequest, list]:
        evidence_cards = self.evidence_cards.list_confirmed_by_project(project_id=project.id)
        return CoursePedagogyRecommendationRequest(
            project_id=project.id,
            context={"grade": project.grade, "topic": project.topic, "lessonMinutes": project.lesson_minutes, "classSize": project.class_size, "studentExperience": project.student_experience or "", "deviceCondition": str((project.devices_json or [""])[0])},
            objectives=[{"id": item.id, "content": item.content, "rationale": item.rationale or ""} for item in objectives],
            evidence=[{"id": str(item.id), "finding": item.main_finding or "", "implication": item.teaching_implication or ""} for item in evidence_cards],
            methods=[{"id": item.id, "name": item.name, "description": item.description or "", "structure": item.typical_structure or "", "risk": item.risk_note or ""} for item in methods],
            prompt=self._PROMPT,
        ), evidence_cards

    def _owned_project(self, *, current_user_id: int, project_id: int) -> CourseProject:
        project = self.projects.get_by_id_and_user(project_id=project_id, user_id=current_user_id)
        if project is None:
            raise ProjectNotFoundError("Project was not found for the current user")
        return project

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

    @staticmethod
    def _require_editable_workflow(project: CourseProject) -> None:
        if project.workflow_state not in {"OBJECTIVE_CONFIRMED", "PEDAGOGY_PENDING", "PEDAGOGY_CONFIRMED"}:
            raise CoursePedagogyWorkflowError("Objectives must be confirmed before editing pedagogy")

    def _draft_for_project(self, project_id: int) -> ProjectPedagogy | None:
        return self.db.scalar(select(ProjectPedagogy).where(ProjectPedagogy.project_id == project_id).order_by(ProjectPedagogy.confirmed.desc(), ProjectPedagogy.id.desc()).limit(1))

    @staticmethod
    def _validate_recommendation_methods(result: CoursePedagogyRecommendationResult, methods: list[PedagogyMethod]) -> None:
        method_ids = {item.id for item in methods}
        for item in [result.recommended, *result.alternatives]:
            if item.method_id not in method_ids:
                raise CoursePedagogyWorkflowError("Recommendation referenced an unavailable pedagogy method")

    def _link_evidence(self, project_id: int, pedagogy: ProjectPedagogy, evidence_cards: list, recommendation: CoursePedagogyRecommendation) -> None:
        if not evidence_cards:
            return
        evidence = evidence_cards[0]
        self.db.add(DesignEvidenceLink(project_id=project_id, biz_type="PEDAGOGY", biz_id=pedagogy.id, evidence_id=evidence.id, principle=evidence.teaching_implication or evidence.main_finding, decision_text=recommendation.rationale, support_level="SUPPORTED"))

    @staticmethod
    def _view(item: ProjectPedagogy) -> dict[str, object]:
        return {"pedagogyId": item.id, "primaryMethodId": item.primary_method_id, "secondaryMethodId": item.secondary_method_id, "rationale": item.rationale, "suitableFor": item.suitable_for_json or [], "riskNote": item.risk_note, "alternatives": item.alternative_json, "teacherAction": item.teacher_action, "confirmed": item.confirmed, "version": item.version, "customName": item.custom_name, "customDescription": item.custom_description, "sourceType": item.source_type}
