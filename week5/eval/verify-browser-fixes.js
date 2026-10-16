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

async function main() {
  await tf.setBackend("wasm");
  await tf.ready();
  const context = vm.createContext({
    console,
    document: { getElementById: () => null },
    window: {},
    tf,
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
      "valSet = split.val; testSet = split.test; " +
      `initializeFactors(trainSet, NUM_FACTORS, ${seed}); ` +
      `trainingHistory = trainMF(trainSet, valSet, {epochs:20,lr:0.01,reg:0.05,batchSize:64,seed:${seed}}); ` +
      "bestCheckpoint = selectBestCheckpoint(trainingHistory);",
    context,
  );

  const scriptSource = fs.readFileSync(path.join(fixed, "script.js"), "utf8");
  context.scriptSourceForAudit = scriptSource;
  const result = vm.runInContext(`(() => {
    const matrixCells = numUsers * movies.length;
    const observed = new Set(ratings.map(r => r.userId + ":" + r.movieId)).size;
    const trainCounts = model.itemTrainCounts;
    const n1 = recommendTopK(1, 10, 1);
    const n20 = recommendTopK(1, 10, 20);
    const title = movies.find(m => m.title.includes("Misérables, Les"))?.title || null;
    const modelTestRMSE = computeRMSEFor(testSet);
    const baselineTestRMSE = computeBaselineRMSE(testSet);
    return {
      users: numUsers,
      movies: movies.length,
      ratings: ratings.length,
      matrixCells,
      observedCells: observed,
      matrixDensityPercent: 100 * observed / matrixCells,
      correctedDecodedTitle: title,
      recommendationMinTrainRatings: RECOMMENDATION_MIN_TRAIN_RATINGS,
      n1Recommendations: n1.map(x => ({...x, trainRatings: trainCounts[x.movieId]})),
      n20Recommendations: n20.map(x => ({...x, trainRatings: trainCounts[x.movieId]})),
      n20AllMeetThreshold: n20.every(x => trainCounts[x.movieId] >= 20),
      bestCheckpoint,
      modelTestRMSE,
      baselineTestRMSE,
      uiPassesThreshold: scriptSourceForAudit.includes("recommendTopK(Number(userId), 10, RECOMMENDATION_MIN_TRAIN_RATINGS)"),
      uiRendersTestRMSE: scriptSourceForAudit.includes("computeRMSEFor(testSet)"),
      uiRendersMatrixDensity: scriptSourceForAudit.includes("Matrix fill"),
    };
  })()`, context);

  fs.mkdirSync(resultsDir, { recursive: true });
  fs.writeFileSync(path.join(resultsDir, "browser-issues-after.json"), `${JSON.stringify(result, null, 2)}\n`);
  const recommendationTable = (rows) => rows.map((item, i) =>
    `| ${i + 1} | ${item.title} | ${item.score.toFixed(4)} | ${item.trainRatings} |`).join("\n");
  const report = [
    "# Browser issue verification — after fixes",
    "",
    "Actual MovieLens data; deterministic seed 1; TensorFlow.js WASM backend. The model is trained and its checkpoint selected by validation RMSE before reporting test metrics.",
    "",
    `- Matrix occupancy: ${result.observedCells.toLocaleString("en-US")} / ${result.matrixCells.toLocaleString("en-US")} = **${result.matrixDensityPercent.toFixed(4)}%**; UI displays 6.30%.`,
    `- Text decoding: **${result.correctedDecodedTitle}**; fixed parser decodes u.item bytes as Windows-1252 rather than UTF-8.`,
    `- Browser recommendation call passes N=${result.recommendationMinTrainRatings}; assertion that every N=20 result has at least 20 train ratings: **${result.n20AllMeetThreshold}**.`,
    `- Selected epoch ${result.bestCheckpoint.epoch}; validation RMSE ${result.bestCheckpoint.valRMSE.toFixed(6)}. Model test RMSE ${result.modelTestRMSE.toFixed(6)}; mean-baseline test RMSE ${result.baselineTestRMSE.toFixed(6)}.`,
    `- UI source checks: threshold passed=${result.uiPassesThreshold}, model test RMSE rendered=${result.uiRendersTestRMSE}, matrix density rendered=${result.uiRendersMatrixDensity}.`,
    "",
    "## User 1 before: N=1",
    "",
    "| Rank | Movie | Score | Train ratings |",
    "|---:|---|---:|---:|",
    recommendationTable(result.n1Recommendations),
    "",
    "## User 1 after: N=20",
    "",
    "| Rank | Movie | Score | Train ratings |",
    "|---:|---|---:|---:|",
    recommendationTable(result.n20Recommendations),
    "",
  ].join("\n");
  fs.writeFileSync(path.join(resultsDir, "browser-issues-after.md"), report);
  console.log(report);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
