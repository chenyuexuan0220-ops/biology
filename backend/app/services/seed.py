"""Idempotent importer. Existing reviewed content is never overwritten by seed replay."""

from app.config import ROOT as PROJECT_ROOT
import uuid
import yaml
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select, func
from app import models as m
from app.services.graph import validate_dag

ROOT = PROJECT_ROOT / "seed"


def stable(namespace, key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"biology:{namespace}:{key}"))


def read(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def ensure(db, model, identifier, **data):
    obj = db.get(model, identifier)
    if not obj:
        obj = model(id=identifier, **data)
        db.add(obj)
        db.flush()
    return obj


class QuestionSeed(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_question_no: int = Field(gt=0)
    question_type: str
    stem: str | None
    options: dict[str, str] = Field(default_factory=dict)
    answer: list[str] | None
    explanation: str | None
    knowledge_points: list[str]
    prerequisites: list[str] = Field(default_factory=list)
    competencies: list[str]
    difficulty: dict[str, int]
    grade_suitability: dict = Field(default_factory=dict)
    reasoning_patterns: list = Field(default_factory=list)
    status: str
    metadata: dict = Field(default_factory=dict)


def import_paper(db, folder):
    data = read(folder / "paper.yaml")
    source = ensure(
        db, m.QuestionSource, stable("source", data["source_code"]), code=data["source_code"], name=data["source_name"]
    )
    paper = ensure(
        db,
        m.Paper,
        stable("paper", data["code"]),
        code=data["code"],
        source_id=source.id,
        title=data["title"],
        year=data.get("year"),
        metadata_json=data.get("metadata", {}),
    )
    files = sorted(folder.glob("q[0-9]*.yaml"))
    expected = data.get("metadata", {}).get("expected_questions")
    if expected and len(files) != expected:
        raise ValueError(f"{data['code']} 题数与元数据不一致")
    for file in files:
        q = QuestionSeed.model_validate(read(file))
        kid_map = {k.code: k.id for k in db.scalars(select(m.Knowledge))}
        cid_map = {c.code: c.id for c in db.scalars(select(m.Competency))}
        if not set(q.knowledge_points + q.prerequisites) <= kid_map.keys() or not set(q.competencies) <= cid_map.keys():
            raise ValueError(f"{file} 引用了未知知识或能力")
        if q.status == "PUBLISHED" and (
            not q.stem or not q.answer or not q.explanation or not set(q.answer) <= q.options.keys()
        ):
            raise ValueError(f"{file} 不满足发布门禁")
        identifier = stable("question", f"{data['code']}:{q.source_question_no}")
        item = ensure(
            db,
            m.Question,
            identifier,
            paper_id=paper.id,
            source_question_no=q.source_question_no,
            question_type=q.question_type,
            stem=q.stem,
            answer=q.answer,
            explanation=q.explanation,
            competition_difficulty=q.difficulty["competition"],
            learning_difficulty=q.difficulty["learning"],
            status=q.status,
            metadata_json={
                **q.metadata,
                "grade_suitability": q.grade_suitability,
                "reasoning_patterns": q.reasoning_patterns,
            },
        )
        for label, text in q.options.items():
            ensure(db, m.Option, stable("option", f"{identifier}:{label}"), question_id=item.id, label=label, text=text)
        for relation, codes in [("CORE", q.knowledge_points), ("PREREQUISITE", q.prerequisites)]:
            for code in codes:
                ensure(
                    db,
                    m.QuestionKnowledge,
                    stable("qk", f"{identifier}:{code}:{relation}"),
                    question_id=item.id,
                    knowledge_id=kid_map[code],
                    relation_type=relation,
                )
        for code in q.competencies:
            ensure(
                db,
                m.QuestionCompetency,
                stable("qc", f"{identifier}:{code}"),
                question_id=item.id,
                competency_id=cid_map[code],
            )
    return len(files)


def seed(db, root=ROOT):
    for d in read(root / "knowledge/domains.yaml"):
        ensure(db, m.Domain, stable("domain", d["code"]), **d)
    for c in read(root / "competencies/core.yaml"):
        ensure(db, m.Competency, stable("competency", c["code"]), **c)
    for node in read(root / "knowledge/points.yaml"):
        data = dict(node)
        domain = data.pop("domain")
        kid = stable("knowledge", node["code"])
        ensure(db, m.Knowledge, kid, domain_id=stable("domain", domain), **data)
        for level, verb in enumerate(["识别", "理解", "应用", "分析", "竞赛推理"]):
            ensure(
                db,
                m.KnowledgeLevel,
                stable("level", f"{kid}:{level}"),
                knowledge_id=kid,
                level=level,
                objective=f"{verb}：{node['name']}",
            )
    edge_data = read(root / "knowledge/edges.yaml")
    validate_dag([(e["source"], e["target"]) for e in edge_data if e["relation_type"] == "PREREQUISITE_OF"])
    for e in edge_data:
        ensure(
            db,
            m.Edge,
            stable("edge", f"{e['source']}:{e['target']}:{e['relation_type']}"),
            source_knowledge_id=stable("knowledge", e["source"]),
            target_knowledge_id=stable("knowledge", e["target"]),
            relation_type=e["relation_type"],
        )
    for resource in read(root / "knowledge/resources.yaml"):
        data = dict(resource)
        code = data.pop("knowledge_code")
        ensure(db, m.Resource, stable("resource", resource["title"]), knowledge_id=stable("knowledge", code), **data)
    count = 0
    for paper in sorted((root / "questions").rglob("paper.yaml")):
        count += import_paper(db, paper.parent)
    for path in (root / "curriculum").glob("*.yaml"):
        data = read(path)
        curriculum = ensure(
            db,
            m.Curriculum,
            stable("curriculum", data["code"]),
            code=data["code"],
            title=data["title"],
            template_weeks=data["template_weeks"],
        )
        for unit in data["units"]:
            uid = stable("unit", f"{data['code']}:{unit['sequence']}")
            ensure(
                db,
                m.Unit,
                uid,
                curriculum_id=curriculum.id,
                sequence=unit["sequence"],
                title=unit["title"],
                content=unit["content"],
                knowledge_ids=[stable("knowledge", c) for c in unit["knowledge_points"]],
            )
            ensure(db, m.Objective, stable("objective", uid), unit_id=uid, text=unit["content"])
    for e in read(root / "experiments/core.yaml"):
        eid = stable("experiment", e["code"])
        ensure(db, m.Experiment, eid, **{k: v for k, v in e.items() if k != "steps"})
        for i, instruction in enumerate(e["steps"], 1):
            ensure(
                db,
                m.ExperimentStep,
                stable("step", f"{eid}:{i}"),
                experiment_id=eid,
                sequence=i,
                instruction=instruction,
            )
        for kind, name in [
            ("INDEPENDENT", "本次研究主动改变的因素（由学生明确）"),
            ("DEPENDENT", "记录和测量的结果（由学生明确）"),
            ("CONTROL", "其他保持一致的条件（由学生明确）"),
        ]:
            ensure(
                db, m.ExperimentVariable, stable("variable", f"{eid}:{kind}"), experiment_id=eid, name=name, kind=kind
            )
    ensure(
        db,
        m.Misconception,
        stable("misconception", "CORRELATION_CAUSATION"),
        code="CORRELATION_CAUSATION",
        name="把相关当作因果",
        description="同时变化不等于一个因素导致另一个因素",
        correct_concept="通过对照与干预排除混杂，评价因果证据",
        severity=2,
    )
    from app.services.seed_lessons import seed_lessons
    lessons = seed_lessons(db, root)
    db.flush()
    return {"questions": count, "knowledge": db.scalar(select(func.count()).select_from(m.Knowledge)), "lesson_drafts": lessons}
