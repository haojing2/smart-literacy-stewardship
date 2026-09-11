from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, verify_plaintext_password
from app.db.dependencies import get_db
from app.models.user import SysUser, UserStatus
from app.schemas.auth import LoginData, LoginRequest, LoginUser, RegisterData, RegisterRequest

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(SysUser).where(SysUser.username == payload.username))
    if user is None or not verify_plaintext_password(payload.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": 40101, "message": "用户名或密码错误"},
        )

    status_errors = {
        UserStatus.PENDING: (40301, "您的账号正在等待管理员审核"),
        UserStatus.REJECTED: (40302, "您的注册申请暂未通过，请联系管理员"),
        UserStatus.DISABLED: (40303, "当前账号已停用，请联系管理员"),
    }
    try:
        user_status = UserStatus(user.status)
    except ValueError:
        user_status = UserStatus.DISABLED
    if user_status != UserStatus.ACTIVE:
        code, message = status_errors[user_status]
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": code, "message": message},
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


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    username = payload.username.strip()
    display_name = payload.display_name.strip()
    if not username or not display_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": 42201, "message": "用户名和显示名称不能为空"},
        )

    if db.scalar(select(SysUser.id).where(SysUser.username == username)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": 40901, "message": "用户名已存在"},
        )

    user = SysUser(
        username=username,
        display_name=display_name,
        password=payload.password,
        role="USER",
        status=UserStatus.PENDING,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": 40901, "message": "用户名已存在"},
        ) from None
    db.refresh(user)

    return {
        "code": 0,
        "message": "success",
        "data": RegisterData(
            status=UserStatus.PENDING.name,
            message="注册申请已提交，请等待管理员审核",
        ).model_dump(),
        "requestId": None,
    }
