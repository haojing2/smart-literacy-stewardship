from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.course_project import CourseProject
from app.models.user import SysUser, UserStatus


class AdminUserNotFoundError(Exception):
    pass


class AdminUserTransitionError(Exception):
    pass


class AdminAccountProtectedError(Exception):
    pass


class AdminUserService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def serialize(user: SysUser) -> dict[str, object]:
        return {
            "id": user.id,
            "username": user.username,
            "displayName": user.display_name,
            "role": user.role,
            "status": UserStatus(user.status).name,
            "createdAt": user.created_at,
            "updatedAt": user.updated_at,
        }

    def list_users(self, *, page: int, page_size: int, status_name: str | None, keyword: str | None) -> dict[str, object]:
        filters = []
        if status_name:
            filters.append(SysUser.status == UserStatus[status_name])
        if keyword and keyword.strip():
            term = f"%{keyword.strip()}%"
            filters.append(or_(SysUser.username.like(term), SysUser.display_name.like(term)))
        total = self.db.scalar(select(func.count(SysUser.id)).where(*filters)) or 0
        users = self.db.scalars(
            select(SysUser).where(*filters).order_by(SysUser.created_at.desc())
            .offset((page - 1) * page_size).limit(page_size)
        ).all()
        return {"items": [self.serialize(user) for user in users], "total": total, "page": page, "pageSize": page_size}

    def stats(self) -> dict[str, int]:
        counts = dict(self.db.execute(select(SysUser.status, func.count(SysUser.id)).group_by(SysUser.status)).all())
        return {
            "registeredUsers": sum(counts.values()),
            "pendingUsers": counts.get(UserStatus.PENDING, 0),
            "activeUsers": counts.get(UserStatus.ACTIVE, 0),
            "projectCount": self.db.scalar(select(func.count(CourseProject.id))) or 0,
        }

    def transition(self, user_id: int, *, allowed: set[UserStatus], target: UserStatus) -> dict[str, object]:
        user = self.db.get(SysUser, user_id)
        if user is None:
            raise AdminUserNotFoundError
        if user.role == "ADMIN":
            raise AdminAccountProtectedError
        if UserStatus(user.status) not in allowed:
            raise AdminUserTransitionError
        user.status = target
        self.db.commit()
        self.db.refresh(user)
        return self.serialize(user)

    def approve_user(self, user_id: int):
        return self.transition(user_id, allowed={UserStatus.PENDING, UserStatus.REJECTED}, target=UserStatus.ACTIVE)

    def reject_user(self, user_id: int):
        return self.transition(user_id, allowed={UserStatus.PENDING}, target=UserStatus.REJECTED)

    def disable_user(self, user_id: int):
        return self.transition(user_id, allowed={UserStatus.ACTIVE}, target=UserStatus.DISABLED)

    def enable_user(self, user_id: int):
        return self.transition(user_id, allowed={UserStatus.DISABLED}, target=UserStatus.ACTIVE)
