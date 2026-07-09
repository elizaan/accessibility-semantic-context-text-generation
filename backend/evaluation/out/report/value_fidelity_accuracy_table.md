# Value Fidelity — Numeric Claim Accuracy vs. Real Ground Truth

Source: backend/evaluation/out/report/value_fidelity_accuracy.png / value_fidelity_summary.csv

Scope: 43/59 charts. Includes percent-scale (63% vs 0.63) and thousands-scale (title says "(in 1,000s)") rescaling checks. accuracy_pct = share of extracted numbers (in DIRECT- or DERIVED-flagged claims) matching real ground truth. n = total numbers checked.

## DIRECT claims

| Model | V1 | V2 | V3 | V4 |
|---|---|---|---|---|
| gemini-3.5-flash | 80.5% (n=210) | 78.4% (n=208) | 71.4% (n=105) | 71.9% (n=135) |
| gpt-5.4 | 80.4% (n=525) | 86.6% (n=357) | 69.6% (n=171) | 66.1% (n=165) |
| llama-4-scout-17b-16e-instruct | 72.8% (n=180) | 75.0% (n=96) | 63.9% (n=122) | 70.4% (n=108) |

## DERIVED claims

| Model | V1 | V2 | V3 | V4 |
|---|---|---|---|---|
| gemini-3.5-flash | 89.6% (n=367) | 97.1% (n=340) | 87.2% (n=366) | 88.4% (n=361) |
| gpt-5.4 | 97.0% (n=501) | 97.3% (n=602) | 86.5% (n=252) | 92.5% (n=159) |
| llama-4-scout-17b-16e-instruct | 98.3% (n=59) | 100.0% (n=35) | 86.8% (n=53) | 92.2% (n=51) |
