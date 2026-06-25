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


def get_variant_default_features(variant: int) -> list[str]:
    return _load_prompts()["variants"][variant]["default_features"]


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
        return "[Not specified]", "[Not specified]"
    enc = spec.get("encoding", {})

    def label(channel: dict) -> str:
        return channel.get("title") or channel.get("field") or "[Not specified]"

    return label(enc.get("x", {})), label(enc.get("y", {}))


def _infer_alt_text_level(chart: Chart, enabled_features: list[str]) -> str:
    meta = chart.metadata
    if "l3_caption" in enabled_features and meta.l3_caption:
        return "L3 — trends and patterns"
    if "l2_caption" in enabled_features and meta.l2_caption:
        return "L2 — statistics and relations"
    return "L1 — chart construction only"


def _feature_value(chart: Chart, feature: str, enabled_features: list[str]) -> str:
    """Return the metadata value for a feature, or [NOT PROVIDED] if absent/disabled."""
    if feature not in enabled_features:
        return "[NOT PROVIDED]"
    value = getattr(chart.metadata, feature, None)
    if value is None:
        return "[NOT PROVIDED]"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip() or "[NOT PROVIDED]"


def build_prompt(
    chart: Chart,
    enabled_features: list[str],
    include_image: bool,
    variant: int = 1,
    custom_suffix: str | None = None,
) -> tuple[str, str]:
    """
    Returns (system_prompt, user_prompt).

    Fully self-contained — send as a fresh single-turn call every time.
    No conversation history is needed or should be carried between runs.
    """
    prompts = _load_prompts()
    template: str = prompts["variants"][variant]["template"]

    x_axis, y_axis = _extract_axis_labels(chart.metadata.vega_lite_spec)

    values: dict[str, str] = {
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
        "aria_describedby_content": _feature_value(chart, "aria_describedby", enabled_features),
        "domain_context": _feature_value(chart, "domain_context", enabled_features),
        "source_url": _feature_value(chart, "source_url", enabled_features),
        "stakeholder_context": _feature_value(chart, "stakeholder_context", enabled_features),
        "screen_reader_text": (
            _feature_value(chart, "olli_tree", enabled_features)
            if _feature_value(chart, "olli_tree", enabled_features) != "[NOT PROVIDED]"
            else _feature_value(chart, "aria_label", enabled_features)
        ),
    }

    user_prompt = _fill_template(template, values)

    if custom_suffix:
        user_prompt += f"\n\n## Additional Instructions\n{custom_suffix}"

    return get_system_prompt(), user_prompt
