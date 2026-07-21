# Value Fidelity — DIRECT/DERIVED numeric claims vs. real ground truth

Scope: only the 75/102 charts with a resolvable data table (native data_table, or for 6 of 7 Olli charts, the external vega-datasets table their vega_lite_spec references), every variant. accuracy_pct = share of extracted numbers that match the real data table (raw cells for DIRECT; raw cells + simple computed quantities for DERIVED) or a scene_graph axis tick label. SPECULATIVE claims excluded — they don't claim grounding. Checked even in V3/V4, where the model never saw the table but we still know the truth. No noise filter — every number-like token (whole numbers, decimals, percentages, x/y fractions) is assessed, regardless of magnitude. n_matches_axis_label is a separate, weaker tier: matches a real value visible on the chart's axis (scene_graph, vistext only), not a confirmed per-category data point — not counted toward accuracy_pct.

| model_id | variant | flag_kind | n_numbers | n_correct | n_matches_axis_label | n_fabricated | accuracy_pct |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gemini-3.5-flash | 1 | derived | 635 | 576 | 0 | 59 | 90.7 |
| gemini-3.5-flash | 1 | direct | 322 | 261 | 7 | 54 | 81.1 |
| gemini-3.5-flash | 2 | derived | 598 | 576 | 0 | 22 | 96.3 |
| gemini-3.5-flash | 2 | direct | 334 | 277 | 5 | 52 | 82.9 |
| gemini-3.5-flash | 3 | derived | 644 | 570 | 0 | 74 | 88.5 |
| gemini-3.5-flash | 3 | direct | 194 | 141 | 5 | 48 | 72.7 |
| gemini-3.5-flash | 4 | derived | 607 | 543 | 1 | 63 | 89.5 |
| gemini-3.5-flash | 4 | direct | 241 | 174 | 2 | 65 | 72.2 |
| gpt-5.4 | 1 | derived | 958 | 915 | 0 | 43 | 95.5 |
| gpt-5.4 | 1 | direct | 907 | 700 | 12 | 195 | 77.2 |
| gpt-5.4 | 2 | derived | 1104 | 1075 | 1 | 28 | 97.4 |
| gpt-5.4 | 2 | direct | 697 | 582 | 9 | 106 | 83.5 |
| gpt-5.4 | 3 | derived | 458 | 410 | 3 | 45 | 89.5 |
| gpt-5.4 | 3 | direct | 271 | 198 | 7 | 66 | 73.1 |
| gpt-5.4 | 4 | derived | 291 | 267 | 0 | 24 | 91.8 |
| gpt-5.4 | 4 | direct | 315 | 221 | 6 | 88 | 70.2 |
| meta-llama/llama-4-scout-17b-16e-instruct | 1 | derived | 187 | 173 | 0 | 14 | 92.5 |
| meta-llama/llama-4-scout-17b-16e-instruct | 1 | direct | 294 | 208 | 7 | 79 | 70.7 |
| meta-llama/llama-4-scout-17b-16e-instruct | 2 | derived | 192 | 187 | 0 | 5 | 97.4 |
| meta-llama/llama-4-scout-17b-16e-instruct | 2 | direct | 185 | 132 | 2 | 51 | 71.4 |
| meta-llama/llama-4-scout-17b-16e-instruct | 3 | derived | 170 | 145 | 1 | 24 | 85.3 |
| meta-llama/llama-4-scout-17b-16e-instruct | 3 | direct | 221 | 147 | 4 | 70 | 66.5 |
| meta-llama/llama-4-scout-17b-16e-instruct | 4 | derived | 175 | 158 | 1 | 16 | 90.3 |
| meta-llama/llama-4-scout-17b-16e-instruct | 4 | direct | 212 | 149 | 4 | 59 | 70.3 |
