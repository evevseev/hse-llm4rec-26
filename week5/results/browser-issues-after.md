# Browser issue verification — after fixes

Actual MovieLens data; deterministic seed 1; TensorFlow.js WASM backend. The model is trained and its checkpoint selected by validation RMSE before reporting test metrics.

- Matrix occupancy: 100,000 / 1,586,126 = **6.3047%**; UI displays 6.30%.
- Text decoding: **Misérables, Les (1995)**; fixed parser decodes u.item bytes as Windows-1252 rather than UTF-8.
- Browser recommendation call passes N=20; assertion that every N=20 result has at least 20 train ratings: **true**.
- Selected epoch 3; validation RMSE 1.007781. Model test RMSE 1.061236; mean-baseline test RMSE 1.228900.
- UI source checks: threshold passed=true, model test RMSE rendered=true, matrix density rendered=true.

## User 1 before: N=1

| Rank | Movie | Score | Train ratings |
|---:|---|---:|---:|
| 1 | They Made Me a Criminal (1939) | 5.0000 | 1 |
| 2 | 8 1/2 (1963) | 4.9904 | 29 |
| 3 | Bitter Moon (1992) | 4.8967 | 6 |
| 4 | Wings of Desire (1987) | 4.8865 | 44 |
| 5 | Wrong Trousers, The (1993) | 4.8577 | 101 |
| 6 | Third Man, The (1949) | 4.8016 | 69 |
| 7 | Gay Divorcee, The (1934) | 4.7594 | 12 |
| 8 | Boys, Les (1997) | 4.7542 | 3 |
| 9 | Kaspar Hauser (1993) | 4.7104 | 8 |
| 10 | Women, The (1939) | 4.6655 | 12 |

## User 1 after: N=20

| Rank | Movie | Score | Train ratings |
|---:|---|---:|---:|
| 1 | 8 1/2 (1963) | 4.9904 | 29 |
| 2 | Wings of Desire (1987) | 4.8865 | 44 |
| 3 | Wrong Trousers, The (1993) | 4.8577 | 101 |
| 4 | Third Man, The (1949) | 4.8016 | 69 |
| 5 | 12 Angry Men (1957) | 4.6523 | 108 |
| 6 | East of Eden (1955) | 4.6482 | 54 |
| 7 | Dr. Strangelove or: How I Learned to Stop Worrying and Love the Bomb (1963) | 4.6189 | 170 |
| 8 | Manchurian Candidate, The (1962) | 4.6064 | 112 |
| 9 | Big Sleep, The (1946) | 4.5997 | 62 |
| 10 | Great Escape, The (1963) | 4.5995 | 105 |
