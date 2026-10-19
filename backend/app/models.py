import uuid
from datetime import datetime, timezone, date
from sqlalchemy import String, Text, ForeignKey, UniqueConstraint, JSON, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base

J = JSON().with_variant(JSONB(), "postgresql")


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Entity:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)


class User(Entity, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(String(100))
    is_admin: Mapped[bool] = mapped_column(default=False)


class Student(Entity, Base):
    __tablename__ = "students"
    name: Mapped[str] = mapped_column(String(100))


class UserStudent(Entity, Base):
    __tablename__ = "user_students"
    __table_args__ = (UniqueConstraint("user_id", "student_id"),)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    role: Mapped[str] = mapped_column(String(20), default="OWNER")


class LearningContext(Entity, Base):
    __tablename__ = "learning_contexts"
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    education_stage: Mapped[str] = mapped_column(String(20))
    school_grade: Mapped[int] = mapped_column()
    biology_level: Mapped[str] = mapped_column(String(40))
    competition_goal: Mapped[str] = mapped_column(String(40))
    target_exam_date: Mapped[date | None] = mapped_column()
    weekly_hours: Mapped[float] = mapped_column(default=3)
    preferred_learning_days: Mapped[int] = mapped_column(default=5)
    learning_preferences: Mapped[dict] = mapped_column(J, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="active")
    updated_at: Mapped[datetime] = mapped_column(default=now, onupdate=now)


class Domain(Entity, Base):
    __tablename__ = "knowledge_domains"
    code: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(100))


class Knowledge(Entity, Base):
    __tablename__ = "knowledge_points"
    code: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="")
    domain_id: Mapped[str] = mapped_column(ForeignKey("knowledge_domains.id"))
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("knowledge_points.id"))
    level: Mapped[int] = mapped_column(default=1)
    goals: Mapped[list] = mapped_column(J, default=list)
    status: Mapped[str] = mapped_column(String(30), default="PUBLISHED")


class KnowledgeLevel(Entity, Base):
    __tablename__ = "knowledge_levels"
    __table_args__ = (UniqueConstraint("knowledge_id", "level"),)
    knowledge_id: Mapped[str] = mapped_column(ForeignKey("knowledge_points.id"))
    level: Mapped[int] = mapped_column()
    objective: Mapped[str] = mapped_column(Text)


class Edge(Entity, Base):
    __tablename__ = "knowledge_edges"
    __table_args__ = (UniqueConstraint("source_knowledge_id", "target_knowledge_id", "relation_type"),)
    source_knowledge_id: Mapped[str] = mapped_column(ForeignKey("knowledge_points.id"))
    target_knowledge_id: Mapped[str] = mapped_column(ForeignKey("knowledge_points.id"))
    relation_type: Mapped[str] = mapped_column(String(30), default="PREREQUISITE_OF")
    weight: Mapped[float] = mapped_column(default=1)


class Competency(Entity, Base):
    __tablename__ = "competencies"
    code: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(100))


class QuestionSource(Entity, Base):
    __tablename__ = "question_sources"
    code: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(200))


class Paper(Entity, Base):
    __tablename__ = "question_papers"
    code: Mapped[str] = mapped_column(String(100), unique=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("question_sources.id"))
    title: Mapped[str] = mapped_column(String(200))
    year: Mapped[int | None] = mapped_column()
    metadata_json: Mapped[dict] = mapped_column(J, default=dict)


class Question(Entity, Base):
    __tablename__ = "questions"
    __table_args__ = (UniqueConstraint("paper_id", "source_question_no"),)
    paper_id: Mapped[str] = mapped_column(ForeignKey("question_papers.id"), index=True)
    source_question_no: Mapped[int] = mapped_column()
    question_type: Mapped[str] = mapped_column(String(40))
    stem: Mapped[str | None] = mapped_column(Text)
    answer: Mapped[list | None] = mapped_column(J)
    explanation: Mapped[str | None] = mapped_column(Text)
    competition_difficulty: Mapped[int] = mapped_column(default=1)
    learning_difficulty: Mapped[int] = mapped_column(default=1)
    conceptual_difficulty: Mapped[int] = mapped_column(default=1)
    prerequisite_depth: Mapped[int] = mapped_column(default=0)
    data_complexity: Mapped[int] = mapped_column(default=0)
    mathematical_complexity: Mapped[int] = mapped_column(default=0)
    abstraction_level: Mapped[int] = mapped_column(default=0)
    estimated_minutes: Mapped[int] = mapped_column(default=3)
    status: Mapped[str] = mapped_column(String(30), default="REVIEW_REQUIRED", index=True)
    metadata_json: Mapped[dict] = mapped_column(J, default=dict)


