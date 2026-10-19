from copy import deepcopy
from uuid import uuid4

from sqlalchemy import select, func

from app import models as m
from app.services.seed import seed
from conftest import register, learner

P = "/api/v1"


def setup(env, publish=True):
    client, factory = env
    headers = register(client)
    with factory.begin() as db:
        db.scalar(select(m.User)).is_admin = True
    all_drafts = client.get(f"{P}/admin/lessons", headers=headers).json()
    drafts = [draft for draft in all_drafts if draft["lesson"]["unit_code"] == "cell-transport"]
    assert len(drafts) == 12
    if publish:
        for draft in all_drafts:
            for status in ["REVIEWED", "PUBLISHED"]:
                response = client.post(
                    f"{P}/admin/lessons/{draft['id']}/review",
                    headers=headers,
                    json={"decision": status, "note": "隔离测试库审核夹具，不代表人工教研结论"},
                )
                assert response.status_code == 200, response.text
    sid, cid = learner(client, headers)
    return client, factory, headers, sid, cid, drafts


def catalog(client, headers, sid, **params):
    response = client.get(f"{P}/students/{sid}/lessons", headers=headers, params=params)
    assert response.status_code == 200, response.text
    return [item for item in response.json()["lessons"] if item["unit_code"] == "cell-transport"]


def start(client, headers, sid, cid, lesson, **extra):
    response = client.post(
        f"{P}/students/{sid}/lessons/{lesson['id']}/start", headers=headers, json={"learning_context_id": cid, **extra}
    )
    assert response.status_code == 200, response.text
    return response.json()


def complete(client, factory, headers, run, wrong=()):
    submitted = []
    for index, q in enumerate(run["questions"]):
        with factory() as db:
            correct = db.get(m.Question, q["id"]).answer
        answer = [next(o["label"] for o in q["options"] if o["label"] not in correct)] if index in wrong else correct
        payload = {
            "question_id": q["id"],
            "event_id": str(uuid4()),
            "answer": answer,
            "confidence": 0.7,
            "time_seconds": 15,
        }
        response = client.post(f"{P}/lesson-runs/{run['id']}/answer", headers=headers, json=payload)
        assert response.status_code == 200, response.text
        submitted.append(payload)
    response = client.post(f"{P}/lesson-runs/{run['id']}/finish", headers=headers)
    assert response.status_code == 200, response.text
    return response.json(), submitted


def test_drafts_review_and_seed_do_not_publish_or_overwrite(env):
    client, factory, headers, sid, cid, drafts = setup(env, False)
    items = catalog(client, headers, sid)
    assert len(items) == 4 and all(x["state"] == "UNPUBLISHED" for x in items)
    assert (
        client.post(
            f"{P}/students/{sid}/lessons/{items[0]['id']}/start", headers=headers, json={"learning_context_id": cid}
        ).status_code
        == 409
    )
    draft = drafts[0]
    assert (
        client.post(
            f"{P}/admin/lessons/{draft['id']}/review",
            headers=headers,
            json={"decision": "PUBLISHED", "note": "不能跳过审核直接发布"},
        ).status_code
        == 409
    )
    revised = deepcopy(draft["document"])
    revised["title"] += "（修订）"
    response = client.post(f"{P}/admin/lessons/{draft['id']}/revisions", headers=headers, json={"document": revised})
    assert response.status_code == 200, response.text
    new = response.json()
    with factory.begin() as db:
        seed(db)
        assert db.get(m.LessonRevision, new["id"]).document["title"] == revised["title"]
        assert db.get(m.LessonRevision, draft["id"]).document == draft["document"]
        assert db.scalar(select(func.count()).select_from(m.Lesson)) == 15


