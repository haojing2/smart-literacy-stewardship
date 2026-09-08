from __future__ import annotations

import inspect

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.course_project import CourseProject
from app.models.research import (
    ResearchAnalysis,
    ResearchChatMessage,
    ResearchChatSession,
    ResearchResource,
)
from app.models.user import SysUser
from app.services.research_chat_service import ResearchChatService


def create_ready_resource(
    db: Session,
    user: SysUser,
    *,
    status: str = "TEXT_EXTRACTED",
) -> tuple[CourseProject, ResearchResource]:
    project = CourseProject(
        user_id=user.id,
        title="研究对话测试项目",
        topic="AI 信息核验",
        project_type="NEW_TOPIC",
        workflow_state="DRAFT",
        stale_sections_json=[],
    )
    db.add(project)
    db.flush()
    resource = ResearchResource(
        project_id=project.id,
        user_id=user.id,
        original_filename="study.pdf",
        storage_key=f"{user.id}/{project.id}/study.pdf",
        media_type="application/pdf",
        size_bytes=100,
        sha256="c" * 64,
        processing_status=status,
        extracted_text="论文完整正文" if status == "TEXT_EXTRACTED" else None,
    )
    db.add(resource)
    db.commit()
    return project, resource


def create_session(
    client: TestClient,
    headers: dict[str, str],
    project_id: int,
    resource_id: int,
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/projects/{project_id}/research-chat/sessions",
        headers=headers,
        json={"resourceId": resource_id, "title": "论文研读"},
    )
    assert response.status_code == 201
    return response.json()["data"]


def create_project_session(
    client: TestClient,
    headers: dict[str, str],
    project_id: int,
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/projects/{project_id}/research-chat/sessions",
        headers=headers,
        json={"resourceId": None},
    )
    assert response.status_code == 201
    return response.json()["data"]


def test_project_knowledge_session_can_start_without_a_research_resource(
    client: TestClient,
    db: Session,
    teacher: SysUser,
    auth_headers: dict[str, str],
) -> None:
    project = CourseProject(
        user_id=teacher.id,
        title="Direct research chat project",
        topic="AI literacy",
        project_type="NEW_TOPIC",
        workflow_state="DRAFT",
        stale_sections_json=[],
    )
    db.add(project)
    db.commit()

    created = create_project_session(client, auth_headers, project.id)
    repeated = create_project_session(client, auth_headers, project.id)

    assert created["projectId"] == project.id
    assert created["resourceId"] is None
    assert created["latestAnalysis"] is not None
    assert created["readiness"] is not None
    assert repeated["sessionId"] == created["sessionId"]
    assert db.scalar(select(func.count()).select_from(ResearchResource)) == 0
    assert db.scalar(select(func.count()).select_from(ResearchChatSession)) == 1
    assert db.scalar(select(func.count()).select_from(ResearchAnalysis)) == 1


