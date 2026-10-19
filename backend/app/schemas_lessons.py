from typing import Literal
from uuid import UUID
from pydantic import Field, model_validator
from app.schemas import Input


class Section(Input):
    id: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=2, max_length=120)
    text: str = Field(min_length=30, max_length=12000)


class Example(Input):
    prompt: str = Field(min_length=5)
    reasoning: str = Field(min_length=20)


class Misunderstanding(Input):
    claim: str = Field(min_length=5)
    correction: str = Field(min_length=15)


class Check(Input):
    id: str = Field(min_length=1, max_length=40)
    stem: str = Field(min_length=5)
    options: dict[str, str] = Field(min_length=2, max_length=6)
    answer: str
    explanation: str = Field(min_length=15)
    cognitive_level: int = Field(ge=0, le=4)
    competency_code: str
    revisit_section: str
    prerequisite_code: str | None = None
    evidence_kind: Literal["STANDARD", "TRANSFER", "EXPERIMENT"] = "STANDARD"

    @model_validator(mode="after")
    def valid(self):
        if self.answer not in self.options or len(set(self.options.values())) != len(self.options):
            raise ValueError("答案必须属于选项，选项内容不能重复")
        return self


class Diagram(Input):
    kind: Literal["CELL", "MEMBRANE", "DIFFUSION", "OSMOSIS", "TISSUES"]
    caption: str = Field(min_length=10)
    labels: list[str] = Field(min_length=2, max_length=8)


class LessonDocument(Input):
    title: str = Field(min_length=3, max_length=200)
    summary: str = Field(min_length=15)
    objectives: list[str] = Field(min_length=2, max_length=8)
    estimated_minutes: int = Field(ge=5, le=90)
    prerequisites: list[str] = Field(default_factory=list)
    sections: list[Section] = Field(min_length=3, max_length=12)
    diagram: Diagram
    examples: list[Example] = Field(min_length=1, max_length=6)
    misconceptions: list[Misunderstanding] = Field(min_length=2, max_length=8)
    checks: list[Check] = Field(min_length=4, max_length=12)
    pass_ratio: float = Field(default=0.8, ge=0.6, le=1)
    adaptations: dict[str, str]
    sources: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def consistent(self):
        sections = {s.id for s in self.sections}
        if len(sections) != len(self.sections) or len({q.id for q in self.checks}) != len(self.checks):
            raise ValueError("章节与检测题编号不可重复")
        for q in self.checks:
            if q.revisit_section not in sections:
                raise ValueError("错题补习必须指向本课已有章节")
            if q.prerequisite_code and q.prerequisite_code not in self.prerequisites:
                raise ValueError("前置检测题必须关联本课前置知识")
        if not {"junior", "senior"} <= self.adaptations.keys():
            raise ValueError("必须提供低年级和高年级两种引导")
        return self


class StartLesson(Input):
    learning_context_id: UUID
    task_id: UUID | None = None
    mode: Literal["STUDY", "CHECK"] = "STUDY"


class LessonAnswer(Input):
    question_id: UUID
    event_id: UUID
    answer: list[str] = Field(min_length=1, max_length=1)
    confidence: float = Field(default=0.7, ge=0, le=1)
    time_seconds: int = Field(default=0, ge=0, le=3600)


class LessonNotes(Input):
    notes: str = Field(default="", max_length=12000)


class ReviseLesson(Input):
    document: LessonDocument
