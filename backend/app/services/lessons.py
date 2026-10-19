"""Versioned teaching content and evidence-backed, tier-specific unit progression."""

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, func
from fastapi import HTTPException
from app import models as m
from app.schemas import AttemptInput
from app.schemas_lessons import LessonDocument
from app.security import scope, context_scope, task_scope
from app.services.common import require, row, audit, active_context, calculation_time
from app.services.learning import question_view, answer_question
from app.services.seed import stable

TIER_RANK = {"INTRO": 0, "APPLICATION": 1, "COMPETITION": 2}


def validate_document(db, lesson, document):
    document = LessonDocument.model_validate(document)
    codes = set(db.scalars(select(m.Knowledge.code)))
    skills = set(db.scalars(select(m.Competency.code)))
    if not set(document.prerequisites) <= codes:
        raise HTTPException(422, "课文引用了未知前置知识")
    if any(q.competency_code not in skills for q in document.checks):
        raise HTTPException(422, "检测题引用了未知能力")
    own = db.get(m.Knowledge, lesson.knowledge_id)
    if own.code in document.prerequisites:
        raise HTTPException(422, "不能将本知识点作为自己的前置知识")
    graph_parents = set(
        db.scalars(
            select(m.Knowledge.code)
            .join(m.Edge, m.Edge.source_knowledge_id == m.Knowledge.id)
            .where(m.Edge.target_knowledge_id == lesson.knowledge_id, m.Edge.relation_type == "PREREQUISITE_OF")
        )
    )
    if not graph_parents <= set(document.prerequisites):
        raise HTTPException(422, "课程必须保留知识图谱要求的前置关系")
    return document


def revisions(db, at):
    rows = db.scalars(select(m.LessonRevision).where(m.LessonRevision.published_at <= at)
        .order_by(m.LessonRevision.version)).all()
    # Publication/withdrawal is time-versioned in audit, so later moderation
    # cannot change historical catalog or plan previews.
    decisions = {}
    for event in db.scalars(select(m.Audit).where(m.Audit.action == "LESSON_CONTENT_REVIEW",
            m.Audit.created_at <= at).order_by(m.Audit.created_at)):
        decisions[event.details["revision_id"]] = event.details["decision"]
    return {r.lesson_id: r for r in rows if decisions.get(r.id) == "PUBLISHED"}


def progress(db, sid, at):
    runs = db.scalars(
        select(m.LessonRun)
        .where(m.LessonRun.student_id == sid, m.LessonRun.completed_at <= at)
        .order_by(m.LessonRun.completed_at)
    ).all()
    latest = {}
    for run in runs:
        revision = db.get(m.LessonRevision, run.revision_id)
        lesson = db.get(m.Lesson, revision.lesson_id)
        latest[(lesson.knowledge_id, lesson.tier)] = run
        for code in (run.result or {}).get("prerequisite_gaps", []):
            kid = db.scalar(select(m.Knowledge.id).where(m.Knowledge.code == code))
            if kid:
                latest[(kid, lesson.tier)] = run
    return latest


def passed(latest, kid, tier):
    # A later failure at the selected tier withdraws that tier's readiness.
    relevant = [(key, run) for key, run in latest.items() if key[0] == kid and TIER_RANK[key[1]] >= TIER_RANK[tier]]
    if not relevant:
        return False
    _, run = max(relevant, key=lambda item: item[1].completed_at)
    return bool(run.result and run.result["passed"])


def missing_prerequisites(db, lesson, revision, latest):
    nodes = db.scalars(select(m.Knowledge).where(m.Knowledge.code.in_(revision.document["prerequisites"]))).all()
    return [
        {"id": node.id, "code": node.code, "name": node.name}
        for node in nodes
        if not passed(latest, node.id, lesson.tier)
    ]


