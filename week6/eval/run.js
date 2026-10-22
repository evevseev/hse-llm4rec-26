// Generated with an AI assistant
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const os = require("node:os");
const util = require("node:util");
const { fork } = require("node:child_process");
if (typeof util.isNullOrUndefined !== "function") {
  util.isNullOrUndefined = (value) => value === null || value === undefined;
}
const tf = require("@tensorflow/tfjs");
require("@tensorflow/tfjs-node");
const wasmBackend = require("@tensorflow/tfjs-backend-wasm");

const root = path.resolve(__dirname, "..");
const fixed = path.join(root, "fixed");
const resultsDir = path.join(root, "results");
fs.mkdirSync(resultsDir, { recursive: true });
const liveWorkers = new Set();
process.on("exit", () => {
  for (const worker of liveWorkers) worker.kill();
});

function writeJson(name, value) {
  fs.writeFileSync(path.join(resultsDir, name), JSON.stringify(value, null, 2) + "\n");
}

function makeElement(id) {
  return {
    id,
    value: id === "alpha" ? "0.85" : "",
    textContent: "",
    innerHTML: "",
    className: "",
    style: {},
    addEventListener() {},
  };
}

function elapsedMs(started) {
  return Number(process.hrtime.bigint() - started) / 1e6;
}

async function createWorkerPool(size) {
  const workers = [];
  for (let i = 0; i < size; i++) {
    const worker = fork(path.join(__dirname, "worker.js"), [], {
      env: { ...process.env, TFJS_THREADS: "1" },
      stdio: ["ignore", "ignore", "inherit", "ipc"],
      execArgv: [],
    });
    workers.push(worker);
    liveWorkers.add(worker);
    worker.once("exit", () => liveWorkers.delete(worker));
  }
  await Promise.all(workers.map((worker) => new Promise((resolve, reject) => {
    const onMessage = (message) => {
      if (message.type === "ready") {
        worker.off("message", onMessage);
        resolve();
      } else if (message.type === "fatal") {
        worker.off("message", onMessage);
        reject(new Error(message.error));
      }
    };
    worker.on("message", onMessage);
    worker.once("exit", (code) => {
      if (code !== 0) reject(new Error(`PPR worker exited during startup with code ${code}`));
    });
  })));
  return workers;
}

function sendWorkerTask(worker, task, id) {
  return new Promise((resolve, reject) => {
    const onMessage = (message) => {
      if (message.id !== id) return;
      worker.off("message", onMessage);
      if (message.type === "error") reject(new Error(message.error));
      else resolve(message.result);
    };
    worker.on("message", onMessage);
    worker.send({ id, task });
  });
}

async function parallelPprRecall(context, workers, split, alpha, verifyUsers) {
  const name = split === "val" ? "val" : "test";
  const cohort = Array.from(vm.runInContext(`hw6SharedCohort(${JSON.stringify(name)})`, context))
    .sort((a, b) => a - b);
  const shards = workers.map(() => []);
  cohort.forEach((userId, index) => shards[index % workers.length].push(userId));
  const owner = new Map();
  shards.forEach((ids, workerIndex) => ids.forEach((id) => owner.set(id, workerIndex)));
  for (const userId of verifyUsers || []) {
    if (!owner.has(userId)) {
      shards[0].push(userId);
      owner.set(userId, 0);
    }
  }

  const tasks = [];
  for (let i = 0; i < workers.length; i++) {
    if (!shards[i].length) continue;
    const verify = (verifyUsers || []).filter((userId) => owner.get(userId) === i);
    tasks.push(sendWorkerTask(workers[i], {
      split: name,
      alpha,
      userIds: shards[i],
      verifyUsers: verify,
    }, `${name}-${alpha}-${i}-${Date.now()}`));
  }
  const outputs = await Promise.all(tasks);
  const cohortSet = new Set(cohort);
  const perUser = outputs.flatMap((output) => output.rows).filter((row) => cohortSet.has(row.userId))
    .sort((a, b) => a.userId - b.userId);
  let recallSum = 0;
  for (const row of perUser) recallSum += row.relevant ? row.hit / row.relevant : 0;
  const exclusions = vm.runInContext(`hw6CohortExclusions(${JSON.stringify(name)})`, context);
  return {
    report: {
      recall: perUser.length ? recallSum / perUser.length : 0,
      cohort,
      excludedUnseen: exclusions.excludedUnseen,
      excludedNoEligible: exclusions.excludedNoEligible,
      perUser,
    },
    rows: outputs.flatMap((output) => output.rows),
  };
}

