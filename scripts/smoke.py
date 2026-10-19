"""Runs against configured database after migration and seed; creates an isolated verification account."""

from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import app

with TestClient(app) as client:
    email = f"smoke-{uuid4().hex}@example.test"
    auth = client.post("/api/v1/auth/register", json={"email": email, "password": uuid4().hex, "name": "自动验收账号"})
    assert auth.status_code == 201, auth.text
    headers = {"Authorization": f"Bearer {auth.json()['access_token']}"}
    student = client.post("/api/v1/students", headers=headers, json={"name": "自动验收学生"})
    assert student.status_code == 201, student.text
    sid = student.json()["id"]
    context = client.post(
        f"/api/v1/students/{sid}/learning-contexts",
        headers=headers,
        json={"education_stage": "G8", "school_grade": 8, "biology_level": "L2_JUNIOR", "competition_goal": "IBO"},
    )
    assert context.status_code == 201, context.text
    plan = client.post(f"/api/v1/students/{sid}/plan/recalculate", headers=headers, json={})
    assert plan.status_code == 200 and plan.json()["tasks"], plan.text
    q = client.get("/api/v1/questions", headers=headers).json()["items"][0]
    answer = client.post(
        f"/api/v1/questions/{q['id']}/attempt",
        headers=headers,
        json={
            "student_id": sid,
            "learning_context_id": context.json()["id"],
            "event_id": str(uuid4()),
            "answer": [q["options"][0]["label"]],
            "confidence": 0.8,
            "time_seconds": 10,
        },
    )
    assert answer.status_code == 200, answer.text
    report = client.get(f"/api/v1/students/{sid}/reports", headers=headers)
    assert report.status_code == 200 and report.json()["question_count"] == 1, report.text
print("Configured database migration/seed/API smoke passed.")
