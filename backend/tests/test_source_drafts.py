from io import BytesIO

from docx import Document
import pymupdf
import yaml
from sqlalchemy import select

from app.models import User
from app.services.source_drafts import exam_draft, extract_text, textbook_draft
from app.services.knowledge_extraction import mapping_report, split_sections
from conftest import register


def test_extract_pdf_and_word_into_seed_shapes():
    knowledge = [{"code": "BIO.CELL.001", "name": "Cells"}, {"code": "BIO.CELL.004", "name": "Membrane"}]
    pdf = pymupdf.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "1. Cell membrane?\nA. Membrane\nB. Nucleus")
    text, _ = extract_text("exam.pdf", pdf.tobytes())
    files = exam_draft(text, "sample_2024", "Sample exam", "exam.pdf", knowledge)
    question = yaml.safe_load(files["q001.yaml"])
    assert question["options"] == {"A": "Membrane", "B": "Nucleus"}
    assert question["answer"] is None
    assert question["status"] == "REVIEW_REQUIRED"
    assert question["knowledge_points"] == ["BIO.CELL.004"]

    document = Document()
    document.add_paragraph("Chapter 1 Cells")
    document.add_paragraph("Cells have membranes.")
    buffer = BytesIO()
    document.save(buffer)
    text, _ = extract_text("book.docx", buffer.getvalue())
    files = textbook_draft(text, knowledge, "book.docx")
    resources = yaml.safe_load(files["resources.yaml"])
    assert resources[0]["knowledge_code"] == "BIO.CELL.001"
    assert "membranes" in resources[0]["content"]
    assert yaml.safe_load(files["knowledge_review.yaml"])["sections"][0]["review_required"]


def test_textbook_maps_sections_separately_and_proposes_only_related_edges():
    knowledge = [
        {"code": "BIO.CELL.001", "name": "细胞"},
        {"code": "BIO.CELL.004", "name": "细胞膜"},
        {"code": "BIO.CELL.007", "name": "线粒体"},
    ]
    text = "第1章 细胞膜\n细胞膜控制物质进出细胞。\n第2章 线粒体\n线粒体参与能量转换。\n第3章 未收录概念\n这是一段新内容。"
    sections = split_sections(text)
    assert len(sections) == 3
    files = textbook_draft(text, knowledge, "sample.docx")
    resources = yaml.safe_load(files["resources.yaml"])
    assert {item["knowledge_code"] for item in resources} >= {"BIO.CELL.004", "BIO.CELL.007"}
    assert len({item["title"] for item in resources}) == len(resources)
    review = yaml.safe_load(files["knowledge_review.yaml"])
    assert review["new_knowledge_candidates"][0]["name"] == "未收录概念"
    assert all(item["relation_type"] == "RELATED_TO" for item in review["relation_candidates"])
    assert mapping_report(sections, knowledge, "sample.docx") == review


def test_source_upload_requires_admin(env):
    client, _ = env
    headers = register(client)
    response = client.post(
        "/api/v1/admin/source-drafts",
        headers=headers,
        data={"kind": "exam", "title": "Sample", "code": "sample_2024"},
        files={"file": ("exam.pdf", b"%PDF-invalid", "application/pdf")},
    )
    assert response.status_code == 403


def test_admin_upload_returns_section_mappings(env):
    client, factory = env
    headers = register(client, "editor@example.com")
    with factory.begin() as db:
        db.scalar(select(User).where(User.email == "editor@example.com")).is_admin = True
    document = Document()
    document.add_paragraph("第1章 细胞膜")
    document.add_paragraph("细胞膜参与物质交换。")
    document.add_paragraph("第2章 线粒体")
    document.add_paragraph("线粒体参与能量转换。")
    content = BytesIO()
    document.save(content)
    response = client.post(
        "/api/v1/admin/source-drafts",
        headers=headers,
        data={"kind": "textbook", "title": "测试教材", "code": "textbook"},
        files={"file": ("biology.docx", content.getvalue(),
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert response.status_code == 200, response.text
    files = response.json()["files"]
    resources = yaml.safe_load(files["resources.yaml"])
    assert {item["knowledge_code"] for item in resources} >= {"BIO.CELL.004", "BIO.CELL.007"}
    assert len(yaml.safe_load(files["knowledge_review.yaml"])["sections"]) == 2


def test_ai_upload_requires_model_configuration(env):
    client, factory = env
    headers = register(client, "ai-editor@example.com")
    with factory.begin() as db:
        db.scalar(select(User).where(User.email == "ai-editor@example.com")).is_admin = True
    response = client.post(
        "/api/v1/admin/source-drafts",
        headers=headers,
        data={"kind": "textbook", "title": "测试教材", "code": "textbook", "ai_enhance": "true"},
        files={"file": ("biology.pdf", b"%PDF-invalid", "application/pdf")},
    )
    assert response.status_code == 422
    assert "LLM_API_KEY" in response.json()["detail"]
