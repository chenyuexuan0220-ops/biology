from sqlalchemy import select
from fastapi import HTTPException
from app.models import AIContent, Question, QuestionKnowledge, Knowledge, Option, Paper, QuestionSource, Variant
from app.services.common import require, audit, row
from app.services.learning import question_view
from app.ai.gateway import Gateway, GatewayError, validate_question


async def generate_content(db, user, purpose, data):
    nodes = db.scalars(select(Knowledge)).all()
    q = require(db, Question, data.question_id) if data.question_id else None
    allowed = [k.id for k in nodes]
    if not set(map(str, data.knowledge_ids)) <= set(allowed):
        raise HTTPException(422, "知识点不存在")
    request = data.model_dump(mode="json")
    context = {
        "request": request,
        "question": question_view(db, q, reveal=True) if q else None,
        "allowed_knowledge_ids": allowed,
        "knowledge": [{"id": k.id, "name": k.name} for k in nodes],
    }
    try:
        output = await Gateway().generate(purpose, context)
    except GatewayError as exc:
        raise HTTPException(503, str(exc))
    draft = AIContent(
        requested_by=user.id,
        purpose=purpose,
        content=output,
        trace={
            "prompt_version": "content.v1",
            "request": request,
            "provider": "openai-compatible",
            "source": "AI_GENERATED",
        },
    )
    db.add(draft)
    db.flush()
    audit(db, user, "AI_DRAFT_CREATED", content_id=draft.id)
    return row(draft)


def review_content(db, user, draft_id, data):
    draft = require(db, AIContent, draft_id)
    if data.decision == "PUBLISHED" and draft.status != "REVIEWED":
        raise HTTPException(409, "必须先由管理员审核，再发布")
    if data.decision == "REVIEWED" and draft.purpose == "generate":
        try:
            validate_question(
                draft.content,
                list(db.scalars(select(Knowledge.id))),
                int(draft.trace["request"]["target_biology_level"][1]),
            )
        except (GatewayError, ValueError) as exc:
            raise HTTPException(422, str(exc))
    if data.decision == "PUBLISHED":
        if draft.purpose != "generate":
            raise HTTPException(409, "分析结果只供审核，不作为题目发布")
        source = db.scalar(select(QuestionSource).where(QuestionSource.code == "AI_GENERATED"))
        if not source:
            source = QuestionSource(code="AI_GENERATED", name="AI 生成 · 人工审核")
            db.add(source)
            db.flush()
        paper = db.scalar(select(Paper).where(Paper.code == "AI_GENERATED"))
        if not paper:
            paper = Paper(code="AI_GENERATED", source_id=source.id, title="已审核 AI 练习", year=None)
            db.add(paper)
            db.flush()
        from sqlalchemy import func

        number = (
            db.scalar(select(func.max(Question.source_question_no)).where(Question.paper_id == paper.id)) or 0
        ) + 1
        content = draft.content
        q = Question(
            paper_id=paper.id,
            source_question_no=number,
            stem=content["stem"],
            answer=content["answer"],
            explanation=content["explanation"],
            question_type=content["question_type"],
            learning_difficulty=content["learning_difficulty"],
            competition_difficulty=content["competition_difficulty"],
            status="PUBLISHED",
            metadata_json={"ai_content_id": draft.id, "reviewer_id": user.id},
        )
        db.add(q)
        db.flush()
        for label, value in content["options"].items():
            db.add(Option(question_id=q.id, label=label, text=value))
        for kid in content["knowledge_ids"]:
            db.add(QuestionKnowledge(question_id=q.id, knowledge_id=kid))
        parent = draft.trace["request"].get("question_id")
        if parent:
            db.add(
                Variant(
                    parent_question_id=parent,
                    content={**content, **draft.trace["request"], "published_question_id": q.id},
                    status="PUBLISHED",
                )
            )
        draft.trace = {**draft.trace, "published_question_id": q.id}
    draft.status = data.decision
    draft.reviewer_id = user.id
    audit(db, user, "AI_CONTENT_REVIEW", content_id=draft.id, decision=data.decision, note=data.note)
    return row(draft)
