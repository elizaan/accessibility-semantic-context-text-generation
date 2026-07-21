# Output Length (mean word count per output, by model x variant)

Tests the same 'unfaltering fluency' pattern as speculation volume, but with no semantic judgment needed: if length stays flat as metadata drops (V1->V4), the model isn't visibly hedging or truncating when it has less to say.

| model_id | variant | n_records | mean_total_words | min | max |
| --- | --- | --- | --- | --- | --- |
| gemini-3.5-flash | 1 | 102 | 343.4 | 250 | 491 |
| gemini-3.5-flash | 2 | 102 | 327.0 | 180 | 497 |
| gemini-3.5-flash | 3 | 102 | 345.7 | 222 | 490 |
| gemini-3.5-flash | 4 | 102 | 353.8 | 191 | 636 |
| gpt-5.4 | 1 | 102 | 604.5 | 378 | 951 |
| gpt-5.4 | 2 | 102 | 562.5 | 310 | 862 |
| gpt-5.4 | 3 | 102 | 540.2 | 185 | 905 |
| gpt-5.4 | 4 | 102 | 531.1 | 278 | 827 |
| meta-llama/llama-4-scout-17b-16e-instruct | 1 | 102 | 215.5 | 126 | 377 |
| meta-llama/llama-4-scout-17b-16e-instruct | 2 | 102 | 208.4 | 107 | 533 |
| meta-llama/llama-4-scout-17b-16e-instruct | 3 | 102 | 214.6 | 118 | 405 |
| meta-llama/llama-4-scout-17b-16e-instruct | 4 | 102 | 229.0 | 125 | 417 |
