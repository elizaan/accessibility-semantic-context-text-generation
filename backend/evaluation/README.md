# Evaluation

Implements the evaluation plan for the benchmark: flag distribution,
provenance validity audit, value fidelity, L4 fidelity, the two paired
contrasts (V1↔V2 image effect, V3↔V4 framing effect), and Stage-1
calibration. Reads directly from `data/outputs/runs/` and the dataset
`charts.json` files — no separate data export step needed.

## Setup

```
cd backend
.venv/bin/pip install -r requirements.txt   # adds matplotlib, used only by report.py
```

## Scope: 59 charts, not 60

`data/outputs/runs/` currently has output for 60 charts, but `vistext_1`
only has `gemini-3.5-flash` output — `gpt-5.4` and the Llama model were
never run on it. Every script here defaults to the 59 charts with complete
3-model coverage (`load_records()` in `common.py`, `REQUIRED_MODELS`) and
prints exactly what it excluded and why. Pass `require_complete_coverage=False`
to `load_records()` if you specifically want the full 60 for a coverage
audit.

**Claude has zero stored outputs as of this writing** (a `max_tokens=None`
bug was blocking every Claude call until earlier this session) — so
"per model" is currently 3 models, not 4. Add `claude-opus-4-8` /
`claude-sonnet-5` to `REQUIRED_MODELS` in `common.py` once real Claude data
exists, or the per-model scripts will just keep silently running on 3.

## Known data caveats (read before trusting the numbers)