def test_assessment_unlocks_next_and_replans_with_real_minutes(env):
    client, factory, headers, sid, cid, _ = setup(env)
    items = catalog(client, headers, sid)
    assert [x["state"] for x in items] == ["READY", "LOCKED", "LOCKED", "LOCKED"]
    assert (
        client.post(
            f"{P}/students/{sid}/lessons/{items[1]['id']}/start", headers=headers, json={"learning_context_id": cid}
        ).status_code
        == 409
    )
    run = start(client, headers, sid, cid, items[0])
    assert "checks" not in run["document"] and "adaptations" not in run["document"]
    assert all("answer" not in q and "explanation" not in q for q in run["questions"])
    assert start(client, headers, sid, cid, items[0])["id"] == run["id"]
    assert client.post(f"{P}/lesson-runs/{run['id']}/finish", headers=headers).status_code == 409
    client.patch(f"{P}/lesson-runs/{run['id']}/notes", headers=headers, json={"notes": "我用自己的话解释细胞"})
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(m.Attempt)) == 0
    result, submitted = complete(client, factory, headers, run)
    assert result["passed"] and result["next_tasks"][0]["lesson_id"] == items[1]["id"]
    assert catalog(client, headers, sid)[1]["state"] == "READY"
    plan = client.get(f"{P}/students/{sid}/plan/week", headers=headers).json()
    assert plan["tasks"][0]["estimated_minutes"] == items[1]["estimated_minutes"]
    assert sum(t["estimated_minutes"] for t in plan["tasks"]) <= 180
    replay = client.post(f"{P}/lesson-runs/{run['id']}/answer", headers=headers, json=submitted[0])
    assert replay.status_code == 200 and replay.json()["replayed"]
    assert client.post(f"{P}/lesson-runs/{run['id']}/finish", headers=headers).json() == result
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(m.Attempt)) == len(run["questions"])
        assert (
            db.scalar(
                select(func.count()).select_from(m.LearningEvent).where(m.LearningEvent.event_type == "ASSESSMENT")
            )
            == 1
        )
    newrun = start(client, headers, sid, cid, items[0])
    assert newrun["id"] != run["id"]
    assert client.post(f"{P}/lesson-runs/{newrun['id']}/answer", headers=headers, json=submitted[0]).status_code == 409


def test_wrong_prerequisite_routes_back_and_can_recover(env):
    client, factory, headers, sid, cid, drafts = setup(env)
    items = catalog(client, headers, sid)
    complete(client, factory, headers, start(client, headers, sid, cid, items[0]))
    run = start(client, headers, sid, cid, items[1])
    doc = next(d["document"] for d in drafts if d["id"] == run["revision_id"])
    probe = next(i for i, q in enumerate(doc["checks"]) if q.get("prerequisite_code"))
    result, _ = complete(client, factory, headers, run, wrong=[probe])
    assert result["accuracy"] == 0.8 and not result["passed"]
    assert result["prerequisite_gaps"] == ["BIO.CELL.001"]
    assert result["next_tasks"][0]["lesson_id"] == items[0]["id"]
    assert catalog(client, headers, sid)[1]["state"] == "LOCKED"
    complete(client, factory, headers, start(client, headers, sid, cid, items[0]))
    assert catalog(client, headers, sid)[1]["state"] == "REINFORCE"
    for item in items[1:]:
        result, _ = complete(client, factory, headers, start(client, headers, sid, cid, item))
        assert result["passed"]
    assert not result["next_tasks"]
    assert all(item["state"] == "PASSED" for item in catalog(client, headers, sid))


def test_wrong_own_concepts_repeat_same_lesson(env):
    client, factory, headers, sid, cid, _ = setup(env)
    item = catalog(client, headers, sid)[0]
    result, _ = complete(client, factory, headers, start(client, headers, sid, cid, item), wrong=[0, 1])
    assert not result["passed"] and result["revisit_sections"] and not result["prerequisite_gaps"]
    assert result["next_tasks"][0]["lesson_id"] == item["id"]
    assert catalog(client, headers, sid)[0]["state"] == "REINFORCE"


def test_tier_and_grade_are_independent_and_history_isolated(env):
    client, factory, headers, sid, cid, _ = setup(env)
    item = catalog(client, headers, sid)[0]
    run = start(client, headers, sid, cid, item)
    before = m.now()
    complete(client, factory, headers, run)
    assert catalog(client, headers, sid, as_of=before.isoformat())[0]["state"] == "READY"
    assert catalog(client, headers, sid, as_of=before.isoformat())[0]["active_run_id"] is None
    for level, grade in [("L4_OLYMPIAD_FOUNDATION", 7), ("L1_FOUNDATION", 10)]:
        other, context = learner(client, headers, level=level, grade=grade)
        lesson = catalog(client, headers, other)[0]
        variant = start(client, headers, other, context, lesson)
        if grade == 7:
            assert variant["lesson"]["tier"] == "COMPETITION"
            assert variant["document"]["sections"] != run["document"]["sections"]
        else:
            assert variant["document"]["sections"] == run["document"]["sections"]
            assert variant["document"]["grade_guidance"] != run["document"]["grade_guidance"]


