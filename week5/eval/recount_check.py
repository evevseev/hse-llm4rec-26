# Generated with an AI assistant. Independent recount of the key numbers with the Python standard library only.
# It reads original/u.data and does not use any code from fixed/.
import collections, math

ROOT = "original/"
rows = [tuple(map(int, l.split("\t"))) for l in open(ROOT + "u.data")]
titles = {}
for l in open(ROOT + "u.item", encoding="latin-1"):
    f = l.split("|")
    titles[int(f[0])] = f[1]

by_user = collections.defaultdict(list)
for u, m, r, t in rows:
    by_user[u].append((t, m, r))

train, val, test = [], [], []
for u, lst in by_user.items():
    lst.sort()  # timestamp, then movie id
    n = len(lst)
    a, b = int(0.8 * n), int(0.1 * n)
    train += [(u, m, r) for _, m, r in lst[:a]]
    val += [(u, m, r) for _, m, r in lst[a:a + b]]
    test += [(u, m, r) for _, m, r in lst[a + b:]]

print("ratings", len(rows), "users", len(by_user), "movies in u.item", len(titles))
print("matrix fill %.4f%%" % (100 * len(rows) / (943 * 1682)))
print("split", len(train), len(val), len(test))

mu = sum(r for _, _, r in train) / len(train)
rmse = lambda s: math.sqrt(sum((mu - r) ** 2 for _, _, r in s) / len(s))
print("train mean %.4f, baseline RMSE val %.4f test %.4f" % (mu, rmse(val), rmse(test)))

train_movies = collections.Counter(m for _, m, _ in train)
rel = [(u, m) for u, m, r in test if r >= 4.0]
unseen = {m for _, m in rel if m not in train_movies}
rel_by_user = collections.defaultdict(set)
for u, m in rel:
    if m in train_movies:
        rel_by_user[u].add(m)
test_users = {u for u, _, _ in test}
print("relevant test ratings", len(rel), "unseen movie ids", len(unseen))
print("evaluable users", len(rel_by_user), "users without relevant", len(test_users - set(rel_by_user)))
print("relevant test targets (train-known)", sum(len(s) for s in rel_by_user.values()))

# Same user rated the same movie twice? (readme claim check)
pairs = collections.Counter((u, m) for u, m, _, _ in rows)
print("duplicate user-movie pairs", sum(1 for c in pairs.values() if c > 1))
tr_pairs = {(u, m) for u, m, _ in train + val}
print("relevant test pairs already in the same user's train/val", sum((u, m) in tr_pairs for u, m in rel))

# Most-popular baseline (popularity counted on train only), same protocol
seen = collections.defaultdict(set)
for u, m, _ in train + val:
    seen[u].add(m)
pop = [m for m, _ in train_movies.most_common()]
total, hits = 0.0, 0
for u, s in rel_by_user.items():
    top = [m for m in pop if m not in seen[u]][:10]
    h = len(s & set(top))
    hits += h
    total += h / len(s)
print("popularity Recall@10 macro %.4f, hits %d" % (total / len(rel_by_user), hits))
