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
const minimumTrainRatings = 20;

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
      "const split = splitByTimestamp(); trainSet = split.train; " +
      "valSet = split.val; testSet = []; " +
      "initializeFactors(trainSet, NUM_FACTORS, seed); " +
      "trainingHistory = trainMF(trainSet, valSet, {epochs:20,lr:0.01,reg:0.05,batchSize:64,seed}); " +
      "bestCheckpoint = selectBestCheckpoint(trainingHistory);",
    context,
  );

  const snapshots = vm.runInContext(
    "({ trainSet, valSet, movies, testSet, bestCheckpoint, " +
      "itemTrainCounts: Array.from(model.itemTrainCounts), " +
      "recommendations: [recommendTopK(1, 10, 20), recommendTopK(2, 10, 20)] })",
    context,
  );
  const histories = new Map();
  for (const rating of [...snapshots.trainSet, ...snapshots.valSet]) {
    if (!histories.has(rating.userId)) histories.set(rating.userId, []);
    histories.get(rating.userId).push(rating);
  }
  const getMovie = (movieId) => snapshots.movies.find((movie) => movie.id === movieId);
  const genreProfile = (history) => {
    const profile = new Map();
    for (const rating of history) {
      const movie = getMovie(rating.movieId);
      for (const genre of movie?.genres || []) {
        const row = profile.get(genre) || { count: 0, ratingSum: 0 };
        row.count++;
        row.ratingSum += rating.rating;
        profile.set(genre, row);
      }
    }
    return profile;
  };

  const users = {};
  for (const userId of [1, 2]) {
    const history = histories.get(userId) || [];
    const historyMovieIds = new Set(history.map((rating) => rating.movieId));
    const profile = genreProfile(history);
    const favoredGenres = new Set(Array.from(profile.entries())
      .filter(([, row]) => row.count >= 5 && row.ratingSum / row.count >= 4)
      .map(([genre]) => genre));
    const recommendations = snapshots.recommendations[userId - 1].map((item) => {
      const genres = getMovie(item.movieId)?.genres || [];
      const sharedPastGenres = genres.filter((genre) => profile.has(genre));
      const favoredGenreOverlap = genres.filter((genre) => favoredGenres.has(genre));
      return {
        ...item,
        trainRatings: snapshots.itemTrainCounts[item.movieId],
        genres,
        previouslyRatedByUser: historyMovieIds.has(item.movieId),
        sharedPastGenres,
        favoredGenreOverlap,
        entirelyNewGenres: genres.filter((genre) => !profile.has(genre)),
      };
    });
    const historyMean = history.reduce((sum, rating) => sum + rating.rating, 0) / history.length;
    const sortedProfile = Array.from(profile.entries())
      .map(([genre, row]) => ({ genre, ratingCount: row.count, meanRating: row.ratingSum / row.count }))
      .sort((a, b) => b.ratingCount - a.ratingCount || b.meanRating - a.meanRating);
    users[userId] = {
      historyRatings: history.length,
      uniquePreviouslyRatedMovies: historyMovieIds.size,
      historyMeanRating: historyMean,
      favoredGenresRule: "at least 5 genre-tagged past ratings and mean rating >= 4.0",
      favoredGenres: Array.from(favoredGenres),
      topGenresByHistoryCount: sortedProfile.slice(0, 8),
      recommendations,
      summary: {
        top10: recommendations.length,
        knownTitles: recommendations.filter((item) => item.previouslyRatedByUser).length,
        newTitles: recommendations.filter((item) => !item.previouslyRatedByUser).length,
        newTitlesWithAnyPastGenre: recommendations.filter((item) => item.sharedPastGenres.length > 0).length,
        newTitlesWithFavoredGenre: recommendations.filter((item) => item.favoredGenreOverlap.length > 0).length,
        titlesWithOnlyUnseenGenres: recommendations.filter((item) => item.genres.length > 0 && item.sharedPastGenres.length === 0).length,
      },
    };
  }

  const output = {
    seed,
    backend: tf.getBackend(),
    parameters: { factors: 16, epochs: 20, lr: 0.01, reg: 0.05, batchSize: 64 },
    candidateMinTrainRatings: minimumTrainRatings,
    historyDefinition: "Movies rated by the user in train or validation; no test ratings are read or used.",
    testSetAccessed: false,
    trainRatings: snapshots.trainSet.length,
    validationRatings: snapshots.valSet.length,
    bestCheckpoint: snapshots.bestCheckpoint,
    users,
  };
  fs.mkdirSync(resultsDir, { recursive: true });
  fs.writeFileSync(path.join(resultsDir, "discovery-seed1.json"), `${JSON.stringify(output, null, 2)}\n`);

  const sections = [1, 2].flatMap((userId) => {
    const user = users[userId];
    const genreTable = user.topGenresByHistoryCount
      .map((entry) => `${entry.genre} (${entry.ratingCount} ratings, mean ${entry.meanRating.toFixed(2)})`)
      .join(", ");
    return [
      `## User ${userId}`,
      "",
      `Past history: ${user.historyRatings} ratings on ${user.uniquePreviouslyRatedMovies} distinct movies; mean score ${user.historyMeanRating.toFixed(3)}. Most-seen genres: ${genreTable}.`,
      `Favorite-genre rule: ${user.favoredGenresRule}. Genres selected: ${user.favoredGenres.join(", ") || "none"}.`,
      `Top-10: ${user.summary.newTitles}/${user.summary.top10} unseen titles; ${user.summary.newTitlesWithAnyPastGenre} overlap a previously rated genre; ${user.summary.newTitlesWithFavoredGenre} overlap a favored genre; ${user.summary.titlesWithOnlyUnseenGenres} have only genres absent from history.`,
      "",
      "| # | Movie | Score | Train ratings | Genres | Familiar genres | Favored genres |",
      "|---:|---|---:|---:|---|---|---|",
      ...user.recommendations.map((item, i) =>
        `| ${i + 1} | ${item.title} | ${item.score.toFixed(4)} | ${item.trainRatings} | ${item.genres.join(", ") || "—"} | ${item.sharedPastGenres.join(", ") || "—"} | ${item.favoredGenreOverlap.join(", ") || "—"} |`),
      "",
    ];
  });
  const report = [
    "# Familiar tastes vs. new movie discovery",
    "",
    `- Seed ${seed}, TensorFlow.js ${tf.getBackend()}, 16 factors, 20 epochs, lr=0.01, reg=0.05, batchSize=64; selected epoch ${snapshots.bestCheckpoint.epoch} by validation RMSE ${snapshots.bestCheckpoint.valRMSE.toFixed(6)}.`,
    `- Candidate filter: at least ${minimumTrainRatings} train ratings. Lists are averaged from one deterministic seed only; the model excludes movies already rated in train or validation.`,
    "- Familiar title means the user rated that exact movie in train or validation. Familiar genre means the genre occurs in at least one such past rating. A favored genre is more conservatively defined as at least five past genre-tagged ratings with mean >=4.0.",
    "- This is an offline comparison against historical genres, not evidence that the user personally knows every unviewed catalog title. No test labels or ratings are used.",
    "",
    ...sections,
    "## Product interpretation",
    "",
    "Because Top-10 excludes exact titles in train and validation, 10/10 recommendations are new titles by construction. The discovery question is therefore whether those new titles remain connected to genres the user has rated well, and whether any introduce entirely unseen genres.",
    "A list dominated by high-rated familiar genres can offer low-risk discovery: unfamiliar titles with a recognizable taste rationale. Recommendations with no genre overlap are more exploratory and carry more relevance risk. The service can use both kinds to balance engagement with discovery; the score and observed genre history provide a simple explanation for each choice.",
    "",
  ].join("\n");
  fs.writeFileSync(path.join(resultsDir, "discovery-seed1.md"), report);
  console.log(report);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
