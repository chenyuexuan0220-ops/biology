from datetime import datetime
from uuid import UUID
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session
from app import models as m, schemas as s
from app.db import get_db
from app.security import current_user, admin, passwords, token, scope, context_scope, task_scope
from app.services.common import row, require, audit, calculation_time
from app.services.learning import question_view, answer_question, start_diagnostic, finish_diagnostic
from app.services.mastery import snapshot
from app.planners.adaptive import recalculate
from app.services.graph import add_edge
from app.services.content import generate_content, review_content
from app.ai.gateway import Gateway, GatewayError

router = APIRouter(prefix="/api/v1")
DB = Annotated[Session, Depends(get_db)]
User = Annotated[m.User, Depends(current_user)]
Admin = Annotated[m.User, Depends(admin)]


@router.get("/metadata")
def metadata() -> dict:
    return {
        "education_stages": list(s.EducationStage),
        "biology_levels": list(s.BiologyLevel),
        "competition_goals": list(s.Goal),
    }


@router.post("/auth/register", status_code=201)
def register(data: s.Register, db: DB) -> dict:
    if db.scalar(select(m.User).where(m.User.email == data.email)):
        raise HTTPException(409, "邮箱已注册")
    user = m.User(email=data.email, name=data.name, password_hash=passwords.hash(data.password))
    db.add(user)
    db.flush()
    return {
        "access_token": token(user),
        "token_type": "bearer",
        "user": {"id": user.id, "name": user.name, "is_admin": user.is_admin},
    }


@router.post("/auth/login")
def login(data: s.Login, db: DB) -> dict:
    user = db.scalar(select(m.User).where(m.User.email == data.email.strip().lower()))
    if not user or not passwords.verify(data.password, user.password_hash):
        raise HTTPException(401, "邮箱或密码错误")
    return {
        "access_token": token(user),
        "token_type": "bearer",
        "user": {"id": user.id, "name": user.name, "is_admin": user.is_admin},
    }


@router.get("/auth/me")
def me(user: User) -> dict:
    return {"id": user.id, "email": user.email, "name": user.name, "is_admin": user.is_admin}


@router.get("/students")
def students(db: DB, user: User) -> list[dict]:
    links = db.scalars(select(m.UserStudent).where(m.UserStudent.user_id == user.id)).all()
    return [{**row(db.get(m.Student, link.student_id)), "role": link.role} for link in links]


@router.post("/students", status_code=201)
def create_student(data: s.StudentInput, db: DB, user: User) -> dict:
    student = m.Student(**data.model_dump())
    db.add(student)
    db.flush()
    db.add(m.UserStudent(user_id=user.id, student_id=student.id, role="OWNER"))
    audit(db, user, "STUDENT_CREATED", student.id)
    return row(student)


@router.get("/students/{id}")
def student_detail(id: UUID, db: DB, user: User) -> dict:
    return row(scope(db, user, id))


@router.patch("/students/{id}")
def edit_student(id: UUID, data: s.StudentInput, db: DB, user: User) -> dict:
    student = scope(db, user, id, write=True)
    student.name = data.name
    return row(student)


@router.post("/students/{id}/members")
def grant(id: UUID, data: s.Grant, db: DB, user: User) -> dict:
    scope(db, user, id, owner=True)
    recipient = db.scalar(select(m.User).where(m.User.email == data.email.strip().lower()))
    if not recipient:
        raise HTTPException(404, "该邮箱尚未注册")
    link = db.scalar(
        select(m.UserStudent).where(m.UserStudent.user_id == recipient.id, m.UserStudent.student_id == str(id))
    )
    if link and link.role == "OWNER":
        raise HTTPException(409, "不能更改创建者权限")
    if not link:
        link = m.UserStudent(user_id=recipient.id, student_id=str(id))
        db.add(link)
    link.role = data.role
    db.flush()
    audit(db, user, "STUDENT_ACCESS_GRANTED", str(id), recipient_id=recipient.id, role=data.role)
    return row(link)


@router.get("/students/{id}/learning-contexts")
def contexts(id: UUID, db: DB, user: User) -> list[dict]:
    scope(db, user, id)
    return [
        row(c)
        for c in db.scalars(
            select(m.LearningContext)
            .where(m.LearningContext.student_id == str(id))
            .order_by(m.LearningContext.created_at.desc())
        )
    ]


