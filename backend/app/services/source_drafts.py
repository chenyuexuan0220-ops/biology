"""Extract uploaded teaching material into reviewable seed YAML drafts."""

from io import BytesIO
from pathlib import Path
import re
from zipfile import BadZipFile, ZipFile

from docx import Document
import pymupdf
import yaml

from app.services.knowledge_extraction import mapping_report, match_knowledge, split_sections


MAX_UPLOAD = 20 * 1024 * 1024
MAX_TEXT = 500_000
MAX_DOCX_EXPANDED = 60 * 1024 * 1024
QUESTION_START = re.compile(r"^\s*(?:第\s*)?(\d{1,3})\s*(?:题|[.．、）)])\s*(.+)$")
OPTION = re.compile(r"^\s*([A-H])\s*[.．、）)]\s*(.+)$")


def extract_text(filename: str, data: bytes) -> tuple[str, list[str]]:
    name = filename.lower()
    if len(data) > MAX_UPLOAD:
        raise ValueError("文件不能超过 20 MB")
    if name.endswith(".pdf"):
        if not data.startswith(b"%PDF"):
            raise ValueError("文件内容不是有效 PDF")
        try:
            with pymupdf.open(stream=data, filetype="pdf") as document:
                if document.page_count > 250:
                    raise ValueError("PDF 超过 250 页，请分批上传")
                pages = [page.get_text(sort=True) for page in document]
        except (pymupdf.FileDataError, pymupdf.EmptyFileError) as exc:
            raise ValueError("PDF 无法读取或已损坏") from exc
        lines = "\n".join(pages)
    elif name.endswith(".docx"):
        try:
            with ZipFile(BytesIO(data)) as archive:
                if sum(item.file_size for item in archive.infolist()) > MAX_DOCX_EXPANDED:
                    raise ValueError("Word 文件解压后过大")
            document = Document(BytesIO(data))
            lines = "\n".join(p.text for p in document.paragraphs)
            for table in document.tables:
                lines += "\n" + "\n".join("\t".join(cell.text for cell in row.cells) for row in table.rows)
        except (BadZipFile, KeyError) as exc:
            raise ValueError("Word 文件无法读取或已损坏") from exc
    elif name.endswith(".doc"):
        raise ValueError("旧版 .doc 暂不支持，请先另存为 .docx")
    else:
        raise ValueError("仅支持 PDF 和 .docx")
    if not lines.strip():
        raise ValueError("未提取到文字；扫描版 PDF 需要先进行 OCR")
    if len(lines) > MAX_TEXT:
        raise ValueError("提取文字超过 50 万字，请分批上传")
    return lines, ["图表、公式和跨页题干可能需要对照原件补全", "答案与知识映射需人工核对后发布"]


def textbook_draft(text: str, knowledge: list[dict], filename: str, ai_results: list[dict] | None = None) -> dict[str, str]:
    sections = split_sections(text)
    report = mapping_report(sections, knowledge, filename)
    if ai_results is not None:
        if len(ai_results) != len(sections):
            raise ValueError("AI 章节结果数量不一致")
        report["new_knowledge_candidates"] = []
        report["relation_candidates"] = []
        for index, (mapped, ai) in enumerate(zip(report["sections"], ai_results), 1):
            mapped["rule_candidates"] = mapped["candidates"]
            mapped["candidates"] = ai["existing"]
            mapped["method"] = "AI_ASSISTED"
            report["new_knowledge_candidates"].extend(
                {**concept, "section": index, "status": "REVIEW_REQUIRED"} for concept in ai["new_concepts"]
            )
            report["relation_candidates"].extend(
                {**relation, "source_sections": [index], "status": "REVIEW_REQUIRED"}
                for relation in ai["relations"]
            )
    resources = []
    source_name = Path(filename).stem[:40]
    for index, (section, mapped) in enumerate(zip(sections, report["sections"]), 1):
        for candidate in mapped["candidates"][:20 if ai_results is not None else 3]:
            resources.append({
                "knowledge_code": candidate["code"],
                "title": f"{source_name} · {index} · {section['title'][:60]} · {candidate['code']}"[:200],
                "level": 1, "min_grade": 0, "max_grade": 20, "content": section["content"],
            })
    return {
        "resources.yaml": yaml.safe_dump(resources, allow_unicode=True, sort_keys=False),
        "knowledge_review.yaml": yaml.safe_dump(report, allow_unicode=True, sort_keys=False),
    }


def exam_blocks(text: str) -> list[tuple[int, list[str]]]:
    blocks: list[tuple[int, list[str]]] = []
    current: tuple[int, list[str]] | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        match = QUESTION_START.match(line)
        if match:
            if current:
                blocks.append(current)
            current = (int(match.group(1)), [match.group(2)])
        elif current:
            current[1].append(line)
    if current:
        blocks.append(current)
    if not blocks:
        raise ValueError("未识别到编号题目；请检查原件的题号格式")
    numbers = [number for number, _ in blocks]
    if len(numbers) != len(set(numbers)):
        raise ValueError("识别到重复题号，请检查页眉或跨页排版")
    return blocks


def exam_draft(text: str, code: str, title: str, filename: str, knowledge: list[dict],
               ai_results: list[dict] | None = None) -> dict[str, str]:
    blocks = exam_blocks(text)
    if ai_results is not None and len(ai_results) != len(blocks):
        raise ValueError("AI 题目结果数量不一致")
    files = {"paper.yaml": yaml.safe_dump({
        "code": code, "source_code": "uploaded_material", "source_name": "上传试卷",
        "title": title, "year": None, "metadata": {"expected_questions": len(blocks), "source_filename": filename},
    }, allow_unicode=True, sort_keys=False)}
    review = []
    for index, (number, lines) in enumerate(blocks):
        stem, options = [], {}
        for line in lines:
            option = OPTION.match(line)
            if option:
                options[option.group(1)] = option.group(2)
            elif options:
                last = next(reversed(options))
                options[last] += " " + line
            else:
                stem.append(line)
        rule_candidates = match_knowledge("", "\n".join(lines), knowledge)
        candidates = ai_results[index]["existing"] if ai_results is not None else rule_candidates
        item = {"question_no": number, "candidates": candidates, "review_required": True}
        if ai_results is not None:
            item.update({"method": "AI_ASSISTED", "rule_candidates": rule_candidates,
                         "new_concepts": ai_results[index]["new_concepts"],
                         "relation_candidates": ai_results[index]["relations"]})
        review.append(item)
        question = {
            "source_question_no": number,
            "question_type": "SINGLE_CHOICE" if len(options) >= 2 else "COMPREHENSIVE",
            "stem": "\n".join(stem) or None,
            "options": options,
            "answer": None,
            "explanation": None,
            "knowledge_points": [item["code"] for item in candidates[:3]],
            "prerequisites": [],
            "competencies": ["KNOWLEDGE_UNDERSTANDING"],
            "difficulty": {"competition": 1, "learning": 1},
            "status": "REVIEW_REQUIRED",
            "metadata": {"source_filename": filename, "raw_text": "\n".join(lines), "review_notes": ["自动提取草稿，须核对题干、选项、题型、知识映射、答案和解析"]},
        }
        files[f"q{number:03d}.yaml"] = yaml.safe_dump(question, allow_unicode=True, sort_keys=False)
    files["knowledge_review.yaml"] = yaml.safe_dump({"questions": review}, allow_unicode=True, sort_keys=False)
    return files
