// Generated with an AI assistant
// Independent, plain-JavaScript reconstruction of MovieLens user 1 PPR.
// No TensorFlow.js and no application functions are used for the calculation.
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const resultsDir = path.join(root, "results");
const alpha = Number(JSON.parse(fs.readFileSync(path.join(resultsDir, "run-summary.json"), "utf8")).selectedAlpha);
const genreNames = [
  "Action", "Adventure", "Animation", "Children's", "Comedy", "Crime", "Documentary", "Drama", "Fantasy",
  "Film-Noir", "Horror", "Musical", "Mystery", "Romance", "Sci-Fi", "Thriller", "War", "Western",
];

function parseMovies(text) {
  const byId = new Map();
  for (const line of text.trimEnd().split(/\r?\n/)) {
    const fields = line.split("|");
    const flags = fields.slice(6, 24).map(Number);
    byId.set(Number(fields[0]), {
      id: Number(fields[0]),
      title: fields[1],
      genres: genreNames.filter((_, index) => flags[index] === 1),
    });
  }
  return byId;
}

function parseRatings(text) {
  return text.trimEnd().split(/\r?\n/).map((line) => {
    const [userId, movieId, rating, timestamp] = line.split("\t").map(Number);
    return { userId, movieId, rating, timestamp };
  });
}

function splitByUserChronology(ratings) {
  const byUser = new Map();
  for (const row of ratings) {
    if (!byUser.has(row.userId)) byUser.set(row.userId, []);
    byUser.get(row.userId).push(row);
  }
  const split = { train: [], val: [], test: [] };
  for (const rows of byUser.values()) {
    if (rows.length < 5) continue;
    rows.sort((a, b) => a.timestamp - b.timestamp || a.movieId - b.movieId);
    const trainEnd = Math.floor(0.8 * rows.length);
    const valEnd = trainEnd + Math.floor(0.1 * rows.length);
    split.train.push(...rows.slice(0, trainEnd));
    split.val.push(...rows.slice(trainEnd, valEnd));
    split.test.push(...rows.slice(valEnd));
  }
  return split;
}

function buildPositiveGraph(train) {
  const userIds = Array.from(new Set(train.map((row) => row.userId))).sort((a, b) => a - b);
  const movieIds = Array.from(new Set(train.map((row) => row.movieId))).sort((a, b) => a - b);
  const userIndex = new Map(userIds.map((id, index) => [id, index]));
  const movieIndex = new Map(movieIds.map((id, index) => [id, index]));
  const userMovies = new Map(userIds.map((id) => [id, new Set()]));
  const movieUsers = new Map(movieIds.map((id) => [id, new Set()]));
  for (const row of train) {
    if (row.rating < 4) continue;
    userMovies.get(row.userId).add(row.movieId);
    movieUsers.get(row.movieId).add(row.userId);
  }
  return { userIds, movieIds, userIndex, movieIndex, userMovies, movieUsers };
}

function iteratePpr(graph, seedNode, linkProbability, options = {}) {
  const { userIds, movieIds, userIndex, movieIndex, userMovies, movieUsers } = graph;
  const nUsers = userIds.length;
  const nodeCount = nUsers + movieIds.length;
  const degrees = new Float64Array(nodeCount);
  for (let u = 0; u < nUsers; u++) degrees[u] = userMovies.get(userIds[u]).size;
  for (let i = 0; i < movieIds.length; i++) degrees[nUsers + i] = movieUsers.get(movieIds[i]).size;

  const seed = new Float64Array(nodeCount);
  seed[seedNode] = 1;
  let p = Float64Array.from(seed);
  let residual = Infinity;
  let iterations = 0;
  let converged = false;
  let previous = Float64Array.from(p);
  const maxIter = options.maxIter || 500;
  const tol = options.tol === undefined ? 1e-6 : options.tol;

  while (iterations < maxIter) {
    const next = new Float64Array(nodeCount);
    let danglingMass = 0;
    for (let node = 0; node < nodeCount; node++) {
      if (degrees[node] === 0) {
        danglingMass += p[node];
        continue;
      }
      const share = linkProbability * p[node] / degrees[node];
      if (node < nUsers) {
        for (const movieId of userMovies.get(userIds[node])) {
          next[nUsers + movieIndex.get(movieId)] += share;
        }
      } else {
        const movieId = movieIds[node - nUsers];
        for (const userId of movieUsers.get(movieId)) next[userIndex.get(userId)] += share;
      }
    }
    const restartMass = 1 - linkProbability + linkProbability * danglingMass;
    next[seedNode] += restartMass;
    residual = 0;
    for (let node = 0; node < nodeCount; node++) residual += Math.abs(next[node] - p[node]);
    previous = p;
    p = next;
    iterations++;
    if (residual < tol) {
      converged = true;
      break;
    }
  }
  return { p, previous, degrees, iterations, residual, converged, seed };
}

