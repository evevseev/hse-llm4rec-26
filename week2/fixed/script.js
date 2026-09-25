const movieSelectIds = ['movie-select-1', 'movie-select-2', 'movie-select-3'];

// Initialize the application when the window loads
window.onload = async function() {
    try {
        const resultElement = document.getElementById('result');
        resultElement.textContent = 'Loading movie data...';
        resultElement.className = 'loading';

        await loadData();
        populateMoviesDropdown();
        resultElement.textContent = 'Data loaded. Choose one to three movies.';
        resultElement.className = 'success';
    } catch (error) {
        console.error('Initialization error:', error);
        // Error message already set in data.js
    }
};

function getMovieSelectElements() {
    return movieSelectIds.map(id => document.getElementById(id));
}

function populateMoviesDropdown() {
    const titleCounts = new Map();
    for (const movie of movies) {
        const key = getMovieKey(movie);
        titleCounts.set(key, (titleCounts.get(key) || 0) + 1);
    }

    const sortedMovies = [...movies].sort((a, b) =>
        a.title.localeCompare(b.title) || a.id - b.id
    );

    getMovieSelectElements().forEach((selectElement, index) => {
        const placeholder = index === 0 ? 'Choose a movie' : 'Choose another movie (optional)';
        selectElement.replaceChildren(new Option(placeholder, ''));

        sortedMovies.forEach(movie => {
            const duplicateLabel = titleCounts.get(getMovieKey(movie)) > 1 ? ` (record ${movie.id})` : '';
            const option = new Option(`${movie.title}${duplicateLabel}`, String(movie.id));
            option.dataset.titleKey = getMovieKey(movie);
            selectElement.appendChild(option);
        });

        selectElement.addEventListener('change', updateMovieSelectOptions);
    });

    updateMovieSelectOptions();
}

function updateMovieSelectOptions() {
    const selects = getMovieSelectElements();

    selects.forEach(selectElement => {
        const selectedByOthers = new Set(
            selects
                .filter(other => other !== selectElement && other.value)
                .map(other => {
                    const selectedMovie = movies.find(movie => movie.id === Number(other.value));
                    return selectedMovie ? getMovieKey(selectedMovie) : null;
                })
                .filter(Boolean)
        );

        Array.from(selectElement.options).forEach(option => {
            if (!option.value) return;
            option.disabled = selectedByOthers.has(option.dataset.titleKey);
        });
    });
}

// Keep the year in the key so remakes remain distinct; normalize punctuation
// and MovieLens' alternate "Title, The" ordering to catch duplicate records.
function getMovieKey(movie) {
    let words = movie.title
        .toLocaleLowerCase()
        .normalize('NFKD')
        .replace(/[\u0300-\u036f]/g, '')
        .replace(/[^a-z0-9]+/g, ' ')
        .trim()
        .split(/\s+/);

    const lastWord = words[words.length - 1];
    const year = /^\d{4}$/.test(lastWord) ? words.pop() : '';
    const article = words[words.length - 1];
    if (['the', 'a', 'an'].includes(article)) {
        words.unshift(words.pop());
    }

    return [...words, year].filter(Boolean).join(' ');
}

function movieToGenreVector(movie) {
    return genreNames.map(genre => movie.genres.includes(genre) ? 1 : 0);
}

function createUserProfile(selectedMovies) {
    const uniqueMovies = [...new Map(selectedMovies.map(movie => [getMovieKey(movie), movie])).values()];
    if (uniqueMovies.length === 0) return genreNames.map(() => 0);

    const vectors = uniqueMovies.map(movieToGenreVector);
    return genreNames.map((_, genreIndex) =>
        vectors.reduce((sum, vector) => sum + vector[genreIndex], 0) / vectors.length
    );
}

function cosineSimilarity(firstVector, secondVector) {
    let dotProduct = 0;
    let firstSquaredNorm = 0;
    let secondSquaredNorm = 0;

    for (let index = 0; index < firstVector.length; index += 1) {
        dotProduct += firstVector[index] * secondVector[index];
        firstSquaredNorm += firstVector[index] ** 2;
        secondSquaredNorm += secondVector[index] ** 2;
    }

    const denominator = Math.sqrt(firstSquaredNorm) * Math.sqrt(secondSquaredNorm);
    return denominator === 0 ? 0 : dotProduct / denominator;
}

