// Generated with an AI assistant
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const tf = require("@tensorflow/tfjs");
require("@tensorflow/tfjs-backend-wasm");

async function main() {
  await tf.setBackend("wasm");
  await tf.ready();
  const root = path.resolve(__dirname, "..");
  const fixed = path.join(root, "fixed");
  const context = vm.createContext({
    console,
    document: { getElementById: () => null },
    window: {},
    tf,
  });
  vm.runInContext(fs.readFileSync(path.join(fixed, "data.js"), "utf8"), context);
  vm.runInContext(fs.readFileSync(path.join(fixed, "script.js"), "utf8"), context);
  const result = vm.runInContext("runTests()", context);
  for (const check of result.checks) {
    console.log(`${check.status.padEnd(7)} ${check.name}${check.detail ? ` — ${check.detail}` : ""}`);
  }
  console.log(`Tests: ${result.passed} passed / ${result.failed} failed / ${result.pending} pending`);
  if (result.passed !== 11 || result.failed !== 0 || result.pending !== 0) process.exitCode = 1;

  const deterministic = vm.runInContext(`(() => {
    movies = TOY_MOVIES;
    numUsers = 2;
    const opts = { epochs: 3, lr: 0.02, reg: 0.05, batchSize: 2, seed: 777 };
    initializeFactors(TOY_RATINGS, 4, 777);
    const firstHistory = trainMF(TOY_RATINGS, TOY_RATINGS, opts);
    const firstFactors = [Array.from(model.userFactors.dataSync()), Array.from(model.itemFactors.dataSync())];
    initializeFactors(TOY_RATINGS, 4, 777);
    const secondHistory = trainMF(TOY_RATINGS, TOY_RATINGS, opts);
    const secondFactors = [Array.from(model.userFactors.dataSync()), Array.from(model.itemFactors.dataSync())];
    return JSON.stringify(firstHistory) === JSON.stringify(secondHistory) &&
      JSON.stringify(firstFactors) === JSON.stringify(secondFactors);
  })()`, context);
  console.log(`Seed reproducibility: ${deterministic ? "PASS" : "FAIL"} (same seed gives identical toy history and factors)`);
  if (!deterministic) process.exitCode = 1;
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
