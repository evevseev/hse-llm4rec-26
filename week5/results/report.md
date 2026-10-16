# Week 5 matrix factorization results

- TensorFlow.js backend: wasm
- Parameters: epochs=20, lr=0.01, reg=0.05, batchSize=64
- Dataset split: 79619 train / 9596 validation / 10785 test ratings; 0 skipped users
- Training time: 57.7 seconds
- Best validation epoch: 2
- Test mean-baseline RMSE: 1.228900
- Best-checkpoint validation RMSE: 1.015595
- Best-checkpoint test RMSE: 1.049802
- Recall@10: 0.015682
- Recall exclusions: 13 unseen relevant movie IDs; 82 users without relevant candidates
- Top-10 train/validation exclusion check: user 1: 0 overlap(s); user 2: 0 overlap(s)
- Recall ranking candidates: Rank all catalog movies; count relevant test movies only when their IDs occur in train.
- Built-in tests: 11 passed / 0 failed / 0 pending

### User 1

1. Close Shave, A (1995) — 5.0000
2. Casablanca (1942) — 5.0000
3. Pather Panchali (1955) — 5.0000
4. Santa with Muscles (1996) — 5.0000
5. Lamerica (1994) — 4.9966
6. When We Were Kings (1996) — 4.9798
7. Wrong Trousers, The (1993) — 4.9417
8. My Man Godfrey (1936) — 4.9384
9. North by Northwest (1959) — 4.9228
10. Manchurian Candidate, The (1962) — 4.9044

### User 2

1. Braindead (1992) — 4.9004
2. Bad Taste (1987) — 4.8633
3. Quiet Man, The (1952) — 4.7769
4. Killer (Bulletproof Heart) (1994) — 4.7728
5. Steal Big, Steal Little (1995) — 4.7683
6. Maya Lin: A Strong Clear Vision (1994) — 4.6924
7. Nina Takes a Lover (1994) — 4.6807
8. Paris Is Burning (1990) — 4.6770
9. Celluloid Closet, The (1995) — 4.6727
10. Double Happiness (1994) — 4.6659
