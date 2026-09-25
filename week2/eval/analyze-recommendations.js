// Generated with an AI assistant. Run from week2/: node eval/analyze-recommendations.js

const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const projectDir = path.resolve(__dirname, '..');
const fixedDir = path.join(projectDir, 'fixed');
const resultsDir = path.join(projectDir, 'results');
const outputPath = path.join(resultsDir, 'recommendation-analysis.md');
const context = vm.createContext({ console, window: {} });

const dataSource = fs.readFileSync(path.join(fixedDir, 'data.js'), 'utf8');
const scriptSource = fs.readFileSync(path.join(fixedDir, 'script.js'), 'utf8');
const itemText = fs.readFileSync(path.join(fixedDir, 'u.item'), 'utf8');
const ratingText = fs.readFileSync(path.join(fixedDir, 'u.data'), 'utf8');

vm.runInContext(dataSource, context, { filename: 'fixed/data.js' });
context.itemText = itemText;
context.ratingText = ratingText;
vm.runInContext('parseItemData(itemText); parseRatingData(ratingText)', context);
vm.runInContext(scriptSource, context, { filename: 'fixed/script.js' });

const genreNames = Array.from(vm.runInContext('genreNames', context));
const originalMovies = Array.from(vm.runInContext('movies', context));
const ratings = Array.from(vm.runInContext('ratings', context));
const enrichedMovies = Array.from(vm.runInContext(
    'movies.map(movie => ({ id: movie.id, title: movie.title, key: getMovieKey(movie), vector: movieToGenreVector(movie) }))',
    context
));

const movieById = new Map();
const recordsByKey = new Map();
for (let index = 0; index < enrichedMovies.length; index += 1) {
    const movie = { ...enrichedMovies[index], vector: Array.from(enrichedMovies[index].vector) };
    movie.original = originalMovies[index];
    movie.genreCount = movie.vector.reduce((sum, value) => sum + value, 0);
    movieById.set(movie.id, movie);
    if (!recordsByKey.has(movie.key)) recordsByKey.set(movie.key, []);
    recordsByKey.get(movie.key).push(movie);
}

const ratingCountsById = new Map();
const usersByTitle = new Map();
for (const rating of ratings) {
    ratingCountsById.set(rating.itemId, (ratingCountsById.get(rating.itemId) || 0) + 1);
    const movie = movieById.get(rating.itemId);
    if (!movie) continue;
    if (!usersByTitle.has(movie.key)) usersByTitle.set(movie.key, new Set());
    usersByTitle.get(movie.key).add(rating.userId);
}

const entities = [...recordsByKey.entries()].map(([key, records]) => {
    const representative = [...records].sort((a, b) =>
        (ratingCountsById.get(b.id) || 0) - (ratingCountsById.get(a.id) || 0) || a.id - b.id
    )[0];
    return {
        ...representative,
        popularity: usersByTitle.get(key)?.size || 0,
        sourceIds: records.map(record => record.id)
    };
});
const entityByKey = new Map(entities.map(entity => [entity.key, entity]));

function createProfile(selectedMovies) {
    const unique = [...new Map(selectedMovies.map(movie => [movie.key, movie])).values()];
    if (unique.length === 0) return genreNames.map(() => 0);
    return genreNames.map((_, index) =>
        unique.reduce((sum, movie) => sum + movie.vector[index], 0) / unique.length
    );
}

function dotProduct(first, second) {
    return first.reduce((sum, value, index) => sum + value * second[index], 0);
}

function cosineSimilarity(first, second) {
    const dot = dotProduct(first, second);
    const firstNorm = Math.sqrt(first.reduce((sum, value) => sum + value ** 2, 0));
    const secondNorm = Math.sqrt(second.reduce((sum, value) => sum + value ** 2, 0));
    return firstNorm * secondNorm === 0 ? 0 : dot / (firstNorm * secondNorm);
}

