from datetime import timedelta
from uuid import uuid4
import json
import pytest
from sqlalchemy import select, func
from pydantic import ValidationError
from app import models as m
from app.ai.gateway import validate_question, GatewayError, Gateway
from app.schemas import GeneratedQuestion
from app.services.graph import validate_dag
from app.services.mastery import evidence_delta, snapshot
from app.services.seed import seed, import_paper, stable
from app.planners.adaptive import recommendations
from conftest import register, learner


def attempt_payload(sid, cid, answer, event_id=None):
    return {
        "student_id": sid,
        "learning_context_id": cid,
        "event_id": event_id or str(uuid4()),
        "answer": answer,
        "confidence": 0.9,
        "time_seconds": 20,
    }


def test_parent_two_students_full_learning_loop(env):
    client, factory = env
    headers = register(client)
    paths = []
    for level in ["L1_FOUNDATION", "L4_OLYMPIAD_FOUNDATION"]:
        sid, cid = learner(client, headers, level)
        start = client.post(
            "/api/v1/diagnostics/start", headers=headers, json={"student_id": sid, "learning_context_id": cid}
        )
        assert start.status_code == 200, start.text
        diagnostic = start.json()
        for i, question in enumerate(diagnostic["questions"]):
            with factory() as db:
                correct = db.get(m.Question, question["id"]).answer
            answer = correct if i else [next(o["label"] for o in question["options"] if o["label"] not in correct)]
            result = client.post(
                f"/api/v1/diagnostics/{diagnostic['id']}/answer",
                headers=headers,
                json={**attempt_payload(sid, cid, answer), "question_id": question["id"]},
            )
            assert result.status_code == 200, result.text
        finish = client.post(f"/api/v1/diagnostics/{diagnostic['id']}/finish", headers=headers)
        assert finish.status_code == 200, finish.text
        assert finish.json()["knowledge_profile"]
        assert finish.json()["competency_profile"]
        plan = client.post(f"/api/v1/students/{sid}/plan/recalculate", headers=headers, json={})
        assert plan.status_code == 200, plan.text
        paths.append(plan.json()["tasks"])
        assert paths[-1]
        assert sum(t["estimated_minutes"] for t in paths[-1]) <= 180
        assert all(t["reason"]["primary_reason"] and t["reason"]["why_now"] for t in paths[-1])
        assert client.get(f"/api/v1/students/{sid}/errors", headers=headers).json()
    assert [t["title"] for t in paths[0]] != [t["title"] for t in paths[1]]


def test_grade_and_goal_change_content_and_path(env):
    client, factory = env
    headers = register(client)
    sid1, _ = learner(client, headers, "L2_JUNIOR", grade=7)
    sid2, _ = learner(client, headers, "L2_JUNIOR", grade=10)
    sid3, _ = learner(client, headers, "L2_JUNIOR", grade=7, goal="IBO")
    with factory() as db:
        _, a = recommendations(db, sid1)
        _, b = recommendations(db, sid2)
        _, c = recommendations(db, sid3)
    same = next(x for x in a if x["knowledge_id"] == stable("knowledge", "BIO.CELL.001"))
    older = next(x for x in b if x["knowledge_id"] == same["knowledge_id"])
    assert same["description"] != older["description"]
    assert [x["knowledge_id"] for x in a[:20]] != [x["knowledge_id"] for x in c[:20]]


def test_prerequisite_gate_and_difficulty_bridge(env):
    client, factory = env
    sid, _ = learner(client, register(client))
    with factory() as db:
        _, ranked = recommendations(db, sid)
        selected = {r["knowledge_id"] for r in ranked}
        blocked = set(db.scalars(select(m.Edge.target_knowledge_id).where(m.Edge.relation_type == "PREREQUISITE_OF")))
        assert not selected.intersection(blocked)
        for rec in ranked:
            if rec["reason"]["difficulty_bridge"]:
                assert rec["task_type"] == "LEARN"
                assert not rec["question_ids"]


