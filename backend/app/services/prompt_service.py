"""
Builds prompts from prompts.yaml templates.

Each call returns a (system_prompt, user_prompt) tuple — fully self-contained,
no history. Every generation run is a fresh single-turn conversation.
"""

from __future__ import annotations
import csv
import io
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.models.chart import Chart

_PROMPTS_PATH = Path(__file__).parents[2] / "prompts" / "prompts.yaml"


@lru_cache(maxsize=1)
def _load_prompts() -> dict:
    return yaml.safe_load(_PROMPTS_PATH.read_text(encoding="utf-8"))


def get_system_prompt() -> str:
    return _load_prompts()["system"]["content"].strip()


# Metadata fields eligible for the "full metadata" classification and that
# actually get inserted into the prompt below. l4_caption is deliberately
# excluded — it's the ground-truth target this benchmark scores against, so
# it can never be sent to the model regardless of what's checked in the UI.
FULL_CONDITION_FIELDS: tuple[str, ...] = (
    "alt_text",
    "aria_label",
    "aria_describedby",
    "olli_tree",
    "scene_graph",
    "data_table",
    "vega_lite_spec",
    "l1_caption",
    "l2_caption",
    "l3_caption",
    "domain_context",
    "stakeholder_context",
    "source_url",
)

_CONDITION_LABELS: dict[int, str] = {
    0: "Custom / Partial Selection",
    1: "Full Metadata + Image",
    2: "Full Metadata, No Image",
    3: "Sparse (Image Only)",
    4: "Withheld Metadata (Metacognition Test)",
}


def classify_variant(chart: Chart, enabled_features: list[str], include_image: bool) -> int:
    """
    Classify a (features, image) selection into a canonical benchmark
    condition, computed from what's actually available for this specific
    chart — not a fixed field list, since datasets vary in what they
    collected. Returns:

      1 = every available field selected + image
      2 = every available field selected, no image
      3 = no fields selected + image (sparse / visual-only)
      0 = anything else — still a valid run, just not one of the three
          canonical conditions (e.g. a partial selection)
    """
    available = {
        f for f in FULL_CONDITION_FIELDS if getattr(chart.metadata, f, None) is not None
    }
    selected = set(enabled_features) & available
    all_selected = bool(available) and selected == available
    none_selected = len(selected) == 0

    if all_selected and include_image:
        return 1
    if all_selected and not include_image:
        return 2
    if none_selected and include_image:
        return 3
    return 0


def condition_label(variant: int) -> str:
    return _CONDITION_LABELS.get(variant, "Custom / Partial Selection")


def _fill_template(template: str, values: dict[str, str]) -> str:
    """Replace <<key>> placeholders. Keys not in values are left unchanged."""
    result = template
    for key, value in values.items():
        result = result.replace(f"<<{key}>>", value)
    return result


def _format_data_table(data_table: list[dict[str, Any]] | None, max_rows: int = 25) -> str:
    if not data_table:
        return "[NOT PROVIDED]"
    rows = data_table[:max_rows]
    headers = list(rows[0].keys())
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    result = buf.getvalue().strip()
    if len(data_table) > max_rows:
        result += f"\n... ({len(data_table) - max_rows} more rows truncated)"
    return result


def _extract_axis_labels(spec: dict | None) -> tuple[str, str]:
    if not spec:
        return "[NOT PROVIDED]", "[NOT PROVIDED]"
    enc = spec.get("encoding", {})

    def label(channel: dict) -> str:
        return channel.get("title") or channel.get("field") or "[NOT PROVIDED]"

    return label(enc.get("x", {})), label(enc.get("y", {}))


def _infer_alt_text_level(chart: Chart, enabled_features: list[str]) -> str:
    meta = chart.metadata
    if "l3_caption" in enabled_features and meta.l3_caption:
        return "L3 — trends and patterns"
    if "l2_caption" in enabled_features and meta.l2_caption:
        return "L2 — statistics and relations"
    return "L1 — chart construction only"


def _feature_value(
    chart: Chart, feature: str, enabled_features: list[str], max_chars: int = 3000
) -> str:
    """Return the metadata value for a feature, or [NOT PROVIDED] if absent/disabled."""
    if feature not in enabled_features:
        return "[NOT PROVIDED]"
    value = getattr(chart.metadata, feature, None)
    if value is None:
        return "[NOT PROVIDED]"
    text = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value).strip()
    if not text:
        return "[NOT PROVIDED]"
    if len(text) > max_chars:
        text = text[:max_chars] + f"... [truncated, {len(text)} chars total]"
    return text


def build_prompt(
    chart: Chart,
    enabled_features: list[str],
    include_image: bool,
    variant: int = 1,
    custom_suffix: str | None = None,
) -> tuple[str, str]:
    """
    Returns (system_prompt, user_prompt).

    `variant` must already be resolved (see classify_variant / the explicit
    metacognition-test path in llm_service) — this function only renders it.

    Fully self-contained — send as a fresh single-turn call every time.
    No conversation history is needed or should be carried between runs.
    """
    prompts = _load_prompts()
    template_key = 4 if variant == 4 else "standard"
    template: str = prompts["variants"][template_key]["template"]

    x_axis, y_axis = (
        _extract_axis_labels(chart.metadata.vega_lite_spec)
        if "vega_lite_spec" in enabled_features
        else ("[NOT PROVIDED]", "[NOT PROVIDED]")
    )

    values: dict[str, str] = {
        "variant_number": str(variant),
        "condition_label": condition_label(variant),
        "image_clause": "with a chart image" if include_image else "without a chart image (text/metadata only)",
        "chart_image_block": "CHART IMAGE: [attached]" if include_image else "CHART IMAGE: [NOT PROVIDED]",
        "chart_title": chart.title or "[NOT PROVIDED]",
        "x_axis_label": x_axis,
        "y_axis_label": y_axis,
        "data_table_formatted": (
            _format_data_table(chart.metadata.data_table)
            if "data_table" in enabled_features
            else "[NOT PROVIDED]"
        ),
        "alt_text": _feature_value(chart, "alt_text", enabled_features),
        "alt_text_level": _infer_alt_text_level(chart, enabled_features),
        "aria_label": _feature_value(chart, "aria_label", enabled_features),
        "aria_describedby_content": _feature_value(chart, "aria_describedby", enabled_features),
        "olli_tree": _feature_value(chart, "olli_tree", enabled_features),
        "scene_graph": _feature_value(chart, "scene_graph", enabled_features),
        "l1_caption": _feature_value(chart, "l1_caption", enabled_features),
        "l2_caption": _feature_value(chart, "l2_caption", enabled_features),
        "l3_caption": _feature_value(chart, "l3_caption", enabled_features),
        "domain_context": _feature_value(chart, "domain_context", enabled_features),
        "source_url": _feature_value(chart, "source_url", enabled_features),
        "stakeholder_context": _feature_value(chart, "stakeholder_context", enabled_features),
    }

    user_prompt = _fill_template(template, values)

    if custom_suffix:
        user_prompt += f"\n\n## Additional Instructions\n{custom_suffix}"

    return get_system_prompt(), user_prompt