class Option(Entity, Base):
    __tablename__ = "question_options"
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    label: Mapped[str] = mapped_column(String(10))
    text: Mapped[str] = mapped_column(Text)


class QuestionKnowledge(Entity, Base):
    __tablename__ = "question_knowledge"
    __table_args__ = (UniqueConstraint("question_id", "knowledge_id", "relation_type"),)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    knowledge_id: Mapped[str] = mapped_column(ForeignKey("knowledge_points.id"), index=True)
    relation_type: Mapped[str] = mapped_column(String(30), default="CORE")
    importance: Mapped[float] = mapped_column(default=1)


class QuestionCompetency(Entity, Base):
    __tablename__ = "question_competency"
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    competency_id: Mapped[str] = mapped_column(ForeignKey("competencies.id"))
    weight: Mapped[float] = mapped_column(default=1)


class Variant(Entity, Base):
    __tablename__ = "question_variants"
    parent_question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"))
    content: Mapped[dict] = mapped_column(J)
    status: Mapped[str] = mapped_column(String(30), default="REVIEW_REQUIRED")


class Diagnostic(Entity, Base):
    __tablename__ = "diagnostics"
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    learning_context_id: Mapped[str] = mapped_column(ForeignKey("learning_contexts.id"))
    question_ids: Mapped[list] = mapped_column(J)
    answers: Mapped[dict] = mapped_column(J, default=dict)
    result: Mapped[dict | None] = mapped_column(J)
    status: Mapped[str] = mapped_column(String(30), default="IN_PROGRESS")


class LearningEvent(Entity, Base):
    __tablename__ = "learning_events"
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    learning_context_id: Mapped[str] = mapped_column(ForeignKey("learning_contexts.id"))
    task_id: Mapped[str | None] = mapped_column(ForeignKey("daily_tasks.id"))
    question_id: Mapped[str | None] = mapped_column(ForeignKey("questions.id"))
    knowledge_id: Mapped[str | None] = mapped_column(ForeignKey("knowledge_points.id"))
    competency_id: Mapped[str | None] = mapped_column(ForeignKey("competencies.id"))
    event_type: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict] = mapped_column(J, default=dict)
    duration_seconds: Mapped[int] = mapped_column(default=0)


class Attempt(Entity, Base):
    __tablename__ = "question_attempts"
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"))
    task_id: Mapped[str | None] = mapped_column(ForeignKey("daily_tasks.id"))
    event_id: Mapped[str] = mapped_column(ForeignKey("learning_events.id"), unique=True)
    answer: Mapped[list] = mapped_column(J)
    is_correct: Mapped[bool] = mapped_column()
    confidence: Mapped[float] = mapped_column()
    time_seconds: Mapped[int] = mapped_column()
    hint_count: Mapped[int] = mapped_column(default=0)
    attempt_no: Mapped[int] = mapped_column()
    error_type: Mapped[str | None] = mapped_column(String(50))


class Evidence(Entity, Base):
    __tablename__ = "mastery_evidence"
    __table_args__ = (UniqueConstraint("event_id", "target_type", "target_id"),)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("learning_events.id"), index=True)
    target_type: Mapped[str] = mapped_column(String(20))
    target_id: Mapped[str] = mapped_column(String(36), index=True)
    cognitive_level: Mapped[int] = mapped_column(default=0)
    delta: Mapped[float] = mapped_column()
    is_correct: Mapped[bool] = mapped_column()
    explanation: Mapped[str] = mapped_column(Text)


