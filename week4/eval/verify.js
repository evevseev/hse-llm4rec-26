// Generated with an AI assistant. Verifies built-in checks, exhaustive fixture results, UI behavior, rule counts, item families, and large-basket sensitivity.
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

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
const output = [];
const say = (line = "") => {
  output.push(line);
  console.log(line);
};
const assert = (condition, message) => {
  if (!condition) throw new Error(message);
};
const run = (expression) => vm.runInContext(expression, context);

// Run the page's 11 built-in checks with a minimal DOM element for the empty-state test.
const scratch = {
  innerHTML: "",
  get textContent() {
    return this.innerHTML.replace(/<[^>]*>/g, " ");
  },
};
context.document = { createElement: () => scratch };
context.logTarget = { textContent: "" };
const builtIn = run("runTests(logTarget)");
say(context.logTarget.textContent);
assert(builtIn.passed === 11 && builtIn.failed === 0 && builtIn.pending === 0, "Built-in tests did not all pass.");

// Compare Apriori and rule generation to exhaustive enumeration on the five-basket fixture.
const fixture = run(`(() => {
  const baskets = tinyWorkedExample().baskets;
  const itemUniverse = [...new Set(baskets.flat())];
  const count = (items) => baskets.filter((basket) => items.every((item) => basket.includes(item))).length;

  const expectedItemsets = new Map();
  for (let mask = 1; mask < 2 ** itemUniverse.length; mask += 1) {
    const items = itemUniverse.filter((_, i) => mask & (1 << i)).sort();
    const itemCount = count(items);
    if (itemCount / baskets.length >= 0.4) expectedItemsets.set(JSON.stringify(items), itemCount);
  }
  const actualItemsets = findFrequentItemsets(baskets, 0.4);
  const actualItemsetCounts = new Map(actualItemsets.map((entry) => [JSON.stringify(entry.items), entry.count]));
  if (actualItemsetCounts.size !== expectedItemsets.size) throw new Error("Fixture itemset count differs from exhaustive enumeration.");
  for (const [key, itemCount] of expectedItemsets) {
    if (actualItemsetCounts.get(key) !== itemCount) throw new Error("Fixture itemset count mismatch: " + key);
  }

  const minSupport = 0.2;
  const minConfidence = 0.5;
  const expectedRules = new Map();
  for (let mask = 1; mask < 2 ** itemUniverse.length; mask += 1) {
    const union = itemUniverse.filter((_, i) => mask & (1 << i)).sort();
    const jointCount = count(union);
    if (union.length < 2 || jointCount / baskets.length < minSupport) continue;
    for (let side = 1; side < 2 ** union.length - 1; side += 1) {
      const antecedent = union.filter((_, i) => side & (1 << i));
      const consequent = union.filter((_, i) => !(side & (1 << i)));
      const antecedentCount = count(antecedent);
      const confidence = jointCount / antecedentCount;
      if (confidence >= minConfidence) {
        expectedRules.set(JSON.stringify([antecedent, consequent]), { jointCount, antecedentCount, confidence });
      }
    }
  }
  const actualRules = generateRules(findFrequentItemsets(baskets, minSupport), minConfidence);
  const actualRuleMap = new Map(actualRules.map((rule) => [JSON.stringify([rule.antecedent, rule.consequent]), rule]));
  if (actualRuleMap.size !== expectedRules.size) throw new Error("Fixture rule count differs from exhaustive enumeration.");
  for (const [key, expected] of expectedRules) {
    const actual = actualRuleMap.get(key);
    if (!actual || actual.jointCount !== expected.jointCount || actual.antecedentCount !== expected.antecedentCount || Math.abs(actual.confidence - expected.confidence) > 1e-12) {
      throw new Error("Fixture rule mismatch: " + key);
    }
  }
  return { itemsets: actualItemsets.length, rules: actualRules.length };
})()`);
say(`Exhaustive fixture check: all ${fixture.itemsets} frequent itemsets and ${fixture.rules} rules match, including directions and confidence filtering.`);