def test_event_replay_and_conflicting_key(env):
    client, factory = env
    headers = register(client)
    sid, cid = learner(client, headers)
    with factory() as db:
        q = db.scalar(select(m.Question).where(m.Question.status == "PUBLISHED"))
        qid, correct = q.id, q.answer
    payload = attempt_payload(sid, cid, correct)
    first = client.post(f"/api/v1/questions/{qid}/attempt", headers=headers, json=payload)
    assert first.status_code == 200, first.text
    mastery1 = client.get(f"/api/v1/students/{sid}/mastery", headers=headers).json()
    second = client.post(f"/api/v1/questions/{qid}/attempt", headers=headers, json=payload)
    assert second.json()["replayed"]
    assert (
        client.get(f"/api/v1/students/{sid}/mastery", headers=headers).json()[0]["overall_score"]
        == mastery1[0]["overall_score"]
    )
    conflict = client.post(f"/api/v1/questions/{qid}/attempt", headers=headers, json={**payload, "confidence": 0.1})
    assert conflict.status_code == 409
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(m.Attempt)) == 1


def test_student_scope_on_every_private_resource(env):
    client, factory = env
    owner = register(client)
    intruder = register(client, "intruder@example.com")
    sid, cid = learner(client, owner)
    sid2, cid2 = learner(client, intruder)
    for suffix in [
        "",
        "/learning-contexts",
        "/mastery",
        "/competencies",
        "/errors",
        "/evidence",
        "/plan/today",
        "/plan/week",
        "/reports",
    ]:
        assert client.get(f"/api/v1/students/{sid}{suffix}", headers=intruder).status_code == 403
    assert client.post(f"/api/v1/students/{sid}/plan/recalculate", headers=intruder, json={}).status_code == 403
    assert (
        client.post(
            "/api/v1/diagnostics/start", headers=intruder, json={"student_id": sid2, "learning_context_id": cid}
        ).status_code
        == 404
    )
    session = client.post(
        "/api/v1/ai/tutor/session", headers=owner, json={"student_id": sid, "learning_context_id": cid}
    ).json()
    assert (
        client.post(
            "/api/v1/ai/tutor/message", headers=intruder, json={"session_id": session["id"], "message": "请帮助"}
        ).status_code
        == 403
    )
    d = client.post(
        "/api/v1/diagnostics/start", headers=owner, json={"student_id": sid, "learning_context_id": cid}
    ).json()
    assert client.get(f"/api/v1/diagnostics/{d['id']}/result", headers=intruder).status_code == 403
    qid = client.get("/api/v1/questions", headers=owner).json()["items"][0]["id"]
    assert (
        client.post(
            f"/api/v1/questions/{qid}/attempt", headers=intruder, json=attempt_payload(sid, cid, ["A"])
        ).status_code
        == 403
    )
    own_plan = client.post(f"/api/v1/students/{sid}/plan/recalculate", headers=owner, json={}).json()
    assert (
        client.post(
            f"/api/v1/questions/{qid}/attempt",
            headers=intruder,
            json={**attempt_payload(sid2, cid2, ["A"]), "task_id": own_plan["tasks"][0]["id"]},
        ).status_code
        == 404
    )


def test_viewer_cannot_mutate(env):
    client, _ = env
    owner, viewer = register(client), register(client, "viewer@example.com")
    sid, cid = learner(client, owner)
    assert (
        client.post(
            f"/api/v1/students/{sid}/members", headers=owner, json={"email": "viewer@example.com", "role": "VIEWER"}
        ).status_code
        == 200
    )
    assert client.get(f"/api/v1/students/{sid}/reports", headers=viewer).status_code == 200
    assert client.post(f"/api/v1/students/{sid}/plan/recalculate", headers=viewer, json={}).status_code == 403
    assert (
        client.post(
            "/api/v1/events",
            headers=viewer,
            json={"id": str(uuid4()), "student_id": sid, "learning_context_id": cid, "event_type": "REFLECTION"},
        ).status_code
        == 403
    )
    assert client.get("/api/v1/admin/review", headers=owner).status_code == 403


