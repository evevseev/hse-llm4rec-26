// ---------------------------------------------------------------------------
// HW3 — Collaborative Filtering core
//
// Missing-value strategy (see week3/readme.md section 6). Choose EXACTLY ONE
// and keep it consistent in cosineSimilarity below:
//
//   [ ] use co-rated entries only without an overlap correction
//   [ ] mean imputation
//   [x] weight similarity by the number of co-rated items
//
// The cosine uses co-rated entries, then applies an overlap confidence weight.
// ---------------------------------------------------------------------------

// Number of co-rated entries needed for full cosine weight.
let similarityOverlapThreshold = 5;
const MIN_ITEM_BASED_SUPPORTERS = 3;
let minUserBasedSupporters = 3;

// Initialize the application when the window loads
window.onload = async function() {
    const userBased = document.getElementById('user-based-result');
    const itemBased = document.getElementById('item-based-result');

    try {
        userBased.innerHTML = '<p>Loading movie data...</p>';
        itemBased.innerHTML = '<p>Loading movie data...</p>';

        await loadData();

        populateUserDropdown();

        userBased.innerHTML = '<p>Data loaded. Select a user.</p>';
        itemBased.innerHTML = '<p>Data loaded. Select a user.</p>';
    } catch (error) {
        console.error('Initialization error:', error);
        // The error message is already shown by data.js
    }
};

// Populate the user dropdown with one option per user id found in u.data
function populateUserDropdown() {
    const selectElement = document.getElementById('user-select');

    // Clear existing options except the first placeholder
    while (selectElement.options.length > 1) {
        selectElement.remove(1);
    }

    for (let userId = 1; userId <= numUsers; userId++) {
        const option = document.createElement('option');
        option.value = userId;
        option.textContent = `User ${userId}`;
        selectElement.appendChild(option);
    }
}

// ---------------------------------------------------------------------------
// TODO (HW3) — cosine similarity between two rating vectors.
//
// Compare only co-rated (non-zero) entries, per the missing-value strategy
// you chose above. Return 0 when the denominator is 0 (that is, when the two
// vectors share no rated items). See week3/readme.md section 5.3.
//
// Inputs: two arrays of equal length (slice the rating matrix column or row).
// Output: a number in [0, 1].
// ---------------------------------------------------------------------------
function cosineSimilarity(a, b) {
    // A zero in the matrix means "not rated", so include only positions where
    // both users (or both movies) have a rating. This avoids treating a missing
    // value as a real rating of zero.
    let dotProduct = 0;
    let normA = 0;
    let normB = 0;
    let coRatedCount = 0;

    for (let i = 0; i < a.length; i++) {
        if (a[i] === 0 || b[i] === 0) continue;

        coRatedCount++;
        dotProduct += a[i] * b[i];
        normA += a[i] * a[i];
        normB += b[i] * b[i];
    }

    const denominator = Math.sqrt(normA) * Math.sqrt(normB);
    if (denominator === 0) return 0;

    const cosine = dotProduct / denominator;
    const overlapWeight = Math.min(coRatedCount / similarityOverlapThreshold, 1);
    return Math.max(0, Math.min(1, cosine * overlapWeight));
}

function getMovieTitleKey(movie) {
    return movie.title.normalize('NFKC').trim().toLowerCase().replace(/\s+/g, ' ');
}

// ---------------------------------------------------------------------------
// TODO (HW3) — User-Based CF.
//
// Return the top-K recommendations for the active user as an array of
// { title, score }, sorted by score descending.
//
// Suggested steps (week3/readme.md section 5.4):
//   1. compare the active user's rating vector against every other user
//   2. take the N most similar users with positive similarity (e.g. N = 20)
//   3. for each movie the active user has NOT rated, predict a score as the
//      similarity-weighted average of those users' ratings
//   4. sort and take the top K
// ---------------------------------------------------------------------------
function getUserBasedRecommendations(activeUserId, topK = 5) {
    const activeRatings = ratingMatrix[activeUserId];
    const ratedTitleKeys = new Set();
    for (let movieId = 1; movieId <= numMovies; movieId++) {
        if (activeRatings[movieId] !== 0) {
            ratedTitleKeys.add(getMovieTitleKey(movies[movieId - 1]));
        }
    }
    const neighbors = [];

    for (let userId = 1; userId <= numUsers; userId++) {
        if (userId === activeUserId) continue;

        const similarity = cosineSimilarity(activeRatings, ratingMatrix[userId]);
        if (similarity > 0) neighbors.push({ userId, similarity });
    }

    // Break equal-similarity ties by user ID for deterministic output.
    neighbors.sort((a, b) => b.similarity - a.similarity || a.userId - b.userId);
    const selectedNeighbors = neighbors.slice(0, 20);
    const recommendations = [];

    for (let movieId = 1; movieId <= numMovies; movieId++) {
        const movie = movies[movieId - 1];
        if (activeRatings[movieId] !== 0 || ratedTitleKeys.has(getMovieTitleKey(movie))) continue;

        let weightedRatingSum = 0;
        let similaritySum = 0;
        let supportingNeighborCount = 0;

        for (const neighbor of selectedNeighbors) {
            const neighborRating = ratingMatrix[neighbor.userId][movieId];
            if (neighborRating === 0) continue;

            supportingNeighborCount++;
            weightedRatingSum += neighbor.similarity * neighborRating;
            similaritySum += neighbor.similarity;
        }

        if (similaritySum > 0 && supportingNeighborCount >= minUserBasedSupporters) {
            recommendations.push({
                movieId,
                title: movie.title,
                score: weightedRatingSum / similaritySum
            });
        }
    }

    recommendations.sort((a, b) => b.score - a.score || a.movieId - b.movieId);
    const seenTitleKeys = new Set(ratedTitleKeys);
    const uniqueRecommendations = recommendations.filter(recommendation => {
        const titleKey = getMovieTitleKey({ title: recommendation.title });
        if (seenTitleKeys.has(titleKey)) return false;
        seenTitleKeys.add(titleKey);
        return true;
    });
    return uniqueRecommendations.slice(0, topK).map(({ title, score }) => ({ title, score }));
}