class Mastery(Entity, Base):
    __tablename__ = "student_knowledge_mastery"
    __table_args__ = (UniqueConstraint("student_id", "knowledge_id"),)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    knowledge_id: Mapped[str] = mapped_column(ForeignKey("knowledge_points.id"))
    scores: Mapped[list] = mapped_column(J, default=lambda: [0] * 5)
    overall_score: Mapped[float] = mapped_column(default=0)
    confidence: Mapped[float] = mapped_column(default=0)
    exposure_count: Mapped[int] = mapped_column(default=0)
    correct_count: Mapped[int] = mapped_column(default=0)
    incorrect_count: Mapped[int] = mapped_column(default=0)
    recent_accuracy: Mapped[float] = mapped_column(default=0)
    forgetting_risk: Mapped[float] = mapped_column(default=0)
    last_review_at: Mapped[datetime | None] = mapped_column()
    next_review_at: Mapped[datetime | None] = mapped_column()
    updated_at: Mapped[datetime] = mapped_column(default=now)


class CompetencyMastery(Entity, Base):
    __tablename__ = "student_competency_mastery"
    __table_args__ = (UniqueConstraint("student_id", "competency_id"),)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    competency_id: Mapped[str] = mapped_column(ForeignKey("competencies.id"))
    score: Mapped[float] = mapped_column(default=0)
    confidence: Mapped[float] = mapped_column(default=0)
    evidence_count: Mapped[int] = mapped_column(default=0)
    recent_score: Mapped[float] = mapped_column(default=0)
    updated_at: Mapped[datetime] = mapped_column(default=now)


class Misconception(Entity, Base):
    __tablename__ = "misconceptions"
    code: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    correct_concept: Mapped[str] = mapped_column(Text)
    severity: Mapped[int] = mapped_column(default=1)


class Curriculum(Entity, Base):
    __tablename__ = "curriculums"
    code: Mapped[str] = mapped_column(String(100), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    template_weeks: Mapped[int] = mapped_column()


class Unit(Entity, Base):
    __tablename__ = "curriculum_units"
    curriculum_id: Mapped[str] = mapped_column(ForeignKey("curriculums.id"))
    sequence: Mapped[int] = mapped_column()
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    knowledge_ids: Mapped[list] = mapped_column(J, default=list)


class Objective(Entity, Base):
    __tablename__ = "learning_objectives"
    unit_id: Mapped[str] = mapped_column(ForeignKey("curriculum_units.id"))
    text: Mapped[str] = mapped_column(Text)


class Resource(Entity, Base):
    __tablename__ = "learning_resources"
    knowledge_id: Mapped[str] = mapped_column(ForeignKey("knowledge_points.id"))
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    min_grade: Mapped[int] = mapped_column(default=0)
    max_grade: Mapped[int] = mapped_column(default=20)
    level: Mapped[int] = mapped_column(default=1)


class WeeklyPlan(Entity, Base):
    __tablename__ = "weekly_plans"
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    learning_context_id: Mapped[str] = mapped_column(ForeignKey("learning_contexts.id"))
    week_no: Mapped[int] = mapped_column()
    start_date: Mapped[date] = mapped_column()
    end_date: Mapped[date] = mapped_column()
    objectives: Mapped[list] = mapped_column(J)
    estimated_minutes: Mapped[int] = mapped_column()
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE")


class Task(Entity, Base):
    __tablename__ = "daily_tasks"
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    weekly_plan_id: Mapped[str] = mapped_column(ForeignKey("weekly_plans.id"))
    task_date: Mapped[date] = mapped_column(index=True)
    task_type: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    knowledge_ids: Mapped[list] = mapped_column(J)
    question_ids: Mapped[list] = mapped_column(J)
    estimated_minutes: Mapped[int] = mapped_column()
    priority: Mapped[float] = mapped_column()
    reason: Mapped[dict] = mapped_column(J)
    mastery_target: Mapped[float] = mapped_column(default=0.6)
    status: Mapped[str] = mapped_column(String(30), default="TODO")


class Experiment(Entity, Base):
    __tablename__ = "experiments"
    code: Mapped[str] = mapped_column(String(80), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    safety: Mapped[str] = mapped_column(Text)


class ExperimentStep(Entity, Base):
    __tablename__ = "experiment_steps"
    experiment_id: Mapped[str] = mapped_column(ForeignKey("experiments.id"))
    sequence: Mapped[int] = mapped_column()
    instruction: Mapped[str] = mapped_column(Text)


class ExperimentVariable(Entity, Base):
    __tablename__ = "experiment_variables"
    experiment_id: Mapped[str] = mapped_column(ForeignKey("experiments.id"))
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(30))


class Observation(Entity, Base):
    __tablename__ = "experiment_observations"
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    experiment_id: Mapped[str] = mapped_column(ForeignKey("experiments.id"))
    event_id: Mapped[str] = mapped_column(ForeignKey("learning_events.id"))
    data: Mapped[dict] = mapped_column(J)


class ExperimentResult(Entity, Base):
    __tablename__ = "experiment_results"
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    observation_id: Mapped[str] = mapped_column(ForeignKey("experiment_observations.id"))
    conclusion: Mapped[str] = mapped_column(Text)


class TutorSession(Entity, Base):
    __tablename__ = "tutor_sessions"
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    learning_context_id: Mapped[str] = mapped_column(ForeignKey("learning_contexts.id"))
    question_id: Mapped[str | None] = mapped_column(ForeignKey("questions.id"))
    task_id: Mapped[str | None] = mapped_column(ForeignKey("daily_tasks.id"))
    hint_level: Mapped[int] = mapped_column(default=0)
    messages: Mapped[list] = mapped_column(J, default=list)


class AIContent(Entity, Base):
    __tablename__ = "ai_contents"
    requested_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    purpose: Mapped[str] = mapped_column(String(40))
    content: Mapped[dict] = mapped_column(J)
    trace: Mapped[dict] = mapped_column(J)
    status: Mapped[str] = mapped_column(String(30), default="REVIEW_REQUIRED")
    reviewer_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))