function getPopularityByTitle() {
    const keyByMovieId = new Map(movies.map(movie => [movie.id, getMovieKey(movie)]));
    const usersByTitle = new Map();

    ratings.forEach(rating => {
        const titleKey = keyByMovieId.get(rating.itemId);
        if (!titleKey) return;
        if (!usersByTitle.has(titleKey)) usersByTitle.set(titleKey, new Set());
        usersByTitle.get(titleKey).add(rating.userId);
    });

    return new Map([...usersByTitle].map(([key, users]) => [key, users.size]));
}

function getRatingCountsByMovieId() {
    const counts = new Map();
    ratings.forEach(rating => counts.set(rating.itemId, (counts.get(rating.itemId) || 0) + 1));
    return counts;
}

function getTopRecommendations(selectedMovies, count = 5) {
    const uniqueSelected = [...new Map(selectedMovies.map(movie => [getMovieKey(movie), movie])).values()];
    const selectedKeys = new Set(uniqueSelected.map(getMovieKey));
    const profile = createUserProfile(uniqueSelected);
    const popularityByTitle = getPopularityByTitle();
    const ratingCountsById = getRatingCountsByMovieId();
    const candidatesByTitle = new Map();

    movies.forEach(movie => {
        const titleKey = getMovieKey(movie);
        if (selectedKeys.has(titleKey)) return;

        const current = candidatesByTitle.get(titleKey);
        const candidateRatingCount = ratingCountsById.get(movie.id) || 0;
        const currentRatingCount = current ? ratingCountsById.get(current.id) || 0 : -1;
        if (!current || candidateRatingCount > currentRatingCount ||
            (candidateRatingCount === currentRatingCount && movie.id < current.id)) {
            candidatesByTitle.set(titleKey, movie);
        }
    });

    return [...candidatesByTitle.entries()]
        .map(([titleKey, movie]) => ({
            ...movie,
            score: cosineSimilarity(profile, movieToGenreVector(movie)),
            popularity: popularityByTitle.get(titleKey) || 0
        }))
        .sort((a, b) => {
            const scoreDifference = b.score - a.score;
            if (Math.abs(scoreDifference) > 1e-12) return scoreDifference;
            return b.popularity - a.popularity ||
                a.title.localeCompare(b.title) ||
                a.id - b.id;
        })
        .slice(0, count);
}

function getSelectedMovies() {
    const selected = getMovieSelectElements()
        .filter(selectElement => selectElement.value)
        .map(selectElement => movies.find(movie => movie.id === Number(selectElement.value)))
        .filter(Boolean);

    return [...new Map(selected.map(movie => [getMovieKey(movie), movie])).values()];
}

function getRecommendations() {
    const resultElement = document.getElementById('result');

    try {
        const selectedMovies = getSelectedMovies();
        const firstSelect = getMovieSelectElements()[0];
        if (!firstSelect.value) {
            resultElement.textContent = 'Please choose a movie in the first list.';
            resultElement.className = 'error';
            return;
        }

        if (selectedMovies.length === 0) {
            resultElement.textContent = 'The selected movies could not be found.';
            resultElement.className = 'error';
            return;
        }

        resultElement.textContent = 'Calculating recommendations...';
        resultElement.className = 'loading';

        const recommendations = getTopRecommendations(selectedMovies, 5);
        if (recommendations.length === 0) {
            resultElement.textContent = 'No recommendations found for this profile.';
            resultElement.className = 'error';
            return;
        }

        const profileTitles = selectedMovies.map(movie => movie.title).join(', ');
        const recommendationText = recommendations
            .map((movie, index) => `${index + 1}. ${movie.title} (cosine ${movie.score.toFixed(3)})`)
            .join(' | ');
        resultElement.textContent = `Based on ${profileTitles}: ${recommendationText}`;
        resultElement.className = 'success';
    } catch (error) {
        console.error('Error in recommendation calculation:', error);
        resultElement.textContent = 'An error occurred while calculating recommendations.';
        resultElement.className = 'error';
    }
}
