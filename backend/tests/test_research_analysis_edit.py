from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.course_project import CourseProject
from app.models.research import ResearchAnalysis, ResearchResource
from app.models.user import SysUser


def create_session(
    client: TestClient,
    db: Session,
    teacher: SysUser,
    headers: dict[str, str],
) -> tuple[int, ResearchResource]:
    project = CourseProject(
        user_id=teacher.id,
        title="Research analysis editing",
        topic="AI literacy",
        project_type="NEW_TOPIC",
        workflow_state="DRAFT",
        stale_sections_json=[],
    )
    db.add(project)
    db.flush()
    resource = ResearchResource(
        project_id=project.id,
        user_id=teacher.id,
        original_filename="study.pdf",
        storage_key=f"{teacher.id}/{project.id}/study.pdf",
        media_type="application/pdf",
        size_bytes=100,
        sha256="e" * 64,
        processing_status="TEXT_EXTRACTED",
        extracted_text="Complete research paper text.",
    )
    db.add(resource)
    db.commit()
    response = client.post(
        f"/api/v1/projects/{project.id}/research-chat/sessions",
        headers=headers,
        json={"resourceId": resource.id},
    )
    assert response.status_code == 201
    return response.json()["data"]["sessionId"], resource


def complete_analysis_payload() -> dict[str, object]:
    return {
        "participants": ["Grade 5 students"],
        "researchTopic": "AI information verification",
        "aiLiteracyDimensions": ["critical evaluation"],
        "teachingStrategies": ["source comparison"],
        "intervention": "8 weeks",
        "assessmentTools": ["performance rubric"],
        "mainFindings": ["Verification performance improved"],
        "limitations": ["Single-school sample"],
    }


def test_teacher_edit_versions_analysis_and_confirm_marks_resource_reviewed(
    client: TestClient,
    db: Session,
    teacher: SysUser,
    auth_headers: dict[str, str],
) -> None:
    session_id, resource = create_session(
        client, db, teacher, auth_headers
    )

    edited = client.put(
        f"/api/v1/research-chat/sessions/{session_id}/analysis",
        headers=auth_headers,
        json=complete_analysis_payload(),
    )
    assert edited.status_code == 200
    data = edited.json()["data"]
    assert data["version"] == 2
    assert data["latestAnalysis"] == complete_analysis_payload()
    assert data["readiness"] == {
        "ready": True,
        "readinessScore": 100,
        "readinessStatus": "READY",
        "missingRequiredFields": [],
        "missingRecommendedFields": [],
    }
    assert data["teacherConfirmed"] is False
    assert set(data["fieldSources"].values()) == {"TEACHER"}

    analyses = db.scalars(
        select(ResearchAnalysis)
        .where(ResearchAnalysis.resource_id == resource.id)
        .order_by(ResearchAnalysis.version)
    ).all()
    assert [analysis.version for analysis in analyses] == [1, 2]
    assert analyses[0].structured_data_json["research_subjects"] == []
    assert analyses[1].structured_data_json["research_subjects"] == [
        "Grade 5 students"
    ]

    confirmed = client.post(
        f"/api/v1/research-chat/sessions/{session_id}/analysis/confirm",
        headers=auth_headers,
    )
    assert confirmed.status_code == 200
    confirmed_data = confirmed.json()["data"]
    assert confirmed_data["version"] == 2
    assert confirmed_data["teacherConfirmed"] is True
    assert confirmed_data["teacherConfirmedAt"] is not None
    first_confirmed_at = confirmed_data["teacherConfirmedAt"]
    db.refresh(resource)
    assert resource.processing_status == "REVIEWED"

    repeated = client.post(
        f"/api/v1/research-chat/sessions/{session_id}/analysis/confirm",
        headers=auth_headers,
    )
    assert repeated.status_code == 200
    assert repeated.json()["data"]["version"] == 2
    assert repeated.json()["data"]["teacherConfirmedAt"] == first_confirmed_at

    revised_payload = complete_analysis_payload()
    revised_payload["limitations"] = ["A revised limitation"]
    revised = client.put(
        f"/api/v1/research-chat/sessions/{session_id}/analysis",
        headers=auth_headers,
        json=revised_payload,
    )
    assert revised.status_code == 200
    assert revised.json()["data"]["version"] == 3
    assert revised.json()["data"]["teacherConfirmed"] is False
    db.refresh(resource)
    assert resource.processing_status == "TEXT_EXTRACTED"


def test_incomplete_analysis_cannot_be_confirmed(
    client: TestClient,
    db: Session,
    teacher: SysUser,
    auth_headers: dict[str, str],
) -> None:
    session_id, resource = create_session(
        client, db, teacher, auth_headers
    )
    payload = complete_analysis_payload()
    payload["participants"] = ["  "]
    payload["mainFindings"] = []

    edited = client.put(
        f"/api/v1/research-chat/sessions/{session_id}/analysis",
        headers=auth_headers,
        json=payload,
    )
    assert edited.status_code == 200
    assert edited.json()["data"]["readiness"] == {
        "ready": False,
        "readinessScore": 70,
        "readinessStatus": "INCOMPLETE",
        "missingRequiredFields": ["participants", "mainFindings"],
        "missingRecommendedFields": [],
    }

    confirmed = client.post(
        f"/api/v1/research-chat/sessions/{session_id}/analysis/confirm",
        headers=auth_headers,
    )
    assert confirmed.status_code == 409
    assert confirmed.json()["code"] == 40904
    db.refresh(resource)
    assert resource.processing_status == "TEXT_EXTRACTED"


def test_analysis_edit_requires_auth_and_full_payload(
    client: TestClient,
    db: Session,
    teacher: SysUser,
    auth_headers: dict[str, str],
) -> None:
    session_id, _ = create_session(client, db, teacher, auth_headers)
    endpoint = f"/api/v1/research-chat/sessions/{session_id}/analysis"

    assert client.put(endpoint, json=complete_analysis_payload()).status_code == 401
    incomplete = complete_analysis_payload()
    incomplete.pop("limitations")
    assert (
        client.put(endpoint, headers=auth_headers, json=incomplete).status_code
        == 422
    )


def test_analysis_edit_is_hidden_for_deleted_project(
    client: TestClient,
    db: Session,
    teacher: SysUser,
    auth_headers: dict[str, str],
) -> None:
    session_id, resource = create_session(
        client, db, teacher, auth_headers
    )
    project = db.get(CourseProject, resource.project_id)
    project.is_deleted = True
    db.commit()

    edited = client.put(
        f"/api/v1/research-chat/sessions/{session_id}/analysis",
        headers=auth_headers,
        json=complete_analysis_payload(),
    )
    confirmed = client.post(
        f"/api/v1/research-chat/sessions/{session_id}/analysis/confirm",
        headers=auth_headers,
    )
    assert edited.status_code == 404
    assert confirmed.status_code == 404
