from datetime import timedelta
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session
import jwt
from pwdlib import PasswordHash
from app.config import settings
from app.db import get_db
from app.models import User, UserStudent, Student, LearningContext, Task, now

passwords = PasswordHash.recommended()
bearer = HTTPBearer(auto_error=False)


def token(user):
    return jwt.encode(
        {"sub": user.id, "exp": now() + timedelta(hours=12), "iat": now()}, settings.jwt_secret, algorithm="HS256"
    )


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)):
    try:
        claims = jwt.decode(credentials.credentials if credentials else "", settings.jwt_secret, algorithms=["HS256"])
        user = db.get(User, claims["sub"])
        if not user:
            raise ValueError()
        return user
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(401, "请先登录")


def admin(user: User = Depends(current_user)):
    if not user.is_admin:
        raise HTTPException(403, "需要管理员权限")
    return user


def scope(db, user, student_id, write=False, owner=False):
    student_id = str(student_id)
    link = db.scalar(select(UserStudent).where(UserStudent.student_id == student_id, UserStudent.user_id == user.id))
    if not link or (write and link.role == "VIEWER") or (owner and link.role != "OWNER"):
        raise HTTPException(403, "无权访问该学生")
    return db.get(Student, student_id)


def context_scope(db, user, student_id, context_id, write=True):
    student = scope(db, user, student_id, write=write)
    ctx = db.get(LearningContext, str(context_id))
    if not ctx or ctx.student_id != student.id:
        raise HTTPException(404, "学习上下文不存在")
    if write and ctx.status != "active":
        raise HTTPException(409, "请使用当前激活的学习上下文")
    return ctx


def task_scope(db, student_id, task_id, context_id=None):
    if not task_id:
        return None
    from app.models import WeeklyPlan

    task = db.get(Task, str(task_id))
    if not task or task.student_id != str(student_id):
        raise HTTPException(404, "任务不存在")
    plan = db.get(WeeklyPlan, task.weekly_plan_id)
    if context_id and (plan.learning_context_id != str(context_id) or plan.status != "ACTIVE"):
        raise HTTPException(409, "任务已不属于当前学习计划")
    return task
