# Generated with an AI assistant. Independent recount of the key numbers in the report.
# It does not reuse the JavaScript code: plain Python, standard library only.
# Run from week4/:  python3 eval/recount_check.py > results/recount_check.txt
import json
from itertools import combinations
from statistics import median

text = open('original/transactions.js', encoding='utf-8').read()
data = json.loads(text[text.index('window.HW4 = ') + len('window.HW4 = '):].rstrip().rstrip(';'))
S, D = data['stocks'], data['descriptions']
B = [frozenset(b) for b in data['baskets']]
N = len(B)
code = {s: i for i, s in enumerate(S)}


def postings(baskets):
    post = {}
    for k, b in enumerate(baskets):
        for i in b:
            post.setdefault(i, set()).add(k)
    return post


def mine(baskets, min_support):
    post, n = postings(baskets), len(baskets)
    freq = {frozenset([i]): len(p) for i, p in post.items() if len(p) / n >= min_support}
    level = list(freq)
    while level:
        known, k = set(level), len(level[0]) + 1
        cands = {a | b for a, b in combinations(level, 2) if len(a | b) == k}
        cands = {c for c in cands if all(frozenset(x) in known for x in combinations(c, k - 1))}
        level = []
        for c in cands:
            it = iter(c)
            s = set(post[next(it)])
            for i in it:
                s &= post[i]
            if len(s) / n >= min_support:
                freq[c] = len(s)
                level.append(c)
    return freq


def rules(freq, n, min_conf):
    out = []
    for s, c in freq.items():
        for r in range(1, len(s)):
            for a in combinations(s, r):
                a = frozenset(a)
                conf = c / freq[a]
                if conf >= min_conf:
                    out.append((a, s - a, c, freq[a], freq[s - a], c / n, conf, conf / (freq[s - a] / n)))
    return out


def name(s):
    return ' + '.join(D[i] for i in sorted(s))


def show(r):
    return (f'{name(r[0])} -> {name(r[1])}: count(AuB) {r[2]}, count(A) {r[3]}, count(B) {r[4]}, '
            f'support {100 * r[5]:.2f}%, confidence {100 * r[6]:.2f}%, lift {r[7]:.2f}')


print('== Dataset ==')
sizes = [len(b) for b in B]
post = postings(B)
top = max(post, key=lambda i: len(post[i]))
print(f'baskets {N}, items {len(S)}, median basket size {median(sizes)}, max {max(sizes)}, '
      f'baskets with >=100 items {sum(x >= 100 for x in sizes)}')
print(f'most frequent item {S[top]} {D[top]}: {len(post[top])} baskets = {100 * len(post[top]) / N:.2f}%')
print(f'lowest possible lift at confidence 30%: {0.30 / (len(post[top]) / N):.2f}, at 60%: {0.60 / (len(post[top]) / N):.2f}')

print('\n== Thresholds ==')
for ms in (0.005, 0.01, 0.02, 0.03):
    F = mine(B, ms)
    by = {}
    for s in F:
        by[len(s)] = by.get(len(s), 0) + 1
    for mc in ((0.1,) if ms == 0.005 else (0.3, 0.6)):
        R = rules(F, N, mc)
        print(f'support {100 * ms:.1f}% confidence {100 * mc:.0f}%: itemsets {len(F)} {dict(sorted(by.items()))}, '
              f'rules {len(R)}, removed by lift > 1: {sum(r[7] <= 1 for r in R)}')

print('\n== Rules cited in the report ==')
F1 = mine(B, 0.005)
R1 = {(r[0], r[1]): r for r in rules(F1, N, 0.0)}
def get(a, b):
    return R1[(frozenset(code[x] for x in a), frozenset(code[x] for x in b))]
for a, b in [(['20712'], ['21931']), (['21931'], ['20712']),
             (['22697', '22699'], ['22698']), (['22698'], ['22697', '22699']),
             (['22727'], ['22726']), (['22726'], ['22727']),
             (['22916'], ['22917']), (['22726'], ['85123A'])]:
    print(show(get(a, b)))

print('\n== Final table: support 2%, confidence 60% ==')
F2 = mine(B, 0.02)
R2 = sorted(rules(F2, N, 0.6), key=lambda r: (-r[2], -r[7]))
for r in R2:
    print('  ' + show(r))
print(f'rules {len(R2)}, smallest count(AuB) {min(r[2] for r in R2)}, threshold count {0.02 * N:.1f}')

print('\n== Same table without baskets of 100+ items ==')
small = [b for b in B if len(b) < 100]
n2 = len(small)
keep = 0
for r in R2:
    j = sum(1 for b in small if (r[0] | r[1]) <= b)
    a = sum(1 for b in small if r[0] <= b)
    if j / n2 >= 0.02 and j / a >= 0.6:
        keep += 1
    else:
        print(f'  drops: {name(r[0])} -> {name(r[1])}, confidence {100 * j / a:.2f}%')
print(f'baskets left {n2}, rules still passing {keep} of {len(R2)}')