def test_as_of_does_not_read_future_evidence_or_context(env):
    client, factory = env
    headers = register(client)
    sid, cid = learner(client, headers)
    with factory() as db:
        q = db.scalar(select(m.Question).where(m.Question.status == "PUBLISHED"))
        qid, correct = q.id, q.answer
    before = m.now()
    result = client.post(f"/api/v1/questions/{qid}/attempt", headers=headers, json=attempt_payload(sid, cid, correct))
    assert result.status_code == 200
    with factory() as db:
        assert snapshot(db, sid, before) == ({}, {})
        current, _ = snapshot(db, sid, m.now())
        assert current
        past_context, ranked_before = recommendations(db, sid, before)
    client.post(
        f"/api/v1/students/{sid}/learning-contexts",
        headers=headers,
        json={
            "education_stage": "G7",
            "school_grade": 7,
            "biology_level": "L4_OLYMPIAD_FOUNDATION",
            "competition_goal": "IBO",
        },
    )
    with factory() as db:
        ctx, ranked_after = recommendations(db, sid, before)
        assert ctx.id == past_context.id == cid
        assert ranked_before == ranked_after
    assert (
        client.get(
            f"/api/v1/students/{sid}/mastery",
            headers=headers,
            params={"as_of": (m.now() + timedelta(days=1)).isoformat()},
        ).status_code
        == 422
    )


def test_no_client_supplied_score_or_future_event(env):
    client, _ = env
    headers = register(client)
    sid, cid = learner(client, headers)
    base = {
        "id": str(uuid4()),
        "student_id": sid,
        "learning_context_id": cid,
        "event_type": "QUESTION_ANSWER",
        "payload": {"correct": True},
    }
    assert client.post("/api/v1/events", headers=headers, json=base).status_code == 422
    assert (
        client.post(
            "/api/v1/events", headers=headers, json={**base, "event_type": "REVIEW", "created_at": "2099-01-01"}
        ).status_code
        == 422
    )
    assert client.post("/api/v1/events", headers=headers, json={**base, "event_type": "REVIEW"}).status_code == 200
    assert client.get(f"/api/v1/students/{sid}/mastery", headers=headers).json() == []


@pytest.mark.parametrize(
    "correct,confidence,hints,kind,delta",
    [
        (True, 0.9, 0, "STANDARD", 0.08),
        (True, 0.3, 0, "STANDARD", 0.04),
        (False, 0.9, 0, "STANDARD", -0.08),
        (False, 0.3, 0, "STANDARD", -0.04),
        (True, 0.9, 1, "STANDARD", 0.02),
        (True, 0.9, 0, "TRANSFER", 0.1),
        (True, 0.9, 0, "EXPERIMENT", 0.1),
    ],
)
def test_evidence_calculator(correct, confidence, hints, kind, delta):
    assert evidence_delta(correct, confidence, hints, kind) == delta


def test_dag_rejects_cycle():
    validate_dag([("cell", "membrane"), ("membrane", "osmosis")])
    with pytest.raises(ValueError):
        validate_dag([("cell", "membrane"), ("membrane", "osmosis"), ("osmosis", "cell")])


def valid_generated(kid):
    return {
        "stem": "以下哪项可以作为可检验的实验假设？",
        "question_type": "SINGLE_CHOICE",
        "options": {"A": "光照时长会影响株高", "B": "阳光非常美丽"},
        "answer": ["A"],
        "explanation": "假设必须能通过可操作变量和可测量结果进行检验。",
        "knowledge_ids": [kid],
        "prerequisites": [],
        "learning_difficulty": 1,
        "competition_difficulty": 1,
    }


def test_ai_schema_and_rule_gates():
    raw = valid_generated("k")
    assert validate_question(raw, ["k"], 1)
    with pytest.raises(GatewayError):
        validate_question({**raw, "answer": ["D"]}, ["k"], 1)
    with pytest.raises(GatewayError):
        validate_question(raw, ["other"], 1)
    with pytest.raises(GatewayError):
        validate_question({**raw, "learning_difficulty": 7}, ["k"], 1)
    with pytest.raises(ValidationError):
        GeneratedQuestion.model_validate({**raw, "status": "PUBLISHED"})


def test_ai_cannot_publish_without_review(env):
    client, factory = env
    headers = register(client)
    with factory.begin() as db:
        user = db.scalar(select(m.User))
        user.is_admin = True
        kid = db.scalar(select(m.Knowledge.id))
        draft = m.AIContent(
            requested_by=user.id,
            purpose="generate",
            content=valid_generated(kid),
            trace={"request": {"target_biology_level": "L1_FOUNDATION"}},
        )
        db.add(draft)
        db.flush()
        draft_id = draft.id
    path = f"/api/v1/admin/ai-contents/{draft_id}/review"
    assert (
        client.post(path, headers=headers, json={"decision": "PUBLISHED", "note": "已完成内容审核说明"}).status_code
        == 409
    )
    assert (
        client.post(
            path, headers=headers, json={"decision": "REVIEWED", "note": "知识、答案与难度核对通过"}
        ).status_code
        == 200
    )
    assert (
        client.post(path, headers=headers, json={"decision": "PUBLISHED", "note": "确认发布此审核内容"}).status_code
        == 200
    )
    assert (
        client.post(path, headers=headers, json={"decision": "PUBLISHED", "note": "重复发布不应创建题目"}).status_code
        == 409
    )
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(m.Audit).where(m.Audit.action == "AI_CONTENT_REVIEW")) == 2


