# Evaluation

Implements the evaluation plan for the benchmark, organized around three
explicit paired research questions:

| RQ | Comparison | Controlled factor |
|---|---|---|
| **RQ1** accessible-context effect | V1 vs V3 | Same image; context added |
| **RQ2** image contribution | V1 vs V2 | Same context; image added |
| **RQ3** missing-context disclosure | V3 vs V4 | Same evidence; disclosure added |

Plus flag distribution, a provenance validity audit, numeric value
fidelity (with a category/series-aware tuple check on top of plain value
matching), L4 fidelity, and Stage-1 calibration. Reads directly from
`data/outputs/runs/` and the dataset `charts.json` files — no separate
data export step needed.

## Research questions → where to look

| RQ | Script(s) | Key CSV(s) | Report table(s) |
|---|---|---|---|
| RQ1 | `paired_contrasts.py` (contrast `RQ1_accessible_context`), `caution_measures.py` | `paired_contrasts_bootstrap.csv`, `caution_measures_summary.csv` | `report/rq1_accessible_context_table.md` |
| RQ2 | `paired_contrasts.py` (contrast `RQ2_image_contribution`) | `paired_contrasts_bootstrap.csv` | `report/rq2_image_contribution_table.md` |
| RQ3 | `paired_contrasts.py` (contrast `RQ3_missing_context_disclosure`), `caution_measures.py`, `provenance_audit.py` (V3/V4 automated misattribution) | `paired_contrasts_bootstrap.csv`, `caution_measures_summary.csv`, `provenance_automated_v3v4.csv` | `report/rq3_missing_context_disclosure_table.md`, `report/caution_measures_table.md`, `report/misattribution_table.md` |

Every RQ table in `paired_contrasts_bootstrap.csv` reports, per model, 10
chart-paired metric rows with a bootstrap 95% CI: `direct_proportion`,
`derived_proportion`, `speculative_proportion` (via inline-tag counting),
`claims_per_100_words` (verbosity-controlled claim volume),
`numeric_value_match_rate` (from `value_fidelity_claims.csv`, restricted
to the charts value_fidelity can resolve ground truth for), and 5 caution/
metacognition rates (`caution_total_per_100_words` plus its 4 sub-
categories). See `paired_contrasts.py`'s module docstring for the exact
pairing/bootstrap mechanics and why `n_pairs` varies per row.

## Setup

```
cd backend
.venv/bin/pip install -r requirements.txt   # adds matplotlib, used only by report.py
```

## Scope: 101 of 103 charts have complete 3-model coverage

`data/outputs/runs/` currently has output for 103 charts. Every script
here defaults to charts with complete coverage across `REQUIRED_MODELS`
(`gemini-3.5-flash`, `gpt-5.4`, `meta-llama/llama-4-scout-17b-16e-instruct`
— see `common.py`) and prints exactly what it excluded and why. As of this
writing that's 101/103 — the 2 exceptions:
  - `vistext_1`: only has `gemini-3.5-flash` output (`gpt-5.4` and Llama
    were never run on it).
  - `owid_sex_ratio_at_birth_vs_five_years_old`: missing `gpt-5.4`.

Pass `require_complete_coverage=False` to `load_records()` if you
specifically want the full 103 for a coverage audit.

**`llama-4-scout-17b-16e-instruct` was shut down by its provider on
2026-07-17.** `qwen/qwen3.6-27b` is its live free-tier replacement (see
`frontend/lib/types.ts`'s `LLM_MODELS` entry, which already displays it as
"Llama 4 Scout 17B (Vision)" in the UI for the same reason). `common.py`'s
`MODEL_ALIASES` normalizes `qwen/qwen3.6-27b` to
`meta-llama/llama-4-scout-17b-16e-instruct` at load time, so every script
in this package groups post-cutover and pre-cutover Llama records
together automatically — nothing downstream needs to know the swap
happened. Update `MODEL_ALIASES` (not `REQUIRED_MODELS`) if the provider
swaps again.

