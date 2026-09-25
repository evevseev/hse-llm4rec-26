# AI-assisted helper script. Independent recount of key numbers without the JavaScript code.
# Run from week2/: python3 eval/recount_check.py > results/recount_check.txt
import collections
import math

rows = [line.rstrip("\n").split("|") for line in open("original/u.item", encoding="latin-1")]
title = {int(r[0]): r[1] for r in rows}
raters = collections.Counter(int(line.split("\t")[1]) for line in open("original/u.data"))


def vectors(start):
    return {int(r[0]): [int(x) for x in r[start:start + 18]] for r in rows}


def jaccard_top5(vec):
    sets = {i: {k for k, x in enumerate(v) if x} for i, v in vec.items()}
    result = {}
    for a, ga in sets.items():
        scored = []
        for pos, (b, gb) in enumerate(sets.items()):
            if b == a:
                continue
            union = len(ga | gb)
            scored.append((-(len(ga & gb) / union if union else 0), pos, b))
        result[a] = [b for _, _, b in sorted(scored)[:5]]
    return result


# 1. Genre parser: starter reads flags from field 5 (unknown), fixed reads from field 6.
old, new = jaccard_top5(vectors(5)), jaccard_top5(vectors(6))
print("Top-5 changed (with order):", sum(old[k] != new[k] for k in old))
print("Top-5 changed (as a set):", sum(set(old[k]) != set(new[k]) for k in old))

# 2. Cosine and dot product on fixed genres, duplicate titles merged (first ID kept).
vec = vectors(6)
first_id = {}
for i in sorted(vec):
    first_id.setdefault(title[i], i)
ids = [i for i in first_id.values() if sum(vec[i]) > 0]


def cosine(p, c):
    dot = sum(x * y for x, y in zip(p, c))
    norm = math.sqrt(sum(x * x for x in p)) * math.sqrt(sum(x * x for x in c))
    return dot / norm if norm else 0


def top5(selected, score):
    profile = [sum(vec[i][k] for i in selected) / len(selected) for k in range(18)]
    chosen = {title[i] for i in selected}
    ranked = sorted(ids, key=lambda c: (-round(score(profile, vec[c]), 12), -raters[c], title[c], c))
    return [c for c in ranked if title[c] not in chosen][:5]


for name, selected in [("Toy Story", [1]), ("Toy Story + Star Wars + Fargo", [1, 50, 100])]:
    print(f"\nTop-5 for {name}:")
    for c in top5(selected, cosine):
        profile = [sum(vec[i][k] for i in selected) / len(selected) for k in range(18)]
        print(f"  {title[c]}  cosine={cosine(profile, vec[c]):.6f}  raters={raters[c]}")

profile = [sum(vec[i][k] for i in [1, 50, 100]) / 3 for k in range(18)]
print("\nSelected movies vs their own profile:")
for i in [1, 50, 100]:
    print(f"  {title[i]}  cosine={cosine(profile, vec[i]):.6f}")


def dot(p, c):
    return sum(x * y for x, y in zip(p, c))


for name, score in [("cosine", cosine), ("dot product", dot)]:
    genres = [sum(vec[c]) for q in ids for c in top5([q], score)]
    print(f"\nAll {len(ids)} item-to-item queries, {name}: mean genres per recommendation = {sum(genres) / len(genres):.2f}")

# 3. Titles with non-ASCII (Latin-1) bytes, which fetch().text() would decode wrongly as UTF-8.
raw_titles = [line.split(b"|")[1] for line in open("original/u.item", "rb")]
print("\nTitles with non-ASCII bytes:", sum(any(b > 127 for b in t) for t in raw_titles))
