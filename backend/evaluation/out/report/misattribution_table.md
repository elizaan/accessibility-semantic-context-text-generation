# V3/V4 Automated Misattribution Rate

Any [DIRECT] claim in V3/V4 is a misattribution by construction (no metadata was ever provided). `_adjusted` excludes claims that plausibly reference the chart title — all current V3 data predates the chart_title-leak fix, so `_raw` overstates V3's rate; `_adjusted` is the fairer number until V3 is regenerated.

| model_id | variant | n_direct_claims | n_title_excluded | misattribution_rate_raw | misattribution_rate_adjusted |
| --- | --- | --- | --- | --- | --- |
| gemini-3.5-flash | 3 | 118 | 52 | 1.0 | 0.559 |
| gemini-3.5-flash | 4 | 163 | 0 | 1.0 | 1.0 |
| gpt-5.4 | 3 | 420 | 81 | 1.0 | 0.807 |
| gpt-5.4 | 4 | 406 | 0 | 1.0 | 1.0 |
| meta-llama/llama-4-scout-17b-16e-instruct | 3 | 203 | 54 | 1.0 | 0.734 |
| meta-llama/llama-4-scout-17b-16e-instruct | 4 | 182 | 0 | 1.0 | 1.0 |
