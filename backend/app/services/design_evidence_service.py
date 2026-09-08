from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.course_design import (
    AiLiteracyItem,
    DesignEvidenceLink,
    ProjectActivity,
    ProjectAssessment,
    ProjectObjective,
    ProjectPedagogy,
)
from app.models.evidence_card import EvidenceCard
from app.models.course_project import CourseProject
from app.repositories.project_repository import ProjectRepository
from app.services.project_service import ProjectNotFoundError


class DesignEvidenceBusinessNotFoundError(LookupError):
    pass


class DesignEvidenceService:
    """Read persisted evidence supporting one course-design decision."""

    _BIZ_TYPES = {"OBJECTIVE", "PEDAGOGY", "ASSESSMENT", "ACTIVITY"}

    def __init__(self, db: Session) -> None:
        self.db = db
        self.projects = ProjectRepository(db)

    def get_design_evidence(
        self, *, current_user_id: int, project_id: int, biz_type: str, biz_id: int,
    ) -> dict[str, object]:
        project = self._owned_project(current_user_id=current_user_id, project_id=project_id)
        normalized_type = biz_type.upper()
        if normalized_type not in self._BIZ_TYPES:
            raise ValueError("Unsupported bizType")
        business_model = self._business_model(normalized_type)
        business = self._owned_business(
            project_id=project.id, biz_type=normalized_type, biz_id=biz_id
        )
        rows = self.db.execute(
            select(DesignEvidenceLink, EvidenceCard)
            .join(EvidenceCard, EvidenceCard.id == DesignEvidenceLink.evidence_id)
            .join(business_model, business_model.id == DesignEvidenceLink.biz_id)
            .where(
                DesignEvidenceLink.project_id == project.id,
                DesignEvidenceLink.biz_type == normalized_type,
                DesignEvidenceLink.biz_id == biz_id,
                business_model.project_id == project.id,
            )
            .order_by(DesignEvidenceLink.id)
        ).all()
        links = [row[0] for row in rows]
        cards = [row[1] for row in rows]
        objectives = self._related_objectives(
            project_id=project.id, biz_type=normalized_type, business=business
        )
        literacy_ids = {
            ref for objective in objectives
            for ref in (objective.literacy_refs_json or [])
            if isinstance(ref, int)
        }
        literacy = list(
            self.db.scalars(
                select(AiLiteracyItem)
                .where(AiLiteracyItem.id.in_(literacy_ids))
                .order_by(AiLiteracyItem.id)
            ).all()
        ) if literacy_ids else []
        return {
            "aiLiteracy": [
                {
                    "id": item.id, "dimension": item.dimension, "stage": item.stage,
                    "performance": item.performance, "description": item.description,
                }
                for item in literacy
            ],
            "learningObjectives": [
                {
                    "objectiveId": item.id, "content": item.content,
                    "rationale": item.rationale, "standardRefs": item.standard_refs_json or [],
                    "literacyRefs": item.literacy_refs_json or [],
                }
                for item in objectives
            ],
            "researchEvidence": [self._evidence_view(item) for item in cards],
            "resources": self._deduplicated(
                strategy
                for card in cards
                for strategy in (card.recommended_strategies_json or [])
            ),
            "applicableConditions": self._deduplicated(
                condition
                for card in cards
                for condition in (card.implementation_conditions_json or [])
            ),
            "designRationale": self._design_rationale(links, business, normalized_type),
        }

    def _owned_project(self, *, current_user_id: int, project_id: int) -> CourseProject:
        project = self.projects.get_by_id_and_user(project_id=project_id, user_id=current_user_id)
        if project is None:
            raise ProjectNotFoundError("Project was not found for the current user")
        return project

    def _owned_business(self, *, project_id: int, biz_type: str, biz_id: int):
        model = self._business_model(biz_type)
        business = self.db.scalar(
            select(model).where(model.id == biz_id, model.project_id == project_id)
        )
        if business is None:
            raise DesignEvidenceBusinessNotFoundError("Design item was not found")
        return business

    @staticmethod
    def _business_model(biz_type: str):
        return {
            "OBJECTIVE": ProjectObjective,
            "PEDAGOGY": ProjectPedagogy,
            "ASSESSMENT": ProjectAssessment,
            "ACTIVITY": ProjectActivity,
        }[biz_type]

    def _related_objectives(
        self, *, project_id: int, biz_type: str, business: object,
    ) -> list[ProjectObjective]:
        if biz_type == "OBJECTIVE":
            return [business]  # type: ignore[list-item]
        if biz_type == "ASSESSMENT":
            objective_ids = [business.objective_id]  # type: ignore[union-attr]
        elif biz_type == "ACTIVITY":
            objective_ids = list(business.objective_refs_json or [])  # type: ignore[union-attr]
        else:
            objective_ids = list(business.suitable_for_json or [])  # type: ignore[union-attr]
        integer_ids = [value for value in objective_ids if isinstance(value, int)]
        if not integer_ids:
            return []
        return list(
            self.db.scalars(
                select(ProjectObjective)
                .where(
                    ProjectObjective.project_id == project_id,
                    ProjectObjective.id.in_(integer_ids),
                )
                .order_by(ProjectObjective.sequence_no, ProjectObjective.id)
            ).all()
        )

    @staticmethod
    def _evidence_view(card: EvidenceCard) -> dict[str, object]:
        return {
            "id": card.id, "title": card.title, "authors": card.authors,
            "year": card.year, "mainFinding": card.main_finding,
            "evidenceStrength": card.evidence_strength,
            "sourceDocument": card.source_document, "sourcePage": card.source_page,
        }

    @staticmethod
    def _deduplicated(values) -> list[str]:
        result: list[str] = []
        for value in values:
            if isinstance(value, str) and value and value not in result:
                result.append(value)
        return result

    @staticmethod
    def _design_rationale(links: list[DesignEvidenceLink], business: object, biz_type: str) -> str:
        linked_text = [
            link.decision_text or link.principle
            for link in links
            if link.decision_text or link.principle
        ]
        if linked_text:
            return "\n".join(dict.fromkeys(linked_text))
        if biz_type == "OBJECTIVE":
            return business.rationale or business.content  # type: ignore[union-attr]
        if biz_type == "PEDAGOGY":
            return business.custom_description or business.rationale or ""  # type: ignore[union-attr]
        if biz_type == "ASSESSMENT":
            return business.rationale or business.task_content  # type: ignore[union-attr]
        return business.core_task or business.assessment_note or ""  # type: ignore[union-attr]
