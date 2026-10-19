from datetime import date, datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EducationStage(StrEnum):
    PRIMARY = "PRIMARY"
    G7 = "G7"
    G8 = "G8"
    G9 = "G9"
    G10 = "G10"
    G11 = "G11"
    G12 = "G12"
    UNIVERSITY = "UNIVERSITY"
    ADULT = "ADULT"
    OTHER = "OTHER"


class BiologyLevel(StrEnum):
    L0 = "L0_ZERO"
    L1 = "L1_FOUNDATION"
    L2 = "L2_JUNIOR"
    L3 = "L3_HIGH_SCHOOL"
    L4 = "L4_OLYMPIAD_FOUNDATION"
    L5 = "L5_OLYMPIAD_INTENSIVE"
    L6 = "L6_ADVANCED"
    L7 = "L7_UNIVERSITY"


class Goal(StrEnum):
    NONE = "NONE"
    SCHOOL = "SCHOOL"
    LOCAL = "LOCAL"
    PROVINCIAL = "PROVINCIAL"
    NATIONAL_LEAGUE = "NATIONAL_LEAGUE"
    NATIONAL_COMPETITION = "NATIONAL_COMPETITION"
    IBO = "IBO"
    RESEARCH = "RESEARCH"


class Register(Input):
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    password: str = Field(min_length=10, max_length=128)
    name: str = Field(min_length=1, max_length=100)

    @field_validator("email")
    @classmethod
    def normalize(cls, value):
        return value.strip().lower()


class Login(Input):
    email: str = Field(max_length=254)
    password: str = Field(max_length=128)


class StudentInput(Input):
    name: str = Field(min_length=1, max_length=100)


class ContextInput(Input):
    education_stage: EducationStage
    school_grade: int = Field(ge=0, le=20)
    biology_level: BiologyLevel
    competition_goal: Goal
    target_exam_date: date | None = None
    weekly_hours: float = Field(default=3, gt=0, le=60)
    preferred_learning_days: int = Field(default=5, ge=1, le=7)
    learning_preferences: dict = Field(default_factory=dict)


class Grant(Input):
    email: str
    role: Literal["PARENT", "TEACHER", "VIEWER"]


class Scoped(Input):
    student_id: UUID
    learning_context_id: UUID


class AttemptInput(Scoped):
    event_id: UUID
    answer: list[str] = Field(max_length=20)
    confidence: float = Field(default=0.5, ge=0, le=1)
    time_seconds: int = Field(default=0, ge=0, le=86400)
    task_id: UUID | None = None


class DiagnosticAnswer(AttemptInput):
    question_id: UUID


class EventInput(Scoped):
    id: UUID
    event_type: Literal["LEARNING_START", "LEARNING_COMPLETE", "QUESTION_VIEW", "REVIEW", "REFLECTION"]
    task_id: UUID | None = None
    knowledge_id: UUID | None = None
    payload: dict = Field(default_factory=dict)
    duration_seconds: int = Field(default=0, ge=0, le=86400)


class PlanInput(Input):
    as_of: datetime | None = None


class TutorStart(Scoped):
    question_id: UUID | None = None
    task_id: UUID | None = None


class TutorMessage(Input):
    session_id: UUID
    message: str = Field(min_length=1, max_length=4000)
    request_hint: bool = False


class AIRequest(Input):
    question_id: UUID | None = None
    knowledge_ids: list[UUID] = Field(default_factory=list, max_length=20)
    target_grade: int = Field(default=8, ge=0, le=20)
    target_biology_level: BiologyLevel = BiologyLevel.L1
    target_goal: Goal = Goal.NONE
    variant_type: Literal[
        "GRADE_DOWN",
        "GRADE_UP",
        "CONCEPT_REINFORCEMENT",
        "PREREQUISITE",
        "TRANSFER",
        "EXPERIMENT",
        "DATA_ANALYSIS",
        "COMPETITION",
    ] = "CONCEPT_REINFORCEMENT"
    instructions: str = Field(default="", max_length=4000)


class GeneratedQuestion(Input):
    stem: str = Field(min_length=10, max_length=10000)
    question_type: Literal["SINGLE_CHOICE", "MULTIPLE_CHOICE", "TRUE_FALSE"]
    options: dict[str, str] = Field(min_length=2, max_length=8)
    answer: list[str] = Field(min_length=1, max_length=8)
    explanation: str = Field(min_length=10)
    knowledge_ids: list[str] = Field(min_length=1)
    prerequisites: list[str] = Field(default_factory=list)
    learning_difficulty: int = Field(ge=0, le=7)
    competition_difficulty: int = Field(ge=0, le=7)


class AIAnalysis(Input):
    explanation: str = Field(min_length=10)
    knowledge_ids: list[str]
    prerequisites: list[str]
    learning_difficulty: int = Field(ge=0, le=7)
    competition_difficulty: int = Field(ge=0, le=7)
    error_type: str | None = None
    misconception: str | None = None


class ReviewInput(Input):
    decision: Literal["REVIEWED", "PUBLISHED", "ARCHIVED"]
    note: str = Field(min_length=5, max_length=2000)


class QuestionEdit(Input):
    stem: str = Field(min_length=5)
    answer: list[str] = Field(min_length=1)
    explanation: str = Field(min_length=5)
    options: dict[str, str] = Field(min_length=2)


class ExperimentInput(Scoped):
    hypothesis: str = Field(min_length=1, max_length=4000)
    variables: str = Field(min_length=1, max_length=4000)
    observations: str = Field(min_length=1, max_length=10000)
    conclusion: str = Field(min_length=1, max_length=4000)


class EdgeInput(Input):
    source_knowledge_id: UUID
    target_knowledge_id: UUID
    relation_type: Literal[
        "PART_OF",
        "PREREQUISITE_OF",
        "RELATED_TO",
        "EXTENDS",
        "CONTRASTS_WITH",
        "APPLIED_BY",
        "TESTED_BY",
        "REQUIRES_SKILL",
    ]
    weight: float = Field(default=1, gt=0, le=1)