def activate(db, user, ctx):
    db.scalar(select(m.Student).where(m.Student.id == ctx.student_id).with_for_update())
    for old in db.scalars(select(m.LearningContext).where(m.LearningContext.student_id == ctx.student_id)):
        old.status = "inactive"
    ctx.status = "active"
    for old in db.scalars(
        select(m.WeeklyPlan).where(m.WeeklyPlan.student_id == ctx.student_id, m.WeeklyPlan.status == "ACTIVE")
    ):
        old.status = "SUPERSEDED"
    audit(db, user, "CONTEXT_ACTIVATED", ctx.student_id, context_id=ctx.id)


@router.post("/students/{id}/learning-contexts", status_code=201)
def create_context(id: UUID, data: s.ContextInput, db: DB, user: User) -> dict:
    scope(db, user, id, write=True)
    ctx = m.LearningContext(student_id=str(id), **data.model_dump())
    db.add(ctx)
    db.flush()
    activate(db, user, ctx)
    return row(ctx)


@router.post("/learning-contexts/{id}/activate")
def activate_context(id: UUID, db: DB, user: User) -> dict:
    ctx = require(db, m.LearningContext, id)
    scope(db, user, ctx.student_id, write=True)
    activate(db, user, ctx)
    return row(ctx)


@router.get("/knowledge")
def knowledge(db: DB, user: User, q: str = "", domain_id: UUID | None = None) -> list[dict]:
    query = select(m.Knowledge).where(m.Knowledge.status == "PUBLISHED")
    if q:
        query = query.where(or_(m.Knowledge.name.contains(q), m.Knowledge.code.contains(q)))
    if domain_id:
        query = query.where(m.Knowledge.domain_id == str(domain_id))
    return [row(k) for k in db.scalars(query.order_by(m.Knowledge.code))]


@router.get("/domains")
def domains(db: DB, user: User) -> list[dict]:
    return [row(d) for d in db.scalars(select(m.Domain))]


@router.get("/knowledge-edges")
def edges(db: DB, user: User) -> list[dict]:
    return [row(e) for e in db.scalars(select(m.Edge))]


@router.get("/knowledge/{id}")
def knowledge_detail(id: UUID, db: DB, user: User) -> dict:
    k = require(db, m.Knowledge, id)
    return {
        **row(k),
        "levels": [
            row(level) for level in db.scalars(select(m.KnowledgeLevel).where(m.KnowledgeLevel.knowledge_id == k.id))
        ],
        "resources": [row(r) for r in db.scalars(select(m.Resource).where(m.Resource.knowledge_id == k.id))],
    }


@router.get("/knowledge/{id}/{relation}")
def knowledge_relations(id: UUID, relation: str, db: DB, user: User) -> list[dict]:
    require(db, m.Knowledge, id)
    if relation == "children":
        nodes = db.scalars(select(m.Knowledge).where(m.Knowledge.parent_id == str(id)))
    elif relation == "prerequisites":
        nodes = db.scalars(
            select(m.Knowledge)
            .join(m.Edge, m.Knowledge.id == m.Edge.source_knowledge_id)
            .where(m.Edge.target_knowledge_id == str(id), m.Edge.relation_type == "PREREQUISITE_OF")
        )
    elif relation == "related":
        nodes = db.scalars(
            select(m.Knowledge)
            .join(m.Edge, m.Knowledge.id == m.Edge.target_knowledge_id)
            .where(m.Edge.source_knowledge_id == str(id))
        )
    else:
        raise HTTPException(404, "未知关系")
    return [row(k) for k in nodes]


@router.post("/admin/knowledge-edges")
def create_edge(data: s.EdgeInput, db: DB, user: Admin) -> dict:
    require(db, m.Knowledge, data.source_knowledge_id)
    require(db, m.Knowledge, data.target_knowledge_id)
    edge = add_edge(db, data)
    audit(db, user, "KNOWLEDGE_EDGE_CREATED", edge_id=edge.id)
    return row(edge)


@router.get("/papers")
def papers(db: DB, user: User) -> list[dict]:
    return [row(p) for p in db.scalars(select(m.Paper))]


