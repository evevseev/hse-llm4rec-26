// Generated with an AI assistant
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const tf = require("@tensorflow/tfjs");
require("@tensorflow/tfjs-backend-wasm");

const root = path.resolve(__dirname, "..");
const fixed = path.join(root, "fixed");
const messages = [];
let readyResolve;
let resultResolve;
const ready = new Promise((resolve) => { readyResolve = resolve; });
const result = new Promise((resolve) => { resultResolve = resolve; });

async function main() {
  await tf.setBackend("wasm");
  await tf.ready();
  // In a real Worker the backend resolves its .wasm URL relative to its CDN
  // bundle; Node already has the package-local wasm binary for this smoke test.
  if (tf.wasm && typeof tf.wasm.setWasmPaths === "function") tf.wasm.setWasmPaths = function () {};
  const document = { readyState: "loading", getElementById: () => null, addEventListener() {} };
  const context = vm.createContext({ console, document, tf, TextDecoder, setTimeout });
  context.self = context;
  context.postMessage = (message) => {
    messages.push(message);
    if (message.type === "ready") readyResolve(message);
    if (message.type === "result") resultResolve(message);
    if (message.type === "init-error" || message.type === "task-error") resultResolve(message);
  };
  context.fetch = async (name) => {
    const bytes = fs.readFileSync(path.join(fixed, name));
    return {
      ok: true,
      status: 200,
      arrayBuffer: async () => bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength),
      text: async () => bytes.toString("utf8"),
    };
  };
  context.importScripts = (...names) => {
    for (const name of names) {
      if (/^https?:/.test(name)) continue;
      vm.runInContext(fs.readFileSync(path.join(fixed, name), "utf8"), context, { filename: name });
    }
  };
  vm.runInContext(fs.readFileSync(path.join(fixed, "ppr-worker.js"), "utf8"), context, { filename: "ppr-worker.js" });
  const readyMessage = await ready;
  if (readyMessage.type !== "ready") throw new Error(readyMessage.error || "PPR worker did not become ready");

  const user = JSON.parse(vm.runInContext(`JSON.stringify((() => {
    const parts = splitByTimestamp();
    const graph = getGraph();
    const excluded = new Set();
    for (const name of ["train", "val"]) for (const row of parts[name]) {
      if (row.userId === 1) excluded.add(row.movieId);
    }
    const relevant = parts.test.filter((row) => row.userId === 1 && row.rating >= 4 &&
      graph.movieIndexOf.has(row.movieId) && !excluded.has(row.movieId)).map((row) => row.movieId);
    return { userId: 1, nodeIndex: graph.nodeOfUser(1), excludedMovieIds: [...excluded], relevantMovieIds: relevant };
  })())`, context));
  context.onmessage({ data: {
    type: "recall", requestId: "smoke", alpha: 0.5, k: 10, users: [user], debug: true,
  } });
  const taskResult = await result;
  if (taskResult.type !== "result") throw new Error(taskResult.error || "PPR worker task failed");

  const appTop10 = JSON.parse(fs.readFileSync(path.join(root, "results/top10-users-1-2.json"), "utf8"))
    .users["1"].ppr;
  const row = taskResult.rows[0];
  const appIds = appTop10.map((item) => item.movieId);
  const workerIds = row.top10.map((item) => item.movieId);
  let maxAbsScoreDifference = 0;
  for (let i = 0; i < appTop10.length; i++) {
    maxAbsScoreDifference = Math.max(maxAbsScoreDifference, Math.abs(appTop10[i].score - row.top10[i].score));
  }
  const report = {
    executionEnvironment: "Node VM worker shim; not a live browser run",
    backend: readyMessage.summary.backend,
    userId: row.userId,
    relevant: row.relevant,
    hit: row.hit,
    recall: row.hit / row.relevant,
    appRecall: JSON.parse(fs.readFileSync(path.join(root, "results/manual-ppr-user1.json"), "utf8"))
      .testRecallAt10.appRecall,
    top10MovieIdsMatch: JSON.stringify(workerIds) === JSON.stringify(appIds),
    maxAbsoluteScoreDifference: maxAbsScoreDifference,
    workerMessages: messages.length,
  };
  fs.writeFileSync(path.join(root, "results/browser-worker-smoke.json"), JSON.stringify(report, null, 2) + "\n");
  console.log(JSON.stringify(report, null, 2));
  if (row.relevant !== 19 || row.hit !== 3 || report.recall !== report.appRecall ||
      !report.top10MovieIdsMatch || maxAbsScoreDifference > 1e-6) {
    throw new Error("Browser-worker PPR smoke test differs from saved application results");
  }
}

main().catch((error) => {
  console.error(error && error.stack ? error.stack : error);
  process.exitCode = 1;
});