function rank(selectedMovies, metric, count = 5, tieBreak = 'popularity') {
    const uniqueSelected = [...new Map(selectedMovies.map(movie => [movie.key, movie])).values()];
    const selectedKeys = new Set(uniqueSelected.map(movie => movie.key));
    const profile = createProfile(uniqueSelected);

    return entities
        .filter(candidate => !selectedKeys.has(candidate.key))
        .map(candidate => ({
            ...candidate,
            score: metric === 'cosine'
                ? cosineSimilarity(profile, candidate.vector)
                : dotProduct(profile, candidate.vector)
        }))
        .sort((a, b) => {
            const difference = b.score - a.score;
            if (Math.abs(difference) > 1e-12) return difference;
            if (tieBreak === 'id') return a.id - b.id;
            return b.popularity - a.popularity ||
                a.title.localeCompare(b.title) ||
                a.id - b.id;
        })
        .slice(0, count);
}

function appRecommendations(selectedMovies, count = 5) {
    context.selectedMovies = selectedMovies.map(movie => movie.original);
    return Array.from(vm.runInContext('getTopRecommendations(selectedMovies, recommendationCount)',
        Object.assign(context, { recommendationCount: count })));
}

function assertMatchesApp(selectedMovies, independentlyRanked) {
    const appTop = appRecommendations(selectedMovies);
    if (appTop.length !== independentlyRanked.length || appTop.some((movie, index) =>
        movie.id !== independentlyRanked[index].id || Math.abs(movie.score - independentlyRanked[index].score) > 1e-12
    )) {
        throw new Error('Analysis cosine ranking does not match fixed/script.js.');
    }
}

function findEntity(title) {
    const movie = entities.find(candidate => candidate.title === title);
    if (!movie) throw new Error(`Could not find movie: ${title}`);
    return movie;
}

const toyStory = findEntity('Toy Story (1995)');
const starWars = findEntity('Star Wars (1977)');
const fargo = findEntity('Fargo (1996)');
const toyTop = rank([toyStory], 'cosine');
const profileSeeds = [toyStory, starWars, fargo];
const profileTop = rank(profileSeeds, 'cosine');
assertMatchesApp([toyStory], toyTop);
assertMatchesApp(profileSeeds, profileTop);

const toyKeys = new Set(toyTop.map(movie => movie.key));
const profileKeys = new Set(profileTop.map(movie => movie.key));
const overlap = [...toyKeys].filter(key => profileKeys.has(key)).length;

const singleItemQueries = entities
    .filter(movie => movie.genreCount > 0)
    .map(movie => [movie]);

// Use real users' three highest-rated distinct movies rated 4 or 5 as profile seeds.
const likedByUser = new Map();
for (const rating of ratings) {
    if (rating.rating < 4) continue;
    const movie = movieById.get(rating.itemId);
    if (!movie) continue;
    if (!likedByUser.has(rating.userId)) likedByUser.set(rating.userId, new Map());
    const likes = likedByUser.get(rating.userId);
    const previous = likes.get(movie.key);
    if (!previous || rating.rating > previous.rating) {
        likes.set(movie.key, { movie: entityByKey.get(movie.key), rating: rating.rating });
    }
}

const userQueries = [];
for (const [userId, likes] of likedByUser) {
    const topLiked = [...likes.values()].sort((a, b) =>
        b.rating - a.rating || a.movie.title.localeCompare(b.movie.title) || a.movie.id - b.movie.id
    ).slice(0, 3).map(entry => entry.movie);
    if (topLiked.length === 3) userQueries.push({ userId, single: [topLiked[0]], profile: topLiked });
}

function evaluate(queries, selection, metric, tieBreak = 'popularity') {
    const recommendations = [];
    for (const query of queries) recommendations.push(...rank(selection(query), metric, 5, tieBreak));

    const lowPopularityCutoff = thresholds.lowPopularity;
    const broadAndPopularCutoff = thresholds.popular;
    const uniqueKeys = new Set(recommendations.map(movie => movie.key));
    const longTailRecommendations = recommendations.filter(movie => movie.popularity <= lowPopularityCutoff);
    const longTailKeys = new Set(longTailRecommendations.map(movie => movie.key));

    return {
        queries: queries.length,
        slots: recommendations.length,
        meanGenres: mean(recommendations.map(movie => movie.genreCount)),
        broadGenreShare: share(recommendations, movie => movie.genreCount >= 5),
        meanRaters: mean(recommendations.map(movie => movie.popularity)),
        longTailSlots: longTailRecommendations.length,
        longTailShare: share(recommendations, movie => movie.popularity <= lowPopularityCutoff),
        broadPopularShare: share(recommendations, movie =>
            movie.genreCount >= 5 && movie.popularity >= broadAndPopularCutoff
        ),
        uniqueTitles: uniqueKeys.size,
        uniqueLongTailTitles: longTailKeys.size
    };
}