@router.get("/questions")
def questions(
    db: DB,
    user: User,
    paper_id: UUID | None = None,
    q: str = "",
    offset: int = Query(0, ge=0),
    limit: int = Query(40, ge=1, le=100),
) -> dict:
    query = select(m.Question).where(m.Question.status == "PUBLISHED")
    if paper_id:
        query = query.where(m.Question.paper_id == str(paper_id))
    if q:
        query = query.where(m.Question.stem.contains(q))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    return {
        "items": [
            question_view(db, item)
            for item in db.scalars(
                query.order_by(m.Question.paper_id, m.Question.source_question_no).offset(offset).limit(limit)
            )
        ],
        "total": total,
    }


@router.get("/questions/{id}")
def question_detail(id: UUID, db: DB, user: User) -> dict:
    q = require(db, m.Question, id)
    if q.status != "PUBLISHED":
        raise HTTPException(404, "题目尚未发布")
    return question_view(db, q)


@router.get("/questions/{id}/variants")
def variants(id: UUID, db: DB, user: User) -> list[dict]:
    return [
        {**row(v), "content": {key: value for key, value in v.content.items() if key not in {"answer", "explanation"}}}
        for v in db.scalars(
            select(m.Variant).where(m.Variant.parent_question_id == str(id), m.Variant.status == "PUBLISHED")
        )
    ]


@router.post("/questions/{id}/attempt")
def attempt(id: UUID, data: s.AttemptInput, db: DB, user: User) -> dict:
    return answer_question(db, user, id, data)


@router.post("/diagnostics/start")
def diagnostic_start(data: s.Scoped, db: DB, user: User) -> dict:
    return start_diagnostic(db, user, data)


@router.post("/diagnostics/{id}/answer")
def diagnostic_answer(id: UUID, data: s.DiagnosticAnswer, db: DB, user: User) -> dict:
    d = require(db, m.Diagnostic, id)
    scope(db, user, d.student_id, write=True)
    if (
        d.student_id != str(data.student_id)
        or d.learning_context_id != str(data.learning_context_id)
        or str(data.question_id) not in d.question_ids
    ):
        raise HTTPException(422, "作答不属于该诊断")
    if d.status != "IN_PROGRESS":
        raise HTTPException(409, "诊断已完成")
    previous = d.answers.get(str(data.question_id))
    if previous and previous["event_id"] != str(data.event_id):
        raise HTTPException(409, "该诊断题已作答")
    result = answer_question(db, user, data.question_id, data)
    d.answers = {**d.answers, str(data.question_id): {"correct": result["is_correct"], "event_id": str(data.event_id)}}
    return result


@router.post("/diagnostics/{id}/finish")
def diagnostic_finish(id: UUID, db: DB, user: User) -> dict:
    d = require(db, m.Diagnostic, id)
    scope(db, user, d.student_id, write=True)
    context_scope(db, user, d.student_id, d.learning_context_id)
    return finish_diagnostic(db, d)


@router.get("/diagnostics/{id}/result")
def diagnostic_result(id: UUID, db: DB, user: User) -> dict:
    d = require(db, m.Diagnostic, id)
    scope(db, user, d.student_id)
    return {"status": d.status, "result": d.result}


@router.get("/students/{id}/mastery")
def mastery(id: UUID, db: DB, user: User, as_of: datetime | None = None) -> list[dict]:
    scope(db, user, id)
    known, _ = snapshot(db, str(id), calculation_time(as_of))
    return [{**value, "name": db.get(m.Knowledge, kid).name} for kid, value in known.items()]


@router.get("/students/{id}/competencies")
def competencies(id: UUID, db: DB, user: User, as_of: datetime | None = None) -> list[dict]:
    scope(db, user, id)
    _, known = snapshot(db, str(id), calculation_time(as_of))
    return [
        {**row(c), **known.get(c.id, {"score": 0, "confidence": 0, "evidence_count": 0})}
        for c in db.scalars(select(m.Competency))
    ]


@router.get("/students/{id}/errors")
def errors(id: UUID, db: DB, user: User, as_of: datetime | None = None) -> list[dict]:
    scope(db, user, id)
    items = db.scalars(
        select(m.Attempt)
        .where(
            m.Attempt.student_id == str(id),
            m.Attempt.is_correct.is_(False),
            m.Attempt.created_at <= calculation_time(as_of),
        )
        .order_by(m.Attempt.created_at.desc())
        .limit(100)
    )
    return [{**row(a), "question": question_view(db, db.get(m.Question, a.question_id), reveal=True)} for a in items]


