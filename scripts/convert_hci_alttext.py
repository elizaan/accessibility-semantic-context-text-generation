"""
Convert the HCI Alt Text Dataset (Chintalapati et al., ASSETS 2022) to AccessViz format.

Setup (run once):
  1. Clone the dataset repo:
       git clone https://github.com/allenai/hci-alt-texts.git /tmp/hci-alt-texts

  2. Download and extract the chart images (~82 MB):
       curl -L https://ai2-s2-hci-alt-texts.s3-us-west-2.amazonaws.com/images.tar.gz \
         | tar -xz -C /tmp/hci-alt-texts/

  3. Run this script:
       python scripts/convert_hci_alttext.py \
         --jsonl /tmp/hci-alt-texts/data/hci-alt-text-dataset-20220915.jsonl \
         --images /tmp/hci-alt-texts/images \
         --out data/hci_alt_texts

Output: data/hci_alt_texts/charts.json + data/hci_alt_texts/images/ (copies PNGs/JPGs)
"""

from __future__ import annotations
import argparse
import json
import re
import shutil
from pathlib import Path


CHART_TYPE_KEYWORDS: list[tuple[str, list[str]]] = [
    ("bar",      ["stacked bar", "stacked-bar", "100% bar", "grouped bar",
                  "bar chart", "bar graph", "bar plot", "histogram", "bar figure"]),
    ("line",     ["line chart", "line graph", "time series", "trend line", "slope",
                  "multi-line", "multiple lines", "multi series", "area chart"]),
    ("scatter",  ["scatter plot", "scatter chart", "scatterplot", "dot plot", "bubble chart"]),
    ("heatmap",  ["heat map", "heatmap", "matrix plot", "confusion matrix"]),
    ("box_plot", ["box plot", "boxplot", "box-and-whisker", "violin plot"]),
]

VENUE_DOMAIN_MAP: dict[str, str] = {
    "ASSETS":  "general",
    "CHI":     "general",
    "CSCW":    "general",
    "UIST":    "general",
    "IUI":     "general",
    "VIS":     "general",
    "EuroVis": "general",
    "TVCG":    "general",
    "InfoVis": "general",
}


def infer_chart_type(alt_text: str) -> str:
    lower = alt_text.lower()
    for chart_type, keywords in CHART_TYPE_KEYWORDS:
        if any(kw in lower for kw in keywords):
            return chart_type
    return "other"


def infer_domain(venue: str) -> str:
    for key, domain in VENUE_DOMAIN_MAP.items():
        if key.lower() in venue.lower():
            return domain
    return "general"


def sentences_by_level(
    sentences: list[str],
    levels: list[int],
    target_level: int,
) -> str | None:
    matched = [s for s, lv in zip(sentences, levels) if lv == target_level]
    return " ".join(matched).strip() or None


def convert(
    jsonl_path: Path,
    images_dir: Path | None,
    out_dir: Path,
    max_non_plot: int = 500,
) -> None:
    out_images = out_dir / "images"
    out_images.mkdir(parents=True, exist_ok=True)

    entries = [json.loads(line) for line in jsonl_path.read_text().splitlines() if line.strip()]

    charts: list[dict] = []
    missing_images = 0
    non_plot_count = 0

    for entry in entries:
        is_plot: bool = bool(entry.get("is_plot"))
        # Include all plots; include non-plots up to max_non_plot (still have alt texts worth studying)
        if not is_plot:
            if non_plot_count >= max_non_plot:
                continue
            non_plot_count += 1

        pdf_hash: str = entry.get("pdf_hash", "")
        raw_uri = entry.get("local_uri", "")
        local_uri: str = (raw_uri[0] if isinstance(raw_uri, list) else raw_uri) or ""
        alt_text: str = entry.get("alt_text", "").strip()
        caption: str = entry.get("caption", "").strip()
        venue: str = entry.get("venue", "")
        year: str | int = entry.get("year", "")
        corpus_id: str = str(entry.get("corpus_id", ""))
        sentences: list[str] = entry.get("sentences", [])
        levels: list[int] = entry.get("levels", [])
        annotated: bool = bool(entry.get("annotated", False))

        # Derive chart ID from pdf_hash + image filename
        img_filename = Path(local_uri).name if local_uri else f"{pdf_hash}.jpg"
        chart_id = f"hci_{re.sub(r'[^a-zA-Z0-9_-]', '_', img_filename.replace('.jpg', ''))}"

        # Copy image if available
        image_rel: str | None = None
        if images_dir and local_uri:
            src = images_dir / img_filename
            if src.exists():
                dst = out_images / img_filename
                if not dst.exists():
                    shutil.copy2(src, dst)
                image_rel = f"hci_alt_texts/images/{img_filename}"
            else:
                missing_images += 1
        else:
            missing_images += 1

        # Skip if no image and no alt text — nothing to benchmark
        if image_rel is None and not alt_text:
            continue

        # Build level captions from sentence-level annotations (only for annotated entries)
        l1 = l2 = l3 = l4 = None
        if annotated and sentences and levels and len(sentences) == len(levels):
            l1 = sentences_by_level(sentences, levels, 1)
            l2 = sentences_by_level(sentences, levels, 2)
            l3 = sentences_by_level(sentences, levels, 3)
            l4 = sentences_by_level(sentences, levels, 4)

        source_url = (
            f"https://www.semanticscholar.org/paper/{corpus_id}" if corpus_id else None
        )
        domain_context = (
            f"From a paper published at {venue} ({year}). Figure caption: {caption}"
            if caption
            else (f"From a paper published at {venue} ({year})." if venue else None)
        )

        charts.append({
            "chart_id": chart_id,
            "source": "hci_alt_texts",
            "chart_type": infer_chart_type(alt_text),
            "domain": infer_domain(venue),
            "image_path": image_rel or "",
            "title": caption[:120] if caption else None,
            "metadata": {
                "alt_text": alt_text or None,
                "aria_label": None,
                "aria_describedby": None,
                "olli_tree": None,
                "scene_graph": None,
                "data_table": None,
                "vega_lite_spec": None,
                "l1_caption": l1,
                "l2_caption": l2,
                "l3_caption": l3,
                "l4_caption": l4,
                "domain_context": domain_context,
                "stakeholder_context": None,
                "source_url": source_url,
            },
            "ground_truth_description": {
                "context": caption or "",
                "semantic_meaning": l3 or "",
                "real_world_significance": l4 or "",
            },
        })

    out_path = out_dir / "charts.json"
    out_path.write_text(json.dumps(charts, indent=2, ensure_ascii=False))

    annotated_count = sum(
        1 for c in charts
        if c["metadata"]["l1_caption"] or c["metadata"]["l2_caption"]
    )
    print(f"Converted {len(charts)} charts ({annotated_count} with level annotations)")
    print(f"Missing images: {missing_images}")
    print(f"Written to {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--jsonl",
        required=True,
        help="Path to hci-alt-text-dataset-*.jsonl",
    )
    parser.add_argument(
        "--images",
        default=None,
        help="Directory containing extracted chart images (optional)",
    )
    parser.add_argument(
        "--out",
        default="data/hci_alt_texts",
        help="Output directory (default: data/hci_alt_texts)",
    )
    args = parser.parse_args()

    convert(
        jsonl_path=Path(args.jsonl),
        images_dir=Path(args.images) if args.images else None,
        out_dir=Path(args.out),
    )


if __name__ == "__main__":
    main()
