import shutil
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from app.config import settings
from app.db import get_db
from app.main import app
from app.services.seed import seed


@pytest.fixture(scope="session")
def template(tmp_path_factory):
    path = tmp_path_factory.mktemp("database") / "template.db"
    old = settings.database_url
    settings.database_url = f"sqlite:///{path.as_posix()}"
    command.upgrade(Config("alembic.ini"), "head")
    engine = create_engine(settings.database_url)
    factory = sessionmaker(engine)
    with factory.begin() as db:
        seed(db)
    engine.dispose()
    settings.database_url = old
    return path


@pytest.fixture
def env(template, tmp_path):
    path = tmp_path / "test.db"
    shutil.copyfile(template, path)
    engine = create_engine(f"sqlite:///{path.as_posix()}", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def fk(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")

    factory = sessionmaker(engine, expire_on_commit=False)

    def override():
        with factory() as db:
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise

    app.dependency_overrides[get_db] = override
    with TestClient(app) as client:
        yield client, factory
    app.dependency_overrides.clear()
    engine.dispose()


def register(client, email="parent@example.com"):
    response = client.post(
        "/api/v1/auth/register", json={"email": email, "name": "家长", "password": "test-password-123"}
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def learner(client, headers, level="L1_FOUNDATION", grade=7, goal="NATIONAL_LEAGUE"):
    s = client.post("/api/v1/students", headers=headers, json={"name": "测试学生"})
    assert s.status_code == 201, s.text
    sid = s.json()["id"]
    c = client.post(
        f"/api/v1/students/{sid}/learning-contexts",
        headers=headers,
        json={
            "education_stage": f"G{grade}",
            "school_grade": grade,
            "biology_level": level,
            "competition_goal": goal,
            "weekly_hours": 3,
            "preferred_learning_days": 5,
        },
    )
    assert c.status_code == 201, c.text
    return sid, c.json()["id"]
