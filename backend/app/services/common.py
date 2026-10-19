from fastapi import HTTPException
from sqlalchemy import inspect, select
from app.models import Audit, LearningContext, now


def row(obj):
    return {column.key: getattr(obj, column.key) for column in inspect(obj).mapper.column_attrs}


def require(db, model, identifier):
    result = db.get(model, str(identifier))
    if not result:
        raise HTTPException(404, "记录不存在")
    return result


def audit(db, user, action, student_id=None, **details):
    db.add(Audit(actor_id=user.id, student_id=student_id, action=action, details=details))


def active_context(db, student_id, at=None):
    query = select(LearningContext).where(LearningContext.student_id == student_id)
    if at:
        # Context activations are time-versioned in audit records by the API.
        from app.models import Audit

        change = db.scalar(
            select(Audit)
            .where(Audit.student_id == student_id, Audit.action == "CONTEXT_ACTIVATED", Audit.created_at <= at)
            .order_by(Audit.created_at.desc())
        )
        if change:
            return db.get(LearningContext, change.details["context_id"])
        query = query.where(LearningContext.created_at <= at)
    else:
        query = query.where(LearningContext.status == "active")
    ctx = db.scalar(query.order_by(LearningContext.created_at.desc()))
    if not ctx:
        raise HTTPException(409, "请先设置学习上下文")
    return ctx


def calculation_time(value=None):
    from datetime import timezone

    if value and value.tzinfo:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    if value and value > now():
        raise HTTPException(422, "as_of 不得晚于当前时间")
    return value or now()
