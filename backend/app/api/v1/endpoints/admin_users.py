from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_admin
from app.core.responses import success_response
from app.db.dependencies import get_db
from app.models.user import SysUser, UserStatus
from app.services.admin_user_service import (
    AdminAccountProtectedError,
    AdminUserNotFoundError,
    AdminUserService,
    AdminUserTransitionError,
)

router = APIRouter(prefix="/api/v1/admin/users", tags=["admin-users"])


@router.get("")
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, alias="pageSize", ge=1, le=100),
    status_name: str | None = Query(None, alias="status"),
    keyword: str | None = Query(None),
    _: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if status_name and status_name not in UserStatus.__members__:
        raise HTTPException(status_code=422, detail={"code": 42201, "message": "Invalid user status"})
    return success_response(AdminUserService(db).list_users(page=page, page_size=page_size, status_name=status_name, keyword=keyword))


def _transition(user_id: int, action: str, db: Session):
    service = AdminUserService(db)
    try:
        return success_response(getattr(service, action)(user_id))
    except AdminUserNotFoundError:
        raise HTTPException(status_code=404, detail={"code": 40430, "message": "User was not found"}) from None
    except AdminAccountProtectedError:
        raise HTTPException(status_code=409, detail={"code": 40930, "message": "管理员账号不能通过普通用户管理操作修改"}) from None
    except AdminUserTransitionError:
        raise HTTPException(status_code=409, detail={"code": 40931, "message": "当前用户状态不允许此操作"}) from None


@router.post("/{user_id}/approve")
def approve(user_id: int, _: SysUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    return _transition(user_id, "approve_user", db)


@router.post("/{user_id}/reject")
def reject(user_id: int, _: SysUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    return _transition(user_id, "reject_user", db)


@router.post("/{user_id}/disable")
def disable(user_id: int, _: SysUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    return _transition(user_id, "disable_user", db)


@router.post("/{user_id}/enable")
def enable(user_id: int, _: SysUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    return _transition(user_id, "enable_user", db)
