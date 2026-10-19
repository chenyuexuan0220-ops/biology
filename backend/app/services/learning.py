from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, func
from app.models import (
    Question,
    Option,
    QuestionKnowledge,
    QuestionCompetency,
    Attempt,
    LearningEvent,
    Student,
    TutorSession,
    Diagnostic,
    Knowledge,
    LearningContext,
)
from app.security import context_scope, task_scope
from app.services.common import require, row
from app.services.mastery import record_question_evidence, snapshot


def question_view(db, q, reveal=False):
    result = row(q)
    result["answer_format"] = q.metadata_json.get("original_format", "CHOICE")
    result["options"] = [
        {"label": o.label, "text": o.text}
        for o in db.scalars(select(Option).where(Option.question_id == q.id).order_by(Option.label))
    ]
    result["knowledge_ids"] = list(
        db.scalars(select(QuestionKnowledge.knowledge_id).where(QuestionKnowledge.question_id == q.id))
    )
    if not reveal:
        for key in ("answer", "explanation", "metadata_json"):
            result.pop(key, None)
    return result


def answer_question(db, user, question_id, data, lesson_run=None):
    sid = str(data.student_id)
    ctx = context_scope(db, user, sid, data.learning_context_id)
    # Serialize writes for each student in PostgreSQL; idempotency keys are also unique at DB level.
    db.scalar(select(Student).where(Student.id == sid).with_for_update())
    q = require(db, Question, question_id)
    lesson_allowed = (
        lesson_run is not None
        and q.status == "LESSON_ONLY"
        and q.id in lesson_run.question_ids
        and q.metadata_json.get("lesson_revision_id") == lesson_run.revision_id
    )
    if (q.status != "PUBLISHED" and not lesson_allowed) or not q.answer:
        raise HTTPException(409, "题目尚未审核发布或缺少答案")
    task = task_scope(db, sid, data.task_id, ctx.id)
    if task and q.id not in task.question_ids:
        raise HTTPException(422, "题目不属于该任务")
    old = db.get(LearningEvent, str(data.event_id))
    if old:
        attempt = db.scalar(select(Attempt).where(Attempt.event_id == old.id))
        if (
            old.student_id != sid
            or old.payload.get("lesson_run_id") != (lesson_run.id if lesson_run else None)
            or old.question_id != q.id
            or old.learning_context_id != ctx.id
            or not attempt
            or attempt.answer != data.answer
            or attempt.confidence != data.confidence
            or attempt.task_id != (str(data.task_id) if data.task_id else None)
        ):
            raise HTTPException(409, "event_id 已用于另一条学习证据")
        return {**row(attempt), "explanation": q.explanation, "correct_answer": q.answer, "replayed": True}
    statement_format = q.metadata_json.get("original_format") == "STATEMENT_TRUE_FALSE"
    if not statement_format and q.question_type not in {"SINGLE_CHOICE", "MULTIPLE_CHOICE", "TRUE_FALSE", "FILL_BLANK"}:
        raise HTTPException(409, "主观题需教师审核评分")
    labels = set(db.scalars(select(Option.label).where(Option.question_id == q.id)))
    if statement_format:
        choices = {answer.split(":")[0]: answer.split(":")[-1] for answer in data.answer}
        if len(data.answer) != len(labels) or set(choices) != labels or not set(choices.values()) <= {"T", "F"}:
            raise HTTPException(422, "请对每个陈述分别选择 T 或 F")
    elif q.question_type != "FILL_BLANK" and (not data.answer or not set(data.answer) <= labels):
        raise HTTPException(422, "请选择有效选项")
    if q.question_type in {"SINGLE_CHOICE", "TRUE_FALSE"} and len(data.answer) != 1:
        raise HTTPException(422, "单选题只能选择一个答案")
    correct = sorted(set(data.answer)) == sorted(set(q.answer))
    hints = (
        db.scalar(
            select(func.max(TutorSession.hint_level)).where(
                TutorSession.student_id == sid,
                TutorSession.question_id == q.id,
                TutorSession.learning_context_id == ctx.id,
            )
        )
        or 0
    )
    event = LearningEvent(
        id=str(data.event_id),
        student_id=sid,
        learning_context_id=ctx.id,
        question_id=q.id,
        task_id=task.id if task else None,
        event_type="QUESTION_ANSWER",
        payload={"answer": data.answer, "correct": correct, **({"lesson_run_id": lesson_run.id} if lesson_run else {})},
        duration_seconds=data.time_seconds,
    )
    db.add(event)
    db.flush()
    links = db.scalars(
        select(QuestionKnowledge).where(
            QuestionKnowledge.question_id == q.id, QuestionKnowledge.relation_type == "CORE"
        )
    ).all()
    skills = db.scalars(select(QuestionCompetency).where(QuestionCompetency.question_id == q.id)).all()
    attempt = Attempt(
        student_id=sid,
        question_id=q.id,
        task_id=event.task_id,
        event_id=event.id,
        answer=data.answer,
        is_correct=correct,
        confidence=data.confidence,
        hint_count=hints,
        time_seconds=data.time_seconds,
        attempt_no=(
            db.scalar(
                select(func.count()).select_from(Attempt).where(Attempt.student_id == sid, Attempt.question_id == q.id)
            )
            or 0
        )
        + 1,
        error_type=None if correct else ("CONCEPT_MISUNDERSTANDING" if data.confidence >= 0.7 else "KNOWLEDGE_GAP"),
    )
    db.add(attempt)
    record_question_evidence(db, event, q, correct, data.confidence, hints, links, skills)
    if task:
        task.status = "DONE"
    db.flush()
    return {
        **row(attempt),
        "explanation": q.explanation,
        "correct_answer": q.answer,
        "replayed": False,
        "correct_statements": len(set(data.answer) & set(q.answer)) if statement_format else None,
        "error_note": None if correct else "基于答案与自报信心的初步分类，需结合推理过程确认",
    }


