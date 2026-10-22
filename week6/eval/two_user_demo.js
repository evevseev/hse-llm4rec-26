// Generated with an AI assistant
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const tf = require("@tensorflow/tfjs");
require("@tensorflow/tfjs-backend-wasm");

const root = path.resolve(__dirname, "..");
const fixed = path.join(root, "fixed");
const resultsDir = path.join(root, "results");
const elements = new Map();
const document = {
  readyState: "loading",
  getElementById(id) {
    if (id === "graph-view") return null;
    if (!elements.has(id)) elements.set(id, {
      value: id === "alpha" ? "0.85" : "",
      textContent: "",
      innerHTML: "",
      className: "",
      style: {},
      addEventListener() {},
    });
    return elements.get(id);
  },
  addEventListener() {},
};

function csvField(value) {
  const text = value === null || value === undefined ? "" : String(value);
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

async function main() {
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
    setGraph(buildGraph(parts.train));
    HW6_STATE.backend = tf.getBackend();`, context);

  const settings = [
    { key: "A", userId: 1, alpha: 0.85, changedFromA: "baseline" },
    { key: "B", userId: 2, alpha: 0.85, changedFromA: "seed user only" },
    { key: "C", userId: 1, alpha: 0.50, changedFromA: "alpha only" },
  ];
  const lists = {};
  for (const setting of settings) {
    vm.runInContext(`hw6SetAlpha(${setting.alpha})`, context);
    const recommendations = vm.runInContext(
      `recommendTopK("ppr", ${setting.userId}, 10, "test")`, context,
    );
    const propagation = vm.runInContext("HW6_STATE.ppr", context);
    lists[setting.key] = {
      ...setting,
      iterations: propagation.iterations,
      residual: propagation.residual,
      converged: propagation.converged,
      recommendations,
      meanPopularity: recommendations.length
        ? recommendations.reduce((sum, row) => sum + row.popularity, 0) / recommendations.length
        : null,
    };
  }

  const overlaps = [
    ["A", "B", "seed user only"],
    ["A", "C", "alpha only"],
    ["B", "C", "both user and alpha differ"],
  ].map(([left, right, comparison]) => {
    const rightIds = new Set(lists[right].recommendations.map((row) => row.movieId));
    const common = lists[left].recommendations.filter((row) => rightIds.has(row.movieId))
      .map((row) => ({ movieId: row.movieId, title: row.title }));
    return { left, right, comparison, commonCount: common.length, commonMovies: common };
  });

  const likedInTrain = {};
  for (const userId of [1, 2]) {
    likedInTrain[userId] = vm.runInContext(`HW6_SPLIT.train
      .filter((row) => row.userId === ${userId} && row.rating >= 4)
      .sort((a, b) => a.timestamp - b.timestamp || a.movieId - b.movieId)
      .map((row) => ({ movieId: row.movieId, title: hw6Title(row.movieId), genres: hw6Genres(row.movieId),
        rating: row.rating, timestamp: row.timestamp }))`, context);
  }

  const report = {
    backend: tf.getBackend(),
    alphaSettings: "A=(user 1, 0.85), B=(user 2, 0.85), C=(user 1, 0.50)",
    candidates: "all movie IDs observed in train; test excludes train- and validation-rated movies",
    scoring: "PPR walk probability; not a rating or purchase probability",
    lists,
    overlaps,
    likedInTrain,
  };
  fs.writeFileSync(path.join(resultsDir, "two-user-demo.json"), JSON.stringify(report, null, 2) + "\n");

  const recRows = [["setting", "userId", "alpha", "rank", "movieId", "title", "genres", "pprScore", "trainPopularity"]];
  for (const setting of settings) {
    lists[setting.key].recommendations.forEach((row, index) => recRows.push([
      setting.key, setting.userId, setting.alpha, index + 1, row.movieId, row.title,
      row.genres.join(";"), row.score, row.popularity,
    ]));
  }
  fs.writeFileSync(path.join(resultsDir, "two-user-demo-recommendations.csv"),
    recRows.map((row) => row.map(csvField).join(",")).join("\r\n") + "\r\n");

  const likedRows = [["userId", "movieId", "title", "genres", "trainRating", "timestamp"]];
  for (const userId of [1, 2]) {
    for (const row of likedInTrain[userId]) {
      likedRows.push([userId, row.movieId, row.title, row.genres.join(";"), row.rating, row.timestamp]);
    }
  }
  fs.writeFileSync(path.join(resultsDir, "users-1-2-train-positive.csv"),
    likedRows.map((row) => row.map(csvField).join(",")).join("\r\n") + "\r\n");

  console.log(JSON.stringify({
    backend: report.backend,
    settings: Object.fromEntries(Object.entries(lists).map(([key, row]) => [key, {
      userId: row.userId,
      alpha: row.alpha,
      iterations: row.iterations,
      converged: row.converged,
      meanPopularity: row.meanPopularity,
      top10: row.recommendations,
    }])),
    overlaps,
    trainPositiveCounts: Object.fromEntries(Object.entries(likedInTrain).map(([userId, rows]) => [userId, rows.length])),
  }, null, 2));
}

main().catch((error) => {
  console.error(error && error.stack ? error.stack : error);
  process.exitCode = 1;
});
