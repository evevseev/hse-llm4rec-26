# Generated with an AI assistant. Independent recount of the key numbers in the report.
# It does not reuse the JavaScript code: plain Python, standard library only.
# Run from week3/:  python3 eval/recount_check.py > results/recount_check.txt
import math
from collections import defaultdict
from statistics import median

ITEM, DATA = 'original/u.item', 'original/u.data'
K_OVERLAP, MIN_SUPPORT, N_NEIGHBORS = 5, 3, 20

titles = {}
for line in open(ITEM, encoding='latin-1').read().splitlines():
    f = line.split('|')
    titles[int(f[0])] = f[1]

R = defaultdict(dict)          # user -> {movie: rating}
raters = defaultdict(dict)     # movie -> {user: rating}
for line in open(DATA):
    u, i, r, _ = map(int, line.split('\t'))
    R[u][i] = r
    raters[i][u] = r
users = sorted(R)


def cosine(a, b, weighted):
    common = a.keys() & b.keys()
    if not common:
        return 0.0, 0
    dot = sum(a[k] * b[k] for k in common)
    na = sum(a[k] ** 2 for k in common)
    nb = sum(b[k] ** 2 for k in common)
    c = dot / math.sqrt(na * nb)
    if weighted:
        c *= min(len(common) / K_OVERLAP, 1)
    return c, len(common)


def user_based(u, weighted, min_support):
    sims = []
    for v in users:
        if v != u:
            s, n = cosine(R[u], R[v], weighted)
            if s > 0:
                sims.append((-s, v, n))
    sims.sort()
    nb = sims[:N_NEIGHBORS]
    preds = []
    for i in titles:
        if i in R[u]:
            continue
        num = den = 0.0
        k = 0
        for s, v, _ in nb:
            if i in R[v]:
                num += -s * R[v][i]
                den += -s
                k += 1
        if den > 0 and k >= min_support:
            preds.append((-(num / den), i, k))
    preds.sort()
    return nb, preds[:5]


print('== Matrix ==')
cells = len(users) * len(titles)
print(f'users {len(users)}, movies {len(titles)}, ratings {sum(len(r) for r in R.values())}, '
      f'filled {100 * 100000 / cells:.2f}%')

print('\n== Co-rated movies between user pairs ==')
co = []
for a in range(len(users)):
    sa = R[users[a]].keys()
    for b in range(a + 1, len(users)):
        co.append(len(sa & R[users[b]].keys()))
print(f'pairs {len(co)}, median {median(co)}, share <=2: {100 * sum(c <= 2 for c in co) / len(co):.2f}%, '
      f'zero: {sum(c == 0 for c in co)}')

print('\n== Similarity work (pairs x vector length) ==')
ub_ops = len(users) * (len(users) - 1) // 2 * len(titles)
ib_ops = len(titles) * (len(titles) - 1) // 2 * len(users)
print(f'user-user {ub_ops:,}  item-item {ib_ops:,}  ratio {ib_ops / ub_ops:.2f}')

print('\n== User-Based over all users ==')
for name, weighted, sup in [('raw cosine, 1 supporter', False, 1),
                            ('weighted cosine, 1 supporter', True, 1),
                            ('weighted cosine, 3 supporters', True, MIN_SUPPORT)]:
    all5 = few = 0
    for u in users:
        nb, top = user_based(u, weighted, sup)
        if top and all(round(-p, 3) >= 5 for p, _, _ in top):
            all5 += 1
        if sum(n <= 2 for _, _, n in nb) > len(nb) / 2:
            few += 1
    print(f'{name}: all Top-5 = 5.000 for {all5}/943; majority of neighbors share <=2 movies for {few}/943')

print('\n== Hand check: user 1, final User-Based ==')
nb, top = user_based(1, True, MIN_SUPPORT)
for p, i, k in top:
    print(f'  {titles[i]}  {-p:.3f}  ({k} neighbors)')
schindler = 318
parts = [(v, -s, R[v][schindler]) for s, v, _ in nb if schindler in R[v]]
num = sum(s * r for _, s, r in parts)
den = sum(s for _, s, _ in parts)
print("  Schindler's List: " + ' + '.join(f'{s:.4f}*{r}' for _, s, r in parts) +
      f' = {num:.4f}; / {den:.4f} = {num / den:.3f}')

print('\n== Item-Based for one user: why the overlap weight cancels ==')
rated = R[196]
for cand in (1309, 1310):   # two Item-Based picks of user 196 before the support filter
    pairs = [(cosine(raters[cand], raters[j], False), rated[j]) for j in rated]
    pairs = [((s, n), r) for (s, n), r in pairs if s > 0]
    raw = sum(s * r for (s, _), r in pairs) / sum(s for (s, _), _ in pairs)
    w = [(s * min(n / K_OVERLAP, 1), r) for (s, n), r in pairs]
    wtd = sum(s * r for s, r in w) / sum(s for s, _ in w)
    print(f'  {titles[cand]}: raters {len(raters[cand])}, raw {raw:.3f}, weighted {wtd:.3f}')

print('\n== Final Item-Based (weighted cosine, >=3 supporting users, title dedup) ==')
title_key = {i: t.strip().casefold() for i, t in titles.items()}
for u in (1, 405):
    rated = R[u]
    rated_keys = {title_key[j] for j in rated}
    users_with_overlap = {v for j in rated for v in raters[j]}
    scored = []
    for c in titles:
        if c in rated or title_key[c] in rated_keys:
            continue
        support = sum(1 for v in raters[c] if v in users_with_overlap and v != u)
        if support < MIN_SUPPORT:
            continue
        num = den = 0.0
        for j, r in rated.items():
            s, _ = cosine(raters[c], raters[j], True)
            num += s * r
            den += s
        if den > 0:
            scored.append((-(num / den), c))
    scored.sort()
    top, seen = [], set()
    for p, c in scored:
        if title_key[c] not in seen:
            seen.add(title_key[c])
            top.append((p, c))
        if len(top) == 5:
            break
    mean = sum(rated.values()) / len(rated)
    print(f'user {u} (mean own rating {mean:.2f}): ' + '; '.join(f'{titles[c]} {-p:.3f}' for p, c in top))
