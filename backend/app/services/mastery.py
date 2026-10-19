from collections import defaultdict
from datetime import timedelta
from sqlalchemy import select
from app.models import Evidence, LearningEvent, Mastery, CompetencyMastery

WEIGHTS = (0.10, 0.20, 0.25, 0.25, 0.20)
INTERVALS = (1, 3, 7, 14, 30, 60)


def evidence_delta(correct, confidence, hints, kind="STANDARD"):
    if not correct:
        return -0.08 if confidence >= 0.7 else -0.04
    if hints:
        return 0.02
    if kind in {"TRANSFER", "EXPERIMENT"}:
        return 0.10
    return 0.08 if confidence >= 0.7 else 0.04


def snapshot(db, student_id, as_of):
    evidence = db.scalars(
        select(Evidence)
        .join(LearningEvent, Evidence.event_id == LearningEvent.id)
        .where(
            Evidence.student_id == student_id,
            LearningEvent.student_id == student_id,
            LearningEvent.created_at <= as_of,
            Evidence.created_at <= as_of,
        )
        .order_by(LearningEvent.created_at, Evidence.id)
    ).all()
    groups = defaultdict(list)
    for item in evidence:
        groups[(item.target_type, item.target_id)].append(item)
    knowledge, competencies = {}, {}
    for (kind, target), items in groups.items():
        scores = [0.0] * 5
        scalar = 0.0
        streak = 0
        for item in items:
            level = item.cognitive_level
            scores[level] = max(0, min(1, scores[level] + item.delta))
            scalar = max(0, min(1, scalar + item.delta))
            streak = streak + 1 if item.is_correct and item.delta >= 0.04 else 0
        last = items[-1]
        interval = INTERVALS[min(max(streak - 1, 0), len(INTERVALS) - 1)]
        due = last.created_at + timedelta(days=interval)
        base = {"confidence": min(1, len(items) / 20), "evidence_count": len(items)}
        if kind == "knowledge":
            knowledge[target] = {
                **base,
                "knowledge_id": target,
                "scores": scores,
                "recognition_score": scores[0],
                "understanding_score": scores[1],
                "application_score": scores[2],
                "analysis_score": scores[3],
                "competition_score": scores[4],
                "overall_score": round(sum(s * w for s, w in zip(scores, WEIGHTS)), 4),
                "exposure_count": len(items),
                "correct_count": sum(i.is_correct for i in items),
                "incorrect_count": sum(not i.is_correct for i in items),
                "recent_accuracy": sum(i.is_correct for i in items[-10:]) / len(items[-10:]),
                "forgetting_risk": min(1, max(0, (as_of - last.created_at).total_seconds() / (interval * 86400))),
                "last_review_at": last.created_at,
                "next_review_at": due,
            }
        else:
            competencies[target] = {
                **base,
                "competency_id": target,
                "score": scalar,
                "recent_score": sum(i.is_correct for i in items[-10:]) / len(items[-10:]),
            }
    return knowledge, competencies


def update_mastery(db, student_id, event):
    """Only the evidence service writes mastery caches. Historical reads never read caches."""
    db.flush()
    knowledge, competencies = snapshot(db, student_id, event.created_at)
    for kid, values in knowledge.items():
        obj = db.scalar(select(Mastery).where(Mastery.student_id == student_id, Mastery.knowledge_id == kid))
        if not obj:
            obj = Mastery(student_id=student_id, knowledge_id=kid)
            db.add(obj)
        for key, value in values.items():
            if key in Mastery.__table__.columns:
                setattr(obj, key, value)
        obj.updated_at = event.created_at
    for cid, values in competencies.items():
        obj = db.scalar(
            select(CompetencyMastery).where(
                CompetencyMastery.student_id == student_id, CompetencyMastery.competency_id == cid
            )
        )
        if not obj:
            obj = CompetencyMastery(student_id=student_id, competency_id=cid)
            db.add(obj)
        for key, value in values.items():
            setattr(obj, key, value)
        obj.updated_at = event.created_at


def record_question_evidence(db, event, question, correct, confidence, hints, knowledge_links, competency_links):
    existing = db.scalar(select(Evidence).where(Evidence.event_id == event.id))
    if existing:
        return
    kind = question.metadata_json.get("evidence_kind", "STANDARD")
    delta = evidence_delta(correct, confidence, hints, kind)
    level = min(4, question.metadata_json.get("cognitive_level", question.learning_difficulty))
    for target_type, links, key in [
        ("knowledge", knowledge_links, "knowledge_id"),
        ("competency", competency_links, "competency_id"),
    ]:
        seen = set()
        for link in links:
            target_id = getattr(link, key)
            if target_id in seen:
                continue
            seen.add(target_id)
            db.add(
                Evidence(
                    student_id=event.student_id,
                    event_id=event.id,
                    target_type=target_type,
                    target_id=target_id,
                    cognitive_level=level,
                    delta=delta,
                    is_correct=correct,
                    explanation=f"{'正确' if correct else '错误'}；信心 {confidence:.0%}；提示 {hints}；证据 {kind}",
                    created_at=event.created_at,
                )
            )
    update_mastery(db, event.student_id, event)
