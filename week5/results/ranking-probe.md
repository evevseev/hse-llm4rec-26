# Ranking/clipping probe

Fresh full MovieLens training with the same default parameters; all ranking variants below use the same selected model factors.

- Selected epoch: 3; validation RMSE 1.010434.
- Evaluable users / relevant candidate test items: 861 / 5142.
- Current clipped-score Top-K: macro Recall@10 0.010101 (61 hits); 3377/8610 Top-10 slots (39.22%) have score exactly 5 after clipping.
- Raw-score ranking, full catalog: macro Recall@10 0.008889 (53 hits).
- Raw-score ranking, train-movie pool only: macro Recall@10 0.008889 (53 hits).
- This is a second random-initialized training run; compare variants within this run, not its absolute numbers with the previously saved run.
