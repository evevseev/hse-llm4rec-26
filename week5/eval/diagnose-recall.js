// Generated with an AI assistant
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const fixed = path.join(root, "fixed");
const resultsDir = path.join(root, "results");
const metrics = JSON.parse(fs.readFileSync(path.join(resultsDir, "metrics.json"), "utf8"));
const rankingProbe = JSON.parse(fs.readFileSync(path.join(resultsDir, "ranking-probe.json"), "utf8"));

const genreNames = [
  "Action", "Adventure", "Animation", "Children's", "Comedy", "Crime",
  "Documentary", "Drama", "Fantasy", "Film-Noir", "Horror", "Musical",
  "Mystery", "Romance", "Sci-Fi", "Thriller", "War", "Western",
];
const movies = new Map();
for (const line of fs.readFileSync(path.join(fixed, "u.item"), "latin1").split(/\r?\n/)) {
  if (!line) continue;
  const fields = line.split("|");
  if (fields.length < 24) continue;
  const genres = fields.slice(6, 24).map(Number)
    .flatMap((flag, i) => flag === 1 ? [genreNames[i]] : []);
  movies.set(Number(fields[0]), { id: Number(fields[0]), title: fields[1], genres });
}

const ratings = [];
for (const line of fs.readFileSync(path.join(fixed, "u.data"), "ascii").split(/\r?\n/)) {
  if (!line) continue;
  const [userId, movieId, rating, timestamp] = line.split("\t").map(Number);
  ratings.push({ userId, movieId, rating, timestamp });
}
const byUser = new Map();
for (const rating of ratings) {
  if (!byUser.has(rating.userId)) byUser.set(rating.userId, []);
  byUser.get(rating.userId).push(rating);
}

const train = [];
const validation = [];
const test = [];
for (const userRatings of byUser.values()) {
  const sorted = userRatings.slice().sort((a, b) => a.timestamp - b.timestamp || a.movieId - b.movieId);
  if (sorted.length < 5) continue;
  const nTrain = Math.floor(0.8 * sorted.length);
  const nVal = Math.floor(0.1 * sorted.length);
  train.push(...sorted.slice(0, nTrain));
  validation.push(...sorted.slice(nTrain, nTrain + nVal));
  test.push(...sorted.slice(nTrain + nVal));
}

const trainMovieIds = new Set(train.map((r) => r.movieId));
const trainingStats = new Map();
for (const rating of train) {
  const stats = trainingStats.get(rating.movieId) || { count: 0, sum: 0 };
  stats.count++;
  stats.sum += rating.rating;
  trainingStats.set(rating.movieId, stats);
}
const popularityRank = new Map(
  Array.from(trainingStats.entries())
    .sort((a, b) => b[1].count - a[1].count || (b[1].sum / b[1].count) - (a[1].sum / a[1].count) || a[0] - b[0])
    .map(([movieId], i) => [movieId, i + 1]),
);

const testUsers = new Set(test.map((r) => r.userId));
const relevantByUser = new Map();
const relevantUnseenIds = new Set();
for (const rating of test) {
  if (rating.rating < 4) continue;
  if (!trainMovieIds.has(rating.movieId)) {
    relevantUnseenIds.add(rating.movieId);
    continue;
  }
  if (!relevantByUser.has(rating.userId)) relevantByUser.set(rating.userId, new Set());
  relevantByUser.get(rating.userId).add(rating.movieId);
}
const evaluableUsers = metrics.recallAt10.perUser.map((row) => row.userId);
const modelUsers = metrics.recallAt10.perUser;
const modelRelevant = modelUsers.reduce((sum, row) => sum + row.relevant, 0);
const modelHits = modelUsers.reduce((sum, row) => sum + row.hit, 0);
const usersWithHit = modelUsers.filter((row) => row.hit > 0).length;
const modelMacroRecall = modelUsers.length
  ? modelUsers.reduce((sum, row) => sum + row.hit / row.relevant, 0) / modelUsers.length
  : 0;
const modelMicroRecall = modelRelevant ? modelHits / modelRelevant : 0;
const noRelevantCandidateUsers = Array.from(testUsers).filter((id) => !relevantByUser.has(id));

function scoreRanking(restrictToTrainMovies) {
  const eligibleMovies = Array.from(movies.keys()).filter((id) => !restrictToTrainMovies || trainMovieIds.has(id));
  const recalls = [];
  let hits = 0;
  let relevantCount = 0;
  for (const userId of evaluableUsers) {
    const rated = new Set([...train, ...validation]
      .filter((r) => r.userId === userId)
      .map((r) => r.movieId));
    const relevant = relevantByUser.get(userId);
    const top = eligibleMovies.filter((id) => !rated.has(id))
      .sort((a, b) => {
        const sa = trainingStats.get(a) || { count: 0, sum: 0 };
        const sb = trainingStats.get(b) || { count: 0, sum: 0 };
        return sb.count - sa.count || (sb.sum / (sb.count || 1)) - (sa.sum / (sa.count || 1)) || a - b;
      })
      .slice(0, 10);
    const hit = top.filter((id) => relevant.has(id)).length;
    hits += hit;
    relevantCount += relevant.size;
    recalls.push(hit / relevant.size);
  }
  return {
    macroRecallAt10: recalls.reduce((sum, recall) => sum + recall, 0) / (recalls.length || 1),
    microRecallAt10: hits / (relevantCount || 1),
    hits,
    relevantTargets: relevantCount,
    evaluableUsers: recalls.length,
    candidatePoolSize: eligibleMovies.length,
  };
}

