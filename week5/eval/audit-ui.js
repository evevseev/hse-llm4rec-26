// Generated with an AI assistant
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const fixed = path.join(root, "fixed");
const resultsDir = path.join(root, "results");
const ratings = fs.readFileSync(path.join(fixed, "u.data"), "ascii")
  .trimEnd()
  .split(/\r?\n/)
  .map((line) => {
    const [userId, movieId, rating, timestamp] = line.split("\t").map(Number);
    return { userId, movieId, rating, timestamp };
  });
const itemBytes = fs.readFileSync(path.join(fixed, "u.item"));
const decodedItems = new TextDecoder("windows-1252").decode(itemBytes);
const movies = decodedItems.trimEnd().split(/\r?\n/).map((line) => {
  const fields = line.split("|");
  return { id: Number(fields[0]), title: fields[1] };
});
const movieByTitle = new Map(movies.map((movie) => [movie.title, movie.id]));
const byUser = new Map();
for (const rating of ratings) {
  if (!byUser.has(rating.userId)) byUser.set(rating.userId, []);
  byUser.get(rating.userId).push(rating);
}
const train = [];
const validation = [];
const test = [];
for (const rows of byUser.values()) {
  const ordered = rows.slice().sort((a, b) => a.timestamp - b.timestamp || a.movieId - b.movieId);
  if (ordered.length < 5) continue;
  const nTrain = Math.floor(0.8 * ordered.length);
  const nVal = Math.floor(0.1 * ordered.length);
  train.push(...ordered.slice(0, nTrain));
  validation.push(...ordered.slice(nTrain, nTrain + nVal));
  test.push(...ordered.slice(nTrain + nVal));
}
const trainCounts = new Map();
for (const rating of train) trainCounts.set(rating.movieId, (trainCounts.get(rating.movieId) || 0) + 1);

const titleBuffer = itemBytes.toString("latin1").split(/\r?\n/)
  .find((line) => line.includes("Misérables, Les"));
const titleUtf8 = titleBuffer?.split("|")[1] || null;
const titleAfterUtf8Decode = titleBuffer ? Buffer.from(titleBuffer, "latin1").toString("utf8").split("|")[1] : null;
const targetMovieTitles = ["Bitter Moon (1992)", "Aparajito (1956)"];
const lowSupportMovies = targetMovieTitles.map((title) => {
  const movieId = movieByTitle.get(title);
  return { title, movieId, trainRatings: movieId ? trainCounts.get(movieId) || 0 : null };
});

const dataSource = fs.readFileSync(path.join(fixed, "data.js"), "utf8");
const scriptSource = fs.readFileSync(path.join(fixed, "script.js"), "utf8");
const datasetRenderer = scriptSource.slice(scriptSource.indexOf("function renderDatasetSummary"), scriptSource.indexOf("function renderSplitSummary"));
const pipeline = scriptSource.slice(scriptSource.indexOf("function runPipeline"), scriptSource.indexOf("function init()"));
const uiRenderer = scriptSource.slice(scriptSource.indexOf("function renderTopK"), scriptSource.indexOf("function renderRecall"));
const maxUserId = ratings.reduce((max, rating) => Math.max(max, rating.userId), 0);
const maxMovieId = movies.reduce((max, movie) => Math.max(max, movie.id), 0);
const possibleObservedCells = maxUserId * maxMovieId;
const uniqueRatedPairs = new Set(ratings.map((rating) => `${rating.userId}:${rating.movieId}`)).size;

const output = {
  data: {
    users: maxUserId,
    movies: movies.length,
    ratings: ratings.length,
    train: train.length,
    validation: validation.length,
    test: test.length,
    uniqueRatedPairs,
    validMatrixCells: possibleObservedCells,
    matrixDensity: uniqueRatedPairs / possibleObservedCells,
  },
  recommendations: {
    uiCallUsesDefaultSupport: uiRenderer.includes("recommendTopK(Number(userId), 10)"),
    functionHasDefaultN1: scriptSource.includes("function recommendTopK(userId, K = 10, minTrainRatings = 1)"),
    chosenN: 20,
    itemSupport: lowSupportMovies,
  },
  encoding: {
    rawTitleBytesHex: titleBuffer ? Buffer.from(titleBuffer, "latin1").toString("hex") : null,
    correctWindows1252Title: titleUtf8,
    displayAfterUtf8Decoding: titleAfterUtf8Decode,
    loadUsesResponseTextUtf8Default: dataSource.includes("moviesResponse.text()"),
  },
  uiMetrics: {
    datasetRendererMentionsDensity: /density|filled|sparsity/i.test(datasetRenderer),
    trainingPipelineComputesTestRMSE: pipeline.includes("computeRMSEFor(testSet)"),
    splitSummaryShowsTestBaseline: scriptSource.includes("computeBaselineRMSE(testSet)"),
  },
};

fs.mkdirSync(resultsDir, { recursive: true });
fs.writeFileSync(path.join(resultsDir, "browser-issues-before.json"), `${JSON.stringify(output, null, 2)}\n`);
const report = [
  "# Browser issue audit — before fixes",
  "",
  "## Real MovieLens split and N wiring",
  "",
  `- Dataset: ${ratings.length} ratings, ${maxUserId} users, ${movies.length} movies; split ${train.length} train / ${validation.length} validation / ${test.length} test.`,
  `- The browser renderer calls \`recommendTopK(user, 10)\` without the N argument; function default is N=1, although validation selected N=20.`,
  ...lowSupportMovies.map((movie) => `- ${movie.title} (movie ${movie.movieId}) has ${movie.trainRatings} train rating(s), so it passes N=1 but must be excluded at N=20.`),
  "",
  "## Real matrix occupancy",
  "",
  `- ${uniqueRatedPairs.toLocaleString("en-US")} observed user–movie cells / ${possibleObservedCells.toLocaleString("en-US")} valid cells (${(100 * uniqueRatedPairs / possibleObservedCells).toFixed(4)}%). The page's dataset renderer prints matrix dimensions but no occupancy ratio.`,
  "",
  "## Real title bytes and decoding",
  "",
  `- The raw u.item row contains a single-byte e9 in \`${titleUtf8}\`; decoding that byte sequence as UTF-8 produces \`${titleAfterUtf8Decode}\` with U+FFFD.`,
  "- `data.js` uses `Response.text()` (UTF-8 default), which explains the replacement diamond in the browser.",
  "",
  "## Test RMSE rendering",
  "",
  `- The split summary computes and shows baseline test RMSE: ${output.uiMetrics.splitSummaryShowsTestBaseline}.`,
  `- ` + "`runPipeline()`" + ` does not compute or render ` + "`computeRMSEFor(testSet)`" + ` after restoring the selected checkpoint: ${!output.uiMetrics.trainingPipelineComputesTestRMSE}.`,
  "",
].join("\n");
fs.writeFileSync(path.join(resultsDir, "browser-issues-before.md"), report);
console.log(report);
