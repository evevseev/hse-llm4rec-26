// Generated with an AI assistant. Benchmarks the requested thresholds and regenerates the rule tables and timing summaries.
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { performance } = require("node:perf_hooks");

const root = path.resolve(__dirname, "..");
const fixedDir = path.join(root, "fixed");
const resultsDir = path.join(root, "results");
fs.mkdirSync(resultsDir, { recursive: true });

const context = { window: {} };
vm.createContext(context);
for (const file of ["transactions.js", "script.js"]) {
  vm.runInContext(fs.readFileSync(path.join(fixedDir, file), "utf8"), context, {
    filename: file,
  });
}
context.datasetIndex = vm.runInContext("buildIndex(TRANSACTIONS)", context);

const output = [];
const say = (line = "") => {
  output.push(line);
  console.log(line);
};
const csvCell = (value) => `"${String(value).replace(/"/g, '""')}"`;
const writeCsv = (file, rows) => {
  const text = rows.map((row) => row.map(csvCell).join(",")).join("\n") + "\n";
  fs.writeFileSync(path.join(resultsDir, file), text);
};
const describe = (stock) => {
  const i = context.window.HW4.stocks.indexOf(stock);
  return `${stock} — ${context.window.HW4.descriptions[i]}`;
};
const countBySize = (itemsets) => {
  const counts = {};
  for (const itemset of itemsets) {
    counts[itemset.items.length] = (counts[itemset.items.length] || 0) + 1;
  }
  return counts;
};
const formatSizeCounts = (counts) =>
  Object.entries(counts)
    .sort(([a], [b]) => Number(a) - Number(b))
    .map(([size, count]) => `${size}-item: ${count}`)
    .join(", ");

function rulesAt(minConfidence) {
  context.minConfidenceForRun = minConfidence;
  const started = performance.now();
  const rules = vm.runInContext(
    "generateRules(currentItemsets, minConfidenceForRun).map((rule) => enrichRule(rule, datasetIndex))",
    context,
  );
  const liftRules = rules.filter((rule) => rule.liftDefined && rule.lift > 1);
  return { rules, liftRules, elapsedMs: performance.now() - started };
}

function tableRows(rules) {
  return [
    ["antecedent", "consequent", "count_A_union_B", "count_A", "count_B", "support", "confidence", "lift"],
    ...[...rules]
      .sort((a, b) => b.lift - a.lift || b.support - a.support)
      .map((rule) => [
        rule.antecedent.map(describe).join(" + "),
        rule.consequent.map(describe).join(" + "),
        rule.jointCount,
        rule.antecedentCount,
        rule.consequentCount,
        rule.support,
        rule.confidence,
        rule.lift,
      ]),
  ];
}

const configurations = [];
say("HW4 association-rule benchmark");
say(`Dataset: ${context.window.HW4.N_BASKETS.toLocaleString("en-US")} baskets; one Apriori run per minimum support.`);
say("Rule tables written below contain only rules with lift > 1 for analysis.");

for (const minSupport of [0.01, 0.02, 0.03]) {
  const miningStarted = performance.now();
  context.currentItemsets = vm.runInContext(
    `findFrequentItemsets(TRANSACTIONS, ${minSupport})`,
    context,
  );
  const miningMs = performance.now() - miningStarted;
  const itemsetsBySize = countBySize(context.currentItemsets);

  for (const minConfidence of [0.3, 0.6]) {
    const { rules, liftRules, elapsedMs } = rulesAt(minConfidence);
    const result = {
      minSupport,
      minConfidence,
      frequentItemsets: context.currentItemsets.length,
      itemsetsBySize,
      rulesBeforeLift: rules.length,
      liftGreaterThanOne: liftRules.length,
      removedByLift: rules.length - liftRules.length,
      miningMs,
      ruleAndLiftMs: elapsedMs,
      pipelineMs: miningMs + elapsedMs,
    };
    configurations.push(result);
    say(
      `Support ${minSupport * 100}% / confidence ${minConfidence * 100}%: ` +
        `${result.frequentItemsets} frequent itemsets (${formatSizeCounts(itemsetsBySize)}); ` +
        `${rules.length} rules, ${liftRules.length} with lift > 1, ${result.removedByLift} removed; ` +
        `${(result.pipelineMs / 1000).toFixed(3)} s total ` +
        `(${(miningMs / 1000).toFixed(3)} s mining, ${(elapsedMs / 1000).toFixed(3)} s rules/filter).`,
    );

    if (
      (minSupport === 0.01 && minConfidence === 0.3) ||
      (minSupport === 0.02 && minConfidence === 0.6)
    ) {
      const suffix = `${Math.round(minSupport * 100)}pct-support-${Math.round(minConfidence * 100)}pct-confidence`;
      writeCsv(`rules-${suffix}-lift-gt-1.csv`, tableRows(liftRules));
    }
  }
}