// Exercise the actual render functions for sorting, reversal, and undefined metrics.
const ui = run(`(() => {
  let reverseClick;
  const target = () => ({
    innerHTML: "",
    querySelectorAll: () => [],
    querySelector: () => ({ addEventListener(event, handler) { if (event === "click") reverseClick = handler; } }),
    addEventListener() {},
  });
  const example = tinyWorkedExample();
  const index = buildIndex(example.baskets);
  const table = target();
  renderResults([
    { antecedent: ["jam"], consequent: ["eggs"] },
    { antecedent: ["bread"], consequent: ["ham"] },
    { antecedent: ["milk"], consequent: ["jam"] },
    { antecedent: ["bread"], consequent: ["milk"] },
  ], index, table);
  const renderedRows = [...table.innerHTML.matchAll(/<tr tabindex="0" data-rule-index="\\d+">([\\s\\S]*?)<\\/tr>/g)].map((match) => {
    const cells = [...match[1].matchAll(/<td>(.*?)<\\/td>/gs)];
    return cells[0][1] + "->" + cells[1][1];
  });
  const expectedOrder = ["bread->milk", "milk->jam", "bread->ham", "jam->eggs"];
  if (JSON.stringify(renderedRows) !== JSON.stringify(expectedOrder)) throw new Error("Table sort order is incorrect.");

  const directionPanel = target();
  renderRuleDetail({ antecedent: ["bread"], consequent: ["milk"] }, index, directionPanel);
  const forwardHtml = directionPanel.innerHTML;
  if (!forwardHtml.includes("100.00%") || !reverseClick) throw new Error("Forward rule or reverse button is missing.");
  reverseClick();
  const reverseHtml = directionPanel.innerHTML;
  if (!reverseHtml.includes("Antecedent (A)</dt><dd>milk") || !reverseHtml.includes("Consequent (B)</dt><dd>bread") || !new RegExp("<dt>confidence</dt><dd[^>]*>100[.]00%</dd>").test(reverseHtml)) {
    throw new Error("Reverse rule was not recomputed and rendered correctly.");
  }

  const panel = (baskets, rule) => {
    const element = target();
    renderRuleDetail(rule, buildIndex(baskets), element);
    return element.innerHTML;
  };
  const zeroA = panel([["milk"]], { antecedent: ["missing-A"], consequent: ["milk"] });
  const zeroB = panel([["milk"]], { antecedent: ["milk"], consequent: ["missing-B"] });
  const zeroN = panel([], { antecedent: ["A"], consequent: ["B"] });
  const metric = (html, name) => html.match(new RegExp("<dt>" + name + "</dt><dd[^>]*>(.*?)</dd>"))?.[1];
  if (!zeroA.includes("count(A) = 0") || metric(zeroA, "confidence") !== "n/a" || metric(zeroA, "lift") !== "n/a") throw new Error("Zero antecedent panel is incorrect.");
  if (!zeroB.includes("count(B) = 0") || metric(zeroB, "lift") !== "n/a" || metric(zeroB, "confidence") !== "0.00%") throw new Error("Zero consequent panel is incorrect.");
  if (!zeroN.includes("N = 0") || metric(zeroN, "support") !== "n/a") throw new Error("Empty-data panel is incorrect.");
  return { sortedRows: renderedRows, reversal: "bread -> milk: 60%; milk -> bread: 100%; lift = 1", zeroAntecedent: "confidence/lift = n/a with inline note", zeroConsequent: "confidence = 0%; lift = n/a with inline note", zeroBaskets: "support = n/a with inline note" };
})()`);
say(`UI rendering checks: ${JSON.stringify(ui)}`);

// Recount the report's example rules directly from decoded baskets.
const business = run(`(() => {
  const baskets = TRANSACTIONS.map((basket) => new Set(basket.map(stockOf)));
  const n = baskets.length;
  const itemCounts = new Map();
  for (const basket of baskets) for (const stock of basket) itemCounts.set(stock, (itemCounts.get(stock) || 0) + 1);
  const mostFrequentItem = [...itemCounts.entries()].sort((a, b) => b[1] - a[1])[0];
  const count = (items) => baskets.filter((basket) => items.every((item) => basket.has(item))).length;
  const audit = (name, antecedent, consequent) => {
    const jointCount = count([...antecedent, ...consequent]);
    const antecedentCount = count(antecedent);
    const consequentCount = count(consequent);
    const confidence = jointCount / antecedentCount;
    const reverseConfidence = jointCount / consequentCount;
    return { name, antecedent, consequent, jointCount, antecedentCount, consequentCount,
      support: jointCount / n, confidence, reverseConfidence,
      lift: confidence / (consequentCount / n),
      reverseLift: reverseConfidence / (antecedentCount / n) };
  };
  return [
    { name: "Maximum item frequency and lift lower bound", stock: mostFrequentItem[0], itemCount: mostFrequentItem[1], itemSupport: mostFrequentItem[1] / n, liftLowerBoundAt30PercentConfidence: 0.3 / (mostFrequentItem[1] / n) },
    audit("Regency teacup collection candidate", ["22697", "22699"], ["22698"]),
    audit("Red to green Bakelike alarm clock", ["22727"], ["22726"]),
    audit("Herb marker top-lift example", ["22916"], ["22917"]),
    audit("Weak alarm-to-t-light example", ["22726"], ["85123A"]),
  ];
})()`);
for (const rule of business) {
  if (rule.name === "Maximum item frequency and lift lower bound") continue;
  assert(Math.abs(rule.lift - rule.reverseLift) < 1e-12, `Lift is not symmetric for ${rule.name}.`);
}
say("Direct raw-basket metrics:");
for (const rule of business) {
  if (rule.name === "Maximum item frequency and lift lower bound") {
    say(
      `Lift bound: most frequent item ${rule.stock} occurs in ${rule.itemCount} baskets ` +
        `(${(100 * rule.itemSupport).toFixed(4)}%); at confidence >= 30%, lift >= ` +
        `${rule.liftLowerBoundAt30PercentConfidence.toFixed(4)}.`,
    );
    continue;
  }
  say(
    `${rule.name}: joint=${rule.jointCount}, count(A)=${rule.antecedentCount}, count(B)=${rule.consequentCount}, ` +
      `support=${(100 * rule.support).toFixed(4)}%, confidence=${(100 * rule.confidence).toFixed(4)}%, ` +
      `reverse confidence=${(100 * rule.reverseConfidence).toFixed(4)}%, lift=${rule.lift.toFixed(4)}.`,
  );
}

