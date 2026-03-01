from __future__ import annotations

from pydantic import BaseModel, Field


class KeyPoint(BaseModel):
    title: str
    bullets: list[str] = Field(default_factory=list)
    time_anchor: str


class ExamPoint(BaseModel):
    level: str
    point: str
    time_anchor: str


class Formula(BaseModel):
    expr: str
    meaning: str
    pitfalls: str
    time_anchor: str


class ProblemPattern(BaseModel):
    trigger: str
    method: str
    steps: list[str] = Field(default_factory=list)
    time_anchor: str


class ExampleItem(BaseModel):
    prompt: str
    skeleton_solution: str
    time_anchor: str


class GlossaryItem(BaseModel):
    term: str
    definition: str
    time_anchor: str


class ChunkSummary(BaseModel):
    key_points: list[KeyPoint] = Field(default_factory=list)
    exam_points: list[ExamPoint] = Field(default_factory=list)
    formulas: list[Formula] = Field(default_factory=list)
    problem_patterns: list[ProblemPattern] = Field(default_factory=list)
    examples: list[ExampleItem] = Field(default_factory=list)
    glossary: list[GlossaryItem] = Field(default_factory=list)
    uncertain: list[str] = Field(default_factory=list)
