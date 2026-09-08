from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models.course_project import CourseProject
from app.models.user import SysUser
from app.services.project_service import ProjectService


DOWNSTREAM_PROJECT_TABLES = (
    "project_objective",
    "project_pedagogy",
    "project_activity",
    "project_assessment",
    "quality_check",
    "artifact",
)


def create_downstream_project_records(db: Session, project_id: int) -> None:
    """Create minimal test-only child rows with production table names.

    These future modules do not yet have ORM mappings. The foreign keys use
    ``ON DELETE CASCADE`` so a physical project deletion would remove the
    records and fail this logical-deletion test.
    """
    for table_name in DOWNSTREAM_PROJECT_TABLES:
        db.execute(
            text(
                f"CREATE TABLE `{table_name}` ("
                "id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, "
                "project_id BIGINT UNSIGNED NOT NULL, "
                "PRIMARY KEY (id), "
                f"CONSTRAINT `fk_{table_name}_test_project` "
                "FOREIGN KEY (project_id) REFERENCES course_project(id) "
                "ON DELETE CASCADE"
                ")"
            )
        )
        db.execute(
            text(f"INSERT INTO `{table_name}` (project_id) VALUES (:project_id)"),
            {"project_id": project_id},
        )
    db.commit()


def drop_downstream_project_tables(db: Session) -> None:
    for table_name in reversed(DOWNSTREAM_PROJECT_TABLES):
        db.execute(text(f"DROP TABLE IF EXISTS `{table_name}`"))
    db.commit()


@pytest.fixture(autouse=True)
def seed_users(db: Session):
    db.add_all(
        [
            SysUser(username="teacher", password="secret", display_name="Teacher", role="TEACHER"),
            SysUser(username="other", password="secret", display_name="Other", role="TEACHER"),
        ]
    )
    db.commit()


@pytest.fixture()
def teacher(db: Session) -> SysUser:
    return db.query(SysUser).filter_by(username="teacher").one()


@pytest.fixture()
def other(db: Session) -> SysUser:
    return db.query(SysUser).filter_by(username="other").one()


@pytest.fixture()
def auth_headers(teacher: SysUser) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(teacher.username)}"}


def create_project(client: TestClient, headers: dict[str, str], title: str = "AI 回答可信吗？") -> int:
    response = client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "title": title,
            "topic": "生成式 AI 信息核验",
            "projectType": "NEW_TOPIC",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["code"] == 0
    assert body["data"]["workflowState"] == "DRAFT"
    return body["data"]["projectId"]


def context_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "grade": 5,
        "classHours": 2,
        "studentLevel": "GENERAL",
        "aiAccessMode": "GROUP",
        "devices": ["COMPUTER"],
        "constraints": [],
        "additionalRequirements": "",
    }
    payload.update(overrides)
    return payload


def test_login_returns_current_user_and_projects_persist_after_relogin(
    client: TestClient,
):
    first_login = client.post("/api/v1/auth/login", json={"username": "teacher", "password": "secret"})
    assert first_login.status_code == 200
    first_body = first_login.json()
    assert first_body["data"]["user"]["username"] == "teacher"
    assert first_body["data"]["expires_in"] == 2 * 24 * 60 * 60
    first_headers = {"Authorization": f"Bearer {first_body['data']['access_token']}"}
    project_id = create_project(client, first_headers)

    second_login = client.post("/api/v1/auth/login", json={"username": "teacher", "password": "secret"})
    second_headers = {"Authorization": f"Bearer {second_login.json()['data']['access_token']}"}
    projects = client.get("/api/v1/projects", headers=second_headers)
    assert projects.status_code == 200
    assert [item["projectId"] for item in projects.json()["data"]["items"]] == [project_id]


def test_projects_require_authentication(client: TestClient):
    response = client.get("/api/v1/projects")
    assert response.status_code == 401
    assert response.json()["code"] == 40101


def test_create_project_uses_authenticated_user_and_draft_state(
    client: TestClient, db: Session, teacher: SysUser, auth_headers: dict[str, str]
):
    project_id = create_project(client, auth_headers)

    project = db.get(CourseProject, project_id)
    assert project is not None
    assert project.user_id == teacher.id
    assert project.workflow_state == "DRAFT"
    assert project.stale_sections_json == []


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        (
            {"title": "", "topic": "主题", "projectType": "NEW_TOPIC"},
            "title",
        ),
        (
            {"title": "项目", "topic": "主题", "projectType": "INVALID"},
            "projectType",
        ),
    ],
)
def test_create_project_rejects_invalid_payload(
    client: TestClient, auth_headers: dict[str, str], payload: dict[str, str], field: str
):
    response = client.post("/api/v1/projects", headers=auth_headers, json=payload)
    assert response.status_code == 422
    assert response.json()["code"] == 42201
    assert any(error["loc"][-1] == field for error in response.json()["errors"])


