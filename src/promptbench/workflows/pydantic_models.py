from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ReviewFindingOutput(BaseModel):
    severity: str = Field(default="info")
    code: str | None = None
    message: str
    suggestion: str | None = None
    location: str | None = None


class ReviewModelOutput(BaseModel):
    findings: list[ReviewFindingOutput] = Field(default_factory=list)


class EvalMetricOutput(BaseModel):
    metric_name: str
    metric_value: float
    weight: float | None = None


class EvalModelOutput(BaseModel):
    score: float = 0.0
    metrics: list[EvalMetricOutput] = Field(default_factory=list)
    assertions_passed: list[str] = Field(default_factory=list)
    assertions_failed: list[str] = Field(default_factory=list)


class EnhanceModelOutput(BaseModel):
    suggestions: list[str] = Field(default_factory=list)
    revised_content: str | None = None


class SuggestionListOutput(BaseModel):
    suggestions: list[str] = Field(default_factory=list)


class EvalSeedTestOutput(BaseModel):
    id: str | None = None
    prompt: str
    expected: dict[str, Any] = Field(default_factory=dict)
    references: list[str] = Field(default_factory=list)


class EvalSeedModelOutput(BaseModel):
    tests: list[EvalSeedTestOutput] = Field(default_factory=list)
