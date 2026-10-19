from datetime import datetime
from uuid import UUID
from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app import models as m
from app.schemas import ReviewInput
from app.schemas_lessons import StartLesson, LessonAnswer, LessonNotes, ReviseLesson
from app.security import current_user, admin, scope, context_scope
from app.services.common import row, require
from app.services import lessons

router = APIRouter(prefix="/api/v1")
DB = Annotated[Session, Depends(get_db)]
User = Annotated[m.User, Depends(current_user)]
Admin = Annotated[m.User, Depends(admin)]


@router.get("/students/{sid}/lessons")
def catalog(sid: UUID, db: DB, user: User, as_of: datetime | None = None) -> dict:
    scope(db, user, sid)
    return lessons.catalog(db, str(sid), as_of)


@router.post("/students/{sid}/lessons/{id}/start")
def start(sid: UUID, id: UUID, data: StartLesson, db: DB, user: User) -> dict:
    return lessons.start(db, user, str(sid), id, data)


@router.get("/lesson-runs/{id}")
def detail(id: UUID, db: DB, user: User) -> dict:
    return lessons.run_view(db, user, require(db, m.LessonRun, id))


@router.post("/lesson-runs/{id}/answer")
def answer(id: UUID, data: LessonAnswer, db: DB, user: User) -> dict:
    return lessons.answer(db, user, id, data)


@router.patch("/lesson-runs/{id}/notes")
def notes(id: UUID, data: LessonNotes, db: DB, user: User) -> dict:
    run = require(db, m.LessonRun, id)
    context_scope(db, user, run.student_id, run.learning_context_id)
    run.notes = data.notes
    return {"notes": run.notes}


@router.post("/lesson-runs/{id}/finish")
def finish(id: UUID, db: DB, user: User) -> dict:
    return lessons.finish(db, user, id)


@router.get("/admin/lessons")
def queue(db: DB, user: Admin) -> list[dict]:
    return [
        {**row(rev), "lesson": row(db.get(m.Lesson, rev.lesson_id))}
        for rev in db.scalars(
            select(m.LessonRevision)
            .join(m.Lesson)
            .order_by(m.Lesson.sequence, m.Lesson.min_level, m.LessonRevision.version.desc())
        )
    ]


@router.post("/admin/lessons/{id}/review")
def review(id: UUID, data: ReviewInput, db: DB, user: Admin) -> dict:
    return lessons.review(db, user, id, data)


@router.post("/admin/lessons/{id}/revisions")
def revise(id: UUID, data: ReviseLesson, db: DB, user: Admin) -> dict:
    return lessons.revise(db, user, id, data)
