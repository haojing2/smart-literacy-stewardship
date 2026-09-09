"""One-time repair: label empty, unconfirmed resource analyses as FAILED."""

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.research import ResearchAnalysis


MEANINGFUL_FIELDS = (
    "research_subjects", "research_topics", "ai_literacy_dimensions",
    "teaching_strategies", "intervention_duration", "assessment_tools",
    "main_findings", "limitations", "teaching_implications", "source_excerpt",
)


def main() -> None:
    updated = 0
    with SessionLocal() as db:
        analyses = db.scalars(
            select(ResearchAnalysis).where(
                ResearchAnalysis.resource_id.is_not(None),
                ResearchAnalysis.teacher_confirmed.is_(False),
            )
        ).all()
        for analysis in analyses:
            data = analysis.structured_data_json or {}
            if analysis.generation_status != "FAILED" and not any(data.get(key) for key in MEANINGFUL_FIELDS):
                analysis.generation_status = "FAILED"
                updated += 1
        db.commit()
    print(f"Marked {updated} empty, unconfirmed resource analyses as FAILED")


if __name__ == "__main__":
    main()
