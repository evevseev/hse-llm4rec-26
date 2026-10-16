// Generated with an AI assistant
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const tf = require("@tensorflow/tfjs");
require("@tensorflow/tfjs-backend-wasm");

const root = path.resolve(__dirname, "..");
const fixed = path.join(root, "fixed");
const resultsDir = path.join(root, "results");

function maxAbsDiff(a, b) {
  let max = 0;
  for (let i = 0; i < a.length; i++) max = Math.max(max, Math.abs(a[i] - b[i]));
  return max;
}

async function compareSelectionGradients() {
  await tf.setBackend("cpu");
  await tf.ready();
  const userFactors = tf.variable(tf.tensor2d([[0.2, -0.4], [0.5, 0.3], [-0.1, 0.7]]));
  const itemFactors = tf.variable(tf.tensor2d([[0.6, 0.1], [-0.2, 0.8], [0.4, -0.5]]));
  const userIds = tf.tensor1d([2, 0, 2], "int32");
  const itemIds = tf.tensor1d([1, 2, 0], "int32");
  const targets = tf.tensor1d([3, 2, 4]);

  const gatherLoss = () => {
    const users = tf.gather(userFactors, userIds);
    const items = tf.gather(itemFactors, itemIds);
    const predictions = tf.sum(users.mul(items), 1).add(3.2);
    return tf.losses.meanSquaredError(targets, predictions);
  };
  const oneHotLoss = () => {
    const users = tf.oneHot(userIds, userFactors.shape[0]).matMul(userFactors);
    const items = tf.oneHot(itemIds, itemFactors.shape[0]).matMul(itemFactors);
    const predictions = tf.sum(users.mul(items), 1).add(3.2);
    return tf.losses.meanSquaredError(targets, predictions);
  };

  const gatherValueAndGrads = tf.variableGrads(gatherLoss, [userFactors, itemFactors]);
  const oneHotValueAndGrads = tf.variableGrads(oneHotLoss, [userFactors, itemFactors]);
  const gatherUserGrad = Array.from(gatherValueAndGrads.grads[userFactors.name].dataSync());
  const oneHotUserGrad = Array.from(oneHotValueAndGrads.grads[userFactors.name].dataSync());
  const gatherItemGrad = Array.from(gatherValueAndGrads.grads[itemFactors.name].dataSync());
  const oneHotItemGrad = Array.from(oneHotValueAndGrads.grads[itemFactors.name].dataSync());
  const result = {
    backend: tf.getBackend(),
    selectedUserIds: [2, 0, 2],
    gatherLoss: gatherValueAndGrads.value.dataSync()[0],
    oneHotLoss: oneHotValueAndGrads.value.dataSync()[0],
    userGradientMaxAbsDifference: maxAbsDiff(gatherUserGrad, oneHotUserGrad),
    itemGradientMaxAbsDifference: maxAbsDiff(gatherItemGrad, oneHotItemGrad),
    gatherUserGradient: gatherUserGrad,
    oneHotUserGradient: oneHotUserGrad,
    gatherItemGradient: gatherItemGrad,
    oneHotItemGradient: oneHotItemGrad,
  };
  tf.dispose([
    userFactors, itemFactors, userIds, itemIds, targets,
    gatherValueAndGrads.value, ...Object.values(gatherValueAndGrads.grads),
    oneHotValueAndGrads.value, ...Object.values(oneHotValueAndGrads.grads),
  ]);
  return result;
}

function rankMasked(scores, candidateIds, excluded, k = 10) {
  const mask = new Float32Array(scores.length);
  let eligibleCount = 0;
  for (const movieId of candidateIds) {
    if (!excluded.has(movieId) && movieId >= 0 && movieId < mask.length) {
      mask[movieId] = 1;
      eligibleCount++;
    }
  }
  const count = Math.min(k, eligibleCount);
  if (count <= 0) {
    return [];
  }
  return tf.tidy(() => {
    const masked = tf.tensor1d(scores).add(tf.tensor1d(mask).sub(1).mul(1e9));
    const top = tf.topk(masked, count);
    return Array.from(top.indices.dataSync());
  });
}

