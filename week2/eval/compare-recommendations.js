// Generated with an AI assistant. Run from week2/: node eval/compare-recommendations.js

const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const projectDir = path.resolve(__dirname, '..');
const genreNames = [
    'Action', 'Adventure', 'Animation', "Children's", 'Comedy',
    'Crime', 'Documentary', 'Drama', 'Fantasy', 'Film-Noir',
    'Horror', 'Musical', 'Mystery', 'Romance', 'Sci-Fi',
    'Thriller', 'War', 'Western'
];

function loadMovies(folder) {
    const folderPath = path.join(projectDir, folder);
    const source = fs.readFileSync(path.join(folderPath, 'data.js'), 'utf8');
    const itemText = new TextDecoder('iso-8859-1').decode(fs.readFileSync(path.join(folderPath, 'u.item')));
    const context = vm.createContext({ console });

    // Run the folder's data.js unchanged, then parse its actual u.item file.
    vm.runInContext(source, context, { filename: `${folder}/data.js` });
    context.itemText = itemText;
    vm.runInContext('parseItemData(itemText)', context);

    return {
        movies: Array.from(vm.runInContext('movies', context)),
        itemText
    };
}

function expectedGenresById(itemText) {
    const expected = new Map();

    for (const line of itemText.split(/\r?\n/)) {
        if (line.trim() === '') continue;
        const fields = line.split('|');
        const id = Number.parseInt(fields[0], 10);
        const genres = genreNames.filter((_, index) => Number(fields[6 + index]) === 1);
        expected.set(id, genres);
    }

    return expected;
}

function topRecommendations(movies, likedMovie, count = 5) {
    const likedGenres = new Set(likedMovie.genres);

    return movies
        .filter(movie => movie.id !== likedMovie.id)
        .map(movie => {
            const candidateGenres = new Set(movie.genres);
            const intersectionSize = [...likedGenres].filter(genre => candidateGenres.has(genre)).length;
            const unionSize = new Set([...likedGenres, ...candidateGenres]).size;

            return {
                id: movie.id,
                title: movie.title,
                score: unionSize > 0 ? intersectionSize / unionSize : 0
            };
        })
        .sort((a, b) => b.score - a.score)
        .slice(0, count);
}

function sameIds(first, second) {
    return first.length === second.length && first.every((movie, index) => movie.id === second[index].id);
}

function sameMembers(first, second) {
    return first.length === second.length && first.every(movie => second.some(other => other.id === movie.id));
}

function formatTop(top) {
    return top.map(movie => `${movie.title} [id=${movie.id}, J=${movie.score.toFixed(3)}]`).join('\n    ');
}

const original = loadMovies('original');
const fixed = loadMovies('fixed');
const expectedById = expectedGenresById(fixed.itemText);
const fixedById = new Map(fixed.movies.map(movie => [movie.id, movie]));

let genreMismatches = 0;
for (const [id, expectedGenres] of expectedById) {
    const actual = fixedById.get(id);
    if (!actual || JSON.stringify(actual.genres) !== JSON.stringify(expectedGenres)) {
        genreMismatches += 1;
        if (genreMismatches === 1) {
            console.error('First genre mismatch:', {
                id,
                title: actual?.title,
                expectedGenres,
                parsedGenres: actual?.genres
            });
        }
    }
}

const originalById = new Map(original.movies.map(movie => [movie.id, movie]));
const comparableMovies = original.movies.filter(movie => fixedById.has(movie.id));
let changedOrderedTop5 = 0;
let changedTop5Membership = 0;
const westernExamples = [];

for (const movie of comparableMovies) {
    const fixedMovie = fixedById.get(movie.id);
    const originalTop5 = topRecommendations(original.movies, movie);
    const fixedTop5 = topRecommendations(fixed.movies, fixedMovie);

    if (!sameIds(originalTop5, fixedTop5)) changedOrderedTop5 += 1;
    if (!sameMembers(originalTop5, fixedTop5)) changedTop5Membership += 1;

    const expectedGenres = expectedById.get(movie.id) ?? [];
    if (expectedGenres.includes('Western') && westernExamples.length === 0 && !sameIds(originalTop5, fixedTop5)) {
        westernExamples.push({ movie, fixedMovie, originalTop5, fixedTop5, expectedGenres });
    }
}

console.log(`Genre check for fixed/: ${expectedById.size - genreMismatches}/${expectedById.size} match u.item; mismatches: ${genreMismatches}.`);
console.log(`Movies with comparable IDs: ${comparableMovies.length}.`);
console.log(`Ordered Top-5 changed: ${changedOrderedTop5}/${comparableMovies.length}.`);
console.log(`Top-5 membership changed (ignoring order): ${changedTop5Membership}/${comparableMovies.length}.`);

if (westernExamples.length > 0) {
    const example = westernExamples[0];
    console.log(`\nExample Western movie: ${example.movie.title} [id=${example.movie.id}]`);
    console.log(`Correct genres: ${example.expectedGenres.join(', ')}`);
    console.log(`original/ Top-5:\n    ${formatTop(example.originalTop5)}`);
    console.log(`fixed/ Top-5:\n    ${formatTop(example.fixedTop5)}`);
} else {
    console.log('\nNo Western movie with a changed ordered Top-5 was found.');
}

if (genreMismatches > 0 || comparableMovies.length !== original.movies.length || comparableMovies.length !== fixed.movies.length) {
    process.exitCode = 1;
}