@router.get("/students/{id}/evidence")
def evidence(id: UUID, db: DB, user: User, as_of: datetime | None = None) -> list[dict]:
    scope(db, user, id)
    return [
        row(e)
        for e in db.scalars(
            select(m.Evidence)
            .where(m.Evidence.student_id == str(id), m.Evidence.created_at <= calculation_time(as_of))
            .order_by(m.Evidence.created_at.desc())
            .limit(200)
        )
    ]


@router.post("/students/{id}/plan/recalculate")
def plan_recalculate(id: UUID, data: s.PlanInput, db: DB, user: User) -> dict:
    scope(db, user, id, write=True)
    db.scalar(select(m.Student).where(m.Student.id == str(id)).with_for_update())
    return recalculate(db, str(id), data.as_of)


@router.get("/students/{id}/plan/{period}")
def plan(id: UUID, period: str, db: DB, user: User) -> dict:
    scope(db, user, id)
    if period not in {"today", "week"}:
        raise HTTPException(404, "未知计划周期")
    p = db.scalar(
        select(m.WeeklyPlan)
        .where(m.WeeklyPlan.student_id == str(id), m.WeeklyPlan.status == "ACTIVE")
        .order_by(m.WeeklyPlan.created_at.desc())
    )
    if not p:
        return {"plan": None, "tasks": []}
    query = select(m.Task).where(m.Task.weekly_plan_id == p.id, m.Task.student_id == str(id))
    if period == "today":
        query = query.where(m.Task.task_date == m.now().date())
    return {
        "plan": row(p),
        "tasks": [row(t) for t in db.scalars(query.order_by(m.Task.task_date, m.Task.priority.desc()))],
    }


@router.post("/events")
def events(data: s.EventInput, db: DB, user: User) -> dict:
    ctx = context_scope(db, user, data.student_id, data.learning_context_id)
    task = task_scope(db, data.student_id, data.task_id, ctx.id)
    if data.knowledge_id:
        require(db, m.Knowledge, data.knowledge_id)
    old = db.get(m.LearningEvent, str(data.id))
    if old:
        if (
            old.student_id != str(data.student_id)
            or old.learning_context_id != ctx.id
            or old.event_type != data.event_type
            or old.payload != data.payload
            or old.task_id != (str(data.task_id) if data.task_id else None)
        ):
            raise HTTPException(409, "event_id 已被使用")
        return {**row(old), "replayed": True}
    event = m.LearningEvent(**data.model_dump(mode="json"))
    db.add(event)
    if task and data.event_type == "LEARNING_COMPLETE":
        if task.reason.get("lesson_id"):
            raise HTTPException(409, "课程任务请完成随堂检测后结算")
        if task.question_ids:
            raise HTTPException(409, "练习任务请通过作答完成")
        task.status = "DONE"
    db.flush()
    return row(event)


@router.get("/curriculums")
def curriculums(db: DB, user: User) -> list[dict]:
    return [
        {
            **row(c),
            "units": [
                row(u) for u in db.scalars(select(m.Unit).where(m.Unit.curriculum_id == c.id).order_by(m.Unit.sequence))
            ],
        }
        for c in db.scalars(select(m.Curriculum))
    ]


@router.get("/students/{id}/reports")
def report(id: UUID, db: DB, user: User, as_of: datetime | None = None) -> dict:
    scope(db, user, id)
    at = calculation_time(as_of)
    known, skills = snapshot(db, str(id), at)
    attempts = db.scalars(select(m.Attempt).where(m.Attempt.student_id == str(id), m.Attempt.created_at <= at)).all()
    duration = (
        db.scalar(
            select(func.sum(m.LearningEvent.duration_seconds)).where(
                m.LearningEvent.student_id == str(id), m.LearningEvent.created_at <= at
            )
        )
        or 0
    )
    return {
        "as_of": at,
        "question_count": len(attempts),
        "accuracy": sum(a.is_correct for a in attempts) / len(attempts) if attempts else None,
        "learning_minutes": round(duration / 60),
        "knowledge_count": len(known),
        "evidence_count": sum(v["exposure_count"] for v in known.values()),
        "average_mastery": sum(v["overall_score"] for v in known.values()) / len(known) if known else 0,
        "due_reviews": sum(v["next_review_at"] <= at for v in known.values()),
        "competencies": list(skills.values()),
        "note": "掌握度来自答题证据；完成任务本身不代表已经掌握。",
    }


