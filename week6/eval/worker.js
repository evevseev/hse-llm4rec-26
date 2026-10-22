// Generated with an AI assistant
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const tf = require("@tensorflow/tfjs");
require("@tensorflow/tfjs-backend-wasm");

const fixed = path.resolve(__dirname, "../fixed");
const elements = new Map();
const document = {
  readyState: "loading",
  getElementById(id) {
    if (id === "graph-view") return null;
    if (!elements.has(id)) {
      elements.set(id, {
        value: id === "alpha" ? "0.85" : "",
        textContent: "",
        innerHTML: "",
        className: "",
        style: {},
        addEventListener() {},
      });
    }
    return elements.get(id);
  },
  addEventListener() {},
};

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
  vm.runInContext(`parseItemData(${JSON.stringify(items)});
    parseRatingData(${JSON.stringify(ratings)});
    numUsers = ratings.reduce((max, row) => Math.max(max, row.userId), 0);
    numMovies = movies.length;
    buildRatingMatrix();
    const parts = splitByTimestamp();
    HW6_SPLIT.train = parts.train;
    HW6_SPLIT.val = parts.val;
    HW6_SPLIT.test = parts.test;
    HW6_MAX_MOVIE_ID = movies.reduce((max, movie) => Math.max(max, movie.id), 0);
    hw6BuildSplitIndices(HW6_SPLIT);
    setGraph(buildGraph(parts.train));`, context);
  return context;
}

function runTask(context, task) {
  vm.runInContext(`hw6SetAlpha(${Number(task.alpha)})`, context);
  const split = task.split === "val" ? "val" : "test";
  const verifyIds = new Set(task.verifyUsers || []);
  const rows = [];
  for (const userId of task.userIds) {
    const recs = vm.runInContext(
      `recommendTopK("ppr", ${Number(userId)}, 10, ${JSON.stringify(split)})`,
      context,
    );
    const details = vm.runInContext(`(() => {
      const userId = ${Number(userId)};
      const excluded = hw6ExclusionSet(${JSON.stringify(split)}, userId);
      const grades = HW6_STATE.gradesBySplit[${JSON.stringify(split)}].get(userId) || new Map();
      const relevant = [];
      grades.forEach((rating, movieId) => {
        if (rating >= 4 && HW6_STATE.candidateSet.has(movieId) && !excluded.has(movieId)) relevant.push(movieId);
      });
      return relevant;
    })()`, context);
    const relevant = new Set(details);
    let hit = 0;
    for (const rec of recs) if (relevant.has(rec.movieId)) hit++;
    const row = { userId, relevant: relevant.size, hit };
    if (verifyIds.has(userId)) {
      const propagation = vm.runInContext("HW6_STATE.ppr", context);
      row.scores = Array.from(propagation.scores);
      row.iterations = propagation.iterations;
      row.residual = propagation.residual;
      row.converged = propagation.converged;
      row.recommendations = recs;
    }
    rows.push(row);
  }
  return { rows };
}

initialize().then((context) => {
  process.send({ type: "ready" });
  process.on("message", (message) => {
    try {
      process.send({ type: "result", id: message.id, result: runTask(context, message.task) });
    } catch (error) {
      process.send({ type: "error", id: message.id, error: String(error && error.stack ? error.stack : error) });
    }
  });
}).catch((error) => {
  if (process.send) process.send({ type: "fatal", error: String(error && error.stack ? error.stack : error) });
  process.exitCode = 1;
});