function mean(values) {
    return values.length === 0 ? 0 : values.reduce((sum, value) => sum + value, 0) / values.length;
}

function share(values, predicate) {
    return values.length === 0 ? 0 : values.filter(predicate).length / values.length;
}

function quantile(values, q) {
    const sorted = [...values].sort((a, b) => a - b);
    return sorted[Math.max(0, Math.ceil(q * sorted.length) - 1)];
}

const popularityValues = entities.map(movie => movie.popularity);
const thresholds = {
    lowPopularity: quantile(popularityValues, 0.25),
    popular: quantile(popularityValues, 0.80)
};
const catalogLongTailCount = entities.filter(movie => movie.popularity <= thresholds.lowPopularity).length;
const catalogLongTailShare = catalogLongTailCount / entities.length;

const genreCountSummary = [...new Set(entities.map(movie => movie.genreCount))]
    .sort((a, b) => a - b)
    .map(genreCount => {
        const moviesInGroup = entities.filter(movie => movie.genreCount === genreCount);
        return {
            genreCount,
            movieCount: moviesInGroup.length,
            meanRaters: mean(moviesInGroup.map(movie => movie.popularity))
        };
    });

const allSingleCosine = evaluate(singleItemQueries, query => query, 'cosine');
const allSingleDot = evaluate(singleItemQueries, query => query, 'dot');
const userSingleCosine = evaluate(userQueries, query => query.single, 'cosine');
const userSingleDot = evaluate(userQueries, query => query.single, 'dot');
const userProfileCosine = evaluate(userQueries, query => query.profile, 'cosine');
const userProfileDot = evaluate(userQueries, query => query.profile, 'dot');
const userSingleIdTieBreak = evaluate(userQueries, query => query.single, 'cosine', 'id');
const userProfileIdTieBreak = evaluate(userQueries, query => query.profile, 'cosine', 'id');

const normalizationFinding = `Across all single-item queries, cosine recommended films with an average of ${formatNumber(allSingleCosine.meanGenres)} genres versus ${formatNumber(allSingleDot.meanGenres)} for dot product. Films with 5+ genres made up ${formatPercent(allSingleCosine.broadGenreShare)} versus ${formatPercent(allSingleDot.broadGenreShare)}; multi-genre popular films made up ${formatPercent(allSingleCosine.broadPopularShare)} versus ${formatPercent(allSingleDot.broadPopularShare)}. The same pattern appears for real-user profiles (${formatNumber(userProfileCosine.meanGenres)} versus ${formatNumber(userProfileDot.meanGenres)} genres; ${formatPercent(userProfileCosine.broadPopularShare)} versus ${formatPercent(userProfileDot.broadPopularShare)} multi-genre popular films). On this dataset, cosine normalization reduces the advantage of movies with many genres; popularity itself is not normalized by cosine.`;
const longTailFinding = `Across ${userQueries.length} paired user queries, three-movie profiles returned Long-tail films in ${formatPercent(userProfileCosine.longTailShare)} of recommendation slots versus ${formatPercent(userSingleCosine.longTailShare)} for item-to-item. They covered ${userProfileCosine.uniqueLongTailTitles} unique Long-tail films versus ${userSingleCosine.uniqueLongTailTitles}. In this sample, profiles surfaced more and a wider range of lesser-known films, although the absolute shares remained low. The popularity tie-break works the same way for both approaches and favors better-known movies when cosine scores tie.`;
const singleTailTieEffect = userSingleIdTieBreak.longTailSlots - userSingleCosine.longTailSlots;
const profileTailTieEffect = userProfileIdTieBreak.longTailSlots - userProfileCosine.longTailSlots;
function tieBreakEffectText(effect, label) {
    if (effect > 0) return `reduces Long-tail slots for ${label} by ${effect}`;
    if (effect < 0) return `adds ${Math.abs(effect)} Long-tail slots for ${label}`;
    return `does not change the number of Long-tail slots for ${label}`;
}
const tieBreakFinding = `On the same ${userQueries.length} queries, sorting tied scores by ascending ID gives ${userSingleIdTieBreak.longTailSlots}/${userSingleIdTieBreak.slots} Long-tail slots (${formatPercent(userSingleIdTieBreak.longTailShare)}) for item-to-item and ${userProfileIdTieBreak.longTailSlots}/${userProfileIdTieBreak.slots} (${formatPercent(userProfileIdTieBreak.longTailShare)}) for profiles. The current popularity rule changes these to ${userSingleCosine.longTailSlots}/${userSingleCosine.slots} (${formatPercent(userSingleCosine.longTailShare)}) and ${userProfileCosine.longTailSlots}/${userProfileCosine.slots} (${formatPercent(userProfileCosine.longTailShare)}). Compared with the ID tie-break, the popularity rule ${tieBreakEffectText(singleTailTieEffect, 'item-to-item')} and ${tieBreakEffectText(profileTailTieEffect, 'profiles')}. This isolates the tie-break effect while keeping cosine, Top-5, and deduplication unchanged.`;

