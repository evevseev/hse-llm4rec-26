// Generated with an AI assistant
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const tf = require("@tensorflow/tfjs");
require("@tensorflow/tfjs-backend-wasm");

const root = path.resolve(__dirname, "..");
const fixed = path.join(root, "fixed");
const resultsDir = path.join(root, "results");

async function main() {
  await tf.setBackend("wasm");
  await tf.ready();
  const context = vm.createContext({ console, document: { getElementById: () => null }, window: {}, tf });
  vm.runInContext(fs.readFileSync(path.join(fixed, "data.js"), "utf8"), context);
  vm.runInContext(fs.readFileSync(path.join(fixed, "script.js"), "utf8"), context);
  context.itemText = fs.readFileSync(path.join(fixed, "u.item"), "latin1");
  context.ratingText = fs.readFileSync(path.join(fixed, "u.data"), "ascii");
  vm.runInContext(
    "parseItemData(itemText); parseRatingData(ratingText); " +
      "numUsers = ratings.reduce((m, r) => Math.max(m, r.userId), 0); " +
      "numMovies = movies.length; buildRatingMatrix(); " +
      "const split = splitByTimestamp(); trainSet = split.train; " +
      "valSet = split.val; testSet = split.test; " +
      "initializeFactors(trainSet, NUM_FACTORS); " +
      "trainingHistory = trainMF(trainSet, valSet, {epochs: 20, lr: 0.01, reg: 0.05, batchSize: 64}); " +
      "bestCheckpoint = selectBestCheckpoint(trainingHistory);",
    context,
  );

  const snapshot = vm.runInContext(
    "({ userFactors: Array.from(model.userFactors.dataSync()), " +
      "itemFactors: Array.from(model.itemFactors.dataSync()), " +
      "factorCount: model.userFactors.shape[1], globalMean: model.globalMean, " +
      "movies, trainSet, valSet, testSet, history: trainingHistory, bestCheckpoint })",
    context,
  );
  const movieIds = snapshot.movies.map((movie) => movie.id);
  const trainMovieIds = new Set(snapshot.trainSet.map((rating) => rating.movieId));
  const testUsers = new Set(snapshot.testSet.map((rating) => rating.userId));
  const relevantByUser = new Map();
  for (const rating of snapshot.testSet) {
    if (rating.rating < 4 || !trainMovieIds.has(rating.movieId)) continue;
    if (!relevantByUser.has(rating.userId)) relevantByUser.set(rating.userId, new Set());
    relevantByUser.get(rating.userId).add(rating.movieId);
  }
  const evaluableUsers = Array.from(relevantByUser.keys());
  const f = snapshot.factorCount;
  const itemRows = snapshot.itemFactors.length / f;
  const userHistory = new Map();
  for (const rating of [...snapshot.trainSet, ...snapshot.valSet]) {
    if (!userHistory.has(rating.userId)) userHistory.set(rating.userId, new Set());
    userHistory.get(rating.userId).add(rating.movieId);
  }

  const clippedHits = new Map();
  let topScoresAtFive = 0;
  let topSlots = 0;
  for (const userId of evaluableUsers) {
    context.probeUserId = userId;
    const recs = vm.runInContext("recommendTopK(probeUserId, 10)", context);
    const relevant = relevantByUser.get(userId);
    clippedHits.set(userId, recs.filter((item) => relevant.has(item.movieId)).length);
    topScoresAtFive += recs.filter((item) => item.score === 5).length;
    topSlots += recs.length;
  }

  function evaluateRawScores(trainPoolOnly) {
    let hits = 0;
    let relevantCount = 0;
    let macroRecall = 0;
    for (const userId of evaluableUsers) {
      const userStart = userId * f;
      const rated = userHistory.get(userId) || new Set();
      const candidates = movieIds.filter((id) =>
        id < itemRows && !rated.has(id) && (!trainPoolOnly || trainMovieIds.has(id)));
      candidates.sort((a, b) => {
        let scoreA = 0;
        let scoreB = 0;
        const itemStartA = a * f;
        const itemStartB = b * f;
        for (let k = 0; k < f; k++) {
          scoreA += snapshot.userFactors[userStart + k] * snapshot.itemFactors[itemStartA + k];
          scoreB += snapshot.userFactors[userStart + k] * snapshot.itemFactors[itemStartB + k];
        }
        return scoreB - scoreA || a - b;
      });
      const top = candidates.slice(0, 10);
      const relevant = relevantByUser.get(userId);
      const hit = top.filter((id) => relevant.has(id)).length;
      hits += hit;
      relevantCount += relevant.size;
      macroRecall += hit / relevant.size;
    }
    return {
      macroRecallAt10: macroRecall / (evaluableUsers.length || 1),
      microRecallAt10: hits / (relevantCount || 1),
      hits,
      relevantTargets: relevantCount,
      evaluableUsers: evaluableUsers.length,
    };
  }

  const clippedRecall = Array.from(clippedHits.entries()).reduce(
    (sum, [userId, hits]) => sum + hits / relevantByUser.get(userId).size, 0,
  ) / (evaluableUsers.length || 1);
  const clippedTotalHits = Array.from(clippedHits.values()).reduce((sum, hits) => sum + hits, 0);
  const rawAllCatalog = evaluateRawScores(false);
  const rawTrainPool = evaluateRawScores(true);
  const result = {
    backend: tf.getBackend(),
    parameters: { epochs: 20, lr: 0.01, reg: 0.05, batchSize: 64 },
    bestCheckpoint: snapshot.bestCheckpoint,
    candidatePools: { fullCatalog: movieIds.length, trainMovies: trainMovieIds.size },
    evaluableUsers: evaluableUsers.length,
    relevantTargets: Array.from(relevantByUser.values()).reduce((sum, ids) => sum + ids.size, 0),
    currentClippedTopK: {
      macroRecallAt10: clippedRecall,
      microRecallAt10: clippedTotalHits / (Array.from(relevantByUser.values()).reduce((sum, ids) => sum + ids.size, 0) || 1),
      hits: clippedTotalHits,
      topSlots,
      scoresClampedTo5: topScoresAtFive,
      shareOfSlotsClampedTo5: topScoresAtFive / (topSlots || 1),
    },
    rawScoreRanking: {
      fullCatalog: rawAllCatalog,
      trainMoviePool: rawTrainPool,
    },
    note: "This is one fresh default-parameter training run; raw-score rankings keep the same fitted factors and differ only in ranking/clipping and candidate pool.",
  };
  fs.mkdirSync(resultsDir, { recursive: true });
  fs.writeFileSync(path.join(resultsDir, "ranking-probe.json"), `${JSON.stringify(result, null, 2)}\n`);
  const report = [
    "# Ranking/clipping probe",
    "",
    "Fresh full MovieLens training with the same default parameters; all ranking variants below use the same selected model factors.",
    "",
    `- Selected epoch: ${result.bestCheckpoint.epoch}; validation RMSE ${result.bestCheckpoint.valRMSE.toFixed(6)}.`,
    `- Evaluable users / relevant candidate test items: ${result.evaluableUsers} / ${result.relevantTargets}.`,
    `- Current clipped-score Top-K: macro Recall@10 ${clippedRecall.toFixed(6)} (${clippedTotalHits} hits); ${topScoresAtFive}/${topSlots} Top-10 slots (${(100 * topScoresAtFive / (topSlots || 1)).toFixed(2)}%) have score exactly 5 after clipping.`,
    `- Raw-score ranking, full catalog: macro Recall@10 ${rawAllCatalog.macroRecallAt10.toFixed(6)} (${rawAllCatalog.hits} hits).`,
    `- Raw-score ranking, train-movie pool only: macro Recall@10 ${rawTrainPool.macroRecallAt10.toFixed(6)} (${rawTrainPool.hits} hits).`,
    "- This is a second random-initialized training run; compare variants within this run, not its absolute numbers with the previously saved run.",
    "",
  ].join("\n");
  fs.writeFileSync(path.join(resultsDir, "ranking-probe.md"), report);
  console.log(report);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
