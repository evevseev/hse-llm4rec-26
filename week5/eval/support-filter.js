// Generated with an AI assistant
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const tf = require("@tensorflow/tfjs");
require("@tensorflow/tfjs-backend-wasm");

const root = path.resolve(__dirname, "..");
const fixed = path.join(root, "fixed");
const resultsDir = path.join(root, "results");
const seeds = [101, 202, 303];
const thresholds = [1, 5, 10, 20];
const trainText = fs.readFileSync(path.join(fixed, "u.data"), "ascii");
const itemText = fs.readFileSync(path.join(fixed, "u.item"), "latin1");

function makeContext(seed) {
  const context = vm.createContext({
    console,
    document: { getElementById: () => null },
    window: {},
    tf,
    dataSeed: seed,
    itemText,
    ratingText: trainText,
  });
  vm.runInContext(fs.readFileSync(path.join(fixed, "data.js"), "utf8"), context);
  vm.runInContext(fs.readFileSync(path.join(fixed, "script.js"), "utf8"), context);
  vm.runInContext(
    "parseItemData(itemText); parseRatingData(ratingText); " +
      "numUsers = ratings.reduce((m, r) => Math.max(m, r.userId), 0); " +
      "numMovies = movies.length; buildRatingMatrix(); " +
      "const split = splitByTimestamp(); " +
      "trainSet = split.train; valSet = split.val; testSet = []; " +
      "const heldoutTest = split.test; " +
      "initializeFactors(trainSet, NUM_FACTORS, dataSeed); " +
      "trainingHistory = trainMF(trainSet, valSet, " +
      `{"epochs":20,"lr":0.01,"reg":0.05,"batchSize":64,"seed":${seed}}); ` +
      "bestCheckpoint = selectBestCheckpoint(trainingHistory);",
    context,
  );
  return context;
}

function mean(values) {
  return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0;
}

function sampleStd(values) {
  if (values.length < 2) return 0;
  const avg = mean(values);
  return Math.sqrt(values.reduce((sum, value) => sum + (value - avg) ** 2, 0) / (values.length - 1));
}

function evaluateValidation(context, seed, users, relevantByUser, trainCounts, movieCount) {
  const originalVal = vm.runInContext("valSet", context);
  vm.runInContext("valSet = []", context);
  const fullRankings = new Map();
  for (const userId of users) {
    context.evalUserId = userId;
    context.evalMovieCount = movieCount;
    const ranked = vm.runInContext("recommendTopK(evalUserId, evalMovieCount, 1)", context);
    fullRankings.set(userId, ranked);
  }
  context.valToRestore = originalVal;
  vm.runInContext("valSet = valToRestore", context);

  const byThreshold = {};
  const perUser = {};
  for (const n of thresholds) {
    let totalHit = 0;
    let totalRelevant = 0;
    let macro = 0;
    let conditionalMacro = 0;
    let conditionalUsers = 0;
    let usersWithEligibleRelevant = 0;
    let removedRelevant = 0;
    const recalls = [];

    for (const userId of users) {
      const allRelevant = relevantByUser.get(userId);
      const eligibleRelevant = new Set(Array.from(allRelevant).filter((id) => (trainCounts.get(id) || 0) >= n));
      const recommendations = fullRankings.get(userId)
        .filter((item) => (trainCounts.get(item.movieId) || 0) >= n)
        .slice(0, 10);
      const recommendedIds = new Set(recommendations.map((item) => item.movieId));
      const hit = Array.from(eligibleRelevant).filter((id) => recommendedIds.has(id)).length;
      const endToEndRecall = hit / allRelevant.size;
      recalls.push(endToEndRecall);
      macro += endToEndRecall;
      totalHit += hit;
      totalRelevant += allRelevant.size;
      removedRelevant += allRelevant.size - eligibleRelevant.size;
      if (eligibleRelevant.size) {
        conditionalUsers++;
        usersWithEligibleRelevant++;
        conditionalMacro += hit / eligibleRelevant.size;
      }
      perUser[userId] ||= {};
      perUser[userId][`N${n}`] = {
        recall: endToEndRecall,
        hits: hit,
        relevant: allRelevant.size,
        eligibleRelevant: eligibleRelevant.size,
      };
    }

    byThreshold[n] = {
      macroRecall: macro / (users.length || 1),
      microRecall: totalHit / (totalRelevant || 1),
      hits: totalHit,
      relevantTargets: totalRelevant,
      evaluableUsers: users.length,
      usersWithEligibleRelevant,
      usersWithoutEligibleRelevant: users.length - usersWithEligibleRelevant,
      relevantTargetsFilteredByN: removedRelevant,
      conditionalMacroRecall: conditionalMacro / (conditionalUsers || 1),
    };
  }
  return { seed, byThreshold, perUser, fullRankings };
}

