# Gather gradients and Recall candidate-pool audit

## `tf.gather` and one-hot `matMul` gradient check (CPU)

- Same factors, indices [2,0,2] (including a repeated user), paired movie rows, and MSE objective.
- Gather loss 1.140966654; one-hot/matMul loss 1.140966654.
- Maximum absolute gradient difference: user factors 0.000e+0, item factors 0.000e+0.
- Current code uses gather in `predictRating` and the TensorFlow path of `computeRMSEFor`; `trainMF` uses one-hot selection plus `matMul`.

## Train/test overlap and `unseenIds` on MovieLens 100k

- 100000 ratings, 100000 unique user/movie pairs; duplicate pairs: 0.
- Relevant test ratings (>=4): 5155; relevant test pairs also present for that same user in train: 0.
- 13 relevant test-rating rows refer to 13 distinct movie IDs absent from the global train pool. Those are the IDs counted by `unseenIds`.
- 5142 relevant test rows have a movie ID present in another user's train history but not in this user's train history; those are not unseen IDs.
- The data has no duplicate user/movie pairs, so the README's same-user train/test overlap scenario does not occur here. The code's `unseenIds` is global item-ID absence, not same-user overlap.

## Recall on the same fitted weights (seed 1)

- Training: 79619 train ratings; selected epoch 3; validation RMSE 1.007781.
- Full catalog, with all relevant test targets in denominator: 0.014292 macro / 0.015325 micro (79/5155, 862 users).
- Full catalog, restricted to the train-known relevant targets for an apples-to-apples comparison: 0.014312 macro / 0.015364 micro (79/5142, 861 users).
- Train-only candidate pool, same train-known targets: 0.014312 macro / 0.015364 micro (79/5142, 861 users).
- Existing `recallAtK(10, 1)` result matches direct train-pool calculation: true.
- Candidate pools: 1682 catalog movies vs 1611 movies appearing in train.
- Full-catalog and train-only rows use the same saved user/item factors and same per-user train+validation exclusions; full-catalog's standard denominator includes relevant test items absent from train, while the shared-target comparison isolates ranking-pool effects.