async function main() {
  const threads = Math.max(1, Math.floor(Number(process.env.TFJS_THREADS) || 1));
  wasmBackend.setThreadsCount(threads);
  await tf.setBackend("wasm");
  await tf.ready();

  const elements = new Map();
  const document = {
    readyState: "loading",
    getElementById(id) {
      if (id === "graph-view") return null;
      if (!elements.has(id)) elements.set(id, makeElement(id));
      return elements.get(id);
    },
    addEventListener() {},
  };
  const context = vm.createContext({ console, document, tf, setTimeout });
  context.window = context;
  for (const filename of ["data.js", "graph.js", "script.js"]) {
    vm.runInContext(fs.readFileSync(path.join(fixed, filename), "utf8"), context, { filename });
  }

  const itemText = new TextDecoder("windows-1252").decode(fs.readFileSync(path.join(fixed, "u.item")));
  const ratingText = fs.readFileSync(path.join(fixed, "u.data"), "utf8");
  const split = await vm.runInContext(`(async () => {
    parseItemData(${JSON.stringify(itemText)});
    parseRatingData(${JSON.stringify(ratingText)});
    numUsers = ratings.reduce((max, row) => Math.max(max, row.userId), 0);
    numMovies = movies.length;
    buildRatingMatrix();
    const parts = splitByTimestamp();
    HW6_SPLIT.train = parts.train;
    HW6_SPLIT.val = parts.val;
    HW6_SPLIT.test = parts.test;
    HW6_MAX_MOVIE_ID = movies.reduce((max, movie) => Math.max(max, movie.id), 0);
    hw6BuildSplitIndices(HW6_SPLIT);
    const graph = buildGraph(parts.train);
    setGraph(graph);
    return { parts, graph, movieCount: movies.length, ratingCount: ratings.length };
  })()`, context);

  const selfChecks = vm.runInContext("runSelfChecks()", context);
  const verification = {
    backend: tf.getBackend(),
    passed: selfChecks.passed,
    failed: selfChecks.failed,
    pending: selfChecks.pending,
    checks: selfChecks.checks,
  };
  writeJson("verification.json", verification);
  console.log(`Self-checks: ${verification.passed} pass, ${verification.failed} fail, ${verification.pending} pending`);
  if (verification.failed || verification.pending) {
    throw new Error("Built-in self-checks did not all pass; see results/verification.json");
  }

  const graph = split.graph;
  const testCohortExclusions = vm.runInContext('hw6CohortExclusions("test")', context);
  const datasetSummary = {
    movieRecords: split.movieCount,
    ratingRecords: split.ratingCount,
    splitCounts: {
      train: split.parts.train.length,
      validation: split.parts.val.length,
      test: split.parts.test.length,
    },
    graph: {
      users: graph.nUsers,
      movies: graph.nMovies,
      nodes: graph.nodeCount,
      positiveEdges: graph.positiveEdges,
      directedAdjacencyEntries: graph.positiveEdges * 2,
      zeroDegreeUsers: graph.zeroDegreeUsers.length,
      zeroDegreeMovies: graph.zeroDegreeMovies.length,
    },
    backend: tf.getBackend(),
  };

  if (process.argv.includes("--smoke")) {
    const started = Date.now();
    const result = vm.runInContext("personalizedPageRank(getGraph().nodeOfUser(1), 0.85)", context);
    console.log(JSON.stringify({
      backend: tf.getBackend(),
      iterations: result.iterations,
      residual: result.residual,
      converged: result.converged,
      elapsedMs: Date.now() - started,
    }));
    return;
  }

  if (process.argv.includes("--mf-profile")) {
    await tf.setBackend("tensorflow");
    await tf.ready();
    vm.runInContext('HW6_STATE.backend = "tensorflow"; MF_INFO.backend = "tensorflow"', context);
    const started = process.hrtime.bigint();
    const model = await vm.runInContext("hw6EnsureMfForNeed()", context);
    const profile = {
      backend: tf.getBackend(),
      elapsedMs: elapsedMs(started),
      trained: !!model,
      checkpoint: vm.runInContext("MF_INFO.checkpoint", context),
      validationRMSE: vm.runInContext("MF_INFO.validationRMSE", context),
    };
    writeJson("mf-profile.json", profile);
    console.log(JSON.stringify(profile));
    if (!profile.trained) process.exitCode = 1;
    return;
  }

  if (process.argv.includes("--responsive-check")) {
    const synchronous = vm.runInContext('recallAtK("popularity", 10, "test")', context);
    const responsive = await vm.runInContext('hw6RecallAtKResponsive("popularity", 10, "test")', context);
    vm.runInContext(`
      HW6_STATE.selectedAlpha = 0.5;
      document.getElementById("alpha").value = "0.85";
      HW6_MF_MODEL = {};
      MF_INFO.trainedAt = "diagnostic";
      hw6RecallAtKResponsive = async function () {
        return { recall: 0, cohort: hw6SharedCohort("test"), excludedUnseen: 0,
          excludedNoEligible: 0, perUser: [], meanPopularity: 0 };
      };
    `, context);
    const comparison = await vm.runInContext('hw6RunComparison("test")', context);
    const response = {
      syncRecall: synchronous.recall,
      responsiveRecall: responsive.recall,
      sameCohort: JSON.stringify(synchronous.cohort) === JSON.stringify(responsive.cohort),
      samePerUserRecall: JSON.stringify(synchronous.perUser) === JSON.stringify(responsive.perUser),
      comparisonAlphaForPageRank: comparison.find((row) => row.method === "pagerank").alpha,
      comparisonAlphaForPpr: comparison.find((row) => row.method === "ppr").alpha,
      sliderAfterComparison: vm.runInContext('hw6ReadAlpha()', context),
    };
    console.log(JSON.stringify(response, null, 2));
    if (response.syncRecall !== response.responsiveRecall || !response.sameCohort ||
        !response.samePerUserRecall || response.comparisonAlphaForPpr !== 0.5 ||
        response.comparisonAlphaForPageRank !== 0.5) {
      throw new Error("Responsive retrieval or validation-alpha contract check failed");
    }
    return;
  }

  if (process.argv.includes("--profile")) {
    const alphas = [0.5, 0.7, 0.85, 0.95];
    const cohort = vm.runInContext('hw6SharedCohort("val")', context);
    const sampleUsers = Array.from(cohort).slice(0, 16);
    const perAlpha = [];
    for (const alpha of alphas) {
      let totalMs = 0;
      let totalIterations = 0;
      let converged = 0;
      for (const userId of sampleUsers) {
        const started = process.hrtime.bigint();
        const result = vm.runInContext(`personalizedPageRank(getGraph().nodeOfUser(${Number(userId)}), ${alpha})`, context);
        totalMs += Number(process.hrtime.bigint() - started) / 1e6;
        totalIterations += result.iterations;
        if (result.converged) converged++;
      }
      perAlpha.push({
        alpha,
        sampleUsers: sampleUsers.length,
        totalMs,
        meanMsPerUser: sampleUsers.length ? totalMs / sampleUsers.length : 0,
        meanIterations: sampleUsers.length ? totalIterations / sampleUsers.length : 0,
        converged,
        estimatedSweepSeconds: sampleUsers.length ? (totalMs / sampleUsers.length) * cohort.length / 1000 : 0,
      });
      console.log(`profile alpha=${alpha}: ${totalMs.toFixed(0)} ms for ${sampleUsers.length} users`);
    }
    const pagerankStart = process.hrtime.bigint();
    const global = vm.runInContext("pageRank(0.85)", context);
    const globalMs = Number(process.hrtime.bigint() - pagerankStart) / 1e6;
    const profile = {
      backend: tf.getBackend(),
      threads: wasmBackend.getThreadsCount(),
      logicalCpus: os.availableParallelism ? os.availableParallelism() : os.cpus().length,
      startupAndDataSetupMs: split.setupMs || null,
      validationCohortSize: cohort.length,
      sampleUsers: sampleUsers.length,
      perAlpha,
      globalPageRankMs: globalMs,
      globalPageRankIterations: global.iterations,
      timings: {
        alphaSweepEstimatedSeconds: perAlpha.reduce((sum, row) => sum + row.estimatedSweepSeconds, 0),
      },
    };
    writeJson("profile-single-thread.json", profile);
    console.log(`Estimated complete validation sweep: ${profile.timings.alphaSweepEstimatedSeconds.toFixed(1)} s`);
    return;
  }

  if (process.argv.includes("--worker-smoke")) {
    const alpha = 0.85;
    const cohort = Array.from(vm.runInContext('hw6SharedCohort("val")', context));
    const users = cohort.slice(0, 32);
    const baseline = new Map();
    const sequentialStarted = process.hrtime.bigint();
    for (const userId of users) {
      const recommendations = vm.runInContext(`recommendTopK("ppr", ${Number(userId)}, 10, "val")`, context);
      const propagation = vm.runInContext("HW6_STATE.ppr", context);
      baseline.set(userId, {
        scores: Array.from(propagation.scores),
        iterations: propagation.iterations,
        recommendations: recommendations.map((row) => row.movieId),
      });
    }
    const sequentialMs = elapsedMs(sequentialStarted);
    const poolStarted = process.hrtime.bigint();
    const workers = await createWorkerPool(Math.min(8, os.availableParallelism ? os.availableParallelism() : os.cpus().length));
    const workerStartupMs = elapsedMs(poolStarted);
    const shards = workers.map(() => []);
    users.forEach((userId, index) => shards[index % workers.length].push(userId));
    const parallelStarted = process.hrtime.bigint();
    const outputs = await Promise.all(shards.map((userIds, index) => userIds.length
      ? sendWorkerTask(workers[index], {
        split: "val", alpha, userIds, verifyUsers: userIds,
      }, `smoke-${index}-${Date.now()}`)
      : Promise.resolve({ rows: [] })));
    const parallelMs = elapsedMs(parallelStarted);
    const after = new Map(outputs.flatMap((output) => output.rows).map((row) => [row.userId, row]));
    const comparisons = users.map((userId) => {
      const before = baseline.get(userId);
      const result = after.get(userId);
      let maxAbsDiff = 0;
      for (let i = 0; i < before.scores.length; i++) {
        maxAbsDiff = Math.max(maxAbsDiff, Math.abs(before.scores[i] - result.scores[i]));
      }
      return {
        userId,
        iterationsMatch: before.iterations === result.iterations,
        maxAbsScoreDifference: maxAbsDiff,
        top10MovieIdsMatch: JSON.stringify(before.recommendations) ===
          JSON.stringify(result.recommendations.map((row) => row.movieId)),
      };
    });
    for (const worker of workers) worker.kill();
    const benchmark = {
      alpha,
      users: users.length,
      workers: workers.length,
      sequentialMs,
      parallelCalculationMs: parallelMs,
      workerStartupMs,
      speedup: sequentialMs / (workerStartupMs + parallelMs),
      allEquivalent: comparisons.every((row) => row.iterationsMatch && row.maxAbsScoreDifference === 0 && row.top10MovieIdsMatch),
      comparisons,
    };
    writeJson("worker-benchmark.json", benchmark);
    console.log(JSON.stringify({
      workers: benchmark.workers,
      users: benchmark.users,
      sequentialMs: Math.round(sequentialMs),
      parallelCalculationMs: Math.round(parallelMs),
      speedup: Number(benchmark.speedup.toFixed(2)),
      allEquivalent: benchmark.allEquivalent,
    }));
    return;
  }

  const workerCount = Math.max(1, Math.min(
    Number(process.env.HW6_WORKERS) || 8,
    os.availableParallelism ? os.availableParallelism() : os.cpus().length,
  ));
  const totalStarted = process.hrtime.bigint();
  console.log(`Starting ${workerCount} independent TF.js WASM workers for user-level PPR...`);
  const poolStarted = process.hrtime.bigint();
  const workers = await createWorkerPool(workerCount);
  const workerStartupMs = elapsedMs(poolStarted);
  const alphaTimings = [];
  const alphaRows = [];
  let best = null;
  let bestRecall = -Infinity;
  console.log("Selecting alpha on validation...");
  for (const alpha of [0.5, 0.7, 0.85, 0.95]) {
    const started = process.hrtime.bigint();
    const outcome = await parallelPprRecall(context, workers, "val", alpha, []);
    const row = {
      alpha,
      recall: outcome.report.recall,
      cohortSize: outcome.report.cohort.length,
      error: null,
    };
    alphaRows.push(row);
    alphaTimings.push({ alpha, elapsedMs: elapsedMs(started) });
    if (row.recall > bestRecall) {
      bestRecall = row.recall;
      best = alpha;
    }
    console.log(`  alpha=${alpha}: Recall@10=${row.recall.toFixed(6)} (${row.cohortSize} users)`);
  }
  const sweep = { rows: alphaRows, best, note: "Parallelized by user; each PPR walk uses the same fixed implementation and TF.js WASM backend." };
  writeJson("alpha-sweep.json", sweep);
  if (sweep.best === null) throw new Error("No alpha could be selected on validation");
  vm.runInContext(`hw6SetAlpha(${Number(sweep.best)})`, context);

  console.log(`Selected alpha=${sweep.best}; preparing baseline PPR checks...`);
  const testReports = {};
  const testTimings = {};
  let parallelTestPprRows = [];
  const verificationUsers = [1, 2, 3];
  const baseline = {};
  for (const userId of verificationUsers) {
    const recommendations = vm.runInContext(`recommendTopK("ppr", ${userId}, 10, "test")`, context);
    const propagation = vm.runInContext("HW6_STATE.ppr", context);
    baseline[userId] = {
      scores: Array.from(propagation.scores),
      iterations: propagation.iterations,
      residual: propagation.residual,
      converged: propagation.converged,
      recommendations,
    };
  }

  const convergenceStarted = process.hrtime.bigint();
  const globalConvergence = vm.runInContext(`pageRank(${Number(sweep.best)})`, context);
  const convergence = {
    globalPageRank: {
      iterations: globalConvergence.iterations,
      residual: globalConvergence.residual,
      converged: globalConvergence.converged,
    },
    pprUser1: { iterations: baseline[1].iterations, residual: baseline[1].residual, converged: baseline[1].converged },
    pprUser2: { iterations: baseline[2].iterations, residual: baseline[2].residual, converged: baseline[2].converged },
  };
  const convergenceMs = elapsedMs(convergenceStarted);

  for (const method of ["popularity", "pagerank", "ppr"]) {
    console.log(`  Recall@10: ${method}`);
    const started = process.hrtime.bigint();
    let report;
    if (method === "ppr") {
      const parallelResult = await parallelPprRecall(context, workers, "test", sweep.best, verificationUsers);
      report = parallelResult.report;
      parallelTestPprRows = parallelResult.rows;
    } else {
      report = vm.runInContext(`recallAtK(${JSON.stringify(method)}, 10, "test")`, context);
    }
    testTimings[method] = elapsedMs(started);
    testReports[method] = {
      recall: report.recall,
      cohortSize: report.cohort.length,
      candidateUsers: testCohortExclusions.candidateUsers,
      excludedNoPositiveEdge: testCohortExclusions.excludedNoPositiveEdge,
      excludedUnseen: report.excludedUnseen,
      excludedNoEligible: report.excludedNoEligible,
      perUser: report.perUser,
    };
  }
  writeJson("test-recall.json", { alpha: sweep.best, cohortExclusions: testCohortExclusions, methods: testReports });

  const speedEquivalence = verificationUsers.map((userId) => {
    const after = parallelTestPprRows.find((row) => row.userId === userId);
    const before = baseline[userId];
    if (!after) return { userId, availableInSharedTestCohort: false };
    let maxAbsDiff = 0;
    for (let i = 0; i < before.scores.length; i++) {
      maxAbsDiff = Math.max(maxAbsDiff, Math.abs(before.scores[i] - after.scores[i]));
    }
    const sameRankedIds = JSON.stringify(before.recommendations.map((rec) => rec.movieId)) ===
      JSON.stringify(after.recommendations.map((rec) => rec.movieId));
    return {
      userId,
      availableInSharedTestCohort: true,
      iterationsMatch: before.iterations === after.iterations,
      convergedMatch: before.converged === after.converged,
      maxAbsScoreDifference: maxAbsDiff,
      top10MovieIdsMatch: sameRankedIds,
    };
  });
  writeJson("speed-equivalence.json", {
    alpha: sweep.best,
    baseline: "single-process, single-thread TF.js WASM",
    accelerated: `${workerCount} independent Node processes, one TF.js WASM thread each`,
    comparisons: speedEquivalence,
  });

  console.log("Training provided MF model on the native TensorFlow.js backend...");
  await tf.setBackend("tensorflow");
  await tf.ready();
  vm.runInContext('HW6_STATE.backend = "tensorflow"; MF_INFO.backend = "tensorflow"', context);
  const mfStarted = process.hrtime.bigint();
  await vm.runInContext("hw6EnsureMfForNeed()", context);
  const mfTrainingMs = elapsedMs(mfStarted);
  const mfState = vm.runInContext("({ checkpoint: MF_INFO.checkpoint, validationRMSE: MF_INFO.validationRMSE, backend: MF_INFO.backend, trainedAt: MF_INFO.trainedAt })", context);
  if (mfState.checkpoint === null || mfState.trainedAt === null) {
    throw new Error("Provided MF reference did not train; refusing to report an invalid four-method comparison");
  }
  const mfStart = process.hrtime.bigint();
  const mfReport = vm.runInContext('recallAtK("mf", 10, "test")', context);
  testTimings.mf = elapsedMs(mfStart);
  testReports.mf = {
    recall: mfReport.recall,
    cohortSize: mfReport.cohort.length,
    candidateUsers: testCohortExclusions.candidateUsers,
    excludedNoPositiveEdge: testCohortExclusions.excludedNoPositiveEdge,
    excludedUnseen: mfReport.excludedUnseen,
    excludedNoEligible: mfReport.excludedNoEligible,
    perUser: mfReport.perUser,
  };
  writeJson("test-recall.json", { alpha: sweep.best, cohortExclusions: testCohortExclusions, methods: testReports });

  console.log("Building Top-10 lists for users 1 and 2...");
  const top10 = {};
  for (const userId of [1, 2]) {
    top10[userId] = {};
    for (const method of ["popularity", "pagerank", "ppr", "mf"]) {
      top10[userId][method] = method === "ppr"
        ? baseline[userId].recommendations
        : vm.runInContext(`recommendTopK(${JSON.stringify(method)}, ${userId}, 10, "test")`, context);
    }
  }
  writeJson("top10-users-1-2.json", { alpha: sweep.best, users: top10 });
  const csvField = (value) => {
    const text = value === null || value === undefined ? "" : String(value);
    return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  };
  const recommendationCsv = [["userId", "method", "alpha", "rank", "movieId", "title", "genres", "score", "trainingPopularity"]];
  for (const userId of [1, 2]) {
    for (const method of ["popularity", "pagerank", "ppr", "mf"]) {
      top10[userId][method].forEach((rec, index) => recommendationCsv.push([
        userId,
        method,
        method === "ppr" || method === "pagerank" ? sweep.best : "",
        index + 1,
        rec.movieId,
        rec.title,
        rec.genres.join(";"),
        rec.score,
        rec.popularity,
      ]));
    }
  }
  fs.writeFileSync(
    path.join(resultsDir, "recommendations.csv"),
    recommendationCsv.map((row) => row.map(csvField).join(",")).join("\r\n") + "\r\n",
  );
  const methodBackend = { popularity: "javascript", pagerank: "wasm", ppr: "wasm", mf: mfState.backend };
  const resultsCsv = [[
    "method", "split", "alpha", "selectedPprAlpha", "alphaSelection", "recallAt10", "candidateUsers",
    "cohortSize", "excludedNoPositiveEdge", "excludedUnseen", "excludedNoEligible", "mfCheckpoint",
    "mfValidationRMSE", "backend",
  ]];
  for (const method of ["popularity", "pagerank", "ppr", "mf"]) {
    const row = testReports[method];
    const usesAlpha = method === "pagerank" || method === "ppr";
    resultsCsv.push([
      method,
      "test",
      usesAlpha ? sweep.best : "",
      sweep.best,
      usesAlpha ? "validation Recall@10" : "",
      row.recall,
      row.candidateUsers,
      row.cohortSize,
      row.excludedNoPositiveEdge,
      row.excludedUnseen,
      row.excludedNoEligible,
      method === "mf" ? mfState.checkpoint : "",
      method === "mf" ? mfState.validationRMSE : "",
      methodBackend[method],
    ]);
  }
  fs.writeFileSync(
    path.join(resultsDir, "results.csv"),
    resultsCsv.map((row) => row.map(csvField).join(",")).join("\r\n") + "\r\n",
  );
  writeJson("convergence.json", { alpha: sweep.best, tolerance: 1e-6, maxIterations: 500, results: convergence });
  writeJson("run-summary.json", {
    dataset: datasetSummary,
    selectedAlpha: sweep.best,
    validationSweep: sweep.rows,
    testRecall: Object.fromEntries(Object.entries(testReports).map(([method, report]) => [method, {
      recall: report.recall,
      candidateUsers: report.candidateUsers,
      cohortSize: report.cohortSize,
      excludedNoPositiveEdge: report.excludedNoPositiveEdge,
      excludedUnseen: report.excludedUnseen,
      excludedNoEligible: report.excludedNoEligible,
    }])),
    convergence,
    mf: vm.runInContext("({ checkpoint: MF_INFO.checkpoint, validationRMSE: MF_INFO.validationRMSE, backend: MF_INFO.backend })", context),
  });
  writeJson("performance.json", {
    propagationBackend: "wasm",
    wasmThreadsPerProcess: wasmBackend.getThreadsCount(),
    mfBackend: tf.getBackend(),
    workers: workerCount,
    logicalCpus: os.availableParallelism ? os.availableParallelism() : os.cpus().length,
    workerStartupMs,
    alphaSweepMs: alphaTimings,
    alphaSweepTotalMs: alphaTimings.reduce((sum, row) => sum + row.elapsedMs, 0),
    convergenceMs,
    mfTrainingMs,
    testEvaluationMs: testTimings,
    totalMs: elapsedMs(totalStarted),
  });
  for (const worker of workers) worker.kill();
  console.log("Results written to week6/results/.");
}

main().catch((error) => {
  console.error(error && error.stack ? error.stack : error);
  process.exitCode = 1;
});
