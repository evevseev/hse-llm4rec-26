# Generated with an AI assistant
"""Matrix factorization of log viewing counts with explicit missing-pair loss.

Unlike binary-preference implicit ALS, observed regression targets retain repeat
strength. Alpha=0 is uniform-confidence regularized matrix factorization;
alpha=20 also gives repeated observations higher confidence.
"""
import numpy as np
from scipy.linalg import cho_factor, cho_solve


VARIANTS = {
    'ppr_raw_counts': {'family': 'PPR', 'personalization': 'Normalized raw qualified-airing counts',
                       'damping': .85, 'neighbors': 50, 'min_pair_users': 3,
                       'tolerance_l1': 1e-8, 'max_iterations': 100},
    'als_log_counts_weighted': {'family': 'MF', 'target': 'log1p(qualified-airing count)',
        'alpha': 20., 'regularization': .1, 'factors': 32, 'iterations': 15, 'seed': 42,
        'confidence': '1 + 20*log1p(count) for observations; 1 for missing pairs'},
    'als_log_counts_uniform': {'family': 'MF', 'target': 'log1p(qualified-airing count)',
        'alpha': 0., 'regularization': .1, 'factors': 32, 'iterations': 15, 'seed': 42,
        'confidence': '1 for every user-item pair, observed or missing'}}


def log_count_update(counts, other, regularization=.1, alpha=20.):
    """Solve rows against other-side factors, including all missing pairs."""
    base = other.T @ other+regularization*np.eye(other.shape[1])
    factors = np.zeros((counts.shape[0], other.shape[1]))
    for row in range(counts.shape[0]):
        left, right = counts.indptr[row:row+2]
        if left == right:
            continue
        selected = other[counts.indices[left:right]]
        target = np.log1p(counts.data[left:right])
        excess = alpha*target
        system = base+selected.T @ (excess[:, None]*selected)
        response = selected.T @ ((1+excess)*target)
        factors[row] = cho_solve(cho_factor(system, lower=True, check_finite=False), response, check_finite=False)
    return factors


def log_count_objective(counts, users, items, regularization=.1, alpha=20.):
    rows = np.repeat(np.arange(counts.shape[0]), np.diff(counts.indptr))
    prediction = np.einsum('ij,ij->i', users[rows], items[counts.indices])
    target = np.log1p(counts.data)
    confidence = 1+alpha*target
    all_squared = np.sum((users.T @ users)*(items.T @ items))
    correction = np.sum(confidence*(target-prediction)**2-prediction**2)
    penalty = regularization*(np.sum(users**2)+np.sum(items**2))
    return float(all_squared+correction+penalty)


def fit_log_count_als(counts, alpha=20., factors=32, iterations=15, regularization=.1, seed=42):
    if alpha < 0 or regularization <= 0:
        raise ValueError('Require nonnegative confidence alpha and positive regularization.')
    counts = counts.astype(np.float64).tocsr(copy=True)
    counts.sort_indices()
    if not np.all(counts.data > 0):
        raise ValueError('Observed counts must be positive.')
    transpose = counts.T.tocsr()
    rng = np.random.default_rng(seed)
    items = rng.normal(0, .01, size=(counts.shape[1], factors))
    users = np.zeros((counts.shape[0], factors))
    history = [{'iteration': 0, 'stage': 'initial',
                'training_objective': log_count_objective(counts, users, items, regularization, alpha)}]
    for iteration in range(1, iterations+1):
        users = log_count_update(counts, items, regularization, alpha)
        history.append({'iteration': iteration, 'stage': 'user_update',
                        'training_objective': log_count_objective(counts, users, items, regularization, alpha)})
        items = log_count_update(transpose, users, regularization, alpha)
        history.append({'iteration': iteration, 'stage': 'item_update',
                        'training_objective': log_count_objective(counts, users, items, regularization, alpha)})
    losses = [r['training_objective'] for r in history]
    assert all(b <= a+1e-7*max(1, a) for a, b in zip(losses, losses[1:]))
    assert np.isfinite(users).all() and np.isfinite(items).all()
    return users, items, history
