from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.dependencies import get_db
from app.models.user import SysUser, UserStatus

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> SysUser:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": 40101, "message": "Authentication credentials are required"},
        )

    try:
        subject = decode_access_token(credentials.credentials)["sub"]
    except (KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": 40101, "message": "Invalid or expired access token"},
        ) from None

    user = db.scalar(
        select(SysUser).where(SysUser.username == subject, SysUser.status == UserStatus.ACTIVE)
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": 40101, "message": "Current user is unavailable"},
        )
    return user


def get_current_admin(
    current_user: SysUser = Depends(get_current_user),
) -> SysUser:
    if current_user.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": 40310, "message": "Administrator permission is required"},
        )
    return current_user
