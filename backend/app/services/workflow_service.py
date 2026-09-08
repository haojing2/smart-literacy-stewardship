from __future__ import annotations

from enum import StrEnum


class WorkflowState(StrEnum):
    DRAFT = "DRAFT"
    CONTEXT_READY = "CONTEXT_READY"
    RESEARCH_READY = "RESEARCH_READY"
    OBJECTIVE_PENDING = "OBJECTIVE_PENDING"
    OBJECTIVE_CONFIRMED = "OBJECTIVE_CONFIRMED"
    PEDAGOGY_PENDING = "PEDAGOGY_PENDING"
    PEDAGOGY_CONFIRMED = "PEDAGOGY_CONFIRMED"
    ASSESSMENT_PENDING = "ASSESSMENT_PENDING"
    ASSESSMENT_CONFIRMED = "ASSESSMENT_CONFIRMED"
    ACTIVITY_READY = "ACTIVITY_READY"
    QUALITY_READY = "QUALITY_READY"
    QUALITY_CHECKED = "QUALITY_CHECKED"
    ARTIFACT_READY = "ARTIFACT_READY"


CONTEXT_DOWNSTREAM_SECTIONS = [
    "OBJECTIVE",
    "PEDAGOGY",
    "ASSESSMENT",
    "ACTIVITY",
    "QUALITY",
    "ARTIFACT",
]

STALE_SECTIONS_BY_CHANGE = {
    "CONTEXT": CONTEXT_DOWNSTREAM_SECTIONS,
    "OBJECTIVE": ["PEDAGOGY", "ASSESSMENT", "ACTIVITY", "QUALITY", "ARTIFACT"],
    "PEDAGOGY": ["ASSESSMENT", "ACTIVITY", "QUALITY", "ARTIFACT"],
    "ASSESSMENT": ["ACTIVITY", "QUALITY", "ARTIFACT"],
    "ACTIVITY": ["QUALITY", "ARTIFACT"],
}


class WorkflowService:
    """Workflow decisions that do not perform persistence themselves."""

    @staticmethod
    def context_save_result(
        workflow_state: str,
        stale_sections: list | None,
    ) -> tuple[str, list]:
        if workflow_state == WorkflowState.DRAFT:
            return WorkflowState.CONTEXT_READY, []

        if workflow_state in {
            WorkflowState.OBJECTIVE_PENDING,
            WorkflowState.OBJECTIVE_CONFIRMED,
            WorkflowState.PEDAGOGY_PENDING,
            WorkflowState.PEDAGOGY_CONFIRMED,
            WorkflowState.ASSESSMENT_PENDING,
            WorkflowState.ASSESSMENT_CONFIRMED,
            WorkflowState.ACTIVITY_READY,
            WorkflowState.QUALITY_READY,
            WorkflowState.QUALITY_CHECKED,
            WorkflowState.ARTIFACT_READY,
        }:
            return workflow_state, CONTEXT_DOWNSTREAM_SECTIONS.copy()

        return workflow_state, list(stale_sections or [])

    @staticmethod
    def research_complete_result(workflow_state: str) -> str:
        """Advance the explicit research stage without regressing later work."""
        if workflow_state == WorkflowState.CONTEXT_READY:
            return WorkflowState.RESEARCH_READY

        if workflow_state in {
            WorkflowState.RESEARCH_READY,
            WorkflowState.OBJECTIVE_PENDING,
            WorkflowState.OBJECTIVE_CONFIRMED,
            WorkflowState.PEDAGOGY_PENDING,
            WorkflowState.PEDAGOGY_CONFIRMED,
            WorkflowState.ASSESSMENT_PENDING,
            WorkflowState.ASSESSMENT_CONFIRMED,
            WorkflowState.ACTIVITY_READY,
            WorkflowState.QUALITY_READY,
            WorkflowState.QUALITY_CHECKED,
            WorkflowState.ARTIFACT_READY,
        }:
            return workflow_state

        raise ValueError(
            f"Research cannot be completed from workflow state {workflow_state}"
        )

    @staticmethod
    def stale_sections_after_design_basis_change(
        workflow_state: str,
        stale_sections: list | None,
    ) -> list:
        """Backward-compatible name for a teaching-context change."""
        return WorkflowService.stale_sections_after_change(
            changed_section="CONTEXT",
            workflow_state=workflow_state,
            stale_sections=stale_sections,
        )

    @staticmethod
    def stale_sections_after_change(
        *,
        changed_section: str,
        workflow_state: str,
        stale_sections: list | None,
    ) -> list:
        """Merge the explicit six-stage dependency graph into stale sections.

        ``workflow_state`` is retained in the signature so callers have one
        stable API while design sections are implemented incrementally. A
        context-only draft has no downstream artefacts to invalidate.
        """
        if workflow_state == WorkflowState.DRAFT:
            return list(stale_sections or [])

        existing_sections = list(stale_sections or [])
        return existing_sections + [
            section
            for section in STALE_SECTIONS_BY_CHANGE[changed_section]
            if section not in existing_sections
        ]

    @staticmethod
    def stale_sections_after_objective_change(
        workflow_state: str, stale_sections: list | None
    ) -> list:
        return WorkflowService.stale_sections_after_change(
            changed_section="OBJECTIVE",
            workflow_state=workflow_state,
            stale_sections=stale_sections,
        )

    @staticmethod
    def stale_sections_after_pedagogy_change(
        workflow_state: str, stale_sections: list | None
    ) -> list:
        return WorkflowService.stale_sections_after_change(
            changed_section="PEDAGOGY",
            workflow_state=workflow_state,
            stale_sections=stale_sections,
        )

    @staticmethod
    def stale_sections_after_assessment_change(
        workflow_state: str, stale_sections: list | None
    ) -> list:
        return WorkflowService.stale_sections_after_change(
            changed_section="ASSESSMENT",
            workflow_state=workflow_state,
            stale_sections=stale_sections,
        )

    @staticmethod
    def stale_sections_after_activity_change(
        workflow_state: str, stale_sections: list | None
    ) -> list:
        return WorkflowService.stale_sections_after_change(
            changed_section="ACTIVITY",
            workflow_state=workflow_state,
            stale_sections=stale_sections,
        )