- **`gpt-5.4` doesn't keep `flags.direct_claims`/`derived_claims`/`speculative_claims`
  verbatim-synced with its inline-tagged text** — it paraphrases when
  populating those lists (e.g. the list says `"...— source: streaming
  analytics domain"`, the inline text says `"...[SPECULATIVE: streaming
  platform economics]"` for what's evidently the same claim). Any
  per-section breakdown must count the inline `[DIRECT]`/`[DERIVED]`/
  `[SPECULATIVE]` tags directly (`common.count_inline_flags`), not match
  claims-list strings against section text — an earlier version of
  `flag_distribution.py`/`section_speculation.py` did the latter and
  silently got a ~100% "unmatched" rate for this model alone. Both scripts
  now use the inline-tag approach. The claims lists themselves are still
  fine for whole-output totals (that's just `len(list)`, no matching
  involved) — it's specifically cross-referencing them against section
  text that breaks for this model.
- **V3's `chart_title` leak**: every V3 record currently on disk was
  generated *before* the fix that withholds the chart title in the
  "sparse" condition (see `prompt_service.py`). `provenance_audit.py`'s
  automated check reports both a raw and a title-adjusted misattribution
  rate for exactly this reason — use the adjusted number, or regenerate V3
  outputs post-fix if you want the raw and adjusted numbers to converge.
- **L4 ground truth doesn't exist yet**: `chart.ground_truth_description`
  and `chart.metadata.l4_caption` are empty for all 59 charts (vistext's
  own notes call L4 "the gap to fill"). `l4_fidelity.py` uses
  `metadata.domain_context` as a proxy instead, available for 44/59 charts
  (every source except vistext). This is a proxy, not the real thing —
  say so if you cite these numbers.
- **Some model outputs return lists instead of strings** for
  `generated_description` fields — a genuine schema-compliance failure on
  the model's part, not a bug here. `common.py` coerces and tracks it
  (`section_schema_ok`); the loader prints how many records were affected.
- **Number matching in `value_fidelity.py` is a candidate generator, not a
  verdict.** It checks numbers *inside DIRECT/DERIVED-flagged claims only*
  (SPECULATIVE excluded — never claims grounding) against every ground
  truth source available for that chart: native `data_table`; for 6 of 7
  Olli charts, the external vega-datasets table their `vega_lite_spec`
  actually references (checked directly, not assumed — none of the 7
  embed data inline, all reference `raw.githubusercontent.com/vega/vega-datasets`
  by URL; fetched once and cached to `evaluation/cache/`); for all 7 Olli
  charts including the one with neither of the above (`olli_choropleth-map`,
  whose spec only has county-boundary topology), `olli_tree`'s accessible-
  summary statistics (avg/min/max/count per group) go into the DERIVED
  pool, since they're real but aggregate, not a single literal cell; and
  for vistext charts, real axis tick labels pulled from `scene_graph` (a
  separate, weaker `matches_axis_label` tier — a real value visible on the
  chart's scale, not a confirmed per-category data point). Scope: 43/59
  charts (15 vistext, 21/25 OWID, all 7 Olli, 0/12 hci_alt_texts — that
  source only ever provided alt text). Went through several corrections
  worth knowing about before citing a rate:
  - **The single biggest one**: 22 of the 36 charts (61%) store at least
    one numeric column as a *string* (`'−0.1872'`, several using the
    Unicode minus U+2212, not ASCII `-`). The original version only
    accepted `isinstance(v, (int, float))`, silently dropping every one of
    those values from the ground truth pool. This alone moved DIRECT
    accuracy from ~9-17% to ~67-89% once fixed — the earlier low numbers
    were substantially a parsing bug, not a real finding about model
    behavior. `_parse_numeric_value` in `value_fidelity.py` handles both
    now.
  - The number-extraction regex had four narrower corner cases, all now
    fixed and each verified against real claim text before/after: 4-digit
    numbers with no comma silently truncated to 3 digits (`"2018"` ->
    `"201"`); hyphenated ranges misread as negative numbers (`"20-25%"`
    -> 20 and *-25*); `"COVID-19"`-style compound names misread as
    negative numbers (*-19*); this project's own `"L1"`-`"L4"` caption
    labels misread as data values.
  - Larger tables produce a larger DERIVED candidate pool, which
    mechanically raises the odds of an *accidental* match — DERIVED
    accuracy isn't perfectly comparable across charts of very different
    table sizes.
  - Read `value_fidelity_claims.csv` before citing a rate regardless —
    this is pattern matching over a candidate space, not a verified
    re-derivation of the model's reasoning.
- **Text embeddings cannot verify DERIVED arithmetic — confirmed
  empirically, not assumed.** `text-embedding-3-small` cosine similarity
  between "rose by 49%" and "rose by 4900%" (two orders of magnitude off)
  is 0.91 — embeddings encode topic/sentence structure, not the magnitude
  of the number inside. `value_fidelity_embedding.py` is a genuinely
  different, complementary check (does this claim's phrasing sound
  topically grounded), not a second opinion on numeric correctness — don't
  read its similarity score as an accuracy check.
- **`l4_fidelity.py`'s default similarity is lexical (TF-IDF cosine), not
  semantic** — zero-dependency, zero-cost, but weaker than a real
  embedding. Pass `--use-openai-embeddings` for `text-embedding-3-small`
  via the OpenAI API instead (costs API calls).

## Running it

```
cd backend
.venv/bin/python -m evaluation.run_all
```

Runs everything automatable in order. Two things still need a human:

1. **Provenance audit.** `run_all` generates `out/provenance_audit_sample.csv`
   — a stratified ~12% sample of individual claims across every
   (model, variant), with full reference context (title, data table
   preview, captions, domain/stakeholder context) inline so you don't need
   to flip back to the app. Fill in `annotator1_valid` / `annotator2_valid`
   per row (`valid` / `invalid` / `unsure`), then:
   ```
   .venv/bin/python -m evaluation.provenance_audit score evaluation/out/provenance_audit_sample.csv
   ```
   This prints Cohen's κ and the per-model DIRECT-claim misattribution
   rate, and writes `out/provenance_scored_misattribution.csv`.

2. **L4 rubric.** Fill in `topically_relevant` / `correct_domain` /
   `invented_stakes` in `out/l4_fidelity_human_rubric.csv`.

Individual scripts can also be run standalone, e.g.
`.venv/bin/python -m evaluation.flag_distribution`.

## What's in `out/`

Auto-generated (safe to delete and regenerate via `run_all.py`):

| File | From |
|---|---|
| `flag_distribution_by_section.csv`, `flag_distribution_summary.csv` | `flag_distribution.py` |
| `section_speculation_summary.csv`, `report/section_speculation.png` | `section_speculation.py` — "is L4 speculative everywhere?" |
| `output_length_summary.csv`, `output_length_by_section.csv`, `report/output_length_*.png`, `report/output_length_table.md` | `output_length.py` — second, semantics-free "unfaltering fluency" check |
| `paired_contrasts_by_variant.csv`, `paired_contrasts_deltas.csv` | `paired_contrasts.py` |
| `stage1_calibration.csv`, `stage1_overconfidence_v3v4.csv` | `stage1_calibration.py` |
| `value_fidelity_claims.csv`, `value_fidelity_summary.csv` | `value_fidelity.py` |
| `provenance_automated_v3v4.csv` | `provenance_audit.py automated` |
| `l4_fidelity_similarity.csv` | `l4_fidelity.py` |
| `report/*` (tables, figure, excerpts) | `report.py` |

**Not auto-regenerable — real work product, don't delete once filled in:**

| File | Filled in by |
|---|---|
| `provenance_audit_sample.csv` (after annotation) | two human annotators |
| `l4_fidelity_human_rubric.csv` (after annotation) | human annotator |
| `provenance_scored_misattribution.csv` | derived from the above, but the κ/rate calc is cheap to rerun — the annotations underneath it aren't |

`out/` is *not* gitignored for exactly this reason — the auto-generated
CSVs and the annotated ones live side by side, and blanket-ignoring the
folder would silently hide annotation work from git. Decide for yourself
what to commit.

## Paper deliverables (`report.py` / `run_all.py`)

- `report/flag_distribution_table.md` — one flag-distribution table (model x variant)
- `report/speculation_volume.png` — one figure (speculation volume V1→V4, per model)
- `report/misattribution_table.md` — the misattribution table
- `report/paired_deltas_table.md` — the two paired deltas
- `report/qualitative_excerpts.md` — auto-picked failure-excerpt *candidates*
  (highest speculative-claim-count V1 record per model — speculating when
  nothing is missing is the cleanest failure to quote). Curate down to 2-3,
  read them first — these are candidates, not a final selection.
