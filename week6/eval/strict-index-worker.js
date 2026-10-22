// Generated with an AI assistant
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const tf = require("@tensorflow/tfjs");
require("@tensorflow/tfjs-backend-wasm");

const fixed = path.resolve(__dirname, "../fixed");
const document = { readyState: "loading", getElementById: () => null, addEventListener() {} };

async function initialize() {
  await tf.setBackend("wasm");
  await tf.ready();
  const context = vm.createContext({ console, document, tf, setTimeout });
  context.window = context;
  for (const filename of ["data.js", "graph.js", "script.js"]) {
    vm.runInContext(fs.readFileSync(path.join(fixed, filename), "utf8"), context, { filename });
  }
  const items = new TextDecoder("windows-1252").decode(fs.readFileSync(path.join(fixed, "u.item")));
  const ratings = fs.readFileSync(path.join(fixed, "u.data"), "utf8");
  const q = (value) => JSON.stringify(value);
  vm.runInContext(`parseItemData(${q(items)});
    parseRatingData(${q(ratings)});
    numUsers = ratings.reduce((max, row) => Math.max(max, row.userId), 0);
    numMovies = movies.length;
    buildRatingMatrix();
    const split = splitByTimestamp();
    HW6_SPLIT.train = split.train;
    HW6_SPLIT.val = split.val;
    HW6_SPLIT.test = split.test;
    HW6_MAX_MOVIE_ID = movies.reduce((max, movie) => Math.max(max, movie.id), 0);
    hw6BuildSplitIndices(HW6_SPLIT);
    setGraph(buildGraph(split.train));`, context);
  const cohort = Array.from(vm.runInContext('hw6SharedCohort("test")', context));
  return { context, cohort };
}

function runUser(context, userId, alpha) {
  return JSON.parse(vm.runInContext(`JSON.stringify((() => {
    const graph = getGraph();
    // Counterfactual: treat the raw user ID as the documented global node index.
    const propagation = pageRank(${alpha}, { _restartIndex: ${userId} });
    const perMovie = movieScores(propagation.p, graph);
    const excluded = hw6ExclusionSet("test", ${userId});
    const eligible = HW6_STATE.candidateIds.map((movieId, localIndex) => ({
      movieId,
      score: Number(perMovie[localIndex]),
    })).filter((row) => !excluded.has(row.movieId) && Number.isFinite(row.score));
    eligible.sort((a, b) => b.score - a.score || a.movieId - b.movieId);
    const recs = eligible.slice(0, 10);
    const grades = HW6_STATE.gradesBySplit.test.get(${userId}) || new Map();
    const relevant = [];
    grades.forEach((rating, movieId) => {
      if (rating >= 4 && HW6_STATE.candidateSet.has(movieId) && !excluded.has(movieId)) relevant.push(movieId);
    });
    const relevantSet = new Set(relevant);
    const hit = recs.filter((row) => relevantSet.has(row.movieId)).length;
    const seedNode = ${userId};
    const seedUserId = seedNode < graph.nUsers ? graph.userIds[seedNode] : null;
    return { userId: ${userId}, seedNode, seedUserId, relevant: relevant.length, hit };
  })())`, context));
}

initialize().then(({ context, cohort }) => {
  process.send({ type: "ready", cohort });
  process.on("message", (message) => {
    try {
      const rows = message.task.userIds.map((userId) => runUser(context, userId, message.task.alpha));
      process.send({ type: "result", id: message.id, rows });
    } catch (error) {
      process.send({ type: "error", id: message.id, error: String(error && error.stack ? error.stack : error) });
    }
  });
}).catch((error) => {
  process.send({ type: "fatal", error: String(error && error.stack ? error.stack : error) });
  process.exitCode = 1;
});
