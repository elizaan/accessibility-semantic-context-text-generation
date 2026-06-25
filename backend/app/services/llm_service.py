"""
Orchestrates generation: builds prompt → calls LLM → saves output JSON.

Every call is STATELESS — each run sends exactly [SystemMessage, HumanMessage]
with no conversation history. Variant N never sees Variant N-1's output.

Output files: outputs/runs/<chart_id>/<output_id>.json
"""

from __future__ import annotations
import base64
import json
import re
import time
import uuid
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import settings
from app.core.llm_manager import get_llm, is_vision_capable
from app.models.chart import Chart
from app.models.output import GenerationOutput, GenerationRequest, TokenUsage
from app.services.prompt_service import build_prompt


def generate(chart: Chart, req: GenerationRequest) -> GenerationOutput:
    system_prompt, user_prompt = build_prompt(
        chart=chart,
        enabled_features=req.enabled_features,
        include_image=req.include_image,
        variant=req.variant,
        custom_suffix=req.custom_prompt_suffix,
    )

    llm = get_llm(req.model_id)

    # Build user message — attach image only for vision-capable models.
    # Text-only models (Gemma) silently skip the image regardless of request.
    # SystemMessage is always sent fresh; no prior messages ever included.
    attach_image = req.include_image and is_vision_capable(req.model_id)
    if attach_image and chart.image_path:
        image_path = settings.datasets_dir / chart.image_path
        if image_path.exists():  # noqa: SIM102
            img_bytes = image_path.read_bytes()
            b64 = base64.standard_b64encode(img_bytes).decode()
            mime = "image/jpeg" if image_path.suffix.lower() in (".jpg", ".jpeg") else "image/png"
            user_content: list = [
                {"type": "text", "text": user_prompt},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
            ]
        else:
            user_content = [{"type": "text", "text": user_prompt}]
    else:
        user_content = user_prompt  # type: ignore[assignment]

    # Single-turn, stateless — exactly two messages every time
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_content),
    ]

    t0 = time.monotonic()
    response = llm.invoke(messages)
    latency_ms = (time.monotonic() - t0) * 1000

    raw_text = str(response.content)
    parsed = _extract_json(raw_text)

    output = GenerationOutput(
        output_id=str(uuid.uuid4()),
        chart_id=chart.chart_id,
        dataset_source=chart.source,
        model_id=req.model_id,
        variant=req.variant,
        enabled_features=req.enabled_features,
        include_image=attach_image,
        generated_description=raw_text,
        parsed_output=parsed,
        tokens_used=_extract_usage(response),
        latency_ms=latency_ms,
        created_at=datetime.now(timezone.utc),
    )

    _save_output(output)
    return output


def _extract_json(text: str) -> dict | None:
    """Try to parse JSON from model response, handling markdown code fences."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Strip ```json ... ``` fences
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    # Find the outermost { ... } block
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
    return None


def _extract_usage(response) -> TokenUsage:
    meta = getattr(response, "response_metadata", {}) or {}
    usage_raw = meta.get("usage", meta.get("token_usage", {})) or {}
    return TokenUsage(
        input=usage_raw.get("input_tokens", usage_raw.get("prompt_tokens", 0)),
        output=usage_raw.get("output_tokens", usage_raw.get("completion_tokens", 0)),
    )


def _save_output(output: GenerationOutput) -> None:
    run_dir = settings.outputs_dir / "runs" / output.chart_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / f"{output.output_id}.json").write_text(
        output.model_dump_json(indent=2)
    )


# ─── Read helpers ─────────────────────────────────────────────────────────────

def load_outputs_for_chart(chart_id: str) -> list[GenerationOutput]:
    run_dir = settings.outputs_dir / "runs" / chart_id
    if not run_dir.exists():
        return []
    outputs = []
    for f in sorted(run_dir.glob("*.json"), reverse=True):
        try:
            outputs.append(GenerationOutput.model_validate_json(f.read_text()))
        except Exception:
            pass
    return outputs


def load_all_outputs(
    model_id: str | None = None,
    chart_id: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[GenerationOutput], int]:
    runs_dir = settings.outputs_dir / "runs"
    all_outputs: list[GenerationOutput] = []

    if chart_id:
        all_outputs = load_outputs_for_chart(chart_id)
    else:
        for chart_dir in (sorted(runs_dir.iterdir()) if runs_dir.exists() else []):
            if chart_dir.is_dir():
                all_outputs.extend(load_outputs_for_chart(chart_dir.name))

    if model_id:
        all_outputs = [o for o in all_outputs if o.model_id == model_id]

    all_outputs.sort(key=lambda o: o.created_at, reverse=True)
    total = len(all_outputs)
    start = (page - 1) * page_size
    return all_outputs[start : start + page_size], total


def delete_output(output_id: str) -> bool:
    runs_dir = settings.outputs_dir / "runs"
    for f in runs_dir.rglob(f"{output_id}.json"):
        f.unlink()
        return True
    return False