// ---------------------------------------------------------------------------
// TODO (HW3) — Item-Based CF.
//
// Return the top-K recommendations for the active user as an array of
// { title, score }, sorted by score descending.
//
// Suggested steps (week3/readme.md section 5.5):
//   1. for each movie the active user has rated, compute the item-item
//      similarity against every other movie's rating column
//   2. for each candidate movie the active user has NOT rated, aggregate the
//      similarities from the rated movies, weighted by the user's rating
//   3. sort and take the top K
// ---------------------------------------------------------------------------
function getItemBasedRecommendations(activeUserId, topK = 5) {
    const activeRatings = ratingMatrix[activeUserId];
    const ratedTitleKeys = new Set();
    const ratedMovieIds = [];
    const candidateScores = [];
    const movieColumns = Array.from(
        { length: numMovies + 1 },
        (_, movieId) => ratingMatrix.slice(1).map(row => row[movieId])
    );
    const movieRaters = Array.from({ length: numMovies + 1 }, (_, movieId) => {
        const raters = [];
        for (let userId = 1; userId <= numUsers; userId++) {
            if (ratingMatrix[userId][movieId] !== 0) raters.push(userId);
        }
        return raters;
    });

    for (let movieId = 1; movieId <= numMovies; movieId++) {
        if (activeRatings[movieId] !== 0) {
            ratedMovieIds.push(movieId);
            ratedTitleKeys.add(getMovieTitleKey(movies[movieId - 1]));
        }
    }

    for (let candidateId = 1; candidateId <= numMovies; candidateId++) {
        const candidateMovie = movies[candidateId - 1];
        if (activeRatings[candidateId] !== 0 ||
            ratedTitleKeys.has(getMovieTitleKey(candidateMovie))) continue;

        let weightedSimilaritySum = 0;
        let similaritySum = 0;

        for (const ratedMovieId of ratedMovieIds) {
            const similarity = cosineSimilarity(
                movieColumns[candidateId],
                movieColumns[ratedMovieId]
            );

            weightedSimilaritySum += similarity * activeRatings[ratedMovieId];
            similaritySum += similarity;
        }

        // Count each candidate rater once if their history overlaps any rated film.
        const supportingUserCount = movieRaters[candidateId].filter(coRaterId =>
            ratedMovieIds.some(ratedMovieId => ratingMatrix[coRaterId][ratedMovieId] !== 0)
        ).length;

        // Require evidence from at least three distinct users who rated both
        // the candidate and one or more movies rated by the active user.
        if (similaritySum > 0 && supportingUserCount >= MIN_ITEM_BASED_SUPPORTERS) {
            candidateScores.push({
                movieId: candidateId,
                title: candidateMovie.title,
                score: weightedSimilaritySum / similaritySum
            });
        }
    }

    candidateScores.sort((a, b) => b.score - a.score || a.movieId - b.movieId);
    const seenTitleKeys = new Set(ratedTitleKeys);
    const uniqueRecommendations = candidateScores.filter(candidate => {
        const titleKey = getMovieTitleKey({ title: candidate.title });
        if (seenTitleKeys.has(titleKey)) return false;
        seenTitleKeys.add(titleKey);
        return true;
    });
    return uniqueRecommendations.slice(0, topK).map(({ title, score }) => ({ title, score }));
}

// Provided — read the selected user and render both recommendation lists
function getRecommendations() {
    const selectElement = document.getElementById('user-select');
    const userId = parseInt(selectElement.value, 10);

    if (isNaN(userId)) {
        renderList('user-based-result', [], 'Please select a user first.');
        renderList('item-based-result', [], 'Please select a user first.');
        return;
    }

    renderList('user-based-result', getUserBasedRecommendations(userId));
    renderList('item-based-result', getItemBasedRecommendations(userId));
}

// Provided — render a list of { title, score } into the given element
function renderList(elementId, items, message) {
    const el = document.getElementById(elementId);

    if (message) {
        el.innerHTML = `<p>${message}</p>`;
        return;
    }

    if (!items || items.length === 0) {
        el.innerHTML = '<p>No recommendations. (Implement the TODO above.)</p>';
        return;
    }

    const entries = items
        .map(item => `<li>${item.title} &mdash; ${Number(item.score).toFixed(3)}</li>`)
        .join('');
    el.innerHTML = `<ul>${entries}</ul>`;
}