@router.get("/experiments")
def experiments(db: DB, user: User) -> list[dict]:
    return [
        {
            **row(e),
            "steps": [
                row(x)
                for x in db.scalars(
                    select(m.ExperimentStep)
                    .where(m.ExperimentStep.experiment_id == e.id)
                    .order_by(m.ExperimentStep.sequence)
                )
            ],
            "variables": [
                row(v)
                for v in db.scalars(select(m.ExperimentVariable).where(m.ExperimentVariable.experiment_id == e.id))
            ],
        }
        for e in db.scalars(select(m.Experiment))
    ]


@router.post("/experiments/{id}/observations")
def observation(id: UUID, data: s.ExperimentInput, db: DB, user: User) -> dict:
    require(db, m.Experiment, id)
    ctx = context_scope(db, user, data.student_id, data.learning_context_id)
    event = m.LearningEvent(
        student_id=ctx.student_id,
        learning_context_id=ctx.id,
        event_type="EXPERIMENT",
        payload={"experiment_id": str(id)},
    )
    db.add(event)
    db.flush()
    item = m.Observation(
        student_id=ctx.student_id,
        experiment_id=str(id),
        event_id=event.id,
        data=data.model_dump(mode="json", exclude={"student_id", "learning_context_id"}),
    )
    db.add(item)
    db.flush()
    db.add(m.ExperimentResult(student_id=ctx.student_id, observation_id=item.id, conclusion=data.conclusion))
    return {**row(item), "note": "已记录真实观察，实验能力评分等待教师评价"}


@router.post("/ai/tutor/session")
def tutor_start(data: s.TutorStart, db: DB, user: User) -> dict:
    ctx = context_scope(db, user, data.student_id, data.learning_context_id)
    task_scope(db, data.student_id, data.task_id, ctx.id)
    if data.question_id:
        q = require(db, m.Question, data.question_id)
        if q.status != "PUBLISHED":
            raise HTTPException(404, "题目未发布")
    item = m.TutorSession(**data.model_dump(mode="json"))
    db.add(item)
    db.flush()
    return row(item)


@router.post("/ai/tutor/message")
async def tutor_message(data: s.TutorMessage, db: DB, user: User) -> dict:
    session = require(db, m.TutorSession, data.session_id)
    ctx = context_scope(db, user, session.student_id, session.learning_context_id)
    known, skills = snapshot(db, ctx.student_id, m.now())
    q = db.get(m.Question, session.question_id) if session.question_id else None
    previous = (
        db.scalar(
            select(m.Attempt)
            .where(m.Attempt.student_id == ctx.student_id, m.Attempt.question_id == session.question_id)
            .order_by(m.Attempt.created_at.desc())
        )
        if q
        else None
    )
    names = (
        list(
            db.scalars(
                select(m.Knowledge.name).join(m.QuestionKnowledge).where(m.QuestionKnowledge.question_id == q.id)
            )
        )
        if q
        else []
    )
    context = {
        "grade": ctx.school_grade,
        "biology_level": ctx.biology_level,
        "competition_goal": ctx.competition_goal,
        "mastery": known,
        "competencies": skills,
        "question": q.stem if q else None,
        "student_answer": previous.answer if previous else None,
        "last_error": previous.error_type if previous else None,
        "task": row(db.get(m.Task, session.task_id)) if session.task_id else None,
        "knowledge_names": names,
        "explanation": q.explanation if q else None,
    }
    session.hint_level = min(4, session.hint_level + 1) if data.request_hint else session.hint_level
    try:
        response = await Gateway().tutor(context, data.message, session.hint_level)
    except GatewayError as exc:
        raise HTTPException(503, str(exc))
    session.messages = [
        *session.messages,
        {"role": "user", "content": data.message},
        {"role": "assistant", "content": response["message"]},
    ]
    db.add(
        m.LearningEvent(
            student_id=ctx.student_id,
            learning_context_id=ctx.id,
            question_id=session.question_id,
            task_id=session.task_id,
            event_type="HINT_REQUEST" if data.request_hint else "AI_DIALOG",
            payload={"session_id": session.id, "hint_level": session.hint_level, "mode": response["mode"]},
        )
    )
    return response


@router.post("/ai/questions/generate")
async def ai_generate(data: s.AIRequest, db: DB, user: Admin) -> dict:
    return await generate_content(db, user, "generate", data)


