// Generated with an AI assistant. Run from week2/: node eval/verify-cosine-recommendations.js

const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const fixedDir = path.resolve(__dirname, '..', 'fixed');
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

const movies = Array.from(vm.runInContext('movies', context));
function findMovie(title) {
    const movie = movies.find(candidate => candidate.title === title);
    if (!movie) throw new Error(`Movie not found: ${title}`);
    return movie;
}

const toyStory = findMovie('Toy Story (1995)');
const aladdin = findMovie('Aladdin (1992)');
context.firstMovie = toyStory;
context.secondMovie = aladdin;
const firstVector = vm.runInContext('movieToGenreVector(firstMovie)', context);
const secondVector = vm.runInContext('movieToGenreVector(secondMovie)', context);
context.firstVector = firstVector;
context.secondVector = secondVector;

const dotProduct = firstVector.reduce((sum, value, index) => sum + value * secondVector[index], 0);
const firstNormSquared = firstVector.reduce((sum, value) => sum + value ** 2, 0);
const secondNormSquared = secondVector.reduce((sum, value) => sum + value ** 2, 0);
const manualCosine = dotProduct / (Math.sqrt(firstNormSquared) * Math.sqrt(secondNormSquared));
const codeCosine = vm.runInContext('cosineSimilarity(firstVector, secondVector)', context);

console.log('Manual cosine check: Toy Story (1995) × Aladdin (1992)');
console.log(`Genres: ${firstNormSquared} and ${secondNormSquared}; shared genres: ${dotProduct}.`);
console.log(`cosine = ${dotProduct} / (√${firstNormSquared} × √${secondNormSquared}) = ${manualCosine.toFixed(6)}`);
console.log(`Value returned by cosineSimilarity: ${codeCosine.toFixed(6)}`);

if (Math.abs(manualCosine - codeCosine) > 1e-12) {
    throw new Error('Manual cosine calculation does not match cosineSimilarity().');
}

function getTop5(selectedMovies) {
    context.selectedMovies = selectedMovies;
    return Array.from(vm.runInContext('getTopRecommendations(selectedMovies, 5)', context));
}

function getMovieKey(movie) {
    context.movie = movie;
    return vm.runInContext('getMovieKey(movie)', context);
}

function printTop5(label, selectedMovies) {
    const top = getTop5(selectedMovies);
    const selectedKeys = new Set(selectedMovies.map(getMovieKey));
    const recommendationKeys = top.map(getMovieKey);

    if (new Set(recommendationKeys).size !== recommendationKeys.length || recommendationKeys.some(key => selectedKeys.has(key))) {
        throw new Error(`Duplicate or selected movie in recommendations for ${label}.`);
    }

    console.log(`\n${label}`);
    top.forEach((movie, index) => {
        console.log(`${index + 1}. ${movie.title} — cosine ${movie.score.toFixed(6)}, raters ${movie.popularity}`);
    });
}

printTop5('Top-5: one-movie profile — Toy Story', [toyStory]);
printTop5('Top-5: profile Toy Story + Star Wars + Fargo', [
    toyStory,
    findMovie('Star Wars (1977)'),
    findMovie('Fargo (1996)')
]);

const duplicateRecords = movies.filter(movie => movie.title === 'Desperate Measures (1998)');
if (duplicateRecords.length > 1) {
    const duplicateKey = getMovieKey(duplicateRecords[0]);
    const duplicateTop5 = getTop5([duplicateRecords[0]]);
    if (duplicateTop5.some(movie => getMovieKey(movie) === duplicateKey)) {
        throw new Error('A duplicate record of the selected movie was recommended.');
    }

    context.duplicateSelections = duplicateRecords;
    const oneMovieProfile = vm.runInContext('createUserProfile([duplicateSelections[0]])', context);
    const duplicateProfile = vm.runInContext('createUserProfile(duplicateSelections)', context);
    if (oneMovieProfile.some((value, index) => Math.abs(value - duplicateProfile[index]) > 1e-12)) {
        throw new Error('Duplicate selections changed the user profile.');
    }
    console.log('\nDuplicate check: the second Desperate Measures record is not recommended and does not double the profile.');
}

console.log('\nChecks passed: code cosine matches the manual calculation; Top-5 excludes selected movies and duplicates.');
