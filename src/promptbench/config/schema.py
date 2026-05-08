from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class ArtifactType(StrEnum):
    SKILLS = "skills"
    PROMPTS = "prompts"
    AGENTS = "agents"
    TOOLS = "tools"


class ObjectLimits(BaseModel):
    max_line_count: int | None = None
    max_token_count: int | None = None


class EvalPrompt(BaseModel):
    id: str | None = None
    language: str | None = None
    text: str


class EvalTest(BaseModel):
    id: str | None = None
    prompt: str | None = None
    prompts: list[EvalPrompt | str] = Field(default_factory=list)
    model: str | None = None
    fallback_models: list[str] | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)
    expected: dict[str, Any] = Field(default_factory=dict)
    references: list[str] = Field(default_factory=list)
    object_limits: ObjectLimits | None = None


class EvalDefinition(BaseModel):
    id: str
    artifact_type: ArtifactType
    target: str
    model: str | None = None
    fallback_models: list[str] | None = None
    randomize_model: bool = False
    object_limits: ObjectLimits | None = None
    tests: list[EvalTest] = Field(default_factory=list)

    # Legacy single-test shape support.
    prompt: str | None = None
    prompts: list[EvalPrompt | str] = Field(default_factory=list)
    rubric: dict[str, Any] = Field(default_factory=dict)
    inputs: dict[str, Any] = Field(default_factory=dict)
    expected: dict[str, Any] = Field(default_factory=dict)
    references: list[str] = Field(default_factory=list)


class ArtifactConfig(BaseModel):
    root_path: str
    improve_references: bool = False
    improve_scripts: bool = False
    evals: list[EvalDefinition] = Field(default_factory=list)


class ArtifactsConfig(BaseModel):
    skills: ArtifactConfig = Field(
        default_factory=lambda: ArtifactConfig(root_path="skills/")
    )
    prompts: ArtifactConfig = Field(
        default_factory=lambda: ArtifactConfig(root_path="prompts/")
    )
    agents: ArtifactConfig = Field(
        default_factory=lambda: ArtifactConfig(root_path="agents/")
    )
    tools: ArtifactConfig = Field(
        default_factory=lambda: ArtifactConfig(root_path="tools/")
    )


class ObjectsConfig(BaseModel):
    defaults: ObjectLimits = Field(default_factory=ObjectLimits)
    skills: ObjectLimits = Field(default_factory=ObjectLimits)
    prompts: ObjectLimits = Field(default_factory=ObjectLimits)
    agents: ObjectLimits = Field(default_factory=ObjectLimits)
    tools: ObjectLimits = Field(default_factory=ObjectLimits)


class ProviderDefaults(BaseModel):
    timeout_seconds: int = 60
    max_retries: int = 3
    temperature: float = 0.2


class ProviderConfig(BaseModel):
    kind: str
    base_url: str
    api_key_env: str
    max_concurrency: int | None = None


class WorkflowProviderConfig(BaseModel):
    provider_kind: str
    model: str
    fallback_models: list[str] | None = None


class ProvidersConfig(BaseModel):
    default_kind: str = "openai-compatible"
    defaults: ProviderDefaults = Field(default_factory=ProviderDefaults)
    registry: dict[str, ProviderConfig] = Field(default_factory=dict)
    workflows: dict[str, WorkflowProviderConfig] = Field(default_factory=dict)


class ReviewWorkflowConfig(BaseModel):
    enabled: bool = True
    max_findings: int = 25


class EvalWorkflowConfig(BaseModel):
    enabled: bool = True
    metrics: list[str] = Field(default_factory=list)
    pass_threshold: float = 0.8
    definition_mode: str = "discover"
    discover_path: str = "evals/"
    inline: list[EvalDefinition] = Field(default_factory=list)


class EnhanceWorkflowConfig(BaseModel):
    enabled: bool = True
    write_mode: str = "suggestion-only"
    run_in_eval_loop: bool = True


class WorkflowsConfig(BaseModel):
    review: ReviewWorkflowConfig = Field(default_factory=ReviewWorkflowConfig)
    eval: EvalWorkflowConfig = Field(default_factory=EvalWorkflowConfig)
    enhance: EnhanceWorkflowConfig = Field(default_factory=EnhanceWorkflowConfig)


class OutputConfig(BaseModel):
    database_path: str = ".promptbench/promptbench.db"
    overwrite: bool = False
    reports_dir: str = ".promptbench/reports"


class PoliciesConfig(BaseModel):
    fail_on_severity: str = "error"
    fail_on_score_below: float = 0.7
    max_workers: int = 1
    require_model_success: bool = True
    log_verbosity: str = "normal"


class ProjectConfig(BaseModel):
    name: str = "project"
    root: str = "."


class PromptBenchConfig(BaseModel):
    version: int = 1
    project: ProjectConfig = Field(default_factory=ProjectConfig)
    objects: ObjectsConfig = Field(default_factory=ObjectsConfig)
    artifacts: ArtifactsConfig = Field(default_factory=ArtifactsConfig)
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)
    workflows: WorkflowsConfig = Field(default_factory=WorkflowsConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    policies: PoliciesConfig = Field(default_factory=PoliciesConfig)

    def project_root(self, base_dir: Path) -> Path:
        root = Path(self.project.root)
        if root.is_absolute():
            return root
        return (base_dir / root).resolve()
