# RQ1: Accessible-Context Effect (V1 vs V3 — same image, context added)

Charts were purposively sampled, not randomly drawn from a defined population. These bootstrap CIs describe resampling variability of the observed paired differences among the charts actually run — they are not a claim about sampling error relative to some larger population of charts. A CI that excludes 0 should be read as "consistent, in this direction, across the charts we have," not as statistical generalizability. Rows marked `*` have n_pairs < 10 — read with extra caution.

| model_id | metric | n_pairs | mean_a | mean_b | mean_diff | ci_lo | ci_hi |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gemini-3.5-flash | direct_proportion | 102 | 0.2449 | 0.141 | -0.1039 | -0.1331 | -0.0748 |
| gemini-3.5-flash | derived_proportion | 102 | 0.3552 | 0.4356 | 0.0804 | 0.048 | 0.113 |
| gemini-3.5-flash | speculative_proportion | 102 | 0.3998 | 0.4234 | 0.0236 | -0.0024 | 0.0494 |
| gemini-3.5-flash | claims_per_100_words | 102 | 3.6796 | 3.5521 | -0.1276 | -0.2333 | -0.0179 |
| gemini-3.5-flash | caution_total_per_100_words | 102 | 0.1389 | 0.1656 | 0.0267 | -0.0231 | 0.0773 |
| gemini-3.5-flash | caution_hedging_per_100_words | 102 | 0.0214 | 0.0339 | 0.0124 | -0.0107 | 0.038 |
| gemini-3.5-flash | caution_abstention_per_100_words | 102 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| gemini-3.5-flash | caution_missing_info_per_100_words | 102 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| gemini-3.5-flash | caution_unsupported_causal_per_100_words | 102 | 0.1175 | 0.1317 | 0.0143 | -0.0313 | 0.0595 |
| gemini-3.5-flash | numeric_value_match_rate | 75 | 0.8781 | 0.867 | -0.0111 | -0.0375 | 0.0156 |
| gpt-5.4 | direct_proportion | 102 | 0.3702 | 0.3009 | -0.0692 | -0.0932 | -0.0452 |
| gpt-5.4 | derived_proportion | 102 | 0.3412 | 0.3485 | 0.0073 | -0.0177 | 0.0332 |
| gpt-5.4 | speculative_proportion | 102 | 0.2886 | 0.3506 | 0.0619 | 0.0453 | 0.0791 |
| gpt-5.4 | claims_per_100_words | 102 | 3.755 | 3.8189 | 0.0638 | -0.0206 | 0.1486 |
| gpt-5.4 | caution_total_per_100_words | 102 | 0.4298 | 0.6228 | 0.193 | 0.1238 | 0.2639 |
| gpt-5.4 | caution_hedging_per_100_words | 102 | 0.1222 | 0.2696 | 0.1474 | 0.0957 | 0.2007 |
| gpt-5.4 | caution_abstention_per_100_words | 102 | 0.0131 | 0.0399 | 0.0269 | 0.01 | 0.0443 |
| gpt-5.4 | caution_missing_info_per_100_words | 102 | 0.0075 | 0.0201 | 0.0125 | 0.0013 | 0.0247 |
| gpt-5.4 | caution_unsupported_causal_per_100_words | 102 | 0.2869 | 0.2932 | 0.0063 | -0.0372 | 0.0498 |
| gpt-5.4 | numeric_value_match_rate | 73 | 0.8945 | 0.8332 | -0.0613 | -0.1037 | -0.0198 |
| meta-llama/llama-4-scout-17b-16e-instruct | direct_proportion | 101 | 0.3685 | 0.3541 | -0.0144 | -0.0508 | 0.0214 |
| meta-llama/llama-4-scout-17b-16e-instruct | derived_proportion | 101 | 0.279 | 0.2803 | 0.0013 | -0.0318 | 0.0361 |
| meta-llama/llama-4-scout-17b-16e-instruct | speculative_proportion | 101 | 0.3525 | 0.3656 | 0.0131 | -0.0149 | 0.0419 |
| meta-llama/llama-4-scout-17b-16e-instruct | claims_per_100_words | 102 | 4.6438 | 4.6367 | -0.0071 | -0.2458 | 0.2341 |
| meta-llama/llama-4-scout-17b-16e-instruct | caution_total_per_100_words | 102 | 0.3376 | 0.5118 | 0.1742 | 0.0589 | 0.2938 |
| meta-llama/llama-4-scout-17b-16e-instruct | caution_hedging_per_100_words | 102 | 0.1679 | 0.3664 | 0.1984 | 0.0945 | 0.3068 |
| meta-llama/llama-4-scout-17b-16e-instruct | caution_abstention_per_100_words | 102 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| meta-llama/llama-4-scout-17b-16e-instruct | caution_missing_info_per_100_words | 102 | 0.0 | 0.0115 | 0.0115 | 0.0 | 0.0262 |
| meta-llama/llama-4-scout-17b-16e-instruct | caution_unsupported_causal_per_100_words | 102 | 0.1697 | 0.1339 | -0.0357 | -0.0923 | 0.0212 |
| meta-llama/llama-4-scout-17b-16e-instruct | numeric_value_match_rate | 66 | 0.8114 | 0.7769 | -0.0344 | -0.0809 | 0.0129 |
