from app.core.security import create_access_token
from app.models.user import SysUser, UserStatus


def _user(db, username: str, status: UserStatus, role: str = "USER") -> SysUser:
    user = SysUser(username=username, password="secret", display_name=username.title(), role=role, status=status)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _headers(user: SysUser) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.username)}"}


def test_register_user_is_pending(client, db):
    response = client.post("/api/v1/auth/register", json={"username": "new-user", "displayName": "New User", "password": "secret"})
    assert response.status_code == 201
    assert response.json()["data"]["status"] == "PENDING"
    user = db.query(SysUser).filter_by(username="new-user").one()
    assert user.role == "USER"
    assert user.status == UserStatus.PENDING


def test_pending_user_cannot_login(client, db):
    _user(db, "pending-user", UserStatus.PENDING)
    response = client.post("/api/v1/auth/login", json={"username": "pending-user", "password": "secret"})
    assert response.status_code == 403
    assert response.json()["code"] == 40301


def test_active_user_can_login(client, db):
    _user(db, "active-user", UserStatus.ACTIVE)
    assert client.post("/api/v1/auth/login", json={"username": "active-user", "password": "secret"}).status_code == 200


def test_rejected_user_cannot_login(client, db):
    _user(db, "rejected-user", UserStatus.REJECTED)
    response = client.post("/api/v1/auth/login", json={"username": "rejected-user", "password": "secret"})
    assert response.status_code == 403
    assert response.json()["code"] == 40302


def test_disabled_user_cannot_login(client, db):
    _user(db, "disabled-user", UserStatus.DISABLED)
    response = client.post("/api/v1/auth/login", json={"username": "disabled-user", "password": "secret"})
    assert response.status_code == 403
    assert response.json()["code"] == 40303


def test_user_cannot_access_admin_api(client, teacher):
    response = client.get("/api/v1/admin/users", headers=_headers(teacher))
    assert response.status_code == 403
    assert response.json()["code"] == 40310


def test_admin_can_list_and_manage_users(client, db):
    admin = _user(db, "admin", UserStatus.ACTIVE, "ADMIN")
    pending = _user(db, "approval-user", UserStatus.PENDING)
    headers = _headers(admin)
    assert client.get("/api/v1/admin/users", headers=headers).status_code == 200
    assert client.post(f"/api/v1/admin/users/{pending.id}/approve", headers=headers).json()["data"]["status"] == "ACTIVE"
    assert client.post(f"/api/v1/admin/users/{pending.id}/disable", headers=headers).json()["data"]["status"] == "DISABLED"
    assert client.post(f"/api/v1/admin/users/{pending.id}/enable", headers=headers).json()["data"]["status"] == "ACTIVE"


def test_admin_can_reject_pending_user(client, db):
    admin = _user(db, "reject-admin", UserStatus.ACTIVE, "ADMIN")
    pending = _user(db, "reject-target", UserStatus.PENDING)
    response = client.post(f"/api/v1/admin/users/{pending.id}/reject", headers=_headers(admin))
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "REJECTED"


def test_admin_cannot_modify_admin_with_normal_user_actions(client, db):
    admin = _user(db, "protected-admin", UserStatus.ACTIVE, "ADMIN")
    response = client.post(f"/api/v1/admin/users/{admin.id}/disable", headers=_headers(admin))
    assert response.status_code == 409
    assert response.json()["code"] == 40930
