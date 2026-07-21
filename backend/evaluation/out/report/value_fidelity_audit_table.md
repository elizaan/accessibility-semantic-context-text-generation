# Value-Fidelity Human Audit

False-positive rate: sampled claims the automated checker called `correct` that both annotators independently judged `invalid`. False-negative rate: sampled claims called `fabricated` that both annotators judged `valid`. The two `tuple_verified` columns are the direct, quantified answer to whether the category/series-aware tuple check (vs. the flat value-only check) actually reduces the false-positive rate.

| n_double_annotated | cohens_kappa | false_positive_rate | false_positive_n | false_negative_rate | false_negative_n | fp_rate_tuple_verified_yes | fp_rate_tuple_verified_not_yes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 1.0 | 0.0 | 10 |  | 0 | 0.0 | 0.0 |
