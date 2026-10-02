# Checks and manual formula verification

## Data parsing and duplicate-title safety

- ISO-8859-1 decoding: movie ID 543 is “Misérables, Les (1995)”; the old UTF-8 decode was “Mis�rables, Les (1995)”; replacement-character titles after the fix: 0.
- Genre offset: movie ID 1 (Toy Story) parses as Animation, Children's, Comedy. The old offset would have reported Children's, Comedy, Crime.
- Exact normalized duplicate-title groups: 18; user/title cases with one duplicate ID rated and another unrated: 655.
- Duplicate-rated Top-5 rows before alias guard (current other policies): User-Based 2; Item-Based 0. After guard: User-Based 0; Item-Based 0.
- Final recommendation lists for users 1 and 196 match the actual fixed JavaScript methods; a full-dataset optimized calculation confirms zero duplicate-rated title rows after the guard.
- Simplifying the Item-Based support count left the Top-5 title/score pairs unchanged for users 1 and 196.

## Manual cosine calculation

User 1 vs user 876; common ratings in order: Antonia's Line (1995) 5×5; Braveheart (1995) 4×4; Hoop Dreams (1994) 5×5; Raiders of the Lost Ark (1981) 5×4; 12 Angry Men (1957) 5×4; Godfather: Part II, The (1974) 4×4; Raising Arizona (1987) 4×4.
- n=7; dot=138; squared norms=148 and 130.
- Raw cosine = 138/(√148 × √130) = 0.994893406; overlap weight = 1.000.
- Adjusted similarity manually = 0.994893406; fixed code = 0.994893406.

## Manual User-Based prediction

For Trainspotting (1996), contributing neighbors: 118: 0.982131×5; 232: 0.982092×5; 139: 0.980972×5.
- Weighted sum = 14.725973347; similarity sum = 2.945194669.
- Prediction = 14.725973347/2.945194669 = 5.000000000; code = 5.000000000.

The script asserts agreement between manual and code values (tolerance 1e-12) and between optimized all-user rankings and the actual fixed recommenders for users 1 and 196.
