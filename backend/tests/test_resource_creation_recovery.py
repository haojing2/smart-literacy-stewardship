from __future__ import annotations

import asyncio

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.assistants.mock_research_assistant import MockResearchAssistant
from app.models.course_design import ProjectActivity, ProjectAssessment, ProjectObjective, ProjectPedagogy
from app.models.course_project import CourseProject
from app.models.resource_creation import TeachingResourceVersion
from app.models.user import SysUser
from app.schemas.resource_creation import (
    ResourceCreationJobCreateRequest,
    ResourceCreationJobUpdateRequest,
    ResourceDraftContent,
    ResourceType,
    TeachingResourceVersionCreateRequest,
)
from app.services.resource_creation_service import ResourceCreationService


class CountingResourceProvider(MockResearchAssistant):
    def __init__(self) -> None:
        super().__init__()
        self.resource_generation_calls = 0

    async def generate_teaching_resource(self, request):
        self.resource_generation_calls += 1
        return await super().generate_teaching_resource(request)


def _confirmed_course(db: Session) -> tuple[SysUser, CourseProject]:
    user = SysUser(
        username="resource-recovery-teacher", password="secret",
        display_name="Teacher", role="TEACHER",
    )
    db.add(user)
    db.flush()
    project = CourseProject(
        user_id=user.id, title="AI 信息核验", topic="信息可信度", project_type="NEW_TOPIC",
        grade=7, class_hours=1, lesson_minutes=40, student_level="中等",
        workflow_state="ACTIVITY_READY",
    )
    db.add(project)
    db.flush()
    objective = ProjectObjective(
        project_id=project.id, content="依据证据判断AI回答", sequence_no=1,
        standard_refs_json=[], literacy_refs_json=[], rationale="可观察", source_type="AI",
        teacher_action="ACCEPT", confirmed=True, version=1,
    )
    db.add(objective)
    db.flush()
    db.add_all([
        ProjectPedagogy(
            project_id=project.id, rationale="协作核查", suitable_for_json=[], alternative_json=None,
            teacher_action="ACCEPT", confirmed=True, version=1, custom_name="探究学习",
            custom_description="小组比较证据", source_type="TEACHER",
        ),
        ProjectAssessment(
            project_id=project.id, objective_id=objective.id, task_content="提交核查记录",
            student_evidence_json=["记录"], criteria_json=["证据准确"], rationale="对齐目标",
            confirmed=True, version=1,
        ),
        ProjectActivity(
            project_id=project.id, sequence_no=1, name="证据核查", duration=40,
            core_task="比较来源", teacher_action="追问理由", student_action="记录证据",
            ai_role="提供候选信息", dominant_actor="STUDENT", assessment_note="观察判断依据",
            scaffolds_json=["核查表"], objective_refs_json=[objective.id], version=1,
        ),
    ])
    db.commit()
    return user, project


def _content(title: str) -> ResourceDraftContent:
    return ResourceDraftContent.model_validate({
        "title": title,
        "blocks": [{"key": "main", "title": "任务", "content": title}],
        "metadata": {},
    })


def _create_job(service, user, project, types) -> int:
    return service.create_job(
        current_user_id=user.id,
        project_id=project.id,
        payload=ResourceCreationJobCreateRequest(projectId=project.id, selectedTypes=types),
    )["job"]["jobId"]


def _advance_to_v4(service, user, project, resource_id) -> None:
    for version_no in range(2, 5):
        service.create_teacher_version(
            current_user_id=user.id, project_id=project.id, resource_id=resource_id,
            payload=TeachingResourceVersionCreateRequest(
                content=_content(f"worksheet v{version_no}"),
                changeSummary=f"teacher edit v{version_no}",
            ),
        )


def test_generate_is_idempotent_and_only_calls_provider_for_missing_types(db: Session) -> None:
    user, project = _confirmed_course(db)
    service = ResourceCreationService(db)
    provider = CountingResourceProvider()
    job_id = _create_job(service, user, project, [ResourceType.WORKSHEET])
    first = asyncio.run(service.generate(
        current_user_id=user.id, project_id=project.id, job_id=job_id, provider=provider,
    ))
    worksheet_id = first["resources"][0]["resourceId"]
    _advance_to_v4(service, user, project, worksheet_id)
    provider.resource_generation_calls = 0

    repeated = asyncio.run(service.generate(
        current_user_id=user.id, project_id=project.id, job_id=job_id, provider=provider,
    ))
    assert provider.resource_generation_calls == 0
    assert repeated["resources"][0]["currentVersionNo"] == 4
    assert db.scalar(select(func.count()).select_from(TeachingResourceVersion)) == 4

    service.update_job(
        current_user_id=user.id, project_id=project.id, job_id=job_id,
        payload=ResourceCreationJobUpdateRequest(
            selectedTypes=[ResourceType.WORKSHEET, ResourceType.ASSESSMENT]
        ),
    )
    partial = asyncio.run(service.generate(
        current_user_id=user.id, project_id=project.id, job_id=job_id, provider=provider,
    ))
    by_type = {item["resourceType"]: item for item in partial["resources"]}
    assert provider.resource_generation_calls == 1
    assert by_type[ResourceType.WORKSHEET.value]["currentVersionNo"] == 4
    assert by_type[ResourceType.ASSESSMENT.value]["currentVersionNo"] == 1


def test_regenerate_explicitly_appends_v5(db: Session) -> None:
    user, project = _confirmed_course(db)
    service = ResourceCreationService(db)
    provider = CountingResourceProvider()
    job_id = _create_job(service, user, project, [ResourceType.WORKSHEET])
    first = asyncio.run(service.generate(
        current_user_id=user.id, project_id=project.id, job_id=job_id, provider=provider,
    ))
    worksheet_id = first["resources"][0]["resourceId"]
    _advance_to_v4(service, user, project, worksheet_id)
    provider.resource_generation_calls = 0

    regenerated = asyncio.run(service.generate(
        current_user_id=user.id, project_id=project.id, job_id=job_id,
        provider=provider, regenerate=True,
    ))
    assert provider.resource_generation_calls == 1
    assert regenerated["resources"][0]["currentVersionNo"] == 5


def test_latest_teacher_version_is_restored_when_latest_job_is_draft(db: Session) -> None:
    user, project = _confirmed_course(db)
    service = ResourceCreationService(db)
    provider = CountingResourceProvider()
    old_job_id = _create_job(service, user, project, [ResourceType.WORKSHEET])
    first = asyncio.run(service.generate(
        current_user_id=user.id, project_id=project.id, job_id=old_job_id, provider=provider,
    ))
    worksheet_id = first["resources"][0]["resourceId"]
    _advance_to_v4(service, user, project, worksheet_id)
    service.create_teacher_version(
        current_user_id=user.id, project_id=project.id, resource_id=worksheet_id,
        payload=TeachingResourceVersionCreateRequest(
            content=_content("teacher worksheet v5"), changeSummary="teacher edit v5",
        ),
    )
    new_job_id = _create_job(service, user, project, [ResourceType.ASSESSMENT])

    state = service.get_state(current_user_id=user.id, project_id=project.id)
    assert state["job"]["jobId"] == new_job_id
    assert state["job"]["status"] == "DRAFT"
    assert len(state["resources"]) == 1
    restored = service.get_resource_detail(
        current_user_id=user.id, project_id=project.id,
        resource_id=state["resources"][0]["resourceId"],
    )
    assert restored["currentVersion"]["versionNo"] == 5
    assert restored["currentVersion"]["content"]["title"] == "teacher worksheet v5"