def catalog(db, sid, as_of=None):
    at = calculation_time(as_of)
    ctx = active_context(db, sid, at if as_of else None)
    level = int(ctx.biology_level[1])
    published = revisions(db, at)
    latest = progress(db, sid, at)
    lessons = db.scalars(
        select(m.Lesson)
        .where(m.Lesson.min_level <= level, m.Lesson.max_level >= level)
        .order_by(m.Lesson.unit_code, m.Lesson.sequence)
    ).all()
    items = []
    for lesson in lessons:
        rev = published.get(lesson.id)
        last = latest.get((lesson.knowledge_id, lesson.tier))
        missing = missing_prerequisites(db, lesson, rev, latest) if rev else []
        state = (
            "UNPUBLISHED"
            if not rev
            else "LOCKED"
            if missing
            else "PASSED"
            if passed(latest, lesson.knowledge_id, lesson.tier)
            else "REINFORCE"
            if last
            else "READY"
        )
        active_run = db.scalar(
            select(m.LessonRun)
            .join(m.LessonRevision)
            .where(
                m.LessonRun.student_id == sid,
                m.LessonRun.learning_context_id == ctx.id,
                m.LessonRun.status == "IN_PROGRESS",
                m.LessonRun.created_at <= at,
                m.LessonRevision.status == "PUBLISHED",
                m.LessonRevision.lesson_id == lesson.id,
            )
            .order_by(m.LessonRun.created_at.desc())
        )
        items.append(
            {
                **row(lesson),
                "name": db.get(m.Knowledge, lesson.knowledge_id).name,
                "state": state,
                "revision_id": rev.id if rev else None,
                "title": rev.document["title"] if rev else db.get(m.Knowledge, lesson.knowledge_id).name,
                "summary": rev.document["summary"] if rev else "课程内容已准备，等待管理员审核发布。",
                "estimated_minutes": rev.document["estimated_minutes"] if rev else None,
                "missing_prerequisites": missing,
                "last_result": last.result if last else None,
                "active_run_id": active_run.id if active_run and rev and not as_of else None,
            }
        )
    return {
        "learning_context_id": ctx.id,
        "biology_level": ctx.biology_level,
        "lessons": items,
        "note": "单元达标用于本单元学习顺序；长期掌握度和高级知识推荐仍使用原有证据门槛。",
    }


def public_document(document, grade):
    result = {key: value for key, value in document.items() if key not in {"checks", "adaptations"}}
    result["grade_guidance"] = document["adaptations"]["junior" if grade < 10 else "senior"]
    return result


def run_view(db, user, run):
    scope(db, user, run.student_id)
    rev = require(db, m.LessonRevision, run.revision_id)
    if rev.status != "PUBLISHED":
        raise HTTPException(409, "此课版本已撤回，请等待内容复核")
    ctx = db.get(m.LearningContext, run.learning_context_id)
    lesson = db.get(m.Lesson, rev.lesson_id)
    return {
        **row(run),
        "lesson": row(lesson),
        "document": public_document(rev.document, ctx.school_grade),
        "questions": [question_view(db, db.get(m.Question, qid)) for qid in run.question_ids],
    }


def start(db, user, sid, lesson_id, data):
    ctx = context_scope(db, user, sid, data.learning_context_id)
    db.scalar(select(m.Student).where(m.Student.id == sid).with_for_update())
    lesson = require(db, m.Lesson, lesson_id)
    level = int(ctx.biology_level[1])
    if not lesson.min_level <= level <= lesson.max_level:
        raise HTTPException(409, "请使用与当前实际能力对应的课程版本")
    rev = revisions(db, m.now()).get(lesson.id)
    if not rev:
        raise HTTPException(409, "课程尚未审核发布")
    missing = missing_prerequisites(db, lesson, rev, progress(db, sid, m.now()))
    if missing:
        raise HTTPException(409, "请先完成同深度的前置课程检测：" + "、".join(x["name"] for x in missing))
    task = task_scope(db, sid, data.task_id, ctx.id)
    if task and task.reason.get("lesson_id") != lesson.id:
        raise HTTPException(422, "课程不属于该任务")
    # Resume rather than allocating duplicate assessment runs on retries or reload.
    old = db.scalar(
        select(m.LessonRun)
        .join(m.LessonRevision)
        .where(
            m.LessonRun.student_id == sid,
            m.LessonRun.learning_context_id == ctx.id,
            m.LessonRevision.lesson_id == lesson.id,
            m.LessonRevision.status == "PUBLISHED",
            m.LessonRun.status == "IN_PROGRESS",
        )
        .order_by(m.LessonRun.created_at.desc())
    )
    if old:
        if task and not old.task_id:
            old.task_id = task.id
        return run_view(db, user, old)
    qids = [stable("lesson-question", f"{rev.id}:{q['id']}") for q in rev.document["checks"]]
    run = m.LessonRun(
        student_id=sid,
        learning_context_id=ctx.id,
        revision_id=rev.id,
        task_id=task.id if task else None,
        mode=data.mode,
        question_ids=qids,
    )
    db.add(run)
    db.flush()
    db.add(
        m.LearningEvent(
            student_id=sid,
            learning_context_id=ctx.id,
            task_id=run.task_id,
            event_type="LEARNING_START",
            payload={"lesson_run_id": run.id, "revision_id": rev.id, "mode": data.mode},
        )
    )
    return run_view(db, user, run)


