from __future__ import annotations

from types import SimpleNamespace

from app.api.auth import login
from app.core.config import Settings
from app.core.security import decode_access_token
from app.main import app
from app.schemas.auth import LoginRequest


class ScalarDb:
    def __init__(self, user) -> None:
        self.user = user

    def scalar(self, _statement):
        return self.user


def test_release_debug_environment_value_does_not_block_settings_startup(
    monkeypatch,
) -> None:
    monkeypatch.setenv("DEBUG", "release")
    loaded = Settings(
        _env_file=None,
        mysql_host="localhost",
        mysql_user="test",
        mysql_password="test",
        mysql_database="test",
        jwt_secret_key="test-secret",
    )
    assert loaded.debug is False


def test_login_returns_a_decodable_token_without_exposing_password() -> None:
    user = SimpleNamespace(
        id=1, username="demo", password="test-password",
        display_name="Demo", role="TEACHER", status=1,
    )
    response = login(
        LoginRequest(username="demo", password="test-password"),
        ScalarDb(user),  # type: ignore[arg-type]
    )
    token = response["data"]["access_token"]
    assert decode_access_token(token)["sub"] == "demo"
    assert "password" not in response["data"]["user"]


def test_login_route_is_registered() -> None:
    assert "post" in app.openapi()["paths"]["/api/v1/auth/login"]