def test_list_projects_is_owned_descending_paginated_and_filterable(
    client: TestClient,
    db: Session,
    teacher: SysUser,
    other: SysUser,
    auth_headers: dict[str, str],
):
    old_id = create_project(client, auth_headers, "较早项目")
    new_id = create_project(client, auth_headers, "较新项目")
    db.add(CourseProject(
        user_id=other.id,
        title="其他教师项目",
        topic="主题",
        project_type="NEW_TOPIC",
        workflow_state="DRAFT",
        stale_sections_json=[],
    ))
    db.commit()

    old_project = db.get(CourseProject, old_id)
    new_project = db.get(CourseProject, new_id)
    assert old_project and new_project
    old_project.updated_at = datetime(2026, 1, 1, 10, 0, 0)
    old_project.grade = 4
    new_project.updated_at = datetime(2026, 1, 2, 10, 0, 0)
    new_project.grade = 5
    db.commit()

    response = client.get("/api/v1/projects?page=1&pageSize=1", headers=auth_headers)
    body = response.json()
    assert response.status_code == 200
    assert body["data"]["total"] == 2
    assert body["data"]["page"] == 1
    assert body["data"]["pageSize"] == 1
    assert [item["title"] for item in body["data"]["items"]] == ["较新项目"]
    assert all(item["title"] != "其他教师项目" for item in body["data"]["items"])

    second_page = client.get("/api/v1/projects?page=2&pageSize=1", headers=auth_headers)
    assert [item["title"] for item in second_page.json()["data"]["items"]] == ["较早项目"]

    grade_response = client.get("/api/v1/projects?grade=4", headers=auth_headers)
    assert [item["projectId"] for item in grade_response.json()["data"]["items"]] == [old_id]


