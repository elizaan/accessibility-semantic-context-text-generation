"""
"Is L4 speculative everywhere across variants?" — flag counts (DIRECT/DERIVED/SPECULATIVE)
broken out separately for each section, model, and variant (V1->V4).

Generates 4 identical, standalone data subplots (without internal legends) and a 5th 
independent horizontal global legend file, optimized with large typography for 2x2 LaTeX grid inclusion.
"""

from __future__ import annotations
from collections import defaultdict
import os
from evaluation.common import OUT_DIR, SECTION_KEYS, count_inline_flags, load_records, write_csv

SECTION_TITLES = {
    "contextual_insights": "Contextual Insights",
    "domain_specific_explanations": "Domain-Specific Explanations",
    "real_world_significance": "Real-World Significance",
    "other": "Other",
}

VARIANT_MAP = {
    "Full Metadata + Image": "V1",
    "Full Metadata, No Image": "V2",
    "Sparse (Image Only)": "V3",
    "Withheld Metadata": "V4",
}

# Clean mapping to prevent long strings from squishing the column width
MODEL_DISPLAY_NAMES = {
    "gemini-3.5-flash": "Gemini 3.5 Flash",
    "gpt-5.4": "GPT-5.4",
    "meta-llama/llama-4-scout-17b-16e-instruct": "Llama 4 Scout"
}

# Factual mean output words from output_length_table.md
WORD_LENGTH_LEGEND = {
    "gemini-3.5-flash": {"V1": 344.9, "V2": 330.7, "V3": 351.4, "V4": 361.5},
    "gpt-5.4": {"V1": 616.5, "V2": 557.9, "V3": 553.8, "V4": 539.4},
    "meta-llama/llama-4-scout-17b-16e-instruct": {"V1": 201.4, "V2": 177.6, "V3": 198.7, "V4": 217.5}
}

def _aggregate() -> dict[tuple[str, str, str], dict[str, int]]:
    records = [r for r in load_records() if r.parse_ok]
    counts: dict[tuple[str, str, str], dict[str, int]] = defaultdict(
        lambda: {"direct": 0, "derived": 0, "speculative": 0}
    )
    
    for r in records:
        v_label = getattr(r, 'variant_label', None) or r.variant
        variant_v = VARIANT_MAP.get(v_label, f"V{v_label}")
        
        for section in SECTION_KEYS:
            text = r.sections.get(section, "")
            if not text:
                continue
            section_counts = count_inline_flags(text)
            bucket = counts[(r.model_id, variant_v, section)]
            for kind, n in section_counts.items():
                bucket[kind] += n
    return counts