function formatNumber(value, digits = 2) {
    return value.toFixed(digits);
}

function formatPercent(value) {
    return `${(value * 100).toFixed(1)}%`;
}

function topTable(rows) {
    return [
        '| # | Movie | Cosine | Genres | Unique raters | Long tail? |',
        '|---:|---|---:|---:|---:|:---:|',
        ...rows.map((movie, index) =>
            `| ${index + 1} | ${movie.title} | ${formatNumber(movie.score, 6)} | ${movie.genreCount} | ${movie.popularity} | ${movie.popularity <= thresholds.lowPopularity ? 'yes' : 'no'} |`
        )
    ].join('\n');
}

function metricsTable(rows) {
    return [
        '| Query set and ranking | Queries | Recommendation slots | Mean genres | With 5+ genres | Mean unique raters | Long-tail slots | Multi-genre popular* | Unique titles / Long tail |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|',
        ...rows.map(([label, stats]) =>
            `| ${label} | ${stats.queries} | ${stats.slots} | ${formatNumber(stats.meanGenres)} | ${formatPercent(stats.broadGenreShare)} | ${formatNumber(stats.meanRaters, 1)} | ${formatPercent(stats.longTailShare)} | ${formatPercent(stats.broadPopularShare)} | ${stats.uniqueTitles} / ${stats.uniqueLongTailTitles} |`
        )
    ].join('\n');
}

function genreCountTable(rows) {
    return [
        '| Genres per movie | Movies | Mean unique raters per movie |',
        '|---:|---:|---:|',
        ...rows.map(row => `| ${row.genreCount} | ${row.movieCount} | ${formatNumber(row.meanRaters, 1)} |`)
    ].join('\n');
}

function longTailTieTable(rows) {
    return [
        '| Query type | Tie-break for equal scores | Long-tail slots / total slots | Long-tail share | Unique Long-tail movies |',
        '|---|---|---:|---:|---:|',
        ...rows.map(([label, stats]) =>
            `| ${label} | ${stats.tieBreak} | ${stats.longTailSlots}/${stats.slots} | ${formatPercent(stats.longTailShare)} | ${stats.uniqueLongTailTitles} |`
        )
    ].join('\n');
}