function recommendationList(graph, probabilities, userId, targetUserId, split, movies) {
  const excluded = new Set();
  for (const row of split.train) if (row.userId === targetUserId) excluded.add(row.movieId);
  for (const row of split.val) if (row.userId === targetUserId) excluded.add(row.movieId);
  return graph.movieIds
    .filter((movieId) => !excluded.has(movieId))
    .map((movieId) => ({
      movieId,
      score: probabilities[graph.userIds.length + graph.movieIndex.get(movieId)],
      title: movies.get(movieId).title,
      genres: movies.get(movieId).genres,
    }))
    .sort((a, b) => b.score - a.score || a.movieId - b.movieId)
    .slice(0, 10);
}

function userRelevantTest(graph, split, userId) {
  const excluded = new Set();
  for (const row of split.train) if (row.userId === userId) excluded.add(row.movieId);
  for (const row of split.val) if (row.userId === userId) excluded.add(row.movieId);
  return split.test.filter((row) => row.userId === userId && row.rating >= 4 &&
    graph.movieIndex.has(row.movieId) && !excluded.has(row.movieId));
}

const movies = parseMovies(new TextDecoder("windows-1252").decode(fs.readFileSync(path.join(root, "fixed/u.item"))));
const ratings = parseRatings(fs.readFileSync(path.join(root, "fixed/u.data"), "utf8"));
const split = splitByUserChronology(ratings);
const graph = buildPositiveGraph(split.train);
const userId = 1;
const userNode = graph.userIndex.get(userId);
if (userNode === undefined) throw new Error("user 1 is not in the training graph");
const degree = graph.userMovies.get(userId).size;

// Compute one update separately so the mass redistribution is inspectable.
const step1 = iteratePpr(graph, userNode, alpha, { maxIter: 1 });
const result = iteratePpr(graph, userNode, alpha);
const testRecs = recommendationList(graph, result.p, userId, userId, split, movies);
const relevant = userRelevantTest(graph, split, userId);
const relevantIds = new Set(relevant.map((row) => row.movieId));
const hits = testRecs.filter((row) => relevantIds.has(row.movieId));

const firstRec = testRecs[0];
const firstMovieUsers = Array.from(graph.movieUsers.get(firstRec.movieId));
const firstMovieContributions = firstMovieUsers.map((connectedUserId) => {
  const node = graph.userIndex.get(connectedUserId);
  const contribution = alpha * result.previous[node] / result.degrees[node];
  return { userId: connectedUserId, userNode: node, userProbability: result.previous[node], userDegree: result.degrees[node], contribution };
}).sort((a, b) => b.contribution - a.contribution);
const incomingScore = firstMovieContributions.reduce((sum, row) => sum + row.contribution, 0);

// Strict node-index interpretation of argument `1`: the second user node.
const strictIndexResult = iteratePpr(graph, 1, alpha);
const strictIndexTargetUserId = graph.userIds[1];
const strictIndexTop10ForUser1 = recommendationList(graph, strictIndexResult.p, userId, userId, split, movies);
const strictIndexTop10ForSeedUser = recommendationList(graph, strictIndexResult.p, strictIndexTargetUserId, strictIndexTargetUserId, split, movies);

