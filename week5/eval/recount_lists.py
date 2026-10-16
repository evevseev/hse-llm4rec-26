# Generated with an AI assistant. Independent check of the saved seed-1 Top-10 lists (users 1 and 2).
# It rebuilds the split and the genres from original/u.data and original/u.item with the standard library only.
import collections, json

GENRES = ["Action", "Adventure", "Animation", "Children's", "Comedy", "Crime", "Documentary", "Drama",
          "Fantasy", "Film-Noir", "Horror", "Musical", "Mystery", "Romance", "Sci-Fi", "Thriller", "War", "Western"]
rows = [tuple(map(int, l.split("\t"))) for l in open("original/u.data")]
genres, titles = {}, {}
for l in open("original/u.item", encoding="latin-1"):
    f = l.split("|")
    titles[int(f[0])] = f[1]
    genres[int(f[0])] = {g for g, v in zip(GENRES, f[6:24]) if v.strip() == "1"}

by_user = collections.defaultdict(list)
for u, m, r, t in rows:
    by_user[u].append((t, m, r))
train, hist, test = [], collections.defaultdict(dict), collections.defaultdict(dict)
for u, lst in by_user.items():
    lst.sort()
    n = len(lst)
    a, b = int(0.8 * n), int(0.1 * n)
    for i, (t, m, r) in enumerate(lst):
        if i < a:
            train.append((u, m, r))
            hist[u][m] = r
        elif i < a + b:
            hist[u][m] = r
        else:
            test[u][m] = r
train_count = collections.Counter(m for _, m, _ in train)

d = json.load(open("results/discovery-all-seed1.json"))
for uid in ("1", "2"):
    u = int(uid)
    recs = d["users"][uid]["recommendations"]
    seen_genres = set().union(*[genres[m] for m in hist[u]])
    in_hist = [r["title"] for r in recs if r["movieId"] in hist[u]]
    new_genre = [r["title"] for r in recs if genres[r["movieId"]] - seen_genres]
    count_ok = all(train_count[r["movieId"]] == r["trainRatings"] for r in recs)
    min_count = min(train_count[r["movieId"]] for r in recs)
    test_hits = [(r["title"], test[u][r["movieId"]]) for r in recs if r["movieId"] in test[u]]
    print("user", u, "history ratings", len(hist[u]), "genres in history", len(seen_genres))
    print("  top-10 titles already in train/val history:", len(in_hist))
    print("  train-rating counts match saved file:", count_ok, "| smallest count in list:", min_count)
    print("  titles with a genre absent from history:", new_genre)
    print("  list titles that user rated in the test split:", test_hits)

ex = d["summary"]["top10MovieExposure"]
print("top-20 most shown movies fill", sum(e["users"] for e in ex), "of", d["summary"]["totalRecommendationSlots"],
      "slots = %.2f%%" % (100 * sum(e["users"] for e in ex) / d["summary"]["totalRecommendationSlots"]))
print("most shown:", ex[0]["title"], "to", ex[0]["users"], "of 943 users")
