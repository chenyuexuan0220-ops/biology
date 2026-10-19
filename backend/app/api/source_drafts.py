from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models as m
from app.ai.gateway import GatewayError
from app.ai.knowledge_graph import analyze_sections
from app.config import settings
from app.db import get_db
from app.security import admin
from app.services.knowledge_extraction import split_sections
from app.services.source_drafts import MAX_UPLOAD, exam_blocks, exam_draft, extract_text, textbook_draft


router = APIRouter(prefix="/api/v1/admin/source-drafts", tags=["source-drafts"])


@router.post("")
async def create_draft(
    file: Annotated[UploadFile, File()],
    kind: Annotated[Literal["textbook", "exam"], Form()],
    title: Annotated[str, Form()],
    code: Annotated[str, Form()],
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[m.User, Depends(admin)],
    ai_enhance: Annotated[bool, Form()] = False,
) -> dict:
    if kind == "exam" and (not code or not code.replace("_", "").isalnum() or len(code) > 80):
        raise HTTPException(422, "试卷编码仅可包含字母、数字和下划线")
    if not title.strip() or len(title) > 200:
        raise HTTPException(422, "请输入 1-200 字的标题")
    if ai_enhance and (not settings.llm_api_key or not settings.llm_model):
        raise HTTPException(422, "请先在 .env 配置 LLM_API_KEY 和 LLM_MODEL，并重启后端")
    data = await file.read(MAX_UPLOAD + 1)
    knowledge = [{"code": item.code, "name": item.name} for item in db.scalars(select(m.Knowledge))]
    existing_edges = []
    if ai_enhance:
        codes = {item.id: item.code for item in db.scalars(select(m.Knowledge))}
        existing_edges = [(codes[edge.source_knowledge_id], codes[edge.target_knowledge_id])
                          for edge in db.scalars(select(m.Edge).where(m.Edge.relation_type == "PREREQUISITE_OF"))]
    try:
        extracted, warnings = extract_text(file.filename or "", data)
        sections = split_sections(extracted) if kind == "textbook" else [
            {"title": f"第{number}题", "content": "\n".join(lines)} for number, lines in exam_blocks(extracted)
        ]
        ai_results = await analyze_sections(sections, knowledge, existing_edges=existing_edges) if ai_enhance else None
        files = textbook_draft(extracted, knowledge, file.filename or "", ai_results) if kind == "textbook" else (
            exam_draft(extracted, code, title, file.filename or "", knowledge, ai_results)
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except GatewayError as exc:
        raise HTTPException(502, str(exc)) from exc
    warnings.append("知识匹配和关系均为待审核建议；未匹配内容不会自动进入知识图谱")
    if ai_enhance:
        warnings.append("AI 识别已使用配置的模型服务处理教材或试题文本")
    return {"kind": kind, "title": title, "files": files, "warnings": warnings,
            "characters": len(extracted), "file_count": len(files), "ai_assisted": ai_enhance}