const popularityAllCatalog = scoreRanking(false);
const popularityTrainPool = scoreRanking(true);
const randomExpectedMacro = evaluableUsers.reduce((sum, userId) => {
  const rated = new Set([...train, ...validation]
    .filter((r) => r.userId === userId)
    .map((r) => r.movieId));
  const available = movies.size - rated.size;
  return sum + Math.min(10, available) / available;
}, 0) / (evaluableUsers.length || 1);

const userId = 1;
const history = [...train, ...validation].filter((r) => r.userId === userId);
const historyGenres = new Map();
for (const rating of history) {
  for (const genre of movies.get(rating.movieId)?.genres || []) {
    const row = historyGenres.get(genre) || { count: 0, sum: 0 };
    row.count++;
    row.sum += rating.rating;
    historyGenres.set(genre, row);
  }
}
const recommendations = metrics.recommendations[0].map((rec) => {
  const stats = trainingStats.get(rec.movieId) || { count: 0, sum: 0 };
  const movieRatings = ratings.filter((r) => r.movieId === rec.movieId);
  const trainValRated = [...train, ...validation].some((r) => r.userId === userId && r.movieId === rec.movieId);
  const testRating = test.find((r) => r.userId === userId && r.movieId === rec.movieId);
  return {
    ...rec,
    genres: movies.get(rec.movieId)?.genres || [],
    trainRatingCount: stats.count,
    trainMeanRating: stats.count ? stats.sum / stats.count : null,
    trainPopularityRank: popularityRank.get(rec.movieId) || null,
    allUsersRatingCount: movieRatings.length,
    ratedByUser1InTrainOrValidation: trainValRated,
    user1TestRating: testRating ? testRating.rating : null,
  };
});
const allMoviesWithRatings = movies.size;
const userTopGenres = Array.from(historyGenres.entries())
  .map(([genre, row]) => ({ genre, ratingCount: row.count, meanRating: row.sum / row.count }))
  .sort((a, b) => b.ratingCount - a.ratingCount);
const userMean = history.reduce((sum, r) => sum + r.rating, 0) / history.length;
const userRatedMovies = new Set(history.map((r) => r.movieId));
const recommendationNovelty = recommendations.map((r) => ({
  movieId: r.movieId,
  title: r.title,
  genreOverlapWithUserHistory: r.genres.filter((genre) => historyGenres.has(genre)),
  trainRatingCount: r.trainRatingCount,
  trainPopularityRank: r.trainPopularityRank,
  testRatingForUser1: r.user1TestRating,
  inPastUserHistory: userRatedMovies.has(r.movieId),
}));
const clippedTopFiveShare = (100 * rankingProbe.currentClippedTopK.shareOfSlotsClampedTo5).toFixed(2);

const output = {
  source: "MovieLens 100k files and the saved evaluation metrics",
  split: { train: train.length, validation: validation.length, test: test.length },
  metricBreakdown: {
    reportedMacroRecallAt10: metrics.recallAt10.overallRecall,
    macroRecallRecomputed: modelMacroRecall,
    microRecallAt10: modelMicroRecall,
    hits: modelHits,
    relevantTargetsInCandidatePool: modelRelevant,
    evaluableUsers: modelUsers.length,
    usersWithAtLeastOneHit: usersWithHit,
    usersWithZeroHits: modelUsers.length - usersWithHit,
    testUsers: testUsers.size,
    usersWithoutRelevantCandidate: noRelevantCandidateUsers.length,
    unseenRelevantMovieIds: relevantUnseenIds.size,
    relevantTestRatingsTotal: test.filter((r) => r.rating >= 4).length,
    randomExpectedMacroRecallAllCatalog: randomExpectedMacro,
  },
  popularityBaseline: {
    allCatalog: popularityAllCatalog,
    trainMoviePool: popularityTrainPool,
  },
  candidatePoolSizes: { fullCatalog: allMoviesWithRatings, trainMovies: trainMovieIds.size },
  user1: {
    historyRatingsTrainAndValidation: history.length,
    meanHistoryRating: userMean,
    distinctHistoryMovies: userRatedMovies.size,
    topGenresByHistoryCount: userTopGenres.slice(0, 8),
    recommendations,
    noveltySummary: recommendationNovelty,
    recommendationItemsAlreadyInTrainOrValidation: recommendations.filter((r) => r.ratedByUser1InTrainOrValidation).length,
    recommendationItemsAlsoRatedInTest: recommendations.filter((r) => r.user1TestRating !== null).length,
  },
};