def test_legacy_project_session_without_analysis_is_backfilled(
    client: TestClient,
    db: Session,
    teacher: SysUser,
    auth_headers: dict[str, str],
) -> None:
    project = CourseProject(
        user_id=teacher.id,
        title="Legacy project chat",
        topic="AI literacy",
        project_type="NEW_TOPIC",
        workflow_state="DRAFT",
        stale_sections_json=[],
    )
    db.add(project)
    db.flush()
    session = ResearchChatSession(
        user_id=teacher.id,
        project_id=project.id,
        resource_id=None,
        title="Legacy session",
        status="ACTIVE",
    )
    db.add(session)
    db.commit()

    response = client.get(
        f"/api/v1/projects/{project.id}/research-chat/sessions/latest",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["data"]["sessionId"] == session.id
    assert response.json()["data"]["latestAnalysis"] is not None
    assert db.scalar(select(func.count()).select_from(ResearchAnalysis)) == 1


def test_project_knowledge_chat_persists_turns_with_session_analysis(
    client: TestClient,
    db: Session,
    teacher: SysUser,
    auth_headers: dict[str, str],
) -> None:
    project = CourseProject(
        user_id=teacher.id,
        title="Multi-turn project chat",
        topic="Collaborative learning",
        project_type="NEW_TOPIC",
        workflow_state="DRAFT",
        stale_sections_json=[],
    )
    db.add(project)
    db.commit()
    session = create_project_session(client, auth_headers, project.id)
    session_id = session["sessionId"]

    first = client.post(
        f"/api/v1/research-chat/sessions/{session_id}/messages",
        headers=auth_headers,
        json={"content": "participants: Grade five students\nmain findings: Collaborative learning improved verification performance."},
    )
    second = client.post(
        f"/api/v1/research-chat/sessions/{session_id}/messages",
        headers=auth_headers,
        json={"content": "How about grade five students?"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    data = second.json()["data"]
    # A normal follow-up answer need not contain a structured patch; the
    # analysis accumulated from the previous turn must still be preserved.
    assert data["analysisPatch"] is None
    assert data["latestAnalysis"] is not None
    assert data["latestAnalysis"]["researchSubjects"] == ["Grade five students"]
    assert data["readiness"] is not None
    assert data["evidenceDraftGenerated"] is False
    refreshed = client.get(
        f"/api/v1/research-chat/sessions/{session_id}", headers=auth_headers
    )
    assert refreshed.status_code == 200
    assert [message["role"] for message in refreshed.json()["data"]["messages"]] == [
        "USER",
        "ASSISTANT",
        "USER",
        "ASSISTANT",
    ]
    assert db.scalar(select(func.count()).select_from(ResearchAnalysis)) >= 2


def test_project_chat_summarizes_only_messages_displaced_from_recent_window(
    client: TestClient,
    db: Session,
    teacher: SysUser,
    auth_headers: dict[str, str],
) -> None:
    project = CourseProject(
        user_id=teacher.id,
        title="Summary project",
        topic="Collaborative learning",
        project_type="NEW_TOPIC",
        workflow_state="DRAFT",
        stale_sections_json=[],
    )
    db.add(project)
    db.commit()
    session_id = create_project_session(client, auth_headers, project.id)["sessionId"]

    for index in range(11):
        response = client.post(
            f"/api/v1/research-chat/sessions/{session_id}/messages",
            headers=auth_headers,
            json={"content": f"Question {index}: how does this apply to grade five?"},
        )
        assert response.status_code == 200

    session = db.get(ResearchChatSession, session_id)
    assert session is not None
    assert session.conversation_summary
    assert session.conversation_summary_through_sequence_no > 0
    assert db.scalar(select(func.count()).select_from(ResearchChatMessage)) == 22


def test_create_session_persists_session_and_initial_analysis(
    client: TestClient,
    db: Session,
    teacher: SysUser,
    auth_headers: dict[str, str],
) -> None:
    project, resource = create_ready_resource(db, teacher)
    data = create_session(client, auth_headers, project.id, resource.id)

    assert data["projectId"] == project.id
    assert data["resourceId"] == resource.id
    assert data["title"] == "论文研读"
    assert data["status"] == "ACTIVE"
    assert data["messages"] == []
    assert data["latestAnalysis"]["researchTopics"] == ["AI 信息核验"]
    assert data["latestAnalysis"]["mainFindings"] == []
    assert data["readiness"] == {
        "ready": False,
        "readinessScore": 23,
        "readinessStatus": "INCOMPLETE",
        "missingRequiredFields": [
            "participants",
            "mainFindings",
            "teachingStrategies",
        ],
        "missingRecommendedFields": [
            "aiLiteracyDimensions",
            "intervention",
            "assessmentTools",
            "limitations",
        ],
    }
    assert db.scalar(select(func.count()).select_from(ResearchChatSession)) == 1
    assert db.scalar(select(func.count()).select_from(ResearchAnalysis)) == 1
    assert db.scalar(select(func.count()).select_from(ResearchChatMessage)) == 0


def test_multi_turn_messages_persist_patch_analysis_and_reach_readiness(
    client: TestClient,
    db: Session,
    teacher: SysUser,
    auth_headers: dict[str, str],
) -> None:
    project, resource = create_ready_resource(db, teacher)
    session = create_session(client, auth_headers, project.id, resource.id)
    session_id = session["sessionId"]

    first = client.post(
        f"/api/v1/research-chat/sessions/{session_id}/messages",
        headers=auth_headers,
        json={"content": "请继续分析。"},
    )
    assert first.status_code == 200
    first_data = first.json()["data"]
    assert first_data["assistantMessage"]["content"] == (
        "当前研究对象尚未确认。你可以在右侧研究解析区补充研究对象。"
    )
    assert first_data["analysisPatch"] is None
    assert first_data["userMessage"]["sequenceNo"] == 1
    assert first_data["assistantMessage"]["sequenceNo"] == 2

    second = client.post(
        f"/api/v1/research-chat/sessions/{session_id}/messages",
        headers=auth_headers,
        json={"content": "研究对象：五年级学生"},
    )
    second_data = second.json()["data"]
    assert second.status_code == 200
    assert second_data["analysisPatch"]["researchSubjects"] == ["五年级学生"]
    assert second_data["assistantMessage"]["content"] == (
        "当前尚未形成主要研究结果，请补充论文中的核心研究发现。"
    )
    assert second_data["readiness"]["ready"] is False

    third = client.post(
        f"/api/v1/research-chat/sessions/{session_id}/messages",
        headers=auth_headers,
        json={"content": "主要研究结果：学生的信息核验表现有所提升"},
    )
    third_data = third.json()["data"]
    assert third.status_code == 200
    assert third_data["assistantMessage"]["content"] == (
        "当前尚未明确教学策略，请补充研究中的教学策略。"
    )
    assert third_data["latestAnalysis"]["researchSubjects"] == ["五年级学生"]
    assert third_data["latestAnalysis"]["mainFindings"] == [
        "学生的信息核验表现有所提升"
    ]
    assert third_data["latestAnalysis"]["evidenceReady"] is False
    assert third_data["readiness"]["readinessScore"] == 53
    assert third_data["readiness"]["readinessStatus"] == "INCOMPLETE"
    assert third_data["readiness"]["missingRequiredFields"] == [
        "teachingStrategies"
    ]

    refreshed = client.get(
        f"/api/v1/research-chat/sessions/{session_id}",
        headers=auth_headers,
    )
    assert refreshed.status_code == 200
    refreshed_data = refreshed.json()["data"]
    assert [message["sequenceNo"] for message in refreshed_data["messages"]] == [
        1,
        2,
        3,
        4,
        5,
        6,
    ]
    assert refreshed_data["latestAnalysis"] == third_data["latestAnalysis"]
    assert refreshed_data["readiness"]["ready"] is False

    analyses = db.scalars(
        select(ResearchAnalysis)
        .where(ResearchAnalysis.resource_id == resource.id)
        .order_by(ResearchAnalysis.version)
    ).all()
    assert [analysis.version for analysis in analyses] == [1, 2, 3]
    analysis = analyses[-1]
    assert analysis.structured_data_json["research_subjects"] == ["五年级学生"]
    assert analysis.structured_data_json["main_findings"] == [
        "学生的信息核验表现有所提升"
    ]
    assert db.scalar(select(func.count()).select_from(ResearchChatMessage)) == 6


def test_chat_endpoints_require_authentication(
    client: TestClient,
    db: Session,
    teacher: SysUser,
    auth_headers: dict[str, str],
) -> None:
    project, resource = create_ready_resource(db, teacher)
    assert (
        client.post(
            f"/api/v1/projects/{project.id}/research-chat/sessions",
            json={"resourceId": resource.id},
        ).status_code
        == 401
    )
    session = create_session(client, auth_headers, project.id, resource.id)
    session_id = session["sessionId"]
    assert client.get(f"/api/v1/research-chat/sessions/{session_id}").status_code == 401
    assert (
        client.post(
            f"/api/v1/research-chat/sessions/{session_id}/messages",
            json={"content": "test"},
        ).status_code
        == 401
    )


def test_cannot_create_session_for_foreign_unextracted_or_deleted_resource(
    client: TestClient,
    db: Session,
    teacher: SysUser,
    other: SysUser,
    auth_headers: dict[str, str],
) -> None:
    foreign_project, foreign_resource = create_ready_resource(db, other)
    own_project, unextracted = create_ready_resource(db, teacher, status="UPLOADED")

    foreign = client.post(
        f"/api/v1/projects/{foreign_project.id}/research-chat/sessions",
        headers=auth_headers,
        json={"resourceId": foreign_resource.id},
    )
    not_ready = client.post(
        f"/api/v1/projects/{own_project.id}/research-chat/sessions",
        headers=auth_headers,
        json={"resourceId": unextracted.id},
    )
    own_project.is_deleted = True
    db.commit()
    deleted = client.post(
        f"/api/v1/projects/{own_project.id}/research-chat/sessions",
        headers=auth_headers,
        json={"resourceId": unextracted.id},
    )
    assert foreign.status_code == 404
    assert not_ready.status_code == 409
    assert deleted.status_code == 404


def test_deleted_project_hides_existing_session(
    client: TestClient,
    db: Session,
    teacher: SysUser,
    auth_headers: dict[str, str],
) -> None:
    project, resource = create_ready_resource(db, teacher)
    session_id = create_session(
        client, auth_headers, project.id, resource.id
    )["sessionId"]
    project.is_deleted = True
    db.commit()

    assert (
        client.get(
            f"/api/v1/research-chat/sessions/{session_id}",
            headers=auth_headers,
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v1/research-chat/sessions/{session_id}/messages",
            headers=auth_headers,
            json={"content": "不应写入"},
        ).status_code
        == 404
    )


def test_research_chat_service_does_not_import_mock_provider() -> None:
    module = __import__(
        "app.services.research_chat_service",
        fromlist=["ResearchChatService"],
    )
    source = inspect.getsource(module)
    assert "MockResearchAssistant" not in source
    assert "mock_research_assistant" not in source