def answer(db, user, run_id, data):
    run = require(db, m.LessonRun, run_id)
    context_scope(db, user, run.student_id, run.learning_context_id)
    db.scalar(select(m.Student).where(m.Student.id == run.student_id).with_for_update())
    db.refresh(run)
    rev = require(db, m.LessonRevision, run.revision_id)
    if rev.status != "PUBLISHED":
        raise HTTPException(409, "课程版本已撤回")
    qid = str(data.question_id)
    if qid not in run.question_ids:
        raise HTTPException(422, "该检测题不属于此课时")
    previous = run.answers.get(qid)
    if previous and previous["event_id"] != str(data.event_id):
        raise HTTPException(409, "本轮检测已回答此题，请在完成后开始新一轮巩固")
    if run.status != "IN_PROGRESS" and not previous:
        raise HTTPException(409, "本轮检测已结束")
    payload = AttemptInput(
        student_id=run.student_id,
        learning_context_id=run.learning_context_id,
        event_id=data.event_id,
        answer=data.answer,
        confidence=data.confidence,
        time_seconds=data.time_seconds,
    )
    result = answer_question(db, user, qid, payload, lesson_run=run)
    run.answers = {
        **run.answers,
        qid: {
            "event_id": str(data.event_id),
            "answer": data.answer,
            "correct": result["is_correct"],
            "feedback": jsonable_encoder(result),
        },
    }
    return result


def finish(db, user, run_id):
    run = require(db, m.LessonRun, run_id)
    context_scope(db, user, run.student_id, run.learning_context_id)
    db.scalar(select(m.Student).where(m.Student.id == run.student_id).with_for_update())
    db.refresh(run)
    if run.result:
        return run.result
    rev = require(db, m.LessonRevision, run.revision_id)
    if rev.status != "PUBLISHED":
        raise HTTPException(409, "课程版本已撤回")
    if set(run.answers) != set(run.question_ids):
        raise HTTPException(409, "请完成全部检测题")
    checks = rev.document["checks"]
    failed = [q for q, qid in zip(checks, run.question_ids) if not run.answers[qid]["correct"]]
    ratio = (len(checks) - len(failed)) / len(checks)
    prior_gaps = sorted({q["prerequisite_code"] for q in failed if q.get("prerequisite_code")})
    is_passed = ratio >= rev.document["pass_ratio"] and not prior_gaps
    lesson = db.get(m.Lesson, rev.lesson_id)
    run.result = {
        "run_id": run.id,
        "accuracy": ratio,
        "passed": is_passed,
        "threshold": rev.document["pass_ratio"],
        "prerequisite_gaps": prior_gaps,
        "revisit_sections": list(dict.fromkeys(q["revisit_section"] for q in failed)),
        "message": "本层次检测达标，可以继续下一课。"
        if is_passed
        else "先补齐前置概念，再回到本课。"
        if prior_gaps
        else "先回看错题对应章节，再做一次巩固检测。",
        "mastery_note": "课时达标不等于长期掌握；本次作答已逐题写入知识与能力证据。",
    }
    run.status = "PASSED" if is_passed else "REINFORCE"
    run.completed_at = m.now()
    # A failed prerequisite probe invalidates unit readiness until that prerequisite is checked again.
    # We retain the source failure rather than manufacturing mastery corrections.
    if run.task_id:
        task = db.get(m.Task, run.task_id)
        if task and task.student_id == run.student_id:
            task.status = "DONE"
    db.add(
        m.LearningEvent(
            student_id=run.student_id,
            learning_context_id=run.learning_context_id,
            task_id=run.task_id,
            event_type="ASSESSMENT",
            payload={"lesson_run_id": run.id, "revision_id": rev.id, "result": run.result},
        )
    )
    db.flush()
    from app.planners.adaptive import recalculate

    plan = recalculate(db, run.student_id)
    run.result = {
        **run.result,
        "weekly_plan_id": plan["plan"]["id"],
        "next_tasks": [
            {"id": t["id"], "title": t["title"], "lesson_id": t["reason"].get("lesson_id")}
            for t in plan["tasks"]
            if t["reason"].get("lesson_id")
        ],
    }
    audit(db, user, "LESSON_ASSESSED", run.student_id, run_id=run.id, lesson_id=lesson.id, passed=is_passed)
    return run.result


