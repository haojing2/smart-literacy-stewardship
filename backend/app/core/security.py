"""HS256 JWT helpers and Demo-only plaintext password comparison."""

import base64
import binascii
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

from app.core.config import settings

def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def verify_plaintext_password(password: str, stored_password: str) -> bool:
    """Compare the Demo database's plaintext password field safely."""
    return hmac.compare_digest(password, stored_password)


def create_access_token(subject: str) -> str:
    if settings.jwt_algorithm != "HS256":
        raise ValueError("Only HS256 JWTs are supported by the current security helper")

    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.access_token_expire_minutes)).timestamp()),
    }
    header = {"alg": "HS256", "typ": "JWT"}
    signing_input = ".".join(
        (
            _b64encode(json.dumps(header, separators=(",", ":")).encode("utf-8")),
            _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
        )
    )
    signature = hmac.new(
        settings.jwt_secret_key.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256
    ).digest()
    return f"{signing_input}.{_b64encode(signature)}"


def decode_access_token(token: str) -> dict[str, object]:
    """Validate an HS256 access token and return its payload."""
    if settings.jwt_algorithm != "HS256":
        raise ValueError("Unsupported JWT algorithm")

    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
        header = json.loads(_b64decode(encoded_header))
        payload = json.loads(_b64decode(encoded_payload))
        signature = _b64decode(encoded_signature)
    except (UnicodeDecodeError, ValueError, binascii.Error, json.JSONDecodeError) as exc:
        raise ValueError("Malformed access token") from exc

    if header.get("alg") != "HS256" or header.get("typ") != "JWT":
        raise ValueError("Invalid access token header")
    expected_signature = hmac.new(
        settings.jwt_secret_key.encode("utf-8"),
        f"{encoded_header}.{encoded_payload}".encode("ascii"),
        hashlib.sha256,
    ).digest()
    if not hmac.compare_digest(signature, expected_signature):
        raise ValueError("Invalid access token signature")
    if not isinstance(payload.get("sub"), str) or not isinstance(payload.get("exp"), int):
        raise ValueError("Invalid access token payload")
    if payload["exp"] <= int(datetime.now(timezone.utc).timestamp()):
        raise ValueError("Expired access token")
    return payload
