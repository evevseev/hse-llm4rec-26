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

  const context = vm.createContext({
    console,
    document: { getElementById: () => null },
    window: {},
    tf,
  });
  vm.runInContext(fs.readFileSync(path.join(fixed, "data.js"), "utf8"), context, {
    filename: "fixed/data.js",
  });
  vm.runInContext(fs.readFileSync(path.join(fixed, "script.js"), "utf8"), context, {
    filename: "fixed/script.js",
  });

  const tests = vm.runInContext("runTests()", context);
  console.log(`Self-checks: ${tests.passed}/${tests.checks.length} passed, ${tests.failed} failed, ${tests.pending} pending`);
  for (const check of tests.checks) {
    console.log(`${check.status.padEnd(7)} ${check.name}${check.detail ? ` — ${check.detail}` : ""}`);
  }
  if (tests.passed !== 11 || tests.failed !== 0 || tests.pending !== 0) {
    throw new Error("Built-in self-checks did not all pass.");
  }

  const itemText = fs.readFileSync(path.join(fixed, "u.item"), "latin1");
  const ratingText = fs.readFileSync(path.join(fixed, "u.data"), "ascii");
  context.itemText = itemText;
  context.ratingText = ratingText;
  vm.runInContext(
    "parseItemData(itemText); parseRatingData(ratingText); " +
      "numUsers = ratings.reduce((m, r) => Math.max(m, r.userId), 0); " +
      "numMovies = movies.length; buildRatingMatrix(); " +
      "const split = splitByTimestamp(); " +
      "trainSet = split.train; valSet = split.val; testSet = split.test;",
    context,
  );

  const splitSummary = vm.runInContext(
    "({ users: numUsers, movies: movies.length, ratings: ratings.length, " +
      "train: trainSet.length, validation: valSet.length, test: testSet.length, " +
      "excludedUsers: SPLIT_EXCLUSIONS.length })",
    context,
  );
  console.log("Loaded MovieLens:", splitSummary);

  const params = { epochs: Number(process.env.EPOCHS || 20), lr: 0.01, reg: 0.05, batchSize: 64 };
  const started = Date.now();
  vm.runInContext(
    "initializeFactors(trainSet, NUM_FACTORS); " +
      `trainingHistory = trainMF(trainSet, valSet, ${JSON.stringify(params)}); ` +
      "bestCheckpoint = selectBestCheckpoint(trainingHistory);",
    context,
  );
  const trainingSeconds = (Date.now() - started) / 1000;

  const modelOutput = vm.runInContext(
    "({ bestCheckpoint, history: trainingHistory, " +
      "baselineTestRMSE: computeBaselineRMSE(testSet), " +
      "validationRMSE: computeRMSEFor(valSet), testRMSE: computeRMSEFor(testSet), " +
      "recommendations: [recommendTopK(1, 10), recommendTopK(2, 10)], " +
      "recallAt10: recallAtK(10) })",
    context,
  );
  context.reportRecommendations = modelOutput.recommendations;
  const recommendationExclusionCheck = vm.runInContext(
    "reportRecommendations.map((items, index) => { " +
      "const userId = index + 1; " +
      "const rated = new Set([...trainSet, ...valSet].filter(r => r.userId === userId).map(r => r.movieId)); " +
      "return { userId, overlaps: items.filter(item => rated.has(item.movieId)).map(item => item.movieId) }; " +
      "})",
    context,
  );
  if (recommendationExclusionCheck.some((row) => row.overlaps.length > 0)) {
    throw new Error("A Top-10 list contains a movie rated in train or validation.");
  }

  const output = {
    backend: tf.getBackend(),
    parameters: params,
    dataset: splitSummary,
    trainingSeconds,
    tests: { passed: tests.passed, failed: tests.failed, pending: tests.pending },
    recommendationExclusionCheck,
    recallCandidateBehavior: "Rank all catalog movies; count relevant test movies only when their IDs occur in train.",
    ...modelOutput,
  };

  fs.mkdirSync(resultsDir, { recursive: true });
  fs.writeFileSync(path.join(resultsDir, "metrics.json"), `${JSON.stringify(output, null, 2)}\n`);
  const recommendationText = output.recommendations
    .map((list, i) => `### User ${i + 1}\n\n${list.map((item, rank) => `${rank + 1}. ${item.title} — ${item.score.toFixed(4)}`).join("\n")}`)
    .join("\n\n");
  const report = [
    "# Week 5 matrix factorization results",
    "",
    `- TensorFlow.js backend: ${output.backend}`,
    `- Parameters: epochs=${params.epochs}, lr=${params.lr}, reg=${params.reg}, batchSize=${params.batchSize}`,
    `- Dataset split: ${splitSummary.train} train / ${splitSummary.validation} validation / ${splitSummary.test} test ratings; ${splitSummary.excludedUsers} skipped users`,
    `- Training time: ${trainingSeconds.toFixed(1)} seconds`,
    `- Best validation epoch: ${output.bestCheckpoint.epoch}`,
    `- Test mean-baseline RMSE: ${output.baselineTestRMSE.toFixed(6)}`,
    `- Best-checkpoint validation RMSE: ${output.validationRMSE.toFixed(6)}`,
    `- Best-checkpoint test RMSE: ${output.testRMSE.toFixed(6)}`,
    `- Recall@10: ${output.recallAt10.overallRecall.toFixed(6)}`,
    `- Recall exclusions: ${output.recallAt10.excluded.unseenIds.length} unseen relevant movie IDs; ${output.recallAt10.excluded.usersWithoutRelevant.length} users without relevant candidates`,
    `- Top-10 train/validation exclusion check: ${recommendationExclusionCheck.map((row) => `user ${row.userId}: ${row.overlaps.length} overlap(s)`).join("; ")}`,
    `- Recall ranking candidates: ${output.recallCandidateBehavior}`,
    `- Built-in tests: ${tests.passed} passed / ${tests.failed} failed / ${tests.pending} pending`,
    "",
    recommendationText,
    "",
  ].join("\n");
  fs.writeFileSync(path.join(resultsDir, "report.md"), report);
  console.log(report);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