fs.mkdirSync(resultsDir, { recursive: true });
fs.writeFileSync(path.join(resultsDir, "recall-diagnosis.json"), `${JSON.stringify(output, null, 2)}\n`);

const report = [
  "# Recall@10 and recommendation diagnosis",
  "",
  "## Evaluation coverage",
  "",
  `- Saved model macro Recall@10: **${modelMacroRecall.toFixed(6)}** (${modelUsers.length} evaluable users). This recomputation matches the saved metric: ${modelMacroRecall === metrics.recallAt10.overallRecall}.`,
  `- Model hits: ${modelHits} out of ${modelRelevant} relevant test items in the reported candidate set; micro Recall@10: ${modelMicroRecall.toFixed(6)}.`,
  `- Only ${usersWithHit}/${modelUsers.length} evaluable users have at least one hit; ${modelUsers.length - usersWithHit} have zero hits.`,
  `- Test users: ${testUsers.size}; ${noRelevantCandidateUsers.length} have no relevant test film in the training movie pool; ${relevantUnseenIds.size} distinct relevant test movie IDs are absent from train.`,
  `- There are ${test.filter((r) => r.rating >= 4).length} relevant (rating >= 4) test ratings before candidate exclusions.`,
  `- Expected macro Recall@10 for a uniformly random 10-item list from the full catalog under the same user exclusions: ${randomExpectedMacro.toFixed(6)}.`,
  "",
  "## Popularity baselines",
  "",
  `- Popularity-ranked Top-10 over all catalog movies: macro Recall@10 **${popularityAllCatalog.macroRecallAt10.toFixed(6)}**, ${popularityAllCatalog.hits}/${popularityAllCatalog.relevantTargets} hits.`,
  `- Popularity-ranked Top-10 restricted to the ${trainMovieIds.size} movies in train: macro Recall@10 **${popularityTrainPool.macroRecallAt10.toFixed(6)}**, ${popularityTrainPool.hits}/${popularityTrainPool.relevantTargets} hits.`,
  "- Both baselines use training rating counts (ties by training mean rating and movie ID), exclude each user's train/validation movies, and average per-user recall over the model's evaluable-user set.",
  `- Separate fresh model run: current clip-before-Top-K ranking gave ${rankingProbe.currentClippedTopK.macroRecallAt10.toFixed(6)}; ranking by unclipped raw scores gave ${rankingProbe.rawScoreRanking.fullCatalog.macroRecallAt10.toFixed(6)} on the full catalog and ${rankingProbe.rawScoreRanking.trainMoviePool.macroRecallAt10.toFixed(6)} on the train pool. ${clippedTopFiveShare}% of Top-10 slots were capped at 5.0.`,
  "",
  "## User 1 recommendations and history",
  "",
  `- User 1 has ${history.length} train+validation ratings, mean rating ${userMean.toFixed(3)}, across ${userRatedMovies.size} distinct films. Top genres by count: ${userTopGenres.slice(0, 5).map((g) => `${g.genre} (${g.ratingCount}, mean ${g.meanRating.toFixed(2)})`).join(", ")}.`,
  `- None of the displayed recommendations is in this user's train/validation history; ${recommendations.filter((r) => r.user1TestRating !== null).length} appears in their test history (test items are intentionally allowed by Top-K).`,
  "",
  "| Rank | Movie | Score | Genres | Train ratings | Popularity rank | User 1 test rating |",
  "|---:|---|---:|---|---:|---:|---:|",
  ...recommendations.map((r, i) => `| ${i + 1} | ${r.title} | ${r.score.toFixed(4)} | ${r.genres.join(", ") || "—"} | ${r.trainRatingCount} | ${r.trainPopularityRank ?? "—"} | ${r.user1TestRating ?? "—"} |`),
  "",
  "## Reading the result",
  "",
  "- RMSE measures rating prediction on every held-out rating; Recall@10 measures whether a small ranked list recovers high-rated held-out films. They answer different questions, so lower RMSE does not guarantee high Recall@10.",
  "- Recall here is macro-averaged over users, so a user with one relevant film has the same weight as a user with many. Most eligible users receive zero hits; a few users with multiple hits lift the mean.",
  "- The saved model's Recall implementation ranks the full catalog, while the documented assignment asks to rank only training-pool movies. The popularity baselines quantify both candidate-pool variants; the model's strict train-pool reranking cannot be reconstructed from the saved output because factor weights were not serialized.",
  "- Santa with Muscles and Lamerica are not necessarily errors: collaborative filtering ranks predicted compatibility, not general fame or quality. But these scores are weakly supported: Santa has two train ratings (both 5) and Lamerica one (5); the prediction is effectively extrapolating from tiny samples. Both fit a genre User 1 has rated, but their position is not reliable evidence of a strong preference.",
  "- Clipping before Top-K creates many maximum-score ties. In the separate probe, raw-score ranking did not improve Recall; this is a diagnosable ranking weakness, not a demonstrated sole cause of the low score.",
  "",
].join("\n");
fs.writeFileSync(path.join(resultsDir, "recall-diagnosis.md"), report);
console.log(report);
