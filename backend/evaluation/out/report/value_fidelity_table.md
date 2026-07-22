# Value Fidelity — DIRECT/DERIVED numeric claims vs. real ground truth

Scope: only the 76/102 charts with a resolvable data table (native data_table, or for 6 of 7 Olli charts, the external vega-datasets table their vega_lite_spec references), every variant. accuracy_pct = share of extracted numbers that match the real data table (raw cells for DIRECT; raw cells + simple computed quantities for DERIVED) or a scene_graph axis tick label. SPECULATIVE claims excluded — they don't claim grounding. Checked even in V3/V4, where the model never saw the table but we still know the truth. No noise filter — every number-like token (whole numbers, decimals, percentages, x/y fractions) is assessed, regardless of magnitude. n_matches_axis_label is a separate, weaker tier: matches a real value visible on the chart's axis (scene_graph, vistext only), not a confirmed per-category data point — not counted toward accuracy_pct.

| model_id | variant | flag_kind | n_numbers | n_correct | n_matches_axis_label | n_fabricated | accuracy_pct |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gemini-3.5-flash | 1 | derived | 639 | 576 | 4 | 59 | 90.1 |
| gemini-3.5-flash | 1 | direct | 323 | 261 | 7 | 55 | 80.8 |
| gemini-3.5-flash | 2 | derived | 601 | 576 | 3 | 22 | 95.8 |
| gemini-3.5-flash | 2 | direct | 335 | 277 | 5 | 53 | 82.7 |
| gemini-3.5-flash | 3 | derived | 657 | 570 | 11 | 76 | 86.8 |
| gemini-3.5-flash | 3 | direct | 194 | 141 | 5 | 48 | 72.7 |
| gemini-3.5-flash | 4 | derived | 612 | 543 | 6 | 63 | 88.7 |
| gemini-3.5-flash | 4 | direct | 242 | 174 | 2 | 66 | 71.9 |
| gpt-5.4 | 1 | derived | 961 | 915 | 3 | 43 | 95.2 |
| gpt-5.4 | 1 | direct | 908 | 700 | 12 | 196 | 77.1 |
| gpt-5.4 | 2 | derived | 1104 | 1075 | 1 | 28 | 97.4 |
| gpt-5.4 | 2 | direct | 698 | 582 | 9 | 107 | 83.4 |
| gpt-5.4 | 3 | derived | 463 | 410 | 8 | 45 | 88.6 |
| gpt-5.4 | 3 | direct | 277 | 198 | 10 | 69 | 71.5 |
| gpt-5.4 | 4 | derived | 296 | 267 | 5 | 24 | 90.2 |
| gpt-5.4 | 4 | direct | 316 | 221 | 6 | 89 | 69.9 |
| meta-llama/llama-4-scout-17b-16e-instruct | 1 | derived | 193 | 173 | 6 | 14 | 89.6 |
| meta-llama/llama-4-scout-17b-16e-instruct | 1 | direct | 295 | 208 | 7 | 80 | 70.5 |
| meta-llama/llama-4-scout-17b-16e-instruct | 2 | derived | 195 | 187 | 2 | 6 | 95.9 |
| meta-llama/llama-4-scout-17b-16e-instruct | 2 | direct | 187 | 132 | 3 | 52 | 70.6 |
| meta-llama/llama-4-scout-17b-16e-instruct | 3 | derived | 177 | 145 | 7 | 25 | 81.9 |
| meta-llama/llama-4-scout-17b-16e-instruct | 3 | direct | 222 | 147 | 4 | 71 | 66.2 |
| meta-llama/llama-4-scout-17b-16e-instruct | 4 | derived | 179 | 158 | 5 | 16 | 88.3 |
| meta-llama/llama-4-scout-17b-16e-instruct | 4 | direct | 213 | 149 | 4 | 60 | 70.0 |
