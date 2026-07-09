# Paired Contrasts (V1<->V2 image effect, V3<->V4 framing effect)

| model_id | contrast | speculative_total_delta | direct_total_delta | groundedness_ratio_delta | speculation_volume_per_record_delta | mean_score_overall_delta |
| --- | --- | --- | --- | --- | --- | --- |
| gemini-3.5-flash | image_effect (V1->V2) | 41 | 30 | -0.059 | 0.7 | -0.288 |
| gemini-3.5-flash | framing_effect (V3->V4) | 28 | 45 | -0.021 | 0.47 | 0.667 |
| gpt-5.4 | image_effect (V1->V2) | -19 | -45 | -0.013 | -0.32 | -0.52 |
| gpt-5.4 | framing_effect (V3->V4) | -10 | -14 | -0.003 | -0.17 | 1.04 |
| meta-llama/llama-4-scout-17b-16e-instruct | image_effect (V1->V2) | 42 | -38 | -0.104 | 0.71 | -0.452 |
| meta-llama/llama-4-scout-17b-16e-instruct | framing_effect (V3->V4) | 20 | -21 | -0.039 | 0.34 | 0.706 |
