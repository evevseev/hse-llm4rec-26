// User-independent PPR evaluation worker. Each task uses the same TensorFlow.js
// graph implementation as the page, but runs off the UI thread.
self.document = {
  readyState: "loading",
  getElementById() { return null; },
  addEventListener() {},
};

const TFJS_CDN = "https://cdn.jsdelivr.net/npm/@tensorflow/tfjs@4.22.0/dist/tf.min.js";
const WASM_CDN = "https://cdn.jsdelivr.net/npm/@tensorflow/tfjs-backend-wasm@4.22.0/dist/";
let graph = null;

async function initializePprWorker() {
  importScripts(TFJS_CDN, WASM_CDN + "tf-backend-wasm.min.js", "data.js", "graph.js");
  if (tf.wasm && typeof tf.wasm.setWasmPaths === "function") tf.wasm.setWasmPaths(WASM_CDN);
  await tf.setBackend("wasm");
  await tf.ready();

  const movieResponse = await fetch("u.item");
  if (!movieResponse.ok) throw new Error("Failed to load u.item in PPR worker: " + movieResponse.status);
  parseItemData(new TextDecoder("windows-1252").decode(await movieResponse.arrayBuffer()));

  const ratingResponse = await fetch("u.data");
  if (!ratingResponse.ok) throw new Error("Failed to load u.data in PPR worker: " + ratingResponse.status);
  parseRatingData(await ratingResponse.text());
  const split = splitByTimestamp();
  graph = setGraph(buildGraph(split.train));
  return { userCount: graph.nUsers, movieCount: graph.nMovies, backend: tf.getBackend() };
}

function evaluateUsers(task) {
  const perUser = [];
  const nUsers = graph.nUsers;

  for (let index = 0; index < task.users.length; index++) {
    const user = task.users[index];
    const result = personalizedPageRank(user.nodeIndex, task.alpha);
    const movieScores = movieScoresForUser(result.p);
    const excluded = new Set(user.excludedMovieIds);
    const relevant = new Set(user.relevantMovieIds);
    const ranked = [];

    for (let movieIndex = 0; movieIndex < graph.movieIds.length; movieIndex++) {
      const movieId = graph.movieIds[movieIndex];
      if (excluded.has(movieId)) continue;
      ranked.push({ movieId, score: Number(movieScores[movieIndex]) });
    }
    ranked.sort((a, b) => b.score - a.score || a.movieId - b.movieId);
    const top = ranked.slice(0, task.k || 10);
    let hit = 0;
    let popularityTotal = 0;
    for (const recommendation of top) {
      if (relevant.has(recommendation.movieId)) hit++;
      const localMovie = graph.movieIndexOf.get(recommendation.movieId);
      popularityTotal += Number(graph.degree[nUsers + localMovie]) || 0;
    }

    const row = {
      userId: user.userId,
      relevant: relevant.size,
      hit,
      meanPopularity: top.length ? popularityTotal / top.length : null,
      iterations: result.iterations,
      residual: result.residual,
      converged: result.converged,
    };
    if (task.debug) {
      row.top10 = top.map((item) => ({ movieId: item.movieId, score: item.score }));
    }
    perUser.push(row);
    self.postMessage({ type: "progress", requestId: task.requestId, done: index + 1, total: task.users.length });
  }
  return perUser;
}

function movieScoresForUser(p) {
  const scores = new Float64Array(graph.movieIds.length);
  for (let movieIndex = 0; movieIndex < graph.movieIds.length; movieIndex++) {
    scores[movieIndex] = Number(p[graph.nUsers + movieIndex]);
  }
  return scores;
}

initializePprWorker().then((summary) => {
  self.postMessage({ type: "ready", summary });
  self.onmessage = (event) => {
    const message = event.data || {};
    if (message.type !== "recall") return;
    try {
      const rows = evaluateUsers(message);
      self.postMessage({ type: "result", requestId: message.requestId, rows });
    } catch (error) {
      self.postMessage({
        type: "task-error",
        requestId: message.requestId,
        error: String(error && error.stack ? error.stack : error),
      });
    }
  };
}).catch((error) => {
  self.postMessage({ type: "init-error", error: String(error && error.stack ? error.stack : error) });
});
