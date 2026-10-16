# Browser issue audit — before fixes

## Real MovieLens split and N wiring

- Dataset: 100000 ratings, 943 users, 1682 movies; split 79619 train / 9596 validation / 10785 test.
- The browser renderer calls `recommendTopK(user, 10)` without the N argument; function default is N=1, although validation selected N=20.
- Bitter Moon (1992) (movie 1268) has 6 train rating(s), so it passes N=1 but must be excluded at N=20.
- Aparajito (1956) (movie 1558) has 5 train rating(s), so it passes N=1 but must be excluded at N=20.

## Real matrix occupancy

- 100,000 observed user–movie cells / 1,586,126 valid cells (6.3047%). The page's dataset renderer prints matrix dimensions but no occupancy ratio.

## Real title bytes and decoding

- The raw u.item row contains a single-byte e9 in `Misérables, Les (1995)`; decoding that byte sequence as UTF-8 produces `Mis�rables, Les (1995)` with U+FFFD.
- `data.js` uses `Response.text()` (UTF-8 default), which explains the replacement diamond in the browser.

## Test RMSE rendering

- The split summary computes and shows baseline test RMSE: true.
- `runPipeline()` does not compute or render `computeRMSEFor(testSet)` after restoring the selected checkpoint: true.