const output = `# MovieLens 100K Recommendation Analysis

Generated from the data in \`fixed/\` by running \`node eval/analyze-recommendations.js\`.

## How to read the metrics

- **Item-to-item and profile** use the same cosine metric and tie-break rule. The single-item example is Toy Story; the example profile contains Toy Story, Star Wars, and Fargo.
- To test normalization, cosine is compared with the **raw dot product** on identical queries. For binary item-to-item vectors: \`cosine = shared genres / (√query genres × √candidate genres)\`; the dot product simply counts shared genres. For one query, its vector length is fixed while a candidate's vector length grows with its number of genres.
- “Multi-genre” means at least 5 genres. “Popular” means the catalog's top 20% by unique raters.
- “Long tail” means movies with no more unique raters than the catalog's lower-quartile threshold (**${thresholds.lowPopularity}**); this is ${catalogLongTailCount} of ${entities.length} movies (${formatPercent(catalogLongTailShare)}). Ties at the threshold can make the share slightly greater than 25%.
- The genre table groups movies by genre count; average raters are unique users averaged across unique movie titles.
- Long-tail share is measured across **Top-5 recommendation slots**: if a movie appears for multiple queries, it counts once per slot. The last column also shows the number of unique recommended Long-tail titles.
- Dot product is an analysis baseline, not another option in the app.
- Main comparisons break ties by unique rater count, then title and ID. The separate Long-tail test uses ascending ID to isolate the tie-break effect.

## Top-5: one movie and a three-movie profile

Single movie: **Toy Story (1995)**. Profile: **Toy Story (1995), Star Wars (1977), Fargo (1996)**. Shared titles between the Top-5 lists: **${overlap} of 5**.

### Item-to-item: Toy Story

${topTable(toyTop)}

### Profile: Toy Story + Star Wars + Fargo

${topTable(profileTop)}

## Genre count and catalog popularity

Each movie is counted once after duplicate titles are merged. Average raters is the mean number of unique raters per movie in each group.

${genreCountTable(genreCountSummary)}

## Does cosine normalization reduce the advantage of broad-genre movies?

The catalog-wide comparison uses all movies with at least one genre as item-to-item queries. We also use real users with at least three distinct movies rated 4 or 5: item-to-item uses their highest-rated movie, while the profile uses those same three movies. Each query returns a Top-5.

${metricsTable([
    ['All item-to-item queries — cosine', allSingleCosine],
    ['All item-to-item queries — dot product', allSingleDot],
    ['Users: one movie — cosine', userSingleCosine],
    ['Users: one movie — dot product', userSingleDot],
    ['Users: three-movie profile — cosine', userProfileCosine],
    ['Users: three-movie profile — dot product', userProfileDot]
])}

\* Recommendations with both 5+ genres and popularity in the catalog's top 20%.

Cosine does not exclude movies with many genres: with the same number of shared genres, a broader candidate has a larger denominator and a lower score. This normalizes genre-vector length, not popularity. The “multi-genre popular” column shows whether the combined share of broad-genre blockbusters changes. Popularity is not part of the cosine score, but the app uses it to break equal-score ties.

**Finding:** ${normalizationFinding}

## Which approach surfaces more Long-tail movies?

Item-to-item and profile results use the same user queries and cosine metric. Compare “Long-tail slots” and “Unique titles / Long tail” for **“Users: one movie — cosine”** and **“Users: three-movie profile — cosine.”** More Long-tail slots means more frequent exposure; more unique Long-tail titles means a wider selection of lesser-known movies.

**Finding:** ${longTailFinding}

## How much does the popularity tie-break change Long-tail exposure?

The same user queries and cosine scores are used in both cases. Only the order of equal-scoring movies changes, keeping Top-5 and deduplication fixed to isolate the tie-break effect.

The comparison is between the current popularity rule and ascending ID (the original \`u.item\` row order).

${longTailTieTable([
    ['Item-to-item: one movie', { ...userSingleCosine, tieBreak: 'Popularity' }],
    ['Item-to-item: one movie', { ...userSingleIdTieBreak, tieBreak: 'Ascending ID' }],
    ['Profile: three movies', { ...userProfileCosine, tieBreak: 'Popularity' }],
    ['Profile: three movies', { ...userProfileIdTieBreak, tieBreak: 'Ascending ID' }]
])}

**Tie-break effect:** ${tieBreakFinding}
`;

fs.mkdirSync(resultsDir, { recursive: true });
fs.writeFileSync(outputPath, output, 'utf8');
console.log(`Analysis saved: ${path.relative(projectDir, outputPath)}`);
console.log(`Candidate movies after duplicate merging: ${entities.length}.`);
console.log(`Three-movie user profiles: ${userQueries.length}.`);
console.log(`Long-tail threshold: ${thresholds.lowPopularity} unique raters; popular threshold: ${thresholds.popular}.`);
console.log(`Overlap between the example Top-5 lists: ${overlap}.`);
