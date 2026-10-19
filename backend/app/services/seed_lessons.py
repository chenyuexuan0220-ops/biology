from sqlalchemy import select
from app import models as m
from app.services.seed import read, stable, ensure
from app.services.lessons import validate_document


def seed_lessons(db, root):
    count = 0
    for file in sorted((root / "lessons").glob("*.yaml")):
        for item in read(file):
            node = db.scalar(select(m.Knowledge).where(m.Knowledge.code == item["knowledge_code"]))
            if not node:
                raise ValueError("课程知识点不存在：" + item["knowledge_code"])
            lesson = ensure(
                db,
                m.Lesson,
                stable("lesson", item["code"]),
                **{
                    k: item[k]
                    for k in ["code", "unit_code", "unit_title", "sequence", "tier", "min_level", "max_level"]
                },
                knowledge_id=node.id,
            )
            document = validate_document(db, lesson, item["document"])
            ensure(
                db,
                m.LessonRevision,
                stable("lesson-revision", f"{item['code']}:{item['version']}"),
                lesson_id=lesson.id,
                version=item["version"],
                document=document.model_dump(),
                status="REVIEW_REQUIRED",
            )
            count += 1
    return count
