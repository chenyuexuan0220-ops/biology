from datetime import timedelta
from sqlalchemy import select
from app.models import (
    Knowledge,
    Edge,
    Question,
    QuestionKnowledge,
    QuestionCompetency,
    Attempt,
    Task,
    WeeklyPlan,
    Resource,
)
from app.services.mastery import snapshot
from app.services.common import active_context, calculation_time, row


def recommendations(db, student_id, as_of=None):
    at = calculation_time(as_of)
    ctx = active_context(db, student_id, at if as_of else None)
    mastery, skills = snapshot(db, student_id, at)
    level = int(ctx.biology_level[1])
    nodes = {
        k.id: k
        for k in db.scalars(select(Knowledge).where(Knowledge.status == "PUBLISHED", Knowledge.created_at <= at))
    }
    predecessors = {kid: [] for kid in nodes}
    for edge in db.scalars(select(Edge).where(Edge.relation_type == "PREREQUISITE_OF", Edge.created_at <= at)):
        if edge.target_knowledge_id in nodes and edge.source_knowledge_id in nodes:
            predecessors[edge.target_knowledge_id].append(edge.source_knowledge_id)
    questions = {
        q.id: q for q in db.scalars(select(Question).where(Question.status == "PUBLISHED", Question.created_at <= at))
    }
    links = db.scalars(select(QuestionKnowledge)).all()
    qskills = db.scalars(select(QuestionCompetency)).all()
    all_resources = db.scalars(
        select(Resource).where(
            Resource.min_grade <= ctx.school_grade, Resource.max_grade >= ctx.school_grade, Resource.created_at <= at
        )
    ).all()
    error_qids = set(
        db.scalars(
            select(Attempt.question_id).where(
                Attempt.student_id == student_id,
                Attempt.is_correct.is_(False),
                Attempt.created_at <= at,
                Attempt.created_at >= at - timedelta(days=14),
            )
        )
    )
    error_kids = {link.knowledge_id for link in links if link.question_id in error_qids}
    priority_nodes = set()
    for kid in nodes:
        if mastery.get(kid, {}).get("overall_score", 0) < 0.8:
            priority_nodes.update(p for p in predecessors[kid] if mastery.get(p, {}).get("overall_score", 0) < 0.4)
    result = []
    for kid, node in nodes.items():
        if any(mastery.get(p, {}).get("overall_score", 0) < 0.4 for p in predecessors[kid]):
            continue
        m = mastery.get(kid, {})
        gap = 1 - m.get("overall_score", 0)
        candidates = [
            questions[link.question_id]
            for link in links
            if link.knowledge_id == kid
            and link.question_id in questions
            and abs(questions[link.question_id].learning_difficulty - level) <= 2
        ]
        candidates.sort(
            key=lambda q: (
                abs(q.learning_difficulty - level),
                abs(q.metadata_json.get("target_grade", ctx.school_grade) - ctx.school_grade),
                q.id,
            )
        )
        competency_ids = {link.competency_id for link in qskills if link.question_id in {q.id for q in candidates}}
        competency_gap = sum(1 - skills.get(cid, {}).get("score", 0) for cid in competency_ids) / max(
            1, len(competency_ids)
        )
        prerequisite_priority = float(kid in priority_nodes)
        goal = float(ctx.competition_goal in node.goals)
        forgetting = m.get("forgetting_risk", 0)
        recent_error = float(kid in error_kids)
        fit = max(0, 1 - abs(node.level - level) / 7)
        score = (
            gap * 0.2
            + prerequisite_priority * 0.2
            + competency_gap * 0.15
            + goal * 0.15
            + forgetting * 0.1
            + recent_error * 0.1
            + fit * 0.1
        )
        bridge = abs(node.level - level) > 2
        task_type = (
            "REVIEW"
            if forgetting >= 0.8
            else ("LEARN" if bridge or not candidates else "DATA_ANALYSIS" if level >= 4 else "PRACTICE")
        )
        resources = [resource for resource in all_resources if resource.knowledge_id == kid]
        resources.sort(key=lambda r: abs(r.level - level))
        style = "用生活观察和结构示意理解" if ctx.school_grade < 10 else "从机制、变量和证据展开分析"
        detail = (
            resources[0].content
            if resources
            else node.description or f"围绕“{node.name}”，记录定义、一个例子与一个待验证问题。"
        )
        reason = {
            "primary_reason": "先补齐后续学习所需的基础" if prerequisite_priority else "根据当前知识缺口安排",
            "knowledge_gap": round(gap, 3),
            "prerequisite_reason": "前置知识已满足" if predecessors[kid] else "可作为学习起点",
            "competition_reason": f"面向 {ctx.competition_goal}；{'目标相关主题' if goal else '通用生物基础'}",
            "competency_reason": f"相关能力缺口 {competency_gap:.0%}",
            "why_now": "已到复习时间"
            if forgetting >= 0.8
            else "当前时间预算与难度匹配；先补基础"
            if bridge
            else "当前知识缺口优先，且前置条件允许",
            "difficulty_bridge": bridge,
            "score_components": {
                "knowledge_gap": gap * 0.2,
                "prerequisite_priority": prerequisite_priority * 0.2,
                "competency_gap": competency_gap * 0.15,
                "competition_relevance": goal * 0.15,
                "forgetting_risk": forgetting * 0.1,
                "recent_error_signal": recent_error * 0.1,
                "schedule_fit": fit * 0.1,
            },
        }
        result.append(
            {
                "knowledge_id": kid,
                "title": f"{node.name} · {'基础桥接' if bridge else '机制与数据' if level >= 4 else '概念与应用'}",
                "description": f"{style}。{detail}",
                "task_type": task_type,
                "question_ids": [] if bridge else [q.id for q in candidates[:1]],
                "priority": round(score, 5),
                "reason": reason,
            }
        )
    return ctx, sorted(result, key=lambda r: (-r["priority"], r["title"]))


