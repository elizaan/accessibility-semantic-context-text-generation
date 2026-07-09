# Value Fidelity — DIRECT/DERIVED numeric claims vs. real ground truth

Scope: only the 43/59 charts with a resolvable data table (native data_table, or for 6 of 7 Olli charts, the external vega-datasets table their vega_lite_spec references), every variant. accuracy_pct = share of extracted numbers that match the real data table (raw cells for DIRECT; raw cells + simple computed quantities for DERIVED) or a scene_graph axis tick label. SPECULATIVE claims excluded — they don't claim grounding. Checked even in V3/V4, where the model never saw the table but we still know the truth. No noise filter — every number-like token (whole numbers, decimals, percentages, x/y fractions) is assessed, regardless of magnitude. n_matches_axis_label is a separate, weaker tier: matches a real value visible on the chart's axis (scene_graph, vistext only), not a confirmed per-category data point — not counted toward accuracy_pct.

| model_id | variant | flag_kind | n_numbers | n_correct | n_matches_axis_label | n_fabricated | accuracy_pct |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gemini-3.5-flash | 1 | derived | 367 | 329 | 0 | 38 | 89.6 |
| gemini-3.5-flash | 1 | direct | 210 | 173 | 6 | 31 | 82.4 |
| gemini-3.5-flash | 2 | derived | 340 | 330 | 0 | 10 | 97.1 |
| gemini-3.5-flash | 2 | direct | 208 | 169 | 4 | 35 | 81.2 |
| gemini-3.5-flash | 3 | derived | 366 | 319 | 0 | 47 | 87.2 |
| gemini-3.5-flash | 3 | direct | 105 | 75 | 1 | 29 | 71.4 |
| gemini-3.5-flash | 4 | derived | 361 | 319 | 1 | 41 | 88.4 |
| gemini-3.5-flash | 4 | direct | 135 | 97 | 1 | 37 | 71.9 |
| gpt-5.4 | 1 | derived | 501 | 486 | 0 | 15 | 97.0 |
| gpt-5.4 | 1 | direct | 525 | 423 | 8 | 94 | 80.6 |
| gpt-5.4 | 2 | derived | 602 | 586 | 1 | 15 | 97.3 |
| gpt-5.4 | 2 | direct | 357 | 309 | 6 | 42 | 86.6 |
| gpt-5.4 | 3 | derived | 252 | 218 | 2 | 32 | 86.5 |
| gpt-5.4 | 3 | direct | 171 | 119 | 7 | 45 | 69.6 |
| gpt-5.4 | 4 | derived | 159 | 147 | 0 | 12 | 92.5 |
| gpt-5.4 | 4 | direct | 165 | 109 | 5 | 51 | 66.1 |
| meta-llama/llama-4-scout-17b-16e-instruct | 1 | derived | 59 | 58 | 0 | 1 | 98.3 |
| meta-llama/llama-4-scout-17b-16e-instruct | 1 | direct | 180 | 131 | 7 | 42 | 72.8 |
| meta-llama/llama-4-scout-17b-16e-instruct | 2 | derived | 35 | 35 | 0 | 0 | 100.0 |
| meta-llama/llama-4-scout-17b-16e-instruct | 2 | direct | 96 | 72 | 1 | 23 | 75.0 |
| meta-llama/llama-4-scout-17b-16e-instruct | 3 | derived | 53 | 46 | 0 | 7 | 86.8 |
| meta-llama/llama-4-scout-17b-16e-instruct | 3 | direct | 122 | 78 | 1 | 43 | 63.9 |
| meta-llama/llama-4-scout-17b-16e-instruct | 4 | derived | 51 | 47 | 0 | 4 | 92.2 |
| meta-llama/llama-4-scout-17b-16e-instruct | 4 | direct | 108 | 76 | 3 | 29 | 70.4 |
