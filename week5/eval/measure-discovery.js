// Generated with an AI assistant
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const tf = require("@tensorflow/tfjs");
require("@tensorflow/tfjs-backend-wasm");

const root = path.resolve(__dirname, "..");
const fixed = path.join(root, "fixed");
const resultsDir = path.join(root, "results");
const seed = 1;
const minTrainRatings = 20;
const popularTopDecile = 0.1;

function avg(values) {
  return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0;
}

function median(values) {
  if (!values.length) return 0;
  const sorted = values.slice().sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

async function main() {
  await tf.setBackend("wasm");
  await tf.ready();
  const context = vm.createContext({
    console,
    document: { getElementById: () => null },
    window: {},
    tf,
    seed,
    itemText: new TextDecoder("windows-1252").decode(fs.readFileSync(path.join(fixed, "u.item"))),
    ratingText: fs.readFileSync(path.join(fixed, "u.data"), "ascii").toString(),
  });
  vm.runInContext(fs.readFileSync(path.join(fixed, "data.js"), "utf8"), context);
  vm.runInContext(fs.readFileSync(path.join(fixed, "script.js"), "utf8"), context);
  vm.runInContext(
    "parseItemData(itemText); parseRatingData(ratingText); " +
      "numUsers = ratings.reduce((m, r) => Math.max(m, r.userId), 0); " +
      "numMovies = movies.length; buildRatingMatrix(); " +
      "const split = splitByTimestamp(); trainSet = split.train; valSet = split.val; testSet = []; " +
      "initializeFactors(trainSet, NUM_FACTORS, seed); " +
      "trainingHistory = trainMF(trainSet, valSet, {epochs:20,lr:0.01,reg:0.05,batchSize:64,seed}); " +
      "bestCheckpoint = selectBestCheckpoint(trainingHistory);",
    context,
  );

  const snapshot = vm.runInContext(
    "({ trainSet, valSet, movies, bestCheckpoint, itemTrainCounts: Array.from(model.itemTrainCounts), " +
      "userIds: Array.from(new Set(trainSet.map(r => r.userId))).sort((a,b) => a-b) })",
    context,
  );
  const candidateIds = snapshot.movies
    .filter((movie) => (snapshot.itemTrainCounts[movie.id] || 0) >= minTrainRatings)
    .map((movie) => movie.id);
  const popularityOrder = snapshot.movies
    .filter((movie) => (snapshot.itemTrainCounts[movie.id] || 0) > 0)
    .sort((a, b) => snapshot.itemTrainCounts[b.id] - snapshot.itemTrainCounts[a.id] || a.id - b.id);
  const popularityRank = new Map(popularityOrder.map((movie, index) => [movie.id, index + 1]));
  const topDecileRank = Math.ceil(popularityOrder.length * popularTopDecile);
  const profiles = new Map();
  const historyMovieIds = new Map();
  for (const rating of [...snapshot.trainSet, ...snapshot.valSet]) {
    if (!profiles.has(rating.userId)) profiles.set(rating.userId, new Map());
    if (!historyMovieIds.has(rating.userId)) historyMovieIds.set(rating.userId, new Set());
    historyMovieIds.get(rating.userId).add(rating.movieId);
    const movie = snapshot.movies.find((item) => item.id === rating.movieId);
    for (const genre of movie?.genres || []) {
      const aggregate = profiles.get(rating.userId).get(genre) || { count: 0, ratingSum: 0 };
      aggregate.count++;
      aggregate.ratingSum += rating.rating;
      profiles.get(rating.userId).set(genre, aggregate);
    }
  }

  const allUsers = [];
  const recSets = [];
  const movieExposure = new Map();
  let totalSlots = 0;
  let genreNovelSlots = 0;
  let familiarOnlySlots = 0;
  let favoredGenreSlots = 0;
  let noGenreOverlapSlots = 0;
  let popularTopDecileSlots = 0;
  let obviousSlots = 0;
  let selfInformationSum = 0;
  let titleHistoryOverlapSlots = 0;
  let usersWithGenreDiscovery = 0;

  for (const userId of snapshot.userIds) {
    context.discoveryUserId = userId;
    const recs = vm.runInContext("recommendTopK(discoveryUserId, 10, 20)", context);
    const historyGenres = profiles.get(userId) || new Map();
    const preferredGenres = new Set(Array.from(historyGenres.entries())
      .filter(([, stats]) => stats.count >= 5 && stats.ratingSum / stats.count >= 4)
      .map(([genre]) => genre));
    let userGenreNovel = 0;
    const enriched = recs.map((rec) => {
      const movie = snapshot.movies.find((item) => item.id === rec.movieId);
      const genres = movie?.genres || [];
      const unseenGenres = genres.filter((genre) => !historyGenres.has(genre));
      const knownGenres = genres.filter((genre) => historyGenres.has(genre));
      const preferredGenreOverlap = genres.filter((genre) => preferredGenres.has(genre));
      const previouslyRated = historyMovieIds.get(userId)?.has(rec.movieId) || false;
      const rank = popularityRank.get(rec.movieId) || null;
      const trainRatings = snapshot.itemTrainCounts[rec.movieId] || 0;
      const surprisalBits = trainRatings > 0 ? -Math.log2(trainRatings / snapshot.trainSet.length) : null;
      const inPopularDecile = rank !== null && rank <= topDecileRank;
      const isGenreDiscovery = unseenGenres.length > 0;
      if (isGenreDiscovery) userGenreNovel++;
      if (previouslyRated) titleHistoryOverlapSlots++;
      if (isGenreDiscovery) genreNovelSlots++;
      else familiarOnlySlots++;
      if (preferredGenreOverlap.length > 0) favoredGenreSlots++;
      if (genres.length && knownGenres.length === 0) noGenreOverlapSlots++;
      if (inPopularDecile) popularTopDecileSlots++;
      if (!isGenreDiscovery && inPopularDecile) obviousSlots++;
      selfInformationSum += surprisalBits || 0;
      totalSlots++;
      movieExposure.set(rec.movieId, (movieExposure.get(rec.movieId) || 0) + 1);
      return {
        ...rec,
        genres,
        trainRatings,
        popularityRank: rank,
        popularityDecileTop10: inPopularDecile,
        selfInformationBits: surprisalBits,
        knownGenres,
        unseenGenres,
        preferredGenreOverlap,
        previouslyRated,
        classification: isGenreDiscovery ? "new-to-user genre" : "new title / familiar genres",
      };
    });
    if (userGenreNovel > 0) usersWithGenreDiscovery++;
    recSets.push(new Set(enriched.map((rec) => rec.movieId)));
    const genreSummary = Array.from(historyGenres.entries())
      .map(([genre, stats]) => ({ genre, count: stats.count, meanRating: stats.ratingSum / stats.count }))
      .sort((a, b) => b.count - a.count || b.meanRating - a.meanRating);
    const history = [...snapshot.trainSet, ...snapshot.valSet].filter((r) => r.userId === userId);
    allUsers.push({
      userId,
      historyRatings: history.length,
      historyMeanRating: avg(history.map((rating) => rating.rating)),
      genresPreviouslyRated: historyGenres.size,
      preferredGenres: Array.from(preferredGenres),
      topGenres: genreSummary.slice(0, 5),
      recommendations: enriched,
      genreDiscoveryItems: userGenreNovel,
      titleHistoryOverlapItems: enriched.filter((rec) => rec.previouslyRated).length,
      genreNoveltyRate: recs.length ? userGenreNovel / recs.length : 0,
    });
  }

  let pairJaccardSum = 0;
  let pairOverlapSum = 0;
  let pairs = 0;
  let maxJaccard = 0;
  for (let i = 0; i < recSets.length; i++) {
    for (let j = i + 1; j < recSets.length; j++) {
      let intersection = 0;
      for (const movieId of recSets[i]) if (recSets[j].has(movieId)) intersection++;
      const union = recSets[i].size + recSets[j].size - intersection;
      const jaccard = union ? intersection / union : 0;
      pairJaccardSum += jaccard;
      pairOverlapSum += intersection;
      maxJaccard = Math.max(maxJaccard, jaccard);
      pairs++;
    }
  }

  const uniqueExposedMovies = movieExposure.size;
  const user1 = allUsers.find((user) => user.userId === 1);
  const user2 = allUsers.find((user) => user.userId === 2);
  const summary = {
    users: allUsers.length,
    topK: 10,
    candidateMinTrainRatings: minTrainRatings,
    totalRecommendationSlots: totalSlots,
    genreNovelSlots: genreNovelSlots,
    genreNovelSlotRate: totalSlots ? genreNovelSlots / totalSlots : 0,
    meanPerUserGenreNoveltyRate: avg(allUsers.map((user) => user.genreNoveltyRate)),
    usersWithAtLeastOneNewGenreRecommendation: usersWithGenreDiscovery,
    usersWithNoNewGenreRecommendation: allUsers.length - usersWithGenreDiscovery,
    familiarGenreOnlySlots: familiarOnlySlots,
    favoredGenreOverlapSlots: favoredGenreSlots,
    noGenreOverlapSlots,
    popularTopDecileSlots,
    obviousSlots,
    obviousSlotRate: totalSlots ? obviousSlots / totalSlots : 0,
    meanSelfInformationBitsPerRecommendation: totalSlots ? selfInformationSum / totalSlots : 0,
    previouslyRatedTitleSlots: titleHistoryOverlapSlots,
    distinctRecommendedMovies: uniqueExposedMovies,
    eligibleCatalogMovies: candidateIds.length,
    eligibleCatalogCoverage: candidateIds.length ? uniqueExposedMovies / candidateIds.length : 0,
    userPairsCompared: pairs,
    meanPairwiseTop10Intersection: pairs ? pairOverlapSum / pairs : 0,
    meanPairwiseJaccard: pairs ? pairJaccardSum / pairs : 0,
    maxPairwiseJaccard: maxJaccard,
    top10MovieExposure: Array.from(movieExposure.entries())
      .map(([movieId, userCount]) => ({
        movieId,
        title: snapshot.movies.find((movie) => movie.id === movieId)?.title || `Movie #${movieId}`,
        users: userCount,
        trainRatings: snapshot.itemTrainCounts[movieId] || 0,
      }))
      .sort((a, b) => b.users - a.users || a.movieId - b.movieId)
      .slice(0, 20),
  };

  const output = {
    seed,
    backend: tf.getBackend(),
    parameters: { factors: 16, epochs: 20, lr: 0.01, reg: 0.05, batchSize: 64 },
    checkpoint: snapshot.bestCheckpoint,
    historyDefinition: "train + validation only; testSet was kept empty and not accessed",
    metricsDefinition: {
      genuineGenreDiscovery: "recommended title has at least one genre absent from that user's train+validation genre history",
      obviousChoice: "all genres are familiar AND movie is in top 10% by train rating count",
      popularityNovelty: "mean -log2(train item rating count / total train ratings), in bits",
      listSimilarity: "mean pairwise Jaccard across all users' Top-10 movie-ID sets",
    },
    summary,
    users: { 1: user1, 2: user2 },
    allUsers: allUsers.map((user) => ({
      userId: user.userId,
      genreNoveltyRate: user.genreNoveltyRate,
      genreDiscoveryItems: user.genreDiscoveryItems,
      historyMeanRating: user.historyMeanRating,
      genreCount: user.genresPreviouslyRated,
      titleHistoryOverlapItems: user.titleHistoryOverlapItems,
    })),
  };

  fs.mkdirSync(resultsDir, { recursive: true });
  fs.writeFileSync(path.join(resultsDir, "discovery-all-seed1.json"), `${JSON.stringify(output, null, 2)}\n`);

  const userSection = (user) => [
    `## User ${user.userId}`,
    "",
    `Past ratings: ${user.historyRatings}; mean ${user.historyMeanRating.toFixed(3)}; known genres: ${user.genresPreviouslyRated}. Preferred genres (>=5 past genre ratings and mean >=4): ${user.preferredGenres.join(", ") || "none"}.`,
    `New-to-user genres in Top-10: ${user.genreDiscoveryItems}/10; exact past-title repeats: ${user.titleHistoryOverlapItems}.`,
    `Top historic genres: ${user.topGenres.map((g) => `${g.genre} (${g.count}, mean ${g.meanRating.toFixed(2)})`).join(", ")}.`,
    "",
    "| # | Movie | Score | Genres | Familiar genres | New genres | Train ratings | Train popularity rank |",
    "|---:|---|---:|---|---|---|---:|---:|",
    ...user.recommendations.map((rec, i) =>
      `| ${i + 1} | ${rec.title} | ${rec.score.toFixed(4)} | ${rec.genres.join(", ") || "—"} | ${rec.knownGenres.join(", ") || "—"} | ${rec.unseenGenres.join(", ") || "—"} | ${rec.trainRatings} | ${rec.popularityRank ?? "—"} |`),
    "",
  ];
  const report = [
    "# Recommendation discovery and repetition — all users, seed 1",
    "",
    `- Model checkpoint: epoch ${snapshot.bestCheckpoint.epoch}, validation RMSE ${snapshot.bestCheckpoint.valRMSE.toFixed(6)}; candidate minimum N=${minTrainRatings}; testSet was kept empty and not accessed.`,
    "- Genuine genre discovery is a Top-10 movie with at least one genre absent from the user's train+validation history. An obvious choice is defined as all genres familiar and the movie in the most-popular 10% of train items. Popularity novelty is reported separately as mean self-information.",
    "",
    "## Main all-user measures",
    "",
    `- **Mean per-user new-genre share (primary): ${(100 * summary.meanPerUserGenreNoveltyRate).toFixed(2)}%**; users with at least one such item: ${usersWithGenreDiscovery}/${allUsers.length}.`,
    `- Across ${totalSlots} recommendation slots: ${genreNovelSlots} have a new-to-user genre (${(100 * summary.genreNovelSlotRate).toFixed(2)}%); ${familiarOnlySlots} use only familiar genres.`,
    `- Obvious choices by the operational definition: ${obviousSlots}/${totalSlots} (${(100 * summary.obviousSlotRate).toFixed(2)}%). Any Top-10 item in the train popularity top decile: ${popularTopDecileSlots}/${totalSlots}.`,
    `- Mean popularity self-information: ${summary.meanSelfInformationBitsPerRecommendation.toFixed(3)} bits per slot.`,
    `- Catalog diversity: ${uniqueExposedMovies} distinct movies surfaced from ${candidateIds.length} eligible movies (${(100 * summary.eligibleCatalogCoverage).toFixed(2)}% coverage); mean pairwise Top-10 Jaccard ${summary.meanPairwiseJaccard.toFixed(4)}, mean shared titles ${summary.meanPairwiseTop10Intersection.toFixed(3)} of 10.`,
    `- Exact previously rated title repeats: ${titleHistoryOverlapSlots}/${totalSlots} (they are excluded by construction).`,
    "",
    ...userSection(user1),
    ...userSection(user2),
    "## Interpretation for a streaming service",
    "",
    `For discovery, the primary measure says ${(100 * summary.meanPerUserGenreNoveltyRate).toFixed(2)}% of the average user's Top-10 introduces a genre not seen in their history. Most recommendations therefore broaden the catalog within known taste areas rather than expand genre interests. The low list Jaccard/unique-title coverage indicate different users are not receiving an identical list; the separate popularity/self-information metric shows whether those different titles are mainstream or niche.`,
    "",
    "All-user table with per-user genre novelty is in `discovery-all-seed1.json`; no test ratings were used.",
    "",
  ].join("\n");
  fs.writeFileSync(path.join(resultsDir, "discovery-all-seed1.md"), report);
  console.log(report);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
