from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class TokenUsage(BaseModel):
    input: int = 0
    output: int = 0


class GenerationOutput(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    output_id: str
    chart_id: str
    dataset_source: str
    model_id: str
    variant: int
    enabled_features: list[str]
    include_image: bool
    generated_description: str
    parsed_output: dict | None = None
    tokens_used: TokenUsage
    latency_ms: float
    created_at: datetime


class GenerationRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    chart_id: str
    model_id: str
    enabled_features: list[str]
    include_image: bool = True
    # 1/2/3 are informational only — the server recomputes the actual
    # condition from enabled_features + include_image (see
    # prompt_service.classify_variant), since datasets vary in what
    # metadata they have. 4 (metadata withheld) is the one value that's
    # honored as sent, since it can't be derived from a checkbox state.
    variant: int = 1
    custom_prompt_suffix: str | None = None
