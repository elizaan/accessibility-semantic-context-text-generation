# RQ2: Image Contribution (V1 vs V2 — same context, image added)

Charts were purposively sampled, not randomly drawn from a defined population. These bootstrap CIs describe resampling variability of the observed paired differences among the charts actually run — they are not a claim about sampling error relative to some larger population of charts. A CI that excludes 0 should be read as "consistent, in this direction, across the charts we have," not as statistical generalizability. Rows marked `*` have n_pairs < 10 — read with extra caution.

| model_id | metric | n_pairs | mean_a | mean_b | mean_diff | ci_lo | ci_hi |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gemini-3.5-flash | direct_proportion | 102 | 0.2449 | 0.2854 | 0.0404 | 0.0145 | 0.0646 |
| gemini-3.5-flash | derived_proportion | 102 | 0.3552 | 0.2704 | -0.0848 | -0.1182 | -0.0519 |
| gemini-3.5-flash | speculative_proportion | 102 | 0.3998 | 0.4442 | 0.0444 | 0.0201 | 0.0685 |
| gemini-3.5-flash | claims_per_100_words | 102 | 3.6796 | 3.7928 | 0.1131 | -0.009 | 0.2368 |
| gemini-3.5-flash | caution_total_per_100_words | 102 | 0.1389 | 0.1573 | 0.0184 | -0.0257 | 0.0633 |
| gemini-3.5-flash | caution_hedging_per_100_words | 102 | 0.0214 | 0.0364 | 0.015 | -0.006 | 0.0353 |
| gemini-3.5-flash | caution_abstention_per_100_words | 102 | 0.0 | 0.0184 | 0.0184 | 0.0036 | 0.0363 |
| gemini-3.5-flash | caution_missing_info_per_100_words | 102 | 0.0 | 0.002 | 0.002 | 0.0 | 0.0059 |
| gemini-3.5-flash | caution_unsupported_causal_per_100_words | 102 | 0.1175 | 0.1005 | -0.017 | -0.0576 | 0.0229 |
| gemini-3.5-flash | numeric_value_match_rate | 75 | 0.8781 | 0.9285 | 0.0504 | 0.0219 | 0.0813 |
| gpt-5.4 | direct_proportion | 102 | 0.3702 | 0.3969 | 0.0267 | 0.0053 | 0.0485 |
| gpt-5.4 | derived_proportion | 102 | 0.3412 | 0.3185 | -0.0228 | -0.0452 | -0.0001 |
| gpt-5.4 | speculative_proportion | 102 | 0.2886 | 0.2846 | -0.004 | -0.0193 | 0.0116 |
| gpt-5.4 | claims_per_100_words | 102 | 3.755 | 3.9022 | 0.1472 | 0.0753 | 0.2204 |
| gpt-5.4 | caution_total_per_100_words | 102 | 0.4298 | 0.375 | -0.0547 | -0.1077 | 0.0008 |
| gpt-5.4 | caution_hedging_per_100_words | 102 | 0.1222 | 0.0632 | -0.059 | -0.0916 | -0.0263 |
| gpt-5.4 | caution_abstention_per_100_words | 102 | 0.0131 | 0.0337 | 0.0206 | 0.002 | 0.0409 |
| gpt-5.4 | caution_missing_info_per_100_words | 102 | 0.0075 | 0.0026 | -0.0049 | -0.0158 | 0.0052 |
| gpt-5.4 | caution_unsupported_causal_per_100_words | 102 | 0.2869 | 0.2756 | -0.0113 | -0.0522 | 0.0295 |
| gpt-5.4 | numeric_value_match_rate | 75 | 0.8944 | 0.925 | 0.0306 | 0.0084 | 0.0543 |
| meta-llama/llama-4-scout-17b-16e-instruct | direct_proportion | 101 | 0.3685 | 0.3437 | -0.0248 | -0.0592 | 0.0105 |
| meta-llama/llama-4-scout-17b-16e-instruct | derived_proportion | 101 | 0.279 | 0.2147 | -0.0642 | -0.0964 | -0.0309 |
| meta-llama/llama-4-scout-17b-16e-instruct | speculative_proportion | 101 | 0.3525 | 0.4415 | 0.089 | 0.0565 | 0.1202 |
| meta-llama/llama-4-scout-17b-16e-instruct | claims_per_100_words | 102 | 4.6438 | 5.0688 | 0.425 | 0.232 | 0.6236 |
| meta-llama/llama-4-scout-17b-16e-instruct | caution_total_per_100_words | 102 | 0.3376 | 0.5863 | 0.2487 | 0.1392 | 0.3626 |
| meta-llama/llama-4-scout-17b-16e-instruct | caution_hedging_per_100_words | 102 | 0.1679 | 0.3752 | 0.2073 | 0.1103 | 0.3074 |
| meta-llama/llama-4-scout-17b-16e-instruct | caution_abstention_per_100_words | 102 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| meta-llama/llama-4-scout-17b-16e-instruct | caution_missing_info_per_100_words | 102 | 0.0 | 0.0094 | 0.0094 | 0.0 | 0.0238 |
| meta-llama/llama-4-scout-17b-16e-instruct | caution_unsupported_causal_per_100_words | 102 | 0.1697 | 0.2017 | 0.0321 | -0.0355 | 0.1013 |
| meta-llama/llama-4-scout-17b-16e-instruct | numeric_value_match_rate | 62 | 0.8073 | 0.86 | 0.0527 | 0.0075 | 0.0976 |