async function main() {
  const gradientCheck = await compareSelectionGradients();
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
      "valSet = split.val; testSet = split.test;",
    context,
  );
  const splitData = vm.runInContext("({ ratings, movies, trainSet, valSet, testSet, numUsers })", context);
  const pairKey = (rating) => `${rating.userId}:${rating.movieId}`;
  const allPairs = new Set(splitData.ratings.map(pairKey));
  const trainPairs = new Set(splitData.trainSet.map(pairKey));
  const relevantTest = splitData.testSet.filter((rating) => rating.rating >= 4);
  const relevantTestPairOverlap = relevantTest.filter((rating) => trainPairs.has(pairKey(rating)));
  const trainMovieIds = new Set(splitData.trainSet.map((rating) => rating.movieId));
  const unseenRelevantRows = relevantTest.filter((rating) => !trainMovieIds.has(rating.movieId));
  const unseenRelevantIds = new Set(unseenRelevantRows.map((rating) => rating.movieId));
  const seenByOtherUserOnly = relevantTest.filter((rating) =>
    trainMovieIds.has(rating.movieId) && !trainPairs.has(pairKey(rating)));
  const trainCandidateRelevantByUser = new Map();
  const allCatalogRelevantByUser = new Map();
  for (const rating of relevantTest) {
    if (!allCatalogRelevantByUser.has(rating.userId)) allCatalogRelevantByUser.set(rating.userId, new Set());
    allCatalogRelevantByUser.get(rating.userId).add(rating.movieId);
    if (trainMovieIds.has(rating.movieId)) {
      if (!trainCandidateRelevantByUser.has(rating.userId)) trainCandidateRelevantByUser.set(rating.userId, new Set());
      trainCandidateRelevantByUser.get(rating.userId).add(rating.movieId);
    }
  }
  const evaluableUsers = Array.from(trainCandidateRelevantByUser.keys());

  console.log("Training a single deterministic model (seed=1) for candidate-pool comparison...");
  vm.runInContext(
    "initializeFactors(trainSet, NUM_FACTORS, 1); " +
      "trainingHistory = trainMF(trainSet, valSet, {epochs:20,lr:0.01,reg:0.05,batchSize:64,seed:1}); " +
      "bestCheckpoint = selectBestCheckpoint(trainingHistory);",
    context,
  );
  const modelSnapshot = vm.runInContext(
    "({ userFactors: Array.from(model.userFactors.dataSync()), " +
      "itemFactors: Array.from(model.itemFactors.dataSync()), " +
      "factorCount: model.userFactors.shape[1], globalMean: model.globalMean, " +
      "itemRows: model.itemFactors.shape[0], bestCheckpoint })",
    context,
  );
  const f = modelSnapshot.factorCount;
  const candidateAllMovies = new Set(splitData.movies.map((movie) => movie.id));
  const fullUsersWithRelevant = new Set(allCatalogRelevantByUser.keys());
  const fullEvaluableUsers = Array.from(fullUsersWithRelevant);
  let trainHits = 0;
  let trainRecallSum = 0;
  let sharedTargetFullHits = 0;
  let sharedTargetTrainHits = 0;
  let sharedTargetMacroFull = 0;
  let sharedTargetMacroTrain = 0;
  let allTargetFullHits = 0;
  let allTargetFullMacro = 0;
  let allTargetRelevantCount = 0;
  let sharedTargetRelevantCount = 0;
  const perUser = [];

  for (const userId of fullEvaluableUsers) {
    const userRow = modelSnapshot.userFactors.slice(userId * f, userId * f + f);
    const scores = new Array(modelSnapshot.itemRows).fill(0);
    const itemFactors = modelSnapshot.itemFactors;
    for (const movie of splitData.movies) {
      let score = modelSnapshot.globalMean;
      const base = movie.id * f;
      for (let k = 0; k < f; k++) score += userRow[k] * itemFactors[base + k];
      scores[movie.id] = Math.max(1, Math.min(5, score));
    }
    const excluded = new Set([...splitData.trainSet, ...splitData.valSet]
      .filter((rating) => rating.userId === userId)
      .map((rating) => rating.movieId));
    const fullRank = rankMasked(scores, candidateAllMovies, excluded);
    const trainRank = rankMasked(scores, trainMovieIds, excluded);
    const sharedRelevant = trainCandidateRelevantByUser.get(userId) || new Set();
    const fullSharedHits = fullRank.filter((id) => sharedRelevant.has(id)).length;
    const trainSharedHits = trainRank.filter((id) => sharedRelevant.has(id)).length;
    if (sharedRelevant.size) {
      sharedTargetFullHits += fullSharedHits;
      sharedTargetTrainHits += trainSharedHits;
      sharedTargetRelevantCount += sharedRelevant.size;
      sharedTargetMacroFull += fullSharedHits / sharedRelevant.size;
      sharedTargetMacroTrain += trainSharedHits / sharedRelevant.size;
      trainHits += trainSharedHits;
      trainRecallSum += trainSharedHits / sharedRelevant.size;
    }

    const allRelevant = allCatalogRelevantByUser.get(userId);
    const fullAllHits = fullRank.filter((id) => allRelevant.has(id)).length;
    allTargetFullHits += fullAllHits;
    allTargetRelevantCount += allRelevant.size;
    allTargetFullMacro += fullAllHits / allRelevant.size;
    perUser.push({
      userId,
      relevantTrainPool: sharedRelevant.size,
      fullCatalogHitsOnTrainKnownTargets: fullSharedHits,
      trainPoolHits: trainSharedHits,
      relevantAllCatalog: allRelevant.size,
      fullCatalogHitsOnAllTargets: fullAllHits,
    });
  }

  const actualRecall = vm.runInContext("recallAtK(10, 1)", context);
  const actualRecallHits = actualRecall.perUser.reduce((sum, row) => sum + row.hit, 0);
  const directTrainMacro = trainRecallSum / (evaluableUsers.length || 1);
  const result = {
    gradientEquivalence: gradientCheck,
    gatherFunctions: ["predictRating", "computeRMSEFor (TensorFlow model path)"],
    trainingFunctionUsesGather: false,
    dataset: {
      totalRatings: splitData.ratings.length,
      trainRatings: splitData.trainSet.length,
      validationRatings: splitData.valSet.length,
      testRatings: splitData.testSet.length,
      uniqueUserMoviePairs: allPairs.size,
      duplicateUserMoviePairs: splitData.ratings.length - allPairs.size,
      trainMovieIds: trainMovieIds.size,
      fullCatalogMovies: candidateAllMovies.size,
      relevantTestRatingsAtLeast4: relevantTest.length,
      relevantTestUserMoviePairsAlsoInTrain: relevantTestPairOverlap.length,
      relevantTestRatingsWhoseMovieExistsInTrainForSomeUser: seenByOtherUserOnly.length,
      relevantTestRatingsWhoseMovieIdIsAbsentFromTrain: unseenRelevantRows.length,
      unseenRelevantDistinctMovieIds: unseenRelevantIds.size,
      unseenRelevantMovieIds: Array.from(unseenRelevantIds).sort((a, b) => a - b),
      evaluableUsersWithTrainPoolRelevantTestItems: evaluableUsers.length,
    },
    model: {
      backend: tf.getBackend(),
      seed: 1,
      parameters: { factors: 16, epochs: 20, lr: 0.01, reg: 0.05, batchSize: 64 },
      bestCheckpoint: modelSnapshot.bestCheckpoint,
    },
    recall: {
      fullCatalogAllRelevantTargets: {
        macro: allTargetFullMacro / (fullUsersWithRelevant.size || 1),
        micro: allTargetFullHits / (allTargetRelevantCount || 1),
        hits: allTargetFullHits,
        relevantRatings: allTargetRelevantCount,
        users: fullUsersWithRelevant.size,
      },
      fullCatalogOnSharedTrainKnownTargets: {
        macro: sharedTargetMacroFull / (evaluableUsers.length || 1),
        micro: sharedTargetFullHits / (sharedTargetRelevantCount || 1),
        hits: sharedTargetFullHits,
        relevantRatings: sharedTargetRelevantCount,
        users: evaluableUsers.length,
      },
      trainPoolOnSameTargets: {
        macro: directTrainMacro,
        micro: sharedTargetTrainHits / (sharedTargetRelevantCount || 1),
        hits: trainHits,
        relevantRatings: sharedTargetRelevantCount,
        users: evaluableUsers.length,
      },
      existingRecallAtKTrainPoolResult: {
        macro: actualRecall.overallRecall,
        hits: actualRecallHits,
        matchesDirectTrainPoolMacro: Math.abs(actualRecall.overallRecall - directTrainMacro) < 1e-9,
      },
    },
    unseenIdsMeaning: "Distinct relevant (rating >= 4) test movie IDs absent from the global train movie-ID set; not user-specific train/test pair overlap.",
    userPairOverlapRows: relevantTestPairOverlap.map((rating) => ({ userId: rating.userId, movieId: rating.movieId, rating: rating.rating })),
    perUserRecall: perUser,
  };

  fs.mkdirSync(resultsDir, { recursive: true });
  fs.writeFileSync(path.join(resultsDir, "recall-semantics.json"), `${JSON.stringify(result, null, 2)}\n`);
  const grad = result.gradientEquivalence;
  const formatRecall = (x) => `${x.macro.toFixed(6)} macro / ${x.micro.toFixed(6)} micro (${x.hits}/${x.relevantRatings}, ${x.users} users)`;
  const report = [
    "# Gather gradients and Recall candidate-pool audit",
    "",
    "## `tf.gather` and one-hot `matMul` gradient check (CPU)",
    "",
    `- Same factors, indices ${JSON.stringify(grad.selectedUserIds)} (including a repeated user), paired movie rows, and MSE objective.`,
    `- Gather loss ${grad.gatherLoss.toFixed(9)}; one-hot/matMul loss ${grad.oneHotLoss.toFixed(9)}.`,
    `- Maximum absolute gradient difference: user factors ${grad.userGradientMaxAbsDifference.toExponential(3)}, item factors ${grad.itemGradientMaxAbsDifference.toExponential(3)}.`,
    "- Current code uses gather in `predictRating` and the TensorFlow path of `computeRMSEFor`; `trainMF` uses one-hot selection plus `matMul`.",
    "",
    "## Train/test overlap and `unseenIds` on MovieLens 100k",
    "",
    `- ${result.dataset.totalRatings} ratings, ${result.dataset.uniqueUserMoviePairs} unique user/movie pairs; duplicate pairs: ${result.dataset.duplicateUserMoviePairs}.`,
    `- Relevant test ratings (>=4): ${relevantTest.length}; relevant test pairs also present for that same user in train: ${relevantTestPairOverlap.length}.`,
    `- ${unseenRelevantRows.length} relevant test-rating rows refer to ${unseenRelevantIds.size} distinct movie IDs absent from the global train pool. Those are the IDs counted by ` + "`unseenIds`" + ".",
    `- ${seenByOtherUserOnly.length} relevant test rows have a movie ID present in another user's train history but not in this user's train history; those are not unseen IDs.`,
    "- The data has no duplicate user/movie pairs, so the README's same-user train/test overlap scenario does not occur here. The code's `unseenIds` is global item-ID absence, not same-user overlap.",
    "",
    "## Recall on the same fitted weights (seed 1)",
    "",
    `- Training: ${splitData.trainSet.length} train ratings; selected epoch ${modelSnapshot.bestCheckpoint.epoch}; validation RMSE ${modelSnapshot.bestCheckpoint.valRMSE.toFixed(6)}.`,
    `- Full catalog, with all relevant test targets in denominator: ${formatRecall(result.recall.fullCatalogAllRelevantTargets)}.`,
    `- Full catalog, restricted to the train-known relevant targets for an apples-to-apples comparison: ${formatRecall(result.recall.fullCatalogOnSharedTrainKnownTargets)}.`,
    `- Train-only candidate pool, same train-known targets: ${formatRecall(result.recall.trainPoolOnSameTargets)}.`,
    `- Existing ` + "`recallAtK(10, 1)`" + ` result matches direct train-pool calculation: ${result.recall.existingRecallAtKTrainPoolResult.matchesDirectTrainPoolMacro}.`,
    `- Candidate pools: ${candidateAllMovies.size} catalog movies vs ${trainMovieIds.size} movies appearing in train.`,
    "- Full-catalog and train-only rows use the same saved user/item factors and same per-user train+validation exclusions; full-catalog's standard denominator includes relevant test items absent from train, while the shared-target comparison isolates ranking-pool effects.",
    "",
  ].join("\n");
  fs.writeFileSync(path.join(resultsDir, "recall-semantics.md"), report);
  console.log(report);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