const appTop10All = JSON.parse(fs.readFileSync(path.join(resultsDir, "top10-users-1-2.json"), "utf8"));
const appTop10 = appTop10All.users[String(userId)].ppr;
const appUser2Top10 = appTop10All.users[String(strictIndexTargetUserId)].ppr;
const appRecallAll = JSON.parse(fs.readFileSync(path.join(resultsDir, "test-recall.json"), "utf8"));
const appRecall = appRecallAll.methods.ppr.perUser.find((row) => row.userId === userId);
const appConvergence = JSON.parse(fs.readFileSync(path.join(resultsDir, "convergence.json"), "utf8"));
const appUserConvergence = appConvergence.results.pprUser1;
const maxAbsScoreDiff = Math.max(...testRecs.map((row, index) => Math.abs(row.score - appTop10[index].score)));
const appIds = appTop10.map((row) => row.movieId);
const manualIds = testRecs.map((row) => row.movieId);
const appRelevantRatings = split.test.filter((row) => row.userId === userId && row.rating >= 4);

const report = {
  userId,
  alpha,
  splitCounts: { train: split.train.length, val: split.val.length, test: split.test.length },
  graph: {
    users: graph.userIds.length,
    movies: graph.movieIds.length,
    nodeCount: graph.userIds.length + graph.movieIds.length,
    userNodeIndex: userNode,
    userNodeLabel: `user ${userId}`,
    userPositiveDegree: degree,
    userPositiveMovieIds: Array.from(graph.userMovies.get(userId)).sort((a, b) => a - b),
  },
  firstStep: {
    userProbabilityAfterRestart: step1.p[userNode],
    linkMass: alpha,
    perPositiveMovieLinkProbability: alpha / degree,
    positiveMoviesCount: degree,
    sumOfMassOnPositiveMovies: alpha,
    samplePositiveMovieMasses: Array.from(graph.userMovies.get(userId)).sort((a, b) => a - b).slice(0, 5)
      .map((movieId) => ({ movieId, title: movies.get(movieId).title, probability: step1.p[graph.userIds.length + graph.movieIndex.get(movieId)] })),
  },
  convergence: {
    manualIterations: result.iterations,
    manualResidual: result.residual,
    manualConverged: result.converged,
    appIterations: appUserConvergence.iterations,
    appResidual: appUserConvergence.residual,
    appConverged: appUserConvergence.converged,
  },
  firstRecommendedMovieScore: {
    movieId: firstRec.movieId,
    title: firstRec.title,
    score: firstRec.score,
    positiveTrainingDegree: firstMovieUsers.length,
    incomingContributionSum: incomingScore,
    scoreEquation: "alpha * sum_{connected users u} p[u] / degree[u]",
    largestIncomingContributions: firstMovieContributions.slice(0, 5),
    appScore: appTop10[0].score,
    absoluteDifference: Math.abs(firstRec.score - appTop10[0].score),
  },
  testRecallAt10: {
    eligibleRelevantCount: relevant.length,
    allPositiveTestRatingsForUser: appRelevantRatings.length,
    hitCount: hits.length,
    hitMovies: hits,
    manualRecall: relevant.length ? hits.length / relevant.length : 0,
    appRelevantCount: appRecall.relevant,
    appHitCount: appRecall.hit,
    appRecall: appRecall.relevant ? appRecall.hit / appRecall.relevant : 0,
  },
  appComparison: {
    top10MovieIdsMatch: JSON.stringify(manualIds) === JSON.stringify(appIds),
    maxAbsoluteScoreDifferenceTop10: maxAbsScoreDiff,
  },
  strictNodeIndexCounterfactual: {
    argumentValue: 1,
    seedNodeIndex: 1,
    actualSeedUserId: strictIndexTargetUserId,
    firstMovieId: strictIndexTop10ForUser1[0].movieId,
    firstMovieTitle: strictIndexTop10ForUser1[0].title,
    firstMovieScore: strictIndexTop10ForUser1[0].score,
    top10MovieIdsWithUser1Exclusions: strictIndexTop10ForUser1.map((row) => row.movieId),
    top10MatchesApplicationForSeedUser2: JSON.stringify(strictIndexTop10ForSeedUser.map((row) => row.movieId)) ===
      JSON.stringify(appUser2Top10.map((row) => row.movieId)),
    appUser2Top10MovieIds: appUser2Top10.map((row) => row.movieId),
  },
};

fs.writeFileSync(path.join(resultsDir, "manual-ppr-user1.json"), JSON.stringify(report, null, 2) + "\n");
console.log(JSON.stringify(report, null, 2));
