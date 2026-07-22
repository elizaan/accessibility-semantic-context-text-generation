# RQ3: Missing-Context Disclosure (V3 vs V4 — same evidence, disclosure added)

Charts were purposively sampled, not randomly drawn from a defined population. These bootstrap CIs describe resampling variability of the observed paired differences among the charts actually run — they are not a claim about sampling error relative to some larger population of charts. A CI that excludes 0 should be read as "consistent, in this direction, across the charts we have," not as statistical generalizability. Rows marked `*` have n_pairs < 10 — read with extra caution.

| model_id | metric | n_pairs | mean_a | mean_b | mean_diff | ci_lo | ci_hi |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gemini-3.5-flash | direct_proportion | 102 | 0.141 | 0.196 | 0.055 | 0.0363 | 0.0739 |
| gemini-3.5-flash | derived_proportion | 102 | 0.4356 | 0.3697 | -0.0659 | -0.0905 | -0.0407 |
| gemini-3.5-flash | speculative_proportion | 102 | 0.4234 | 0.4343 | 0.0109 | -0.0101 | 0.0315 |
| gemini-3.5-flash | claims_per_100_words | 102 | 3.5521 | 3.5818 | 0.0298 | -0.0781 | 0.1359 |
| gemini-3.5-flash | caution_total_per_100_words | 102 | 0.1656 | 0.1567 | -0.0089 | -0.06 | 0.0425 |
| gemini-3.5-flash | caution_hedging_per_100_words | 102 | 0.0339 | 0.0299 | -0.004 | -0.0292 | 0.0199 |
| gemini-3.5-flash | caution_abstention_per_100_words | 102 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| gemini-3.5-flash | caution_missing_info_per_100_words | 102 | 0.0 | 0.0027 | 0.0027 | 0.0 | 0.008 |
| gemini-3.5-flash | caution_unsupported_causal_per_100_words | 102 | 0.1317 | 0.1241 | -0.0076 | -0.0545 | 0.0397 |
| gemini-3.5-flash | numeric_value_match_rate | 76 | 0.8555 | 0.8524 | -0.0031 | -0.024 | 0.0172 |
| gpt-5.4 | direct_proportion | 102 | 0.3009 | 0.3361 | 0.0352 | 0.0115 | 0.0599 |
| gpt-5.4 | derived_proportion | 102 | 0.3485 | 0.317 | -0.0315 | -0.0545 | -0.0093 |
| gpt-5.4 | speculative_proportion | 102 | 0.3506 | 0.3468 | -0.0037 | -0.0228 | 0.0148 |
| gpt-5.4 | claims_per_100_words | 102 | 3.8189 | 3.8965 | 0.0776 | 0.0088 | 0.1445 |
| gpt-5.4 | caution_total_per_100_words | 102 | 0.6228 | 0.6172 | -0.0056 | -0.0748 | 0.0644 |
| gpt-5.4 | caution_hedging_per_100_words | 102 | 0.2696 | 0.2769 | 0.0073 | -0.0456 | 0.0603 |
| gpt-5.4 | caution_abstention_per_100_words | 102 | 0.0399 | 0.0383 | -0.0016 | -0.0252 | 0.0223 |
| gpt-5.4 | caution_missing_info_per_100_words | 102 | 0.0201 | 0.0242 | 0.0042 | -0.0098 | 0.0187 |
| gpt-5.4 | caution_unsupported_causal_per_100_words | 102 | 0.2932 | 0.2778 | -0.0154 | -0.0613 | 0.0301 |
| gpt-5.4 | numeric_value_match_rate | 73 | 0.8203 | 0.7882 | -0.0321 | -0.0745 | 0.0032 |
| meta-llama/llama-4-scout-17b-16e-instruct | direct_proportion | 102 | 0.3533 | 0.3085 | -0.0448 | -0.0793 | -0.0098 |
| meta-llama/llama-4-scout-17b-16e-instruct | derived_proportion | 102 | 0.2802 | 0.2979 | 0.0177 | -0.0166 | 0.0527 |
| meta-llama/llama-4-scout-17b-16e-instruct | speculative_proportion | 102 | 0.3665 | 0.3936 | 0.0271 | -0.0028 | 0.0569 |
| meta-llama/llama-4-scout-17b-16e-instruct | claims_per_100_words | 102 | 4.6367 | 4.4329 | -0.2038 | -0.4727 | 0.0517 |
| meta-llama/llama-4-scout-17b-16e-instruct | caution_total_per_100_words | 102 | 0.5118 | 0.6167 | 0.1049 | 0.0031 | 0.2038 |
| meta-llama/llama-4-scout-17b-16e-instruct | caution_hedging_per_100_words | 102 | 0.3664 | 0.4157 | 0.0493 | -0.0339 | 0.135 |
| meta-llama/llama-4-scout-17b-16e-instruct | caution_abstention_per_100_words | 102 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| meta-llama/llama-4-scout-17b-16e-instruct | caution_missing_info_per_100_words | 102 | 0.0115 | 0.0202 | 0.0087 | -0.0132 | 0.031 |
| meta-llama/llama-4-scout-17b-16e-instruct | caution_unsupported_causal_per_100_words | 102 | 0.1339 | 0.1808 | 0.0468 | -0.0182 | 0.1125 |
| meta-llama/llama-4-scout-17b-16e-instruct | numeric_value_match_rate | 69 | 0.7842 | 0.8005 | 0.0163 | -0.0205 | 0.0531 |
