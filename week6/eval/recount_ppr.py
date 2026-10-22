# Generated with an AI assistant.
# Independent recount for week 6 with the Python standard library only (no TensorFlow.js,
# no code from fixed/). Rebuilds the per-user chronological 80/10/10 split, the positive
# training graph, popularity, the shared cohorts, and Recall@10 for popularity, global
# PageRank and PPR. Also recounts PPR with the restart shifted to the next node (the raw
# user id read as a node index) and the hand chain for user 1.
# Usage: python3 eval/recount_ppr.py > results/recount_ppr.txt
import os
import sys
from collections import defaultdict
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "original")
TOL, MAX_ITER, K = 1e-6, 500, 10

ratings = []
with open(os.path.join(DATA, "u.data")) as f:
    for line in f:
        if line.strip():
            u, i, r, t = map(int, line.split("\t"))
            ratings.append((u, i, r, t))
titles = {}
with open(os.path.join(DATA, "u.item"), encoding="windows-1252") as f:
    for line in f:
        if line.strip():
            parts = line.split("|")
            titles[int(parts[0])] = parts[1]

by_user = defaultdict(list)
for u, i, r, t in ratings:
    by_user[u].append((t, i, r))
train, val, test = [], [], []
for u, rows in by_user.items():
    rows.sort()
    n = len(rows)
    n_train, n_val = n * 8 // 10, n // 10
    for k, (t, i, r) in enumerate(rows):
        (train if k < n_train else val if k < n_train + n_val else test).append((u, i, r))

users = sorted({u for u, i, r in train})
movies = sorted({i for u, i, r in train})
n_users, n_movies = len(users), len(movies)
N = n_users + n_movies
user_node = {u: k for k, u in enumerate(users)}
movie_node = {m: n_users + k for k, m in enumerate(movies)}
neighbors = [set() for _ in range(N)]
for u, i, r in train:
    if r >= 4:
        neighbors[user_node[u]].add(movie_node[i])
        neighbors[movie_node[i]].add(user_node[u])
neighbors = [sorted(s) for s in neighbors]
degree = [len(s) for s in neighbors]
edges = sum(degree[:n_users])
popularity = {m: degree[movie_node[m]] for m in movies}

rated_train, rated_val = defaultdict(set), defaultdict(set)
for u, i, r in train:
    rated_train[u].add(i)
for u, i, r in val:
    rated_val[u].add(i)


def excluded(split, u):
    return rated_train[u] if split == "val" else rated_train[u] | rated_val[u]


def relevant(split, u):
    rows = val if split == "val" else test
    ex = excluded(split, u)
    return {i for uu, i, r in rows if uu == u and r >= 4 and i in movie_node and i not in ex}


rel = {s: {u: relevant(s, u) for u in users} for s in ("val", "test")}
cohort = {s: [u for u in users if degree[user_node[u]] > 0 and rel[s][u]] for s in ("val", "test")}
unseen_test = sum(1 for u, i, r in test if r >= 4 and i not in movie_node)


def propagate(alpha, restart):
    """restart: dict node -> mass (sums to 1). Returns (p, iterations, residual)."""
    v = [0.0] * N
    for node, mass in restart.items():
        v[node] = mass
    p = v[:]
    residual = float("inf")
    for it in range(1, MAX_ITER + 1):
        nxt = [0.0] * N
        dangling = 0.0
        for a in range(N):
            if p[a] == 0.0:
                continue
            if degree[a] == 0:
                dangling += p[a]
                continue
            share = alpha * p[a] / degree[a]
            for b in neighbors[a]:
                nxt[b] += share
        base = (1 - alpha) + alpha * dangling
        for node, mass in restart.items():
            nxt[node] += base * mass
        residual = sum(abs(x - y) for x, y in zip(nxt, p))
        p = nxt
        if residual < TOL:
            return p, it, residual
    return p, MAX_ITER, residual


def top_k(scores, ex):
    order = sorted(movies, key=lambda m: (-scores[m], m))
    return [m for m in order if m not in ex][:K]


def user_recall(args):
    method, split, alpha, u, shift = args
    if method == "ppr":
        seed = user_node[u] + 1 if shift else user_node[u]
        seed = min(seed, N - 1)
        p, _, _ = propagate(alpha, {seed: 1.0})
        scores = {m: p[movie_node[m]] for m in movies}
    else:
        scores = GLOBAL[method]
    hits = len(rel[split][u] & set(top_k(scores, excluded(split, u))))
    return hits / len(rel[split][u])


