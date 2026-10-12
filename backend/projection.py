"""Project chunk embeddings down to 3 dimensions for visualization (PCA via SVD)."""

from __future__ import annotations

from typing import List, Tuple

import numpy as np


def sample_indices(n: int, limit: int) -> np.ndarray:
    """Up to `limit` indices spread evenly over 0..n-1 (deterministic, covers every document)."""
    if n <= limit:
        return np.arange(n)
    return np.unique(np.linspace(0, n - 1, num=limit).round().astype(int))


def pca_project(embeddings: np.ndarray, k: int = 3) -> Tuple[np.ndarray, List[float]]:
    """Return (coords, explained_variance_ratio) for the top-k principal components.

    coords has shape (n, k), scaled so the largest absolute value is 1 (stable for plotting),
    padded with zero columns if the data has fewer than k dimensions or points. A degenerate
    input (fewer than 2 points, or all points identical) yields all-zero coordinates.
    """
    x = np.asarray(embeddings, dtype=np.float64)
    n = x.shape[0]
    coords = np.zeros((n, k))
    explained = [0.0] * k
    if n < 2 or x.shape[1] == 0:
        return coords, explained
    centered = x - x.mean(axis=0, keepdims=True)
    total = float((centered**2).sum())
    if total <= 1e-12:
        return coords, explained
    _u, s, vt = np.linalg.svd(centered, full_matrices=False)
    r = min(k, vt.shape[0])
    coords[:, :r] = centered @ vt[:r].T
    var = (s**2) / total
    explained[:r] = [float(v) for v in var[:r]]
    peak = float(np.abs(coords).max())
    if peak > 0:
        coords = coords / peak
    return coords, explained