**Claude has zero stored outputs as of this writing** — so "per model" is
currently 3 models, not 4. Add `claude-opus-4-8` / `claude-sonnet-5` to
`REQUIRED_MODELS` in `common.py` once real Claude data exists, or the
per-model scripts will just keep silently running on 3.

## File-by-file reference

| File | Purpose | Key outputs |
|---|---|---|
| `common.py` | Shared data loading (`load_records`), model-ID aliasing, inline-flag counting, CSV helpers. Not runnable on its own. | — |
| `bootstrap.py` | Stdlib-only paired-percentile-bootstrap helper (`bootstrap_ci`). Not runnable on its own. | — |
| `flag_distribution.py` | [DIRECT]/[DERIVED]/[SPECULATIVE] counts/proportions per model x variant x section. | `flag_distribution_by_section.csv`, `flag_distribution_summary.csv` |
| `section_speculation.py` | Same flags, broken out per section, with 2x2-grid-ready subplot figures — "is L4 speculative everywhere?" | `section_speculation_variant_summary.csv`, `report/subplot_*.png/.pdf`, `report/global_legend.*` |
| `output_length.py` | Word count per section x variant x model — a second, semantics-free "unfaltering fluency" check. | `output_length_summary.csv`, `output_length_by_section.csv`, `report/output_length_*.png` |
| `value_fidelity.py` | Numeric fidelity: does a DIRECT/DERIVED claim's number match real ground truth? Plus an additive category/series-aware tuple check and a human-audit sample/score workflow for estimating the checker's own false-positive/negative rate. Subcommands: `automated`, `sample`, `score`. | `value_fidelity_claims.csv`, `value_fidelity_summary.csv`, `value_fidelity_audit_sample.csv`, `value_fidelity_scored_audit.csv`, `report/value_fidelity_accuracy.png` |
| `value_fidelity_embedding.py` | A genuinely different, complementary check: does a claim's overall *meaning* semantically match real ground truth (OpenAI embeddings), independent of whether the specific number is correct. Run side by side with `value_fidelity.py`, not as a replacement. | `value_fidelity_embedding_claims.csv`, `value_fidelity_embedding_summary.csv` |
| `caution_measures.py` | Direct measurement of RQ3's caution/metacognition construct: predefined regex/keyword markers (hedging, abstention, missing-info requests, unsupported-causal-in-SPECULATIVE) per record. | `caution_measures_by_record.csv`, `caution_measures_summary.csv` |
| `paired_contrasts.py` | Chart-paired, bootstrap-CI'd estimates for RQ1/RQ2/RQ3 (see above), plus a plain per-variant descriptive table. | `paired_contrasts_bootstrap.csv`, `paired_contrasts_by_variant.csv` |
| `stage1_calibration.py` | Does a model's self-reported 0-5 completeness score track whether that dimension was actually available? Plus the V3/V4 overconfidence signal. | `stage1_calibration.csv`, `stage1_overconfidence_v3v4.csv` |
| `provenance_audit.py` | Provenance validity: automated V3/V4 misattribution signal (any [DIRECT] claim is unauthorized by construction), plus a stratified human-annotation sample/score workflow. Subcommands: `automated`, `sample`, `score`. | `provenance_automated_v3v4.csv`, `provenance_audit_sample.csv`, `provenance_scored_misattribution.csv` |
| `l4_fidelity.py` | How well does the generated `real_world_significance` section track the real domain story? Uses `domain_context` as a ground-truth proxy (L4 itself doesn't exist yet — see caveats). | `l4_fidelity_similarity.csv`, `l4_fidelity_human_rubric.csv` (for human annotation) |
| `report.py` | Assembles paper deliverables from the CSVs above — reads, doesn't recompute. | `report/*.md`, `report/*.png` |
| `run_all.py` | Runs everything automatable, in dependency order. | (all of the above) |

## Known data caveats (read before trusting the numbers)

- **`gpt-5.4` doesn't keep `flags.direct_claims`/`derived_claims`/`speculative_claims`
  verbatim-synced with its inline-tagged text** — it paraphrases when
  populating those lists (e.g. the list says `"...— source: streaming
  analytics domain"`, the inline text says `"...[SPECULATIVE: streaming
  platform economics]"` for what's evidently the same claim). Any
  per-section breakdown must count the inline `[DIRECT]`/`[DERIVED]`/
  `[SPECULATIVE]` tags directly (`common.count_inline_flags`), not match
  claims-list strings against section text. The claims lists themselves
  are still fine for whole-output totals (that's just `len(list)`, no
  matching involved).
- **Inline-tag counting vs. list-length counting is intentionally split
  across this package, not unified.** `paired_contrasts.py` and
  `caution_measures.py` (added in this pass) use inline-tag counting
  exclusively, per the caveat above. `flag_distribution.py`'s per-record
  summary and `provenance_audit.py`'s stratified sampling still use
  `len(r.direct_claims)`/etc. list lengths for their own established
  purposes — this was a deliberate scope decision (confirmed with the
  project owner) to avoid migrating scripts that weren't otherwise being
  touched. If you're cross-referencing a claim *count* between an RQ
  table and `flag_distribution_summary.csv`, expect small discrepancies
  for gpt-5.4 specifically — they're measuring the same concept two
  different, both-documented ways.
- **V3's `chart_title` leak**: every V3 record currently on disk was
  generated *before* the fix that withholds the chart title in the
  "sparse" condition (see `prompt_service.py`). `provenance_audit.py`'s
  automated check reports both a raw and a title-adjusted misattribution
  rate for exactly this reason — use the adjusted number, or regenerate V3
  outputs post-fix if you want the raw and adjusted numbers to converge.
- **L4 ground truth doesn't exist yet**: `chart.ground_truth_description`
  and `chart.metadata.l4_caption` are empty for all charts (vistext's own
  notes call L4 "the gap to fill"). `l4_fidelity.py` uses
  `metadata.domain_context` as a proxy instead, available for 71/101
  charts (every source except vistext). This is a proxy, not the real
  thing — say so if you cite these numbers.
- **Some model outputs return lists instead of strings** for
  `generated_description` fields — a genuine schema-compliance failure on
  the model's part, not a bug here. `common.py` coerces and tracks it
  (`section_schema_ok`); the loader prints how many records were affected.
- **Number matching in `value_fidelity.py` is a candidate generator, not a
  verdict.** It checks numbers *inside DIRECT/DERIVED-flagged claims only*
  (SPECULATIVE excluded — never claims grounding) against every ground
  truth source available for that chart: native `data_table`; for 6 of 7
  Olli charts, the external vega-datasets table their `vega_lite_spec`
  actually references (fetched once and cached to `evaluation/cache/`);
  for all 7 Olli charts including the one with neither of the above
  (`olli_choropleth-map`), `olli_tree`'s accessible-summary statistics
  (avg/min/max/count per group) go into the DERIVED pool; and for vistext
  charts, real axis tick labels pulled from `scene_graph` (a separate,
  weaker `matches_axis_label` tier). Scope: 74/101 charts. Read
  `value_fidelity_claims.csv` before citing a rate regardless — this is
  pattern matching over a candidate space, not a verified re-derivation
  of the model's reasoning.
  - 22 of 36 charts (checked in an earlier pass) store at least one
    numeric column as a *string* (`'−0.1872'`, some using the Unicode
    minus U+2212, not ASCII `-`) — `_parse_numeric_value` handles both.
  - The number-extraction regex excludes four narrow, verified cases:
    4-digit numbers with no comma, hyphenated ranges, `"COVID-19"`-style
    compound names, and this project's own `"L1"`-`"L4"` caption labels.
  - Larger tables produce a larger DERIVED candidate pool, which
    mechanically raises the odds of an *accidental* match — DERIVED
    accuracy isn't perfectly comparable across charts of very different
    table sizes.
- **Tuple verification (`category_matched`/`tuple_verified` columns in
  `value_fidelity_claims.csv`) uses exact-or-substring category matching,
  with no entity-alias table.** "US" won't match "United States" — this
  makes the check conservative (undercounts real category matches, never
  overclaims one) rather than over-permissive, but it means
  `tuple_verified_pct` in `value_fidelity_summary.csv` is a lower bound on
  how often the flat value-only check's "correct" verdicts are actually
  tuple-correct, not a precise rate. An alias table is a reasonable future
  addition, not implemented in this pass.
- **The value-fidelity human audit samples a fixed cap per (model,
  verdict) stratum (default 30), not a flat percentage** — a deliberate
  deviation from `provenance_audit.py`'s flat-12%-of-everything
  convention (confirmed with the project owner), because `fabricated` is
  usually the dominant verdict by count, so a flat fraction would make
  the `correct` stratum tiny for weaker models while making `fabricated`
  unmanageably large to annotate. A model with very few `correct` claims
  in some stratum will have a weaker false-positive-rate estimate as a
  result — read `value_fidelity_scored_audit.csv`'s `false_positive_n`
  before trusting `false_positive_rate` for any one model.
- **Direction-checking (`direction_claimed`/`direction_matched` in
  `value_fidelity_claims.csv`) only resolves for an explicit "from X to Y"
  construction** with both X and Y matching real, distinct category names
  and a numeric column already tuple-verified for that claim — everything
  else (including single-entity time-trend claims) is `direction_matched="n-a"`,
  not a guess.
- **The caution/metacognition marker taxonomy (`caution_measures.py`) is
  predefined regex/keyword matching, not ML-based, same as everything
  else in this package.** The `unsupported_causal` category specifically
  is a heuristic proxy — causal connective words found inside a claim
  span already tagged SPECULATIVE — with two documented failure
  directions: it undercounts if a model mislabels a causal claim as
  DIRECT/DERIVED instead of SPECULATIVE, and it's blind to causal
  phrasing outside its fixed word list.
- **Bootstrap CIs in `paired_contrasts_bootstrap.csv` describe resampling
  variability among the charts actually run, not population-level
  sampling error** — charts were purposively sampled, not randomly drawn
  from a defined population of charts. Percentile method, not BCa (see
  `bootstrap.py`'s docstring for why). Rows with `n_pairs < 10` are
  flagged (`low_n_flag`) but not dropped — read them with extra caution,
  don't ignore them.
- **Text embeddings cannot verify DERIVED arithmetic — confirmed
  empirically, not assumed.** `text-embedding-3-small` cosine similarity
  between "rose by 49%" and "rose by 4900%" (two orders of magnitude off)
  is 0.91 — embeddings encode topic/sentence structure, not the magnitude
  of the number inside. `value_fidelity_embedding.py` is a genuinely
  different, complementary check, not a second opinion on numeric
  correctness — don't read its similarity score as an accuracy check.
- **`l4_fidelity.py`'s default similarity is lexical (TF-IDF cosine), not
  semantic** — zero-dependency, zero-cost, but weaker than a real
  embedding. Pass `--use-openai-embeddings` for `text-embedding-3-small`
  via the OpenAI API instead (costs API calls).

## Running it

```
cd backend
.venv/bin/python -m evaluation.run_all
```

Runs everything automatable in order (`value_fidelity automated` and
`caution_measures` run before `paired_contrasts`, which reads both of
their outputs — see `run_all.py`'s docstring). Four things still need a
human:

1. **Provenance audit.** `run_all` generates `out/provenance_audit_sample.csv`
   — a stratified ~12% sample of individual claims across every
   (model, variant), with full reference context inline. Fill in
   `annotator1_valid` / `annotator2_valid` per row (`valid` / `invalid` /
   `unsure`), then:
   ```
   .venv/bin/python -m evaluation.provenance_audit score evaluation/out/provenance_audit_sample.csv
   ```
   Prints Cohen's κ and the per-model DIRECT-claim misattribution rate,
   writes `out/provenance_scored_misattribution.csv`.

2. **Value-fidelity audit.** `run_all` generates
   `out/value_fidelity_audit_sample.csv` — up to 30 claims per (model,
   verdict) stratum, with the real matched category row inlined so you
   don't need to look anything up. Fill in `annotator1_valid` /
   `annotator2_valid` (judging whether the model's stated *number* is
   actually correct, independent of what `verdict` already says), then:
   ```
   .venv/bin/python -m evaluation.value_fidelity score evaluation/out/value_fidelity_audit_sample.csv
   ```
   Prints Cohen's κ, false-positive/negative rates (overall and split by
   `tuple_verified`), writes `out/value_fidelity_scored_audit.csv`.

3. **L4 rubric.** Fill in `topically_relevant` / `correct_domain` /
   `invented_stakes` in `out/l4_fidelity_human_rubric.csv`.

4. **Qualitative excerpts.** Curate `out/report/qualitative_excerpts.md`
   down to 2-3.

Individual scripts can also be run standalone, e.g.
`.venv/bin/python -m evaluation.flag_distribution`.

## What's in `out/`

Auto-generated (safe to delete and regenerate via `run_all.py`):

| File | From |
|---|---|
| `flag_distribution_by_section.csv`, `flag_distribution_summary.csv` | `flag_distribution.py` |
| `section_speculation_variant_summary.csv`, `report/subplot_*.png/.pdf` | `section_speculation.py` |
| `output_length_summary.csv`, `output_length_by_section.csv`, `report/output_length_*.png` | `output_length.py` |
| `value_fidelity_claims.csv`, `value_fidelity_summary.csv` | `value_fidelity.py automated` |
| `value_fidelity_audit_sample.csv` (blank annotator columns) | `value_fidelity.py sample` |
| `caution_measures_by_record.csv`, `caution_measures_summary.csv` | `caution_measures.py` |
| `paired_contrasts_bootstrap.csv`, `paired_contrasts_by_variant.csv` | `paired_contrasts.py` |
| `stage1_calibration.csv`, `stage1_overconfidence_v3v4.csv` | `stage1_calibration.py` |
| `provenance_automated_v3v4.csv` | `provenance_audit.py automated` |
| `provenance_audit_sample.csv` (blank annotator columns) | `provenance_audit.py sample` |
| `l4_fidelity_similarity.csv` | `l4_fidelity.py` |
| `report/*` (tables, figures, excerpts) | `report.py` |

**Not auto-regenerable — real work product, don't delete once filled in:**

| File | Filled in by |
|---|---|
| `provenance_audit_sample.csv` (after annotation) | two human annotators |
| `value_fidelity_audit_sample.csv` (after annotation) | two human annotators |
| `l4_fidelity_human_rubric.csv` (after annotation) | human annotator |
| `provenance_scored_misattribution.csv`, `value_fidelity_scored_audit.csv` | derived from the above, but the κ/rate calc is cheap to rerun — the annotations underneath it aren't |

`out/` is *not* gitignored for exactly this reason — the auto-generated
CSVs and the annotated ones live side by side, and blanket-ignoring the
folder would silently hide annotation work from git. Decide for yourself
what to commit.

## Paper deliverables (`report.py` / `run_all.py`)

- `report/rq1_accessible_context_table.md`, `rq2_image_contribution_table.md`,
  `rq3_missing_context_disclosure_table.md` — the three chart-paired
  bootstrap-CI tables, one per RQ.
- `report/caution_measures_table.md` — direct RQ3-construct measurement.
- `report/value_fidelity_audit_table.md` — human-audit FP/FN rates for the
  numeric-fidelity checker (degrades gracefully to a "not yet annotated"
  placeholder if the human step hasn't happened yet).
- `report/flag_distribution_table.md` — one flag-distribution table (model x variant)
- `report/speculation_volume.png` — one figure (speculation volume V1→V4, per model)
- `report/misattribution_table.md` — the misattribution table
- `report/qualitative_excerpts.md` — auto-picked failure-excerpt *candidates*
  (highest speculative-claim-count V1 record per model — speculating when
  nothing is missing is the cleanest failure to quote). Curate down to 2-3,
  read them first — these are candidates, not a final selection.