def recalculate(db, student_id, as_of=None):
    ctx, ranked = recommendations(db, student_id, as_of)
    from app.services.lessons import course_recommendation

    course = course_recommendation(db, student_id, calculation_time(as_of))
    if course:
        ranked = [course] + [item for item in ranked if item["knowledge_id"] != course["knowledge_id"]]
    if as_of:
        return {"preview": True, "learning_context_id": ctx.id, "recommendations": ranked[:20]}
    from app.models import now

    today = now().date()
    for old in db.scalars(select(WeeklyPlan).where(WeeklyPlan.student_id == student_id, WeeklyPlan.status == "ACTIVE")):
        old.status = "SUPERSEDED"
    days = ctx.preferred_learning_days
    if ctx.target_exam_date:
        days = max(1, min(days, (ctx.target_exam_date - today).days + 1))
    budget = int(ctx.weekly_hours * 60)
    per_day = max(1, budget // days)
    selected = ranked[: min(len(ranked), days * 2)]
    plan = WeeklyPlan(
        student_id=student_id,
        learning_context_id=ctx.id,
        week_no=today.isocalendar().week,
        start_date=today,
        end_date=today + timedelta(days=6),
        objectives=[r["title"] for r in selected],
        estimated_minutes=0,
    )
    db.add(plan)
    db.flush()
    tasks = []
    for index, rec in enumerate(selected):
        day_offset = min(index // 2, days - 1)
        minutes = min(rec.get("estimated_minutes", max(1, per_day // 2)), budget - plan.estimated_minutes)
        if rec.get("estimated_minutes", 0) > minutes:
            # Keep a complete lesson estimate; skip if this week cannot fit it.
            continue
        if minutes <= 0:
            break
        task = Task(
            student_id=student_id,
            weekly_plan_id=plan.id,
            task_date=today + timedelta(days=day_offset),
            task_type=rec["task_type"],
            title=rec["title"],
            description=rec["description"],
            knowledge_ids=[rec["knowledge_id"]],
            question_ids=rec["question_ids"],
            estimated_minutes=minutes,
            priority=rec["priority"],
            reason=rec["reason"],
        )
        plan.estimated_minutes += minutes
        db.add(task)
        tasks.append(task)
    db.flush()
    return {"plan": row(plan), "tasks": [row(t) for t in tasks]}