def test_seed_repeatability_and_new_paper_without_code_change(env, tmp_path):
    import yaml

    client, factory = env
    with factory.begin() as db:
        counts = {
            table.name: db.scalar(select(func.count()).select_from(table)) for table in m.Base.metadata.sorted_tables
        }
        seed(db)
        assert counts == {
            table.name: db.scalar(select(func.count()).select_from(table)) for table in m.Base.metadata.sorted_tables
        }
        folder = tmp_path / "new_year"
        folder.mkdir()
        (folder / "paper.yaml").write_text(
            yaml.safe_dump(
                {
                    "code": "league_2024",
                    "source_code": "national_league",
                    "source_name": "全国中学生生物学联赛",
                    "title": "新增年份题源",
                    "year": 2024,
                    "metadata": {"expected_questions": 1},
                }
            ),
            encoding="utf-8",
        )
        (folder / "q001.yaml").write_text(
            yaml.safe_dump(
                {
                    "source_question_no": 1,
                    "question_type": "SINGLE_CHOICE",
                    "stem": None,
                    "answer": None,
                    "explanation": None,
                    "knowledge_points": ["BIO.CELL.001"],
                    "competencies": ["OBSERVATION"],
                    "difficulty": {"competition": 4, "learning": 1},
                    "status": "REVIEW_REQUIRED",
                }
            ),
            encoding="utf-8",
        )
        assert import_paper(db, folder) == 1
        assert db.scalar(select(m.Paper).where(m.Paper.year == 2024))


def test_tutor_hint_progression_and_answer_redaction(env):
    client, factory = env
    headers = register(client)
    sid, cid = learner(client, headers)
    q = client.get("/api/v1/questions", headers=headers).json()["items"][0]
    assert "answer" not in q and "explanation" not in q
    session = client.post(
        "/api/v1/ai/tutor/session",
        headers=headers,
        json={"student_id": sid, "learning_context_id": cid, "question_id": q["id"]},
    ).json()
    for hint in range(5):
        result = client.post(
            "/api/v1/ai/tutor/message",
            headers=headers,
            json={"session_id": session["id"], "message": "请提示", "request_hint": hint > 0},
        )
        assert result.status_code == 200, result.text
        assert result.json()["hint_level"] == hint
    with factory() as db:
        answer = db.get(m.Question, q["id"]).answer
    result = client.post(
        f"/api/v1/questions/{q['id']}/attempt", headers=headers, json=attempt_payload(sid, cid, answer)
    )
    assert result.json()["hint_count"] == 4
    with factory() as db:
        assert all(e.delta == 0.02 for e in db.scalars(select(m.Evidence).where(m.Evidence.student_id == sid)))


def test_official_questions_not_published_and_complete_mapping(env):
    _, factory = env
    with factory() as db:
        paper = db.scalar(select(m.Paper).where(m.Paper.year == 2025))
        questions = db.scalars(select(m.Question).where(m.Question.paper_id == paper.id)).all()
        assert len(questions) == paper.metadata_json["expected_questions"] == 72
        for q in questions:
            assert q.status == "REVIEW_REQUIRED"
            assert q.answer is None
            assert q.stem and q.metadata_json["source_pages"]
            assert db.scalar(select(m.QuestionKnowledge).where(m.QuestionKnowledge.question_id == q.id))


def test_gateway_adapter_is_detached_from_database():
    import asyncio

    class FakeAdapter:
        async def complete(self, prompt, context, schema):
            assert "purpose" in context
            assert "properties" in schema
            json.dumps(context)
            return valid_generated("k")

    output = asyncio.run(
        Gateway(FakeAdapter()).generate(
            "generate", {"request": {"target_biology_level": "L1_FOUNDATION"}, "allowed_knowledge_ids": ["k"]}
        )
    )
    assert output["knowledge_ids"] == ["k"]