def test_project_detail_is_owned_and_missing_or_foreign_projects_return_404(
    client: TestClient,
    db: Session,
    other: SysUser,
    auth_headers: dict[str, str],
):
    project_id = create_project(client, auth_headers)
    detail = client.get(f"/api/v1/projects/{project_id}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["projectId"] == project_id

    missing = client.get("/api/v1/projects/999999", headers=auth_headers)
    assert missing.status_code == 404
    assert missing.json()["code"] == 40401

    foreign_project = CourseProject(
        user_id=other.id,
        title="私有项目",
        topic="主题",
        project_type="NEW_TOPIC",
        workflow_state="DRAFT",
        stale_sections_json=[],
    )
    db.add(foreign_project)
    db.commit()
    foreign = client.get(f"/api/v1/projects/{foreign_project.id}", headers=auth_headers)
    assert foreign.status_code == 404


def test_project_basic_info_can_be_updated_without_changing_workflow(
    client: TestClient, auth_headers: dict[str, str]
):
    project_id = create_project(client, auth_headers)
    response = client.patch(
        f"/api/v1/projects/{project_id}",
        headers=auth_headers,
        json={
            "title": "更新后的项目名称",
            "topic": "更新后的教学主题",
            "projectType": "OPTIMIZE_EXISTING",
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["title"] == "更新后的项目名称"
    assert data["topic"] == "更新后的教学主题"
    assert data["projectType"] == "OPTIMIZE_EXISTING"
    assert data["workflowState"] == "DRAFT"


def test_project_update_marks_stale_only_for_real_design_basis_changes(
    client: TestClient, db: Session, auth_headers: dict[str, str]
):
    project_id = create_project(client, auth_headers)
    project = db.get(CourseProject, project_id)
    assert project is not None
    project.workflow_state = "OBJECTIVE_READY"
    db.commit()

    title_only = client.patch(
        f"/api/v1/projects/{project_id}",
        headers=auth_headers,
        json={"title": "\u66f4\u65b0\u540e\u7684\u9879\u76ee\u540d\u79f0"},
    )
    assert title_only.status_code == 200
    assert title_only.json()["data"]["workflowState"] == "OBJECTIVE_READY"
    assert title_only.json()["data"]["staleSections"] == []

    unchanged_topic = client.patch(
        f"/api/v1/projects/{project_id}",
        headers=auth_headers,
        json={"topic": "\u751f\u6210\u5f0fAI\u4fe1\u606f\u6838\u9a8c"},
    )
    assert unchanged_topic.status_code == 200
    assert unchanged_topic.json()["data"]["staleSections"] == []

    changed_topic = client.patch(
        f"/api/v1/projects/{project_id}",
        headers=auth_headers,
        json={"topic": "\u751f\u6210\u5f0fAI\u5b89\u5168\u4f26\u7406"},
    )
    assert changed_topic.status_code == 200
    assert changed_topic.json()["data"]["staleSections"] == [
        "OBJECTIVE",
        "PEDAGOGY",
        "ASSESSMENT",
        "ACTIVITY",
        "QUALITY",
        "ARTIFACT",
    ]


def test_update_title_keeps_workflow_and_stale_sections_unchanged(
    client: TestClient, db: Session, auth_headers: dict[str, str]
):
    project_id = create_project(client, auth_headers, title="AI回答可信吗？")
    project = db.get(CourseProject, project_id)
    assert project is not None
    project.workflow_state = "OBJECTIVE_CONFIRMED"
    project.stale_sections_json = ["PEDAGOGY"]
    db.commit()

    response = client.patch(
        f"/api/v1/projects/{project_id}",
        headers=auth_headers,
        json={"title": "AI的回答可信吗？"},
    )
    assert response.status_code == 200
    db.refresh(project)
    assert project.title == "AI的回答可信吗？"
    assert project.workflow_state == "OBJECTIVE_CONFIRMED"
    assert project.stale_sections_json == ["PEDAGOGY"]


def test_update_topic_in_objective_confirmed_marks_downstream_sections_stale_once(
    client: TestClient, db: Session, auth_headers: dict[str, str]
):
    project_id = create_project(client, auth_headers)
    project = db.get(CourseProject, project_id)
    assert project is not None
    project.workflow_state = "OBJECTIVE_CONFIRMED"
    project.stale_sections_json = []
    db.commit()

    changed = client.patch(
        f"/api/v1/projects/{project_id}",
        headers=auth_headers,
        json={"topic": "生成式AI安全伦理"},
    )
    assert changed.status_code == 200
    expected_stale_sections = [
        "OBJECTIVE",
        "PEDAGOGY",
        "ASSESSMENT",
        "ACTIVITY",
        "QUALITY",
        "ARTIFACT",
    ]
    assert changed.json()["data"]["staleSections"] == expected_stale_sections

    unchanged = client.patch(
        f"/api/v1/projects/{project_id}",
        headers=auth_headers,
        json={"topic": "生成式AI安全伦理"},
    )
    assert unchanged.status_code == 200
    assert unchanged.json()["data"]["staleSections"] == expected_stale_sections


def test_update_project_type_after_downstream_design_marks_sections_stale(
    client: TestClient, db: Session, auth_headers: dict[str, str]
):
    project_id = create_project(client, auth_headers)
    project = db.get(CourseProject, project_id)
    assert project is not None
    project.workflow_state = "OBJECTIVE_CONFIRMED"
    db.commit()

    response = client.patch(
        f"/api/v1/projects/{project_id}",
        headers=auth_headers,
        json={"projectType": "OPTIMIZE_EXISTING"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["staleSections"] == [
        "OBJECTIVE",
        "PEDAGOGY",
        "ASSESSMENT",
        "ACTIVITY",
        "QUALITY",
        "ARTIFACT",
    ]


def test_cannot_update_another_users_project(
    client: TestClient,
    db: Session,
    other: SysUser,
    auth_headers: dict[str, str],
):
    project = CourseProject(
        user_id=other.id,
        title="其他用户项目",
        topic="教学主题",
        project_type="NEW_TOPIC",
        workflow_state="DRAFT",
        stale_sections_json=[],
    )
    db.add(project)
    db.commit()

    response = client.patch(
        f"/api/v1/projects/{project.id}",
        headers=auth_headers,
        json={"title": "越权修改"},
    )
    assert response.status_code == 404


def test_cannot_update_a_soft_deleted_project(
    client: TestClient, db: Session, auth_headers: dict[str, str]
):
    project_id = create_project(client, auth_headers)
    project = db.get(CourseProject, project_id)
    assert project is not None
    project.is_deleted = True
    project.deleted_at = datetime.now()
    db.commit()

    response = client.patch(
        f"/api/v1/projects/{project_id}",
        headers=auth_headers,
        json={"title": "不应被更新"},
    )
    assert response.status_code == 404


def test_delete_project(
    client: TestClient, db: Session, auth_headers: dict[str, str]
):
    project_id = create_project(client, auth_headers)
    response = client.delete(f"/api/v1/projects/{project_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["data"]["projectId"] == project_id
    assert response.json()["data"]["deleted"] is True

    project = db.get(CourseProject, project_id)
    assert project is not None
    assert project.is_deleted is True
    assert project.deleted_at is not None

    assert client.get(f"/api/v1/projects/{project_id}", headers=auth_headers).status_code == 404
    assert client.get("/api/v1/projects", headers=auth_headers).json()["data"]["total"] == 0
    assert (
        client.patch(
            f"/api/v1/projects/{project_id}",
            headers=auth_headers,
            json={"title": "\u4e0d\u5e94\u88ab\u66f4\u65b0"},
        ).status_code
        == 404
    )
    assert (
        client.put(
            f"/api/v1/projects/{project_id}/context",
            headers=auth_headers,
            json=context_payload(),
        ).status_code
        == 404
    )


def test_cannot_delete_another_users_project(
    client: TestClient,
    db: Session,
    other: SysUser,
    auth_headers: dict[str, str],
):
    project = CourseProject(
        user_id=other.id,
        title="其他用户项目",
        topic="教学主题",
        project_type="NEW_TOPIC",
        workflow_state="DRAFT",
        stale_sections_json=[],
    )
    db.add(project)
    db.commit()

    response = client.delete(f"/api/v1/projects/{project.id}", headers=auth_headers)
    assert response.status_code == 404
    db.refresh(project)
    assert project.is_deleted is False
    assert project.deleted_at is None


def test_soft_delete_preserves_downstream_project_records(
    client: TestClient, db: Session, auth_headers: dict[str, str]
):
    project_id = create_project(client, auth_headers)
    create_downstream_project_records(db, project_id)
    try:
        response = client.delete(f"/api/v1/projects/{project_id}", headers=auth_headers)
        assert response.status_code == 200

        project = db.get(CourseProject, project_id)
        assert project is not None
        assert project.is_deleted is True
        assert project.deleted_at is not None
        for table_name in DOWNSTREAM_PROJECT_TABLES:
            count = db.scalar(
                text(f"SELECT COUNT(*) FROM `{table_name}` WHERE project_id = :project_id"),
                {"project_id": project_id},
            )
            assert count == 1, f"{table_name} records must remain after logical deletion"
    finally:
        drop_downstream_project_tables(db)


def test_save_context_transitions_and_persists_values(
    client: TestClient, auth_headers: dict[str, str]
):
    project_id = create_project(client, auth_headers)
    saved = client.put(
        f"/api/v1/projects/{project_id}/context",
        headers=auth_headers,
        json=context_payload(),
    )
    assert saved.status_code == 200
    saved_data = saved.json()["data"]
    assert set(saved_data) == {
        "projectId",
        "workflowState",
        "staleSections",
        "updatedAt",
    }
    assert saved_data["projectId"] == project_id
    assert saved_data["workflowState"] == "CONTEXT_READY"
    assert saved_data["staleSections"] == []

    detail = client.get(f"/api/v1/projects/{project_id}", headers=auth_headers)
    data = detail.json()["data"]
    assert data["grade"] == 5
    assert data["classHours"] == 2
    assert data["studentLevel"] == "GENERAL"
    assert data["aiAccessMode"] == "GROUP"
    assert data["devices"] == ["COMPUTER"]


@pytest.mark.parametrize(("override", "field"), [({"grade": 0}, "grade"), ({"classHours": 0}, "classHours")])
def test_save_context_rejects_invalid_numbers(
    client: TestClient, auth_headers: dict[str, str], override: dict[str, int], field: str
):
    project_id = create_project(client, auth_headers)
    response = client.put(
        f"/api/v1/projects/{project_id}/context",
        headers=auth_headers,
        json=context_payload(**override),
    )
    assert response.status_code == 422
    assert any(error["loc"][-1] == field for error in response.json()["errors"])


def test_context_change_marks_downstream_sections_stale(
    client: TestClient, db: Session, auth_headers: dict[str, str]
):
    project_id = create_project(client, auth_headers)
    project = db.get(CourseProject, project_id)
    assert project is not None
    project.workflow_state = "OBJECTIVE_READY"
    project.updated_at = datetime.now() + timedelta(seconds=1)
    db.commit()

    response = client.put(
        f"/api/v1/projects/{project_id}/context",
        headers=auth_headers,
        json=context_payload(grade=6),
    )
    assert response.status_code == 200
    assert response.json()["data"]["staleSections"] == [
        "OBJECTIVE",
        "PEDAGOGY",
        "ASSESSMENT",
        "ACTIVITY",
        "QUALITY",
        "ARTIFACT",
    ]


def test_complete_research_transitions_context_ready_and_is_idempotent(
    client: TestClient, db: Session, auth_headers: dict[str, str]
):
    project_id = create_project(client, auth_headers)
    project = db.get(CourseProject, project_id)
    assert project is not None
    assert project.workflow_state == "DRAFT"

    saved = client.put(
        f"/api/v1/projects/{project_id}/context",
        headers=auth_headers,
        json=context_payload(),
    )
    assert saved.status_code == 200
    assert saved.json()["data"]["workflowState"] == "CONTEXT_READY"

    completed = client.post(
        f"/api/v1/projects/{project_id}/research/complete",
        headers=auth_headers,
    )
    assert completed.status_code == 200
    assert completed.json()["data"]["projectId"] == project_id
    assert completed.json()["data"]["workflowState"] == "RESEARCH_READY"
    assert completed.json()["data"]["updatedAt"]

    repeated = client.post(
        f"/api/v1/projects/{project_id}/research/complete",
        headers=auth_headers,
    )
    assert repeated.status_code == 200
    assert repeated.json()["data"]["workflowState"] == "RESEARCH_READY"
    db.refresh(project)
    assert project.workflow_state == "RESEARCH_READY"


def test_complete_research_does_not_regress_a_course_design_state(
    client: TestClient, db: Session, auth_headers: dict[str, str]
):
    project_id = create_project(client, auth_headers)
    project = db.get(CourseProject, project_id)
    assert project is not None
    project.workflow_state = "OBJECTIVE_PENDING"
    db.commit()

    response = client.post(
        f"/api/v1/projects/{project_id}/research/complete",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["data"]["workflowState"] == "OBJECTIVE_PENDING"
    db.refresh(project)
    assert project.workflow_state == "OBJECTIVE_PENDING"


def test_complete_research_rejects_draft_project(
    client: TestClient, auth_headers: dict[str, str]
):
    project_id = create_project(client, auth_headers)
    response = client.post(
        f"/api/v1/projects/{project_id}/research/complete",
        headers=auth_headers,
    )
    assert response.status_code == 409
    assert response.json()["code"] == 40916


def test_complete_research_hides_foreign_and_deleted_projects(
    client: TestClient,
    db: Session,
    other: SysUser,
    auth_headers: dict[str, str],
):
    foreign_project = CourseProject(
        user_id=other.id,
        title="Foreign research project",
        topic="Research",
        project_type="NEW_TOPIC",
        workflow_state="CONTEXT_READY",
        stale_sections_json=[],
    )
    db.add(foreign_project)
    db.commit()
    foreign_response = client.post(
        f"/api/v1/projects/{foreign_project.id}/research/complete",
        headers=auth_headers,
    )
    assert foreign_response.status_code == 404

    project_id = create_project(client, auth_headers)
    project = db.get(CourseProject, project_id)
    assert project is not None
    project.workflow_state = "CONTEXT_READY"
    project.is_deleted = True
    db.commit()
    deleted_response = client.post(
        f"/api/v1/projects/{project_id}/research/complete",
        headers=auth_headers,
    )
    assert deleted_response.status_code == 404


def test_unexpected_project_error_uses_unified_500_response(
    client: TestClient, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
):
    def raise_database_error(*_: object, **__: object):
        raise RuntimeError("simulated database failure")

    monkeypatch.setattr(ProjectService, "list_projects", raise_database_error)
    response = client.get("/api/v1/projects", headers=auth_headers)
    assert response.status_code == 500
    body = response.json()
    assert body["code"] == 50000
    assert body["data"] is None
    assert body["requestId"]