def test_private_scope_viewer_and_generic_bypasses(env):
    client, factory, headers, sid, cid, _ = setup(env)
    item = catalog(client, headers, sid)[0]
    run = start(client, headers, sid, cid, item)
    intruder = register(client, "intruder@example.com")
    assert client.get(f"{P}/students/{sid}/lessons", headers=intruder).status_code == 403
    assert client.get(f"{P}/lesson-runs/{run['id']}", headers=intruder).status_code == 403
    client.post(
        f"{P}/students/{sid}/members", headers=headers, json={"email": "intruder@example.com", "role": "VIEWER"}
    )
    assert client.get(f"{P}/lesson-runs/{run['id']}", headers=intruder).status_code == 200
    assert (
        client.patch(f"{P}/lesson-runs/{run['id']}/notes", headers=intruder, json={"notes": "不能写入"}).status_code
        == 403
    )
    assert client.post(f"{P}/lesson-runs/{run['id']}/finish", headers=intruder).status_code == 403
    qid = run["questions"][0]["id"]
    payload = {"question_id": qid, "event_id": str(uuid4()), "answer": ["A"]}
    assert client.post(f"{P}/lesson-runs/{run['id']}/answer", headers=intruder, json=payload).status_code == 403
    assert (
        client.post(
            f"{P}/students/{sid}/lessons/{item['id']}/start", headers=intruder, json={"learning_context_id": cid}
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"{P}/questions/{qid}/attempt",
            headers=headers,
            json={"student_id": sid, "learning_context_id": cid, "event_id": str(uuid4()), "answer": ["A"]},
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"{P}/admin/questions/{qid}/review",
            headers=headers,
            json={"decision": "REVIEWED", "note": "不允许通过通用题库修改"},
        ).status_code
        == 409
    )
    assert (
        client.patch(
            f"{P}/admin/questions/{qid}",
            headers=headers,
            json={
                "stem": "绕过版本修改课程检测题",
                "options": {"A": "正确答案", "B": "错误答案"},
                "answer": ["A"],
                "explanation": "试图绕过课程版本直接修改答案",
            },
        ).status_code
        == 409
    )
    assert all(q["id"] != qid for q in client.get(f"{P}/admin/review", headers=headers).json()["questions"])
    plan = client.post(f"{P}/students/{sid}/plan/recalculate", headers=headers, json={}).json()
    task = plan["tasks"][0]
    assert task["reason"]["lesson_id"] == item["id"]
    assert (
        client.post(
            f"{P}/events",
            headers=headers,
            json={
                "id": str(uuid4()),
                "student_id": sid,
                "learning_context_id": cid,
                "task_id": task["id"],
                "event_type": "LEARNING_COMPLETE",
            },
        ).status_code
        == 409
    )


def test_new_revision_preserves_pinned_content_and_archive_blocks(env):
    client, factory, headers, sid, cid, drafts = setup(env)
    item = catalog(client, headers, sid)[0]
    run = start(client, headers, sid, cid, item)
    old = next(d for d in drafts if d["id"] == run["revision_id"])
    doc = deepcopy(old["document"])
    doc["title"] += "（第二版）"
    revised = client.post(f"{P}/admin/lessons/{old['id']}/revisions", headers=headers, json={"document": doc}).json()
    for status in ["REVIEWED", "PUBLISHED"]:
        assert (
            client.post(
                f"{P}/admin/lessons/{revised['id']}/review",
                headers=headers,
                json={"decision": status, "note": "在隔离库验证修订发布流程"},
            ).status_code
            == 200
        )
    assert (
        client.get(f"{P}/lesson-runs/{run['id']}", headers=headers).json()["document"]["title"]
        == old["document"]["title"]
    )
    assert start(client, headers, sid, cid, item)["id"] == run["id"]
    assert (
        client.post(
            f"{P}/admin/lessons/{old['id']}/review",
            headers=headers,
            json={"decision": "ARCHIVED", "note": "隔离测试撤回旧版内容"},
        ).status_code
        == 200
    )
    assert client.get(f"{P}/lesson-runs/{run['id']}", headers=headers).status_code == 409
    assert client.post(f"{P}/lesson-runs/{run['id']}/finish", headers=headers).status_code == 409


def test_animal_tissues_draft_keeps_cell_prerequisite_and_three_tiers(env):
    client, factory, headers, sid, cid, _ = setup(env, False)
    all_drafts = client.get(f"{P}/admin/lessons", headers=headers).json()
    animal = [draft for draft in all_drafts if draft["lesson"]["unit_code"] == "animal-structure"]
    assert len(animal) == 3
    assert all(draft["document"]["prerequisites"] == ["BIO.CELL.001"] for draft in animal)
    assert all(draft["document"]["diagram"]["kind"] == "TISSUES" for draft in animal)
    assert all(len(draft["document"]["checks"]) == 4 for draft in animal)
    assert client.post(f"{P}/admin/lessons/{animal[0]['id']}/review", headers=headers,
        json={"decision": "REVIEWED", "note": "动物组织内容结构验收"}).status_code == 200
    assert client.post(f"{P}/admin/lessons/{animal[0]['id']}/review", headers=headers,
        json={"decision": "PUBLISHED", "note": "动物组织内容结构验收"}).status_code == 200
    assert client.post(f"{P}/admin/lessons/{animal[0]['id']}/review", headers=headers,
        json={"decision": "PUBLISHED", "note": "不能跳过审核状态"}).status_code == 409
