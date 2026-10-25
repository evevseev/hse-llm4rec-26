# Generated with an AI assistant
"""Small transparent implementations of personalized PageRank and implicit ALS."""
import numpy as np
from scipy import sparse
from scipy.linalg import cho_factor, cho_solve


PPR_PARAMETERS = {'damping': 0.85, 'neighbors': 50, 'min_pair_users': 3,
                  'tolerance_l1': 1e-8, 'max_iterations': 100, 'batch_size': 128,
                  'edge_weight': 'Binary-viewer cosine similarity',
                  'personalization': 'Normalized log1p personal qualified-airing counts',
                  'dangling_policy': 'Return dangling probability to the personal seed distribution'}
ALS_PARAMETERS = {'factors': 32, 'iterations': 15, 'regularization': 0.1,
                  'alpha': 20.0, 'seed': 42, 'dtype': 'float64',
                  'preference': '1 for an observed user-item pair, 0 otherwise',
                  'confidence': '1 + 20*log1p(count) for observations; 1 otherwise',
                  'solver': 'Exact alternating weighted least squares via Cholesky'}


def build_transition(counts, neighbors=50, min_pair_users=3):
    binary = counts.copy().astype(np.float64)
    binary.data[:] = 1
    viewers = np.asarray(binary.sum(axis=0)).ravel()
    pairs = (binary.T @ binary).tocsr()
    rr, cc, vv = [], [], []
    for item in range(counts.shape[1]):
        start, end = pairs.indptr[item:item+2]
        js, supports = pairs.indices[start:end], pairs.data[start:end]
        keep = (js != item) & (supports >= min_pair_users)
        js, supports = js[keep], supports[keep]
        weights = supports/np.sqrt(viewers[item]*viewers[js])
        order = np.lexsort((js, -weights))[:neighbors]
        rr.extend([item]*len(order))
        cc.extend(js[order].tolist())
        vv.extend(weights[order].tolist())
    graph = sparse.csr_matrix((vv, (rr, cc)), shape=(counts.shape[1], counts.shape[1]))
    degree = np.asarray(graph.sum(axis=1)).ravel()
    inverse = np.divide(1., degree, out=np.zeros_like(degree), where=degree > 0)
    transition = sparse.diags(inverse) @ graph
    return transition.tocsr(), degree == 0, graph


def personalized_pagerank(seeds, transition, dangling, damping=.85, tolerance=1e-8, max_iterations=100):
    """Compute personalized rows by power iteration; cold seed rows stay zero."""
    if not 0 <= damping < 1:
        raise ValueError('damping must be in [0,1).')
    personal = seeds.toarray() if sparse.issparse(seeds) else np.asarray(seeds, dtype=float).copy()
    mass = personal.sum(axis=1, keepdims=True)
    personal = np.divide(personal, mass, out=np.zeros_like(personal), where=mass > 0)
    ranks = personal.copy()
    for iteration in range(1, max_iterations+1):
        next_ranks = damping*(transition.T @ ranks.T).T
        return_mass = ranks[:, dangling].sum(axis=1, keepdims=True)
        next_ranks += ((1-damping)+damping*return_mass)*personal
        delta = float(np.abs(next_ranks-ranks).sum(axis=1).max(initial=0))
        ranks = next_ranks
        if delta <= tolerance:
            break
    residual = damping*(transition.T @ ranks.T).T
    residual += ((1-damping)+damping*ranks[:, dangling].sum(axis=1, keepdims=True))*personal
    residual_l1 = np.abs(residual-ranks).sum(axis=1)
    assert np.all(np.isfinite(ranks)) and ranks.min(initial=0) >= 0
    assert np.allclose(ranks.sum(axis=1), (mass[:, 0] > 0).astype(float), atol=1e-10)
    return ranks, {'iterations': iteration, 'last_step_l1': delta,
                   'max_stationary_residual_l1': float(residual_l1.max(initial=0)),
                   'converged': delta <= tolerance}


def als_update(confidence_excess, other_factors, regularization):
    """Solve one side: confidence_excess holds alpha*log1p(count), not C itself."""
    gram = other_factors.T @ other_factors
    base = gram + regularization*np.eye(other_factors.shape[1])
    factors = np.zeros((confidence_excess.shape[0], other_factors.shape[1]))
    for row in range(confidence_excess.shape[0]):
        start, end = confidence_excess.indptr[row:row+2]
        if start == end:
            continue
        selected = other_factors[confidence_excess.indices[start:end]]
        excess = confidence_excess.data[start:end]
        system = base + selected.T @ (excess[:, None]*selected)
        target = selected.T @ (1+excess)
        factors[row] = cho_solve(cho_factor(system, lower=True, check_finite=False), target, check_finite=False)
    return factors


def implicit_objective(excess, user_factors, item_factors, regularization):
    """Full implicit loss, including all missing pairs, without densifying the matrix."""
    rr, cc = excess.nonzero()
    prediction = np.einsum('ij,ij->i', user_factors[rr], item_factors[cc])
    all_squared = np.sum((user_factors.T @ user_factors)*(item_factors.T @ item_factors))
    observed_correction = np.sum((1+excess.data)*(1-prediction)**2-prediction**2)
    penalty = regularization*(np.sum(user_factors**2)+np.sum(item_factors**2))
    return float(all_squared+observed_correction+penalty)


def fit_implicit_als(counts, factors=32, iterations=15, regularization=.1, alpha=20., seed=42):
    excess = counts.copy().astype(np.float64)
    excess.data = alpha*np.log1p(excess.data)
    excess.sort_indices()
    transpose = excess.T.tocsr()
    rng = np.random.default_rng(seed)
    items = rng.normal(0, .01, size=(counts.shape[1], factors))
    users = np.zeros((counts.shape[0], factors))
    history = [{'iteration': 0, 'stage': 'initial',
                'training_objective': implicit_objective(excess, users, items, regularization)}]
    for iteration in range(1, iterations+1):
        users = als_update(excess, items, regularization)
        history.append({'iteration': iteration, 'stage': 'user_update',
                        'training_objective': implicit_objective(excess, users, items, regularization)})
        items = als_update(transpose, users, regularization)
        history.append({'iteration': iteration, 'stage': 'item_update',
                        'training_objective': implicit_objective(excess, users, items, regularization)})
    losses = [r['training_objective'] for r in history]
    assert all(b <= a+1e-7*max(1, abs(a)) for a, b in zip(losses, losses[1:]))
    assert np.isfinite(users).all() and np.isfinite(items).all()
    return users, items, history