def macro(method, split, alpha=None, shift=False, pool=None):
    jobs = [(method, split, alpha, u, shift) for u in cohort[split]]
    values = pool.map(user_recall, jobs, chunksize=8) if pool else list(map(user_recall, jobs))
    return sum(values) / len(values)


GLOBAL = {"popularity": {m: popularity[m] for m in movies}}
pr, pr_it, pr_res = propagate(0.5, {a: 1.0 / N for a in range(N)})
GLOBAL["pagerank"] = {m: pr[movie_node[m]] for m in movies}

if __name__ == "__main__":
    print("split train/val/test:", len(train), len(val), len(test))
    print("graph: users", n_users, "movies", n_movies, "nodes", N, "positive edges", edges)
    print("zero-degree users", sum(1 for k in range(n_users) if degree[k] == 0),
          "zero-degree movies", sum(1 for k in range(n_users, N) if degree[k] == 0))
    print("cohort val", len(cohort["val"]), "test", len(cohort["test"]))
    print("test: relevant movies outside the training pool", unseen_test,
          "| train users without an eligible relevant test movie", n_users - len(cohort["test"]))
    print("global PageRank alpha 0.5: iterations", pr_it, "residual %.3e" % pr_res,
          "total mass %.10f" % sum(pr))
    with Pool(8) as pool:
        for a in (0.5, 0.7, 0.85, 0.95):
            print("PPR val Recall@10 alpha %.2f: %.6f" % (a, macro("ppr", "val", a, pool=pool)))
        print("test Recall@10 popularity: %.6f" % macro("popularity", "test"))
        print("test Recall@10 global PageRank alpha 0.5: %.6f" % macro("pagerank", "test"))
        print("test Recall@10 PPR alpha 0.5: %.6f" % macro("ppr", "test", 0.5, pool=pool))
        print("test Recall@10 PPR alpha 0.5, restart shifted to the next node: %.6f"
              % macro("ppr", "test", 0.5, shift=True, pool=pool))

    # Hand chain for user 1 at alpha 0.5.
    u, alpha = 1, 0.5
    node = user_node[u]
    print("\nuser 1: node", node, "degree", degree[node])
    print("after step 1: mass on user 1 = %.4f, on each liked movie = 0.5/%d = %.10f"
          % (1 - alpha, degree[node], alpha / degree[node]))
    p, it, res = propagate(alpha, {node: 1.0})
    print("PPR iterations", it, "residual %.3e" % res, "total mass %.10f" % sum(p))
    scores = {m: p[movie_node[m]] for m in movies}
    lst = top_k(scores, excluded("test", u))
    for rank, m in enumerate(lst, 1):
        print("  %2d %-45s score %.10f popularity %d %s" % (rank, titles[m], scores[m], popularity[m],
                                                          "HIT" if m in rel["test"][u] else ""))
    hits = len(rel["test"][u] & set(lst))
    print("user 1 Recall@10 = %d / %d = %.6f" % (hits, len(rel["test"][u]), hits / len(rel["test"][u])))

    # Overlaps for users 1 and 2: PPR vs popularity, and one setting at a time (readme 6.2).
    lists = {}
    for uid in (1, 2):
        ex = excluded("test", uid)
        lists[("popularity", uid)] = top_k(GLOBAL["popularity"], ex)
        for a in (0.5, 0.85):
            p, _, _ = propagate(a, {user_node[uid]: 1.0})
            lists[("ppr", a, uid)] = top_k({m: p[movie_node[m]] for m in movies}, ex)
    mean_pop = lambda lst: sum(popularity[m] for m in lst) / len(lst)
    for uid in (1, 2):
        print("user %d: PPR alpha 0.5 vs popularity Top-10 common %d of 10"
              % (uid, len(set(lists[("ppr", 0.5, uid)]) & set(lists[("popularity", uid)]))))
    A, B, C = lists[("ppr", 0.85, 1)], lists[("ppr", 0.85, 2)], lists[("ppr", 0.5, 1)]
    print("A user 1 alpha 0.85 mean popularity %.1f | B user 2 alpha 0.85 %.1f | C user 1 alpha 0.5 %.1f"
          % (mean_pop(A), mean_pop(B), mean_pop(C)))
    print("common A-B %d, A-C %d" % (len(set(A) & set(B)), len(set(A) & set(C))))
    sys.stdout.flush()
