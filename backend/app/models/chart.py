from __future__ import annotations
from typing import Literal, Any
from pydantic import BaseModel


DatasetSource = Literal["vistext", "olli", "our_world_data", "vcc", "hci_alt_texts"]
ChartType = Literal["bar", "line", "scatter", "heatmap", "box_plot", "other"]
Domain = Literal["public_health", "climate", "finance", "education", "demographics", "employment", "general"]


class ChartMetadata(BaseModel):
    alt_text: str | None = None
    aria_label: str | None = None
    aria_describedby: str | None = None
    olli_tree: str | None = None
    scene_graph: dict[str, Any] | None = None
    data_table: list[dict[str, Any]] | None = None
    vega_lite_spec: dict[str, Any] | None = None
    l1_caption: str | None = None
    l2_caption: str | None = None
    l3_caption: str | None = None
    l4_caption: str | None = None
    domain_context: str | None = None
    stakeholder_context: str | None = None
    source_url: str | None = None


class GroundTruthDescription(BaseModel):
    context: str = ""
    semantic_meaning: str = ""
    real_world_significance: str = ""


class Chart(BaseModel):
    chart_id: str
    source: DatasetSource
    chart_type: ChartType
    domain: Domain
    image_path: str
    title: str | None = None
    metadata: ChartMetadata
    ground_truth_description: GroundTruthDescription