class Audit(Entity, Base):
    __tablename__ = "audit_logs"
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    student_id: Mapped[str | None] = mapped_column(ForeignKey("students.id"), index=True)
    action: Mapped[str] = mapped_column(String(80))
    details: Mapped[dict] = mapped_column(J, default=dict)


class Lesson(Entity, Base):
    __tablename__ = "lessons"
    code: Mapped[str] = mapped_column(String(100), unique=True)
    unit_code: Mapped[str] = mapped_column(String(100), index=True)
    unit_title: Mapped[str] = mapped_column(String(200))
    sequence: Mapped[int] = mapped_column()
    knowledge_id: Mapped[str] = mapped_column(ForeignKey("knowledge_points.id"))
    tier: Mapped[str] = mapped_column(String(30))
    min_level: Mapped[int] = mapped_column()
    max_level: Mapped[int] = mapped_column()


class LessonRevision(Entity, Base):
    __tablename__ = "lesson_revisions"
    __table_args__ = (UniqueConstraint("lesson_id", "version"),)
    lesson_id: Mapped[str] = mapped_column(ForeignKey("lessons.id"), index=True)
    version: Mapped[int] = mapped_column()
    document: Mapped[dict] = mapped_column(J)
    status: Mapped[str] = mapped_column(String(30), default="REVIEW_REQUIRED")
    reviewer_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    published_at: Mapped[datetime | None] = mapped_column()


class LessonRun(Entity, Base):
    __tablename__ = "lesson_runs"
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    learning_context_id: Mapped[str] = mapped_column(ForeignKey("learning_contexts.id"))
    revision_id: Mapped[str] = mapped_column(ForeignKey("lesson_revisions.id"))
    task_id: Mapped[str | None] = mapped_column(ForeignKey("daily_tasks.id"))
    mode: Mapped[str] = mapped_column(String(20), default="STUDY")
    status: Mapped[str] = mapped_column(String(30), default="IN_PROGRESS")
    question_ids: Mapped[list] = mapped_column(J)
    answers: Mapped[dict] = mapped_column(J, default=dict)
    notes: Mapped[str] = mapped_column(Text, default="")
    result: Mapped[dict | None] = mapped_column(J)
    completed_at: Mapped[datetime | None] = mapped_column()
