# Generated with an AI assistant. Independent check of the Recall@10 arithmetic with the standard library only.
# It rebuilds the relevant test targets of every user from original/u.data, compares them with the saved
# per-user rows of the seed-1 model (results/recall-semantics.json), and recomputes the macro mean by hand.
import collections, json

rows = [tuple(map(int, l.split("\t"))) for l in open("original/u.data")]
by_user = collections.defaultdict(list)
for u, m, r, t in rows:
    by_user[u].append((t, m, r))
train_movies, test_rel = set(), collections.defaultdict(set)
test_all = collections.defaultdict(set)
for u, lst in by_user.items():
    lst.sort()
    n = len(lst)
    a, b = int(0.8 * n), int(0.1 * n)
    for t, m, r in lst[:a]:
        train_movies.add(m)
    for t, m, r in lst[a + b:]:
        test_all[u].add(m)
        if r >= 4.0:
            test_rel[u].add(m)
mine = {u: {m for m in s if m in train_movies} for u, s in test_rel.items()}
mine = {u: s for u, s in mine.items() if s}

saved = json.load(open("results/recall-semantics.json"))["recall"]["trainPoolOnSameTargets"]
per_user = json.load(open("results/recall-semantics.json"))["perUserRecall"]
agent = {p["userId"]: p for p in per_user if p["relevantTrainPool"] > 0}
print("users with train-known relevant targets: mine", len(mine), "saved rows", len(agent))
print("same user set:", set(mine) == set(agent))
print("denominators equal for every user:", all(len(mine[u]) == agent[u]["relevantTrainPool"] for u in mine))
print("sum of denominators:", sum(len(s) for s in mine.values()))
hits = {u: agent[u]["trainPoolHits"] for u in mine}
macro = sum(hits[u] / len(mine[u]) for u in mine) / len(mine)
print("total hits", sum(hits.values()), "| macro recall from my denominators %.6f" % macro,
      "| saved macro %.6f" % saved["macro"])
u0 = next(u for u in sorted(mine) if hits[u] > 0)
print("hand example: user %d has %d relevant test movies in the train pool and %d hits, so recall = %d/%d = %.4f"
      % (u0, len(mine[u0]), hits[u0], hits[u0], len(mine[u0]), hits[u0] / len(mine[u0])))
