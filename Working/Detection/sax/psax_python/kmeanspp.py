# k-means++ initialisation.
# Taken from the k-means file of Laurent S.:
# https://www.mathworks.com/matlabcentral/fileexchange/28804-k-means
#
# Python port: see psax_python

import numpy as np

# The seed k-means++ draws from when the caller names none. A fixed
# constant, not a recipe parameter: the MATLAB original drew from the global
# generator, which made one recipe (one recipe hash) give different
# Lloyd-Max cutlines, symbol strings and spans from run to run, and the step
# cache froze whichever draw came first. A local generator built from this
# constant makes every encode reproducible without consuming or reseeding
# the global `np.random`, and without changing any saved chain's hash.
KMEANSPP_SEED = 0


def as_rng(random_state):
    """A `np.random.Generator` or `RandomState` passes through; anything
    else (an int, or None for fresh OS entropy) seeds a new Generator."""
    if isinstance(random_state, (np.random.Generator, np.random.RandomState)):
        return random_state
    return np.random.default_rng(random_state)


def kmeanspp(X, k, random_state=KMEANSPP_SEED):
    """
    k-means++ initialisation for 1-D data.

    Parameters
    ----------
    X : array-like — 1-D data (or row vector)
    k : int        — number of cluster centres
    random_state : int, Generator, RandomState or None — the source of the
        two random draws. Defaults to the fixed `KMEANSPP_SEED`, so the same
        X always gives the same centres; pass another seed for a seed sweep,
        or None to opt into a fresh draw. Never touches global `np.random`.

    Returns
    -------
    L : np.ndarray, shape (n,) — cluster label per point (0-based)
    C : np.ndarray, shape (k,) — cluster centres (sorted ascending)
    """
    rng = as_rng(random_state)
    X = np.asarray(X, dtype=float).ravel()
    n = len(X)
    k = min(n, k)

    L  = np.zeros(n, dtype=int)
    L1 = np.full(n, -1, dtype=int)

    while not np.array_equal(np.unique(L), np.arange(k)):
        # Random initial centre
        C = [X[int(round(rng.random() * (n - 1)))]]
        L = np.zeros(n, dtype=int)

        for i in range(1, k):
            # Distance from each point to its current nearest centre
            D  = X - np.array(C)[L]              # signed distance (1-D)
            D  = np.cumsum(np.abs(D))             # cumulative distance

            if D[-1] == 0:
                # Degenerate: fill remaining centres with same point
                while len(C) < k:
                    C.append(X[0])
                break

            # Sample a new centre proportional to distance
            r       = rng.random()
            new_idx = int(np.where(r < D / D[-1])[0][0])
            C.append(X[new_idx])

            # Re-assign labels: argmax of 2*c*x - c^2  ≡  argmin of (x-c)^2
            C_arr = np.array(C)
            scores = 2.0 * C_arr[:, None] * X[None, :] - C_arr[:, None] ** 2
            L      = np.argmax(scores, axis=0)

        break   # mirrors MATLAB's iter<1 loop limit

    C_arr = np.sort(np.array(C))
    return L, C_arr
