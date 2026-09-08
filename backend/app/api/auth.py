from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, verify_plaintext_password
from app.db.dependencies import get_db
from app.models.user import SysUser
from app.schemas.auth import LoginData, LoginRequest, LoginUser

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(SysUser).where(SysUser.username == payload.username))
    if user is None or user.status != 1 or not verify_plaintext_password(payload.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": 40101, "message": "用户名或密码错误"},
        )

    return {
        "code": 0,
        "message": "success",
        "data": LoginData(
            access_token=create_access_token(user.username),
            expires_in=settings.access_token_expire_minutes * 60,
            user=LoginUser(
                id=user.id,
                username=user.username,
                display_name=user.display_name,
                role=user.role,
            ),
        ).model_dump(by_alias=True),
        "requestId": None,
    }