const softSupport = 0.005;
const softConfidence = 0.1;
say("Softest slider setting: support 0.5% / confidence 10%.");
const softMiningStarted = performance.now();
context.currentItemsets = vm.runInContext(
  `findFrequentItemsets(TRANSACTIONS, ${softSupport})`,
  context,
);
const softMiningMs = performance.now() - softMiningStarted;
const softRules = rulesAt(softConfidence);
const softResult = {
  minSupport: softSupport,
  minConfidence: softConfidence,
  frequentItemsets: context.currentItemsets.length,
  itemsetsBySize: countBySize(context.currentItemsets),
  rulesBeforeLift: softRules.rules.length,
  liftGreaterThanOne: softRules.liftRules.length,
  removedByLift: softRules.rules.length - softRules.liftRules.length,
  miningMs: softMiningMs,
  ruleAndLiftMs: softRules.elapsedMs,
  pipelineMs: softMiningMs + softRules.elapsedMs,
};
say(
  `Softest setting: ${softResult.frequentItemsets} frequent itemsets (${formatSizeCounts(softResult.itemsetsBySize)}); ` +
    `${softResult.rulesBeforeLift} rules, ${softResult.liftGreaterThanOne} with lift > 1, ` +
    `${softResult.removedByLift} removed; ${(softResult.pipelineMs / 1000).toFixed(3)} s computation.`,
);

vm.runInContext("primeDescriptions()", context);
context.softRulesForRender = softRules.rules;
context.renderTarget = { innerHTML: "", querySelectorAll: () => [] };
const renderStarted = performance.now();
vm.runInContext("renderResults(softRulesForRender, datasetIndex, renderTarget)", context);
const htmlBuildMs = performance.now() - renderStarted;
say(
  `Softest-setting HTML string: ${Buffer.byteLength(context.renderTarget.innerHTML).toLocaleString("en-US")} bytes for ` +
    `${softRules.rules.length.toLocaleString("en-US")} rule rows; string construction ${(htmlBuildMs / 1000).toFixed(3)} s. ` +
    "This does not include browser HTML parsing or event handling.",
);

const summaryHeader = [
  "support_percent",
  "confidence_percent",
  "frequent_itemsets",
  "itemsets_by_size_json",
  "rules_before_lift",
  "rules_lift_gt_1",
  "removed_by_lift",
  "mining_ms",
  "rules_and_lift_ms",
  "pipeline_ms",
];
const summaryRows = [
  summaryHeader,
  ...[...configurations, softResult].map((result) => [
    result.minSupport * 100,
    result.minConfidence * 100,
    result.frequentItemsets,
    JSON.stringify(result.itemsetsBySize),
    result.rulesBeforeLift,
    result.liftGreaterThanOne,
    result.removedByLift,
    result.miningMs.toFixed(2),
    result.ruleAndLiftMs.toFixed(2),
    result.pipelineMs.toFixed(2),
  ]),
];
writeCsv("benchmark-summary.csv", summaryRows);
fs.writeFileSync(path.join(resultsDir, "benchmark.txt"), output.join("\n") + "\n");