def start_diagnostic(db, user, data):
    ctx = context_scope(db, user, data.student_id, data.learning_context_id)
    level = int(ctx.biology_level[1])
    questions = db.scalars(select(Question).where(Question.status == "PUBLISHED")).all()

    def distance(q):
        metadata = q.metadata_json
        grade = metadata.get("target_grade", ctx.school_grade)
        goal_match = ctx.competition_goal in metadata.get("goals", [])
        return (
            abs(q.learning_difficulty - level),
            abs(grade - ctx.school_grade),
            -int(goal_match),
            q.source_question_no,
        )

    questions.sort(key=distance)
    # Round-robin domains/skills so a diagnostic is not just one topic repeated.
    selected, covered = [], set()
    for q in questions:
        domain = q.metadata_json.get("diagnostic_domain", q.id)
        if domain not in covered:
            selected.append(q.id)
            covered.add(domain)
        if len(selected) >= 8:
            break
    if not selected:
        raise HTTPException(409, "暂无可用于诊断的已发布题目")
    diagnosis = Diagnostic(student_id=str(data.student_id), learning_context_id=ctx.id, question_ids=selected)
    db.add(diagnosis)
    db.flush()
    return {**row(diagnosis), "questions": [question_view(db, db.get(Question, q)) for q in selected]}


def finish_diagnostic(db, diagnosis):
    if diagnosis.result:
        return diagnosis.result
    if len(diagnosis.answers) != len(diagnosis.question_ids):
        raise HTTPException(409, "请完成全部诊断题")
    from app.models import now

    ctx = db.get(LearningContext, diagnosis.learning_context_id)
    knowledge, skills = snapshot(db, diagnosis.student_id, now())
    correct = sum(a["correct"] for a in diagnosis.answers.values())
    accuracy = correct / len(diagnosis.question_ids)
    from app.schemas import BiologyLevel

    level = int(ctx.biology_level[1])
    recommended = max(0, min(7, level + (1 if accuracy >= 0.85 else -1 if accuracy < 0.4 else 0)))
    gaps = [kid for kid, m in knowledge.items() if m["overall_score"] < 0.4]
    diagnosis.result = {
        "recommended_level": list(BiologyLevel)[recommended].value,
        "accuracy": accuracy,
        "knowledge_profile": list(knowledge.values()),
        "competency_profile": list(skills.values()),
        "knowledge_gaps": [{"id": kid, "name": db.get(Knowledge, kid).name} for kid in gaps],
        "prerequisite_gaps": gaps,
        "recommended_first_unit": db.get(Knowledge, gaps[0]).name if gaps else "拓展与迁移",
        "note": "短诊断用于初步定位，能力等级建议需结合持续学习证据；不会自动更改学习上下文。",
    }
    diagnosis.result = jsonable_encoder(diagnosis.result)
    diagnosis.status = "COMPLETED"
    return diagnosis.result