def course_recommendation(db, sid, at):
    last = db.scalar(
        select(m.LessonRun)
        .where(m.LessonRun.student_id == sid, m.LessonRun.created_at <= at)
        .order_by(m.LessonRun.created_at.desc())
    )
    if not last:
        return None
    unit = db.get(m.Lesson, db.get(m.LessonRevision, last.revision_id).lesson_id).unit_code
    items = [item for item in catalog(db, sid, at)["lessons"] if item["unit_code"] == unit]
    completed = db.scalar(
        select(m.LessonRun)
        .where(m.LessonRun.student_id == sid, m.LessonRun.completed_at <= at)
        .order_by(m.LessonRun.completed_at.desc())
    )
    target = None
    if completed and completed.result.get("prerequisite_gaps"):
        for code in completed.result["prerequisite_gaps"]:
            kid = db.scalar(select(m.Knowledge.id).where(m.Knowledge.code == code))
            candidate = next(
                (
                    item
                    for item in items
                    if item["knowledge_id"] == kid and item["state"] in {"PASSED", "REINFORCE", "READY"}
                ),
                None,
            )
            if candidate:
                target = candidate
                break
    if not target:
        target = next((item for item in items if item["state"] in {"REINFORCE", "READY"}), None)
    if not target:
        return None
    return {
        "knowledge_id": target["knowledge_id"],
        "title": target["title"],
        "description": target["summary"],
        "task_type": "LEARN",
        "question_ids": [],
        "priority": 1.0,
        "estimated_minutes": target["estimated_minutes"],
        "reason": {
            "lesson_id": target["id"],
            "revision_id": target["revision_id"],
            "primary_reason": "根据本单元检测安排前置补习或下一课",
            "knowledge_gap": 1 - (target["last_result"] or {}).get("accuracy", 0),
            "prerequisite_reason": "按本层次前置检测结果安排",
            "competition_reason": "课程深度由实际生物能力选择",
            "competency_reason": "检测同时记录知识和推理能力",
            "why_now": "完成上一轮检测后立即调整；长期掌握度独立累计",
            "unit_progression": True,
        },
    }


def review(db, user, revision_id, data):
    rev = require(db, m.LessonRevision, revision_id)
    db.scalar(select(m.LessonRevision).where(m.LessonRevision.id == rev.id).with_for_update())
    db.refresh(rev)
    lesson = db.get(m.Lesson, rev.lesson_id)
    if rev.status in {"PUBLISHED", "ARCHIVED"} and data.decision != "ARCHIVED":
        raise HTTPException(409, "已发布或归档版本不可重写；请创建修订版")
    document = validate_document(db, lesson, rev.document)
    if data.decision == "PUBLISHED":
        if rev.status != "REVIEWED" or not rev.reviewer_id:
            raise HTTPException(409, "必须先完成教师内容审核，再发布")
        source = db.scalar(select(m.QuestionSource).where(m.QuestionSource.code == "LESSON_CHECKS"))
        if not source:
            source = m.QuestionSource(code="LESSON_CHECKS", name="分层课程随堂检测（原创）")
            db.add(source)
            db.flush()
        paper = m.Paper(code=f"lesson:{rev.id}", title=document.title, source_id=source.id, year=None)
        db.add(paper)
        db.flush()
        for index, check in enumerate(document.checks, 1):
            kid = (
                db.scalar(select(m.Knowledge.id).where(m.Knowledge.code == check.prerequisite_code))
                if check.prerequisite_code
                else lesson.knowledge_id
            )
            q = m.Question(
                id=stable("lesson-question", f"{rev.id}:{check.id}"),
                paper_id=paper.id,
                source_question_no=index,
                question_type="SINGLE_CHOICE",
                stem=check.stem,
                answer=[check.answer],
                explanation=check.explanation,
                learning_difficulty=lesson.min_level,
                competition_difficulty=TIER_RANK[lesson.tier] * 2,
                status="LESSON_ONLY",
                metadata_json={
                    "lesson_revision_id": rev.id,
                    "cognitive_level": check.cognitive_level,
                    "evidence_kind": check.evidence_kind,
                },
            )
            db.add(q)
            db.flush()
            for label, text in check.options.items():
                db.add(m.Option(question_id=q.id, label=label, text=text))
            db.add(m.QuestionKnowledge(question_id=q.id, knowledge_id=kid))
            db.add(
                m.QuestionCompetency(
                    question_id=q.id,
                    competency_id=db.scalar(select(m.Competency.id).where(m.Competency.code == check.competency_code)),
                )
            )
        rev.published_at = m.now()
    rev.status = data.decision
    rev.reviewer_id = user.id
    audit(db, user, "LESSON_CONTENT_REVIEW", revision_id=rev.id, decision=data.decision, note=data.note)
    db.flush()
    return row(rev)


def revise(db, user, revision_id, data):
    original = require(db, m.LessonRevision, revision_id)
    lesson = db.get(m.Lesson, original.lesson_id)
    db.scalar(select(m.Lesson).where(m.Lesson.id == lesson.id).with_for_update())
    document = validate_document(db, lesson, data.document)
    version = db.scalar(select(func.max(m.LessonRevision.version)).where(m.LessonRevision.lesson_id == lesson.id)) + 1
    rev = m.LessonRevision(lesson_id=lesson.id, version=version, document=document.model_dump())
    db.add(rev)
    db.flush()
    audit(db, user, "LESSON_REVISION_CREATED", revision_id=rev.id, previous_id=original.id)
    return row(rev)