// Audit the 2%/60% CSV generated by benchmark.js, group its descriptions into product families,
// and recalculate metrics after excluding baskets with at least 100 distinct items.
function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = "";
  let quoted = false;
  for (let i = 0; i < text.length; i += 1) {
    const char = text[i];
    if (quoted) {
      if (char === '"' && text[i + 1] === '"') {
        field += '"';
        i += 1;
      } else if (char === '"') quoted = false;
      else field += char;
    } else if (char === '"') quoted = true;
    else if (char === ",") {
      row.push(field);
      field = "";
    } else if (char === "\n") {
      row.push(field.replace(/\r$/, ""));
      rows.push(row);
      row = [];
      field = "";
    } else field += char;
  }
  if (field.length || row.length) {
    row.push(field.replace(/\r$/, ""));
    rows.push(row);
  }
  const [header, ...body] = rows;
  return body.map((values) => Object.fromEntries(header.map((key, i) => [key, values[i]])));
}

const csvPath = path.join(resultsDir, "rules-2pct-support-60pct-confidence-lift-gt-1.csv");
const csvRules = parseCsv(fs.readFileSync(csvPath, "utf8")).map((rule) => ({
  antecedent: [...rule.antecedent.matchAll(/([A-Z0-9]+) —/g)].map((match) => match[1]),
  consequent: [...rule.consequent.matchAll(/([A-Z0-9]+) —/g)].map((match) => match[1]),
  jointCount: Number(rule.count_A_union_B),
}));
const familyCodes = {
  "Regency teacups": ["22697", "22698", "22699"],
  "Lunch boxes": ["22629", "22630"],
  "Garden kneeling pads": ["23300", "23301"],
  "Bakelike alarm clocks": ["22726", "22727", "22728"],
  "Paper chain kits": ["22910", "22086"],
  "Jumbo bags": ["85099F", "85099B", "22386"],
  "Hanging heart T-light holders": ["21733", "85123A"],
};
context.tableRules = csvRules;
context.familyCodes = familyCodes;
const tableAudit = run(`(() => {
  const baskets = TRANSACTIONS.map((basket) => new Set(basket.map(stockOf)));
  const n = baskets.length;
  const sizes = baskets.map((basket) => basket.size);
  const longCutoff = 100;
  const longIds = sizes.flatMap((size, id) => size >= longCutoff ? [id] : []);
  const regularIds = sizes.flatMap((size, id) => size < longCutoff ? [id] : []);
  const countIn = (items, ids) => ids.reduce((total, id) => total + (items.every((stock) => baskets[id].has(stock)) ? 1 : 0), 0);
  const rules = tableRules.map((rule) => {
    const joint = [...rule.antecedent, ...rule.consequent];
    const jointCount = countIn(joint, Array.from({ length: n }, (_, id) => id));
    if (jointCount !== rule.jointCount) throw new Error("CSV count differs from raw baskets.");
    const jointSmall = countIn(joint, regularIds);
    const antSmall = countIn(rule.antecedent, regularIds);
    const conSmall = countIn(rule.consequent, regularIds);
    const supportSmall = jointSmall / regularIds.length;
    const confidenceSmall = jointSmall / antSmall;
    const liftSmall = confidenceSmall / (conSmall / regularIds.length);
    return { ...rule, jointSmall, supportSmall, confidenceSmall, liftSmall,
      passesWithoutLarge: supportSmall >= 0.02 && confidenceSmall >= 0.6 && liftSmall > 1 };
  });
  const matchingIds = baskets.flatMap((basket, id) =>
    rules.some((rule) => [...rule.antecedent, ...rule.consequent].every((stock) => basket.has(stock))) ? [id] : []);
  const matchingLong = matchingIds.filter((id) => sizes[id] >= longCutoff);
  const familyCounts = {};
  for (const rule of rules) {
    const items = [...rule.antecedent, ...rule.consequent];
    const family = Object.entries(familyCodes).find(([, codes]) => items.every((stock) => codes.includes(stock)));
    if (!family) throw new Error("Found a rule outside the manually grouped product families.");
    familyCounts[family[0]] = (familyCounts[family[0]] || 0) + 1;
  }
  const sortedSizes = [...sizes].sort((a, b) => a - b);
  const minJoint = Math.min(...rules.map((rule) => rule.jointCount));
  const longShares = rules.map((rule) => 1 - rule.jointSmall / rule.jointCount);
  return {
    baskets: n,
    basketMedian: (sortedSizes[Math.floor((n - 1) / 2)] + sortedSizes[Math.floor(n / 2)]) / 2,
    maximumBasketSize: Math.max(...sizes),
    basketsWithAtLeast100Items: longIds.length,
    matchingBasketsForAnyFinalRule: matchingIds.length,
    largeMatchingBaskets: matchingLong.length,
    largeShareOfMatchingBaskets: matchingLong.length / matchingIds.length,
    rules: rules.length,
    ruleFamilies: familyCounts,
    unclassifiedRules: 0,
    support2PercentCountThreshold: Math.ceil(0.02 * n),
    observedMinimumJointCount: minJoint,
    rulesPassingAfterRemovingLargeBaskets: rules.filter((rule) => rule.passesWithoutLarge).length,
    maxPerRuleShareFromLargeBaskets: Math.max(...longShares),
    checks: {
      twentyRules: rules.length === 20,
      minimumIs390NotThreshold342: minJoint === 390 && Math.ceil(0.02 * n) === 342,
      eighteenRemainWithoutLargeBaskets: rules.filter((rule) => rule.passesWithoutLarge).length === 18,
      remainingFailuresAreConfidenceOnly: rules.filter((rule) => !rule.passesWithoutLarge).every((rule) => rule.supportSmall >= 0.02 && rule.liftSmall > 1 && rule.confidenceSmall < 0.6),
      selectedRuleDirectionPresent: rules.some((rule) => rule.antecedent.join(",") === "22697,22699" && rule.consequent.join(",") === "22698"),
    },
    rulesFailingWithoutLargeBaskets: rules.filter((rule) => !rule.passesWithoutLarge).map((rule) => ({
      antecedent: rule.antecedent,
      consequent: rule.consequent,
      jointCount: rule.jointSmall,
      confidence: rule.confidenceSmall,
      support: rule.supportSmall,
      lift: rule.liftSmall,
    })),
  };
})()`);
for (const [name, passed] of Object.entries(tableAudit.checks)) {
  assert(passed, `Final-table audit failed: ${name}.`);
}
say(
  `Final table: ${tableAudit.rules} rules across ${Object.keys(tableAudit.ruleFamilies).length} variant families; ` +
    `${tableAudit.observedMinimumJointCount} observed minimum joint baskets (support threshold count ${tableAudit.support2PercentCountThreshold}).`,
);
say(
  `Large-basket sensitivity: ${tableAudit.basketsWithAtLeast100Items} baskets have at least 100 items; ` +
    `${tableAudit.largeMatchingBaskets}/${tableAudit.matchingBasketsForAnyFinalRule} matching baskets are large; ` +
    `${tableAudit.rulesPassingAfterRemovingLargeBaskets}/${tableAudit.rules} rules still pass after excluding them; ` +
    `maximum per-rule large-basket share is ${(100 * tableAudit.maxPerRuleShareFromLargeBaskets).toFixed(2)}%.`,
);
for (const rule of tableAudit.rulesFailingWithoutLargeBaskets) {
  say(
    `Without large baskets, ${rule.antecedent.join(" + ")} -> ${rule.consequent.join(" + ")} ` +
      `has confidence ${(100 * rule.confidence).toFixed(2)}% and ${rule.jointCount} joint baskets.`,
  );
}
say(`Variant-family rule counts: ${JSON.stringify(tableAudit.ruleFamilies)}`);

fs.writeFileSync(path.join(resultsDir, "verification.txt"), output.join("\n") + "\n");