@router.post("/ai/questions/analyze")
async def ai_analyze(data: s.AIRequest, db: DB, user: Admin) -> dict:
    return await generate_content(db, user, "analyze", data)


@router.post("/ai/explain")
async def ai_explain(data: s.AIRequest, db: DB, user: Admin) -> dict:
    return await generate_content(db, user, "explain", data)


@router.post("/ai/diagnose-error")
async def ai_error(data: s.AIRequest, db: DB, user: Admin) -> dict:
    return await generate_content(db, user, "diagnose-error", data)


@router.get("/admin/review")
def review_queue(db: DB, user: Admin) -> dict:
    return {
        "questions": [
            question_view(db, q, reveal=True)
            for q in db.scalars(
                select(m.Question).where(m.Question.status.not_in(["PUBLISHED", "LESSON_ONLY"])).order_by(m.Question.source_question_no)
            )
        ],
        "ai_contents": [row(c) for c in db.scalars(select(m.AIContent).order_by(m.AIContent.created_at.desc()))],
    }


@router.patch("/admin/questions/{id}")
def question_edit(id: UUID, data: s.QuestionEdit, db: DB, user: Admin) -> dict:
    q = require(db, m.Question, id)
    if q.metadata_json.get("lesson_revision_id"):
        raise HTTPException(409, "课程检测题随内容版本发布，请在分层课程中修订")
    if q.metadata_json.get("original_format") == "STATEMENT_TRUE_FALSE":
        choices = {answer.split(":")[0]: answer.split(":")[-1] for answer in data.answer}
        if (
            len(data.answer) != len(data.options)
            or set(choices) != set(data.options)
            or not set(choices.values()) <= {"T", "F"}
        ):
            raise HTTPException(422, "逐项判断答案格式应为 A:T、B:F 等，且覆盖所有选项")
    elif not set(data.answer) <= set(data.options) or (
        q.question_type in {"SINGLE_CHOICE", "TRUE_FALSE"} and len(data.answer) != 1
    ):
        raise HTTPException(422, "答案必须来自选项，单选题只能有一个答案")
    for old in db.scalars(select(m.Option).where(m.Option.question_id == q.id)):
        db.delete(old)
    for label, text in data.options.items():
        db.add(m.Option(question_id=q.id, label=label, text=text))
    q.stem, q.answer, q.explanation, q.status = data.stem, data.answer, data.explanation, "REVIEW_REQUIRED"
    audit(db, user, "QUESTION_EDITED", question_id=q.id)
    db.flush()
    return question_view(db, q, reveal=True)


@router.post("/admin/questions/{id}/review")
def question_review(id: UUID, data: s.ReviewInput, db: DB, user: Admin) -> dict:
    q = require(db, m.Question, id)
    if q.metadata_json.get("lesson_revision_id"):
        raise HTTPException(409, "课程检测题随内容版本发布，请在分层课程中修订")
    if data.decision == "REVIEWED" and (not q.stem or not q.answer or not q.explanation):
        raise HTTPException(422, "题干、答案、解析不完整")
    if data.decision == "PUBLISHED" and q.status != "REVIEWED":
        raise HTTPException(409, "请先审核")
    q.status = data.decision
    audit(db, user, "QUESTION_REVIEW", question_id=q.id, decision=data.decision, note=data.note)
    return question_view(db, q, reveal=True)


@router.get("/admin/papers/{id}/source")
def paper_source(id: UUID, db: DB, user: Admin):
    from app.config import ROOT
    from fastapi.responses import FileResponse

    paper = require(db, m.Paper, id)
    root = ROOT / "seed"
    filename = paper.metadata_json.get("source_file")
    if not filename:
        raise HTTPException(404, "该题源没有附属 PDF")
    path = (root / filename).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise HTTPException(404, "题源文件不存在")
    return FileResponse(path, media_type="application/pdf", filename=path.name, content_disposition_type="inline")


@router.post("/admin/ai-contents/{id}/review")
def ai_review(id: UUID, data: s.ReviewInput, db: DB, user: Admin) -> dict:
    return review_content(db, user, id, data)


@router.get("/admin/audit")
def audit_logs(db: DB, user: Admin) -> list[dict]:
    return [row(a) for a in db.scalars(select(m.Audit).order_by(m.Audit.created_at.desc()).limit(200))]