function writeCsv(filePath, rows) {
  const columns = Object.keys(rows[0] || {});
  const escape = (value) => {
    const text = String(value ?? "");
    return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  };
  fs.writeFileSync(filePath, [columns.join(","), ...rows.map((row) => columns.map((key) => escape(row[key])).join(","))].join("\n") + "\n");
}

async function main() {
  await tf.setBackend("wasm");
  await tf.ready();

  // The self-checks use only their in-memory toy fixtures; no MovieLens test rows are loaded here.
  const testContext = vm.createContext({ console, document: { getElementById: () => null }, window: {}, tf });
  vm.runInContext(fs.readFileSync(path.join(fixed, "data.js"), "utf8"), testContext);
  vm.runInContext(fs.readFileSync(path.join(fixed, "script.js"), "utf8"), testContext);
  const checks = vm.runInContext("runTests()", testContext);
  console.log(`Self-checks: ${checks.passed}/${checks.checks.length} passed, ${checks.failed} failed, ${checks.pending} pending`);
  if (checks.passed !== 11 || checks.failed !== 0 || checks.pending !== 0) {
    throw new Error("The built-in tests must pass before evaluating support thresholds.");
  }

  const contexts = [];
  const validationRuns = [];
  let trainRatings;
  let validationRatings;
  let movieRows;
  let trainCounts;
  let relevantByUser;
  let evaluableUsers;
  let baseCandidateMovies;

  // Do not put testSet into any context or inspect test labels until N is selected.
  for (const seed of seeds) {
    console.log(`Training seed ${seed}...`);
    const context = makeContext(seed);
    contexts.push(context);
    const data = vm.runInContext(
      "({ trainSet, valSet, movies, bestCheckpoint, " +
        "itemTrainCounts: Array.from(model.itemTrainCounts) })",
      context,
    );
    trainRatings = data.trainSet;
    validationRatings = data.valSet;
    movieRows = data.movies;
    trainCounts = new Map(data.itemTrainCounts.map((count, id) => [id, count]).filter(([, count]) => count > 0));
    const valPositives = new Map();
    for (const rating of validationRatings) {
      if (rating.rating < 4 || !trainCounts.has(rating.movieId)) continue;
      if (!valPositives.has(rating.userId)) valPositives.set(rating.userId, new Set());
      valPositives.get(rating.userId).add(rating.movieId);
    }
    if (!relevantByUser) {
      relevantByUser = valPositives;
      evaluableUsers = Array.from(relevantByUser.keys()).sort((a, b) => a - b);
      baseCandidateMovies = trainCounts.size;
    }
    const evaluated = evaluateValidation(
      context, seed, evaluableUsers, relevantByUser, trainCounts, movieRows.length,
    );
    evaluated.bestCheckpoint = data.bestCheckpoint;
    validationRuns.push(evaluated);
  }

  const validationSummary = {};
  for (const n of thresholds) {
    const rows = validationRuns.map((run) => run.byThreshold[n]);
    validationSummary[n] = {
      macroRecallMean: mean(rows.map((row) => row.macroRecall)),
      macroRecallStd: sampleStd(rows.map((row) => row.macroRecall)),
      microRecallMean: mean(rows.map((row) => row.microRecall)),
      hitsMean: mean(rows.map((row) => row.hits)),
      relevantTargets: rows[0].relevantTargets,
      evaluableUsers: rows[0].evaluableUsers,
      usersWithEligibleRelevantMean: mean(rows.map((row) => row.usersWithEligibleRelevant)),
      relevantTargetsFilteredByN: rows[0].relevantTargetsFilteredByN,
      conditionalMacroRecallMean: mean(rows.map((row) => row.conditionalMacroRecall)),
    };
  }
  const chosenN = thresholds.reduce((best, n) =>
    validationSummary[n].macroRecallMean > validationSummary[best].macroRecallMean ? n : best,
  thresholds[0]);
  console.log(`Chosen N from validation only: ${chosenN}`);

  // Build seed-averaged Top-10s from the three validation-selected model checkpoints.
  const ensembleRecommendations = {};
  for (const userId of [1, 2]) {
    const scoreByMovie = new Map();
    for (const context of contexts) {
      context.evalUserId = userId;
      context.evalMovieCount = movieRows.length;
      const allRanked = vm.runInContext("recommendTopK(evalUserId, evalMovieCount, 1)", context);
      for (const item of allRanked) {
        const row = scoreByMovie.get(item.movieId) || { title: item.title, scoreSum: 0, count: 0 };
        row.scoreSum += item.score;
        row.count++;
        scoreByMovie.set(item.movieId, row);
      }
    }
    const known = new Set([...trainRatings, ...validationRatings]
      .filter((rating) => rating.userId === userId)
      .map((rating) => rating.movieId));
    ensembleRecommendations[userId] = Array.from(scoreByMovie.entries())
      .filter(([movieId, row]) => row.count === seeds.length && (trainCounts.get(movieId) || 0) >= chosenN && !known.has(movieId))
      .map(([movieId, row]) => ({
        movieId,
        title: row.title,
        score: row.scoreSum / row.count,
        trainRatings: trainCounts.get(movieId) || 0,
      }))
      .sort((a, b) => b.score - a.score || a.movieId - b.movieId)
      .slice(0, 10);
  }

  // The N choice is now frozen. This is the only stage that evaluates held-out test labels.
  const heldoutTest = vm.runInContext("heldoutTest", contexts[0]);
  const testRuns = [];
  for (let i = 0; i < contexts.length; i++) {
    const context = contexts[i];
    context.heldoutTest = heldoutTest;
    vm.runInContext("testSet = heldoutTest", context);
    const result = vm.runInContext(`recallAtK(10, ${chosenN})`, context);
    testRuns.push({ seed: seeds[i], result });
  }

  const testMacroScores = testRuns.map((run) => run.result.overallRecall);
  const testRelevant = testRuns[0].result.perUser.reduce((sum, row) => sum + row.relevant, 0);
  const testHitsBySeed = testRuns.map((run) => run.result.perUser.reduce((sum, row) => sum + row.hit, 0));
  const testMacro = mean(testMacroScores);
  const testMeanHits = mean(testHitsBySeed);
  const perUserRows = evaluableUsers.map((userId) => {
    const row = { userId, relevantValidationTargets: relevantByUser.get(userId).size };
    for (const n of [1, chosenN]) {
      const key = `N${n}`;
      const recalls = validationRuns.map((run) => run.perUser[userId][key].recall);
      row[`${key}_validationRecallMean`] = mean(recalls).toFixed(6);
      row[`${key}_validationHitsMean`] = mean(validationRuns.map((run) => run.perUser[userId][key].hits)).toFixed(3);
    }
    return row;
  });

  const output = {
    seeds,
    parameters: { epochs: 20, lr: 0.01, reg: 0.05, batchSize: 64, numFactors: 16 },
    split: {
      trainRatings: trainRatings.length,
      validationRatings: validationRatings.length,
      testRatings: heldoutTest.length,
      movies: movieRows.length,
      trainCandidateMoviesAtN1: baseCandidateMovies,
      validationEligibleUsersAtN1: evaluableUsers.length,
      bestEpochBySeed: validationRuns.map((run) => ({ seed: run.seed, ...run.bestCheckpoint })),
    },
    validation: {
      thresholdSummary: validationSummary,
      selectedN: chosenN,
      selectionMetric: "mean end-to-end macro Recall@10 over 3 seeds, fixed relevant targets (rating >= 4 and at least one train rating); filtered relevant items count as misses",
    },
    testAfterSelection: {
      evaluatedOnlyAfterNWasSelected: true,
      chosenN,
      macroRecallAt10BySeed: testMacroScores,
      meanMacroRecallAt10: testMacro,
      stdMacroRecallAt10: sampleStd(testMacroScores),
      meanHits: testMeanHits,
      relevantTargets: testRelevant,
      usersWithoutRelevant: testRuns[0].result.excluded.usersWithoutRelevant.length,
      unseenRelevantMovieIds: testRuns[0].result.excluded.unseenIds.length,
      lowSupportRelevantMovieIds: testRuns[0].result.excluded.lowSupportIds.length,
    },
    userRecommendations: ensembleRecommendations,
    perUserValidation: perUserRows,
    caveat: "The existing test split was inspected in an earlier diagnostic; this run withheld its labels until N was frozen but cannot make that split historically unseen.",
  };

  fs.mkdirSync(resultsDir, { recursive: true });
  fs.writeFileSync(path.join(resultsDir, "support-filter.json"), `${JSON.stringify(output, null, 2)}\n`);
  writeCsv(path.join(resultsDir, "support-filter-validation-users.csv"), perUserRows);

  const validationTable = thresholds.map((n) => {
    const row = validationSummary[n];
    return `| ${n} | ${row.macroRecallMean.toFixed(6)} ± ${row.macroRecallStd.toFixed(6)} | ${row.microRecallMean.toFixed(6)} | ${row.hitsMean.toFixed(1)} | ${row.usersWithEligibleRelevantMean.toFixed(1)} | ${row.relevantTargetsFilteredByN} |`;
  });
  const recommendationTable = [1, 2].flatMap((userId) => [
    `### User ${userId}`,
    "",
    "| Rank | Movie | Mean score (3 seeds) | Train ratings |",
    "|---:|---|---:|---:|",
    ...ensembleRecommendations[userId].map((item, i) => `| ${i + 1} | ${item.title} | ${item.score.toFixed(4)} | ${item.trainRatings} |`),
    "",
  ]);
  const report = [
    "# Minimum item-support experiment",
    "",
    `- Seeds: ${seeds.join(", ")}; TensorFlow.js backend: ${tf.getBackend()}.` ,
    `- Parameters per seed: factors=16, epochs=20, lr=0.01, reg=0.05, batchSize=64; checkpoint selected by validation RMSE.`,
    `- Training pool: ${trainRatings.length} ratings, ${baseCandidateMovies} distinct candidate movies; validation: ${validationRatings.length} ratings; test: ${heldoutTest.length} ratings.`,
    "- N selected using validation only; metric is end-to-end macro Recall@10 over a fixed set of relevant validation targets (rating >= 4 with at least one train rating). Items filtered by N count as misses, avoiding artificial gains from shrinking the denominator.",
    "",
    "## Validation, average over 3 seeds",
    "",
    "| Minimum train ratings N | Macro Recall@10 (mean ± sample SD) | Micro Recall@10 (mean) | Hits (mean) | Users with relevant target after filter (mean) | Relevant targets filtered by N |",
    "|---:|---:|---:|---:|---:|---:|",
    ...validationTable,
    "",
    `Selected N: **${chosenN}** (highest mean end-to-end macro Recall@10 on validation; ties prefer smaller N).`,
    "",
    "## Test, one post-selection evaluation phase",
    "",
    `- Chosen N=${chosenN}; per-seed macro Recall@10: ${testMacroScores.map((v) => v.toFixed(6)).join(", ")}.`,
    `- Mean macro Recall@10: **${testMacro.toFixed(6)} ± ${sampleStd(testMacroScores).toFixed(6)}** (sample SD); mean hits ${testMeanHits.toFixed(1)} of ${testRelevant} relevant targets.`,
    `- Exclusions: ${testRuns[0].result.excluded.unseenIds.length} unseen relevant movie IDs; ${testRuns[0].result.excluded.lowSupportIds.length} distinct relevant IDs below N; ${testRuns[0].result.excluded.usersWithoutRelevant.length} users without a relevant train-seen test movie.`,
    "",
    "## Seed-averaged Top-10 lists after selected N",
    "",
    ...recommendationTable,
    "Per-user validation comparisons for all eligible users are in `support-filter-validation-users.csv`.",
    "",
    "Caveat: the test labels were withheld in this script until N was chosen, but the existing test split had been inspected in an earlier analysis, so this is not a historically untouched holdout.",
    "",
  ].join("\n");
  fs.writeFileSync(path.join(resultsDir, "support-filter-report.md"), report);
  console.log(report);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
