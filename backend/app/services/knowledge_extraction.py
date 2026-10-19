"""Conservative, explainable candidate matching for uploaded materials."""

import re


HEADING = re.compile(
    r"^(?:第[一二三四五六七八九十百\d]+[章节]|\d+(?:\.\d+)*[.．、]?\s+|[一二三四五六七八九十]+[、.．])\s*(.{2,80})$"
)
TRIM_HEADING = re.compile(r"^(?:第[一二三四五六七八九十百\d]+[章节]|\d+(?:\.\d+)*[.．、]?|[一二三四五六七八九十]+[、.．])\s*")


def split_sections(text: str) -> list[dict]:
    """Split at visible chapter headings while retaining order and source text."""
    sections = []
    title, body = "导入内容", []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if HEADING.match(line):
            if body:
                sections.append({"title": title, "content": "\n".join(body)})
            title, body = line[:100], []
        else:
            body.append(line)
    if body:
        sections.append({"title": title, "content": "\n".join(body)})
    return sections


def match_knowledge(title: str, content: str, knowledge: list[dict], limit: int = 5) -> list[dict]:
    """Return exact-name matches with evidence; a mention is only a candidate."""
    heading = TRIM_HEADING.sub("", title).casefold()
    body = content.casefold()
    matches = []
    for node in knowledge:
        name = node["name"].strip().casefold()
        if len(name) < 2:
            continue
        in_heading = name in heading
        occurrences = len(re.findall(re.escape(name), body))
        if not in_heading and not occurrences:
            continue
        # A heading match is strong; repeated mentions are capped to avoid long-chapter bias.
        score = (5 if heading == name else 3 if in_heading else 0) + min(occurrences, 3)
        if score < 2:
            continue
        matches.append({
            "code": node["code"], "name": node["name"], "score": score,
            "evidence": "章节标题" if in_heading else f"正文出现 {occurrences} 次",
        })
    matches.sort(key=lambda item: (-item["score"], -len(item["name"]), item["code"]))
    return matches[:limit]


def mapping_report(sections: list[dict], knowledge: list[dict], source_filename: str) -> dict:
    mappings, unknown, edges = [], [], {}
    known_names = {node["name"].strip().casefold() for node in knowledge}
    for index, section in enumerate(sections, 1):
        candidates = match_knowledge(section["title"], section["content"], knowledge)
        mappings.append({
            "section": index, "title": section["title"], "source_filename": source_filename,
            "candidates": candidates, "review_required": True,
        })
        if not candidates:
            concept = TRIM_HEADING.sub("", section["title"]).strip()
            if concept and concept != "导入内容" and concept.casefold() not in known_names:
                unknown.append({
                    "section": index, "name": concept, "source_title": section["title"],
                    "description_draft": section["content"][:300],
                    "status": "REVIEW_REQUIRED", "note": "候选新知识点，需检查重复概念、领域、层级与前置关系",
                })
        # Co-occurrence supports RELATED_TO candidates, never prerequisite claims.
        codes = [item["code"] for item in candidates[:3]]
        for left in range(len(codes)):
            for right in range(left + 1, len(codes)):
                pair = tuple(sorted((codes[left], codes[right])))
                edges.setdefault(pair, []).append(index)
    proposals = [
        {"source": source, "target": target, "relation_type": "RELATED_TO",
         "source_sections": pages, "status": "REVIEW_REQUIRED"}
        for (source, target), pages in sorted(edges.items())
    ]
    return {"sections": mappings, "new_knowledge_candidates": unknown, "relation_candidates": proposals}
