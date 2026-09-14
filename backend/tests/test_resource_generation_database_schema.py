from sqlalchemy import select

from app.db.base import Base
from app.models.resource_creation import (
    ResourceCreationJob,
    ResourceGenerationPart,
    ResourceGenerationRun,
)
from app.services.resource_creation_service import ResourceCreationService
from test_resource_generation_context_service import _confirmed_course


def test_progressive_models_are_registered_with_expected_table_names() -> None:
    assert ResourceGenerationRun.__tablename__ == "resource_generation_run"
    assert ResourceGenerationPart.__tablename__ == "resource_generation_part"
    assert "resource_generation_run" in Base.metadata.tables
    assert "resource_generation_part" in Base.metadata.tables


def test_run_and_part_persist_and_run_delete_preserves_job(db, teacher) -> None:
    _, project = _confirmed_course(db, teacher)
    job = ResourceCreationJob(
        project_id=project.id,
        user_id=teacher.id,
        selected_types_json=["DISCUSSION"],
        resource_settings_json={"discussion": {"quantity": 1}},
        status="DRAFT",
    )
    db.add(job)
    db.flush()
    run = ResourceGenerationRun(
        job_id=job.id,
        project_id=project.id,
        user_id=teacher.id,
        status="PENDING",
        selected_types_json=["DISCUSSION"],
        normalized_context_json={},
        total_parts=1,
    )
    db.add(run)
    db.flush()
    part = ResourceGenerationPart(
        run_id=run.id,
        resource_type="DISCUSSION",
        part_key="question_1",
        section="questions",
        sequence_no=1,
        status="PENDING",
        required=True,
        dependencies_json=[],
        spec_json={},
    )
    db.add(part)
    db.commit()

    assert db.scalar(select(ResourceGenerationRun).where(ResourceGenerationRun.id == run.id)) is not None
    assert db.scalar(select(ResourceGenerationPart).where(ResourceGenerationPart.run_id == run.id)) is not None
    state = ResourceCreationService(db).get_state(
        current_user_id=teacher.id,
        project_id=project.id,
    )
    assert state["generationRun"]["runId"] == run.id

    job_id = job.id
    db.delete(run)
    db.commit()
    assert db.get(ResourceCreationJob, job_id) is not None
    assert db.scalar(select(ResourceGenerationPart).where(ResourceGenerationPart.run_id == run.id)) is None
