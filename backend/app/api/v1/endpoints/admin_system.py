from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_admin
from app.core.config import settings
from app.core.responses import success_response
from app.db.dependencies import get_db
from app.models.user import SysUser
from app.services.admin_user_service import AdminUserService

router = APIRouter(prefix="/api/v1/admin", tags=["admin-system"])


@router.get("/system/status")
def system_status(_: SysUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    database = "UP"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        database = "DOWN"
        db.rollback()
    stats = AdminUserService(db).stats() if database == "UP" else {
        "registeredUsers": 0, "pendingUsers": 0, "activeUsers": 0, "projectCount": 0,
    }
    return success_response({
        "api": "UP",
        "database": database,
        "version": settings.app_version,
        "environment": "development" if settings.debug else "production",
        **stats,
    })
