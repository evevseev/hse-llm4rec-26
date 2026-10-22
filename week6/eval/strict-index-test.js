// Generated with an AI assistant
const fs = require("node:fs");
const path = require("node:path");
const os = require("node:os");
const { fork } = require("node:child_process");

const root = path.resolve(__dirname, "..");
const resultsDir = path.join(root, "results");
const appSummary = JSON.parse(fs.readFileSync(path.join(resultsDir, "run-summary.json"), "utf8"));
const alpha = appSummary.selectedAlpha;
const workerCount = Math.min(8, os.availableParallelism ? os.availableParallelism() : os.cpus().length);

function waitForReady(worker) {
  return new Promise((resolve, reject) => {
    const onMessage = (message) => {
      if (message.type === "ready") {
        worker.off("message", onMessage);
        resolve(message.cohort);
      } else if (message.type === "fatal") {
        worker.off("message", onMessage);
        reject(new Error(message.error));
      }
    };
    worker.on("message", onMessage);
  });
}

function dispatch(worker, userIds, id) {
  return new Promise((resolve, reject) => {
    const onMessage = (message) => {
      if (message.id !== id) return;
      worker.off("message", onMessage);
      if (message.type === "error") reject(new Error(message.error));
      else resolve(message.rows);
    };
    worker.on("message", onMessage);
    worker.send({ id, task: { userIds, alpha } });
  });
}

async function main() {
  const workers = Array.from({ length: workerCount }, () => fork(path.join(__dirname, "strict-index-worker.js"), [], {
    env: process.env,
    stdio: ["ignore", "ignore", "inherit", "ipc"],
    execArgv: [],
  }));
  try {
    const cohorts = await Promise.all(workers.map(waitForReady));
    const cohort = cohorts[0].slice().sort((a, b) => a - b);
    const shards = workers.map(() => []);
    cohort.forEach((userId, index) => shards[index % workers.length].push(userId));
    const rows = (await Promise.all(shards.map((ids, index) => dispatch(workers[index], ids, `strict-${index}`))))
      .flat()
      .sort((a, b) => a.userId - b.userId);
    const recall = rows.reduce((sum, row) => sum + (row.relevant ? row.hit / row.relevant : 0), 0) / rows.length;
    const strict = {
      interpretation: "raw MovieLens userId passed unchanged as a graph node index",
      alpha,
      cohortSize: rows.length,
      recallAt10: recall,
      appRecallAt10: appSummary.testRecall.ppr.recall,
      deltaVsApplication: recall - appSummary.testRecall.ppr.recall,
      examples: rows.filter((row) => [1, 2, 942, 943].includes(row.userId)),
    };
    fs.writeFileSync(path.join(resultsDir, "strict-node-index-test.json"), JSON.stringify(strict, null, 2) + "\n");
    console.log(JSON.stringify(strict, null, 2));
  } finally {
    for (const worker of workers) worker.kill();
  }
}

main().catch((error) => {
  console.error(error && error.stack ? error.stack : error);
  process.exitCode = 1;
});