def build_subplots(counts: dict[tuple[str, str, str], dict[str, int]]) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    models = sorted({m for m, _, _ in counts})
    variants = ["V1", "V2", "V3", "V4"]
    flag_kinds = ["direct", "derived", "speculative"]
    
    colors = {"direct": "#2e7d32", "derived": "#1565c0", "speculative": "#e65100"}

    # 1. Loop through and export each of the 4 data sections cleanly
    for section in SECTION_KEYS:
        # Adjusted height slightly to give text elements more vertical space
        fig, axes = plt.subplots(1, len(models), figsize=(14, 4.0))
        
        for col_idx, model in enumerate(models):
            ax = axes[col_idx]
            x = np.arange(len(variants))
            
            # --- Primary Axis: Stacked Bars (Claims) ---
            bottoms = np.zeros(len(variants))
            for kind in flag_kinds:
                ys = [counts.get((model, v, section), {}).get(kind, 0) for v in variants]
                ax.bar(x, ys, bottom=bottoms, label=kind.upper(), color=colors[kind], width=0.55)
                bottoms += ys
            
            # --- Secondary Axis: Line Plot (Mean Word Length Trend) ---
            ax_twin = ax.twinx()
            row_words = [WORD_LENGTH_LEGEND[model][v] for v in variants]
            line_handle = ax_twin.plot(x, row_words, color='#444444', linestyle='--', 
                                       marker='o', markersize=6, linewidth=2.0, label='MEAN OUTPUT LENGTH')
            
            # Row-shared boundary tracking
            padding = (max(row_words) - min(row_words)) * 0.3 or 20
            ax_twin.set_ylim(min(row_words) - padding, max(row_words) + padding)
            
            # Substantially increased text scaling for small grid legibility
            ax.tick_params(axis='both', labelsize=13)
            ax_twin.tick_params(axis='y', labelsize=13)
            
            # Column Header Setup with clean mapped names
            display_name = MODEL_DISPLAY_NAMES.get(model, model.split("/")[-1])
            ax.set_title(display_name, fontsize=14, fontweight='bold', pad=10)
            
            if col_idx == 0:
                ax.set_ylabel("Claim Count", fontsize=14, fontweight='bold')
            
            if col_idx == len(models) - 1:
                ax_twin.set_ylabel("Mean Output Length (words)", fontsize=13, color='#333333', fontweight='bold', labelpad=10)
            else:
                ax_twin.set_yticklabels([])
                
            ax.set_xticks(x)
            ax.set_xticklabels(variants, fontsize=13, fontweight='bold')
            ax.grid(axis='y', linestyle='--', alpha=0.4)

        fig.suptitle(SECTION_TITLES[section], fontsize=16, fontweight='bold', x=0.06, y=0.96, ha='left')
        
        plt.tight_layout()
        fig.subplots_adjust(top=0.78, bottom=0.18, left=0.06, right=0.93, wspace=0.22)
        
        base_path = OUT_DIR / "report" / f"subplot_{section}"
        base_path.parent.mkdir(exist_ok=True, parents=True)
        fig.savefig(base_path.with_suffix(".pdf"), bbox_inches='tight')
        fig.savefig(base_path.with_suffix(".png"), bbox_inches='tight', dpi=180)
        plt.close(fig)

    # 2. Render and export an independent bold horizontal legend panel
    fig_leg, ax_leg = plt.subplots(figsize=(14, 0.5))
    ax_leg.axis('off')
    
    import matplotlib.patches as mpatches
    import matplotlib.lines as mlines
    
    proxy_handles = [
        mpatches.Patch(color=colors["direct"], label="DIRECT"),
        mpatches.Patch(color=colors["derived"], label="DERIVED"),
        mpatches.Patch(color=colors["speculative"], label="SPECULATIVE"),
        mlines.Line2D([], [], color='#444444', linestyle='--', marker='o', markersize=6, linewidth=2.0, label='MEAN OUTPUT LENGTH (RHS)')
    ]
    
    fig_leg.legend(handles=proxy_handles, loc='center', ncol=4, frameon=True, 
                   facecolor='#ffffff', edgecolor='#ccc', fontsize=13)
    
    legend_path = OUT_DIR / "report" / "global_legend"
    fig_leg.savefig(legend_path.with_suffix(".pdf"), bbox_inches='tight')
    fig_leg.savefig(legend_path.with_suffix(".png"), bbox_inches='tight', dpi=180)
    plt.close(fig_leg)
    
    print("[Success] Re-rendered high-contrast subplots and global legend panel.")

def main() -> None:
    counts = _aggregate()
    rows = []
    for (model_id, variant, section), kinds in sorted(counts.items()):
        total = sum(kinds.values())
        rows.append({
            "model_id": model_id,
            "variant": variant,
            "section": section,
            "direct": kinds["direct"],
            "derived": kinds["derived"],
            "speculative": kinds["speculative"],
            "total": total,
            "speculative_pct": round(100 * kinds["speculative"] / total, 1) if total else 0,
        })
    write_csv(OUT_DIR / "section_speculation_variant_summary.csv",
              ["model_id", "variant", "section", "direct", "derived", "speculative", "total", "speculative_pct"], rows)
    build_subplots(counts)

if __name__ == "__main__":
    main()