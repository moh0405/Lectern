import numpy as np
import pytest

from backend.projection import pca_project, sample_indices


def test_sample_indices_is_even_deterministic_and_bounded():
    assert list(sample_indices(5, 10)) == [0, 1, 2, 3, 4]
    idx = sample_indices(1000, 100)
    assert len(idx) <= 100 and idx[0] == 0 and idx[-1] == 999
    assert np.array_equal(idx, sample_indices(1000, 100))
    assert np.all(np.diff(idx) > 0)


def test_pca_recovers_the_dominant_directions():
    rng = np.random.default_rng(0)
    # 3 true axes with very different spreads, embedded in 20 dimensions
    basis = np.linalg.qr(rng.normal(size=(20, 3)))[0]
    data = (rng.normal(size=(300, 3)) * np.array([10.0, 3.0, 1.0])) @ basis.T
    coords, explained = pca_project(data, 3)
    assert coords.shape == (300, 3)
    assert explained[0] > explained[1] > explained[2] > 0
    assert explained[0] > 0.8 and sum(explained) > 0.99
    assert abs(coords).max() == pytest.approx(1.0)
    # components are uncorrelated
    corr = np.corrcoef(coords.T)
    assert abs(corr[0, 1]) < 1e-6 and abs(corr[0, 2]) < 1e-6


def test_clusters_stay_separated_after_projection():
    rng = np.random.default_rng(1)
    a = rng.normal(loc=0.0, scale=0.05, size=(50, 16)) + np.eye(16)[0]
    b = rng.normal(loc=0.0, scale=0.05, size=(50, 16)) + np.eye(16)[5]
    coords, _ = pca_project(np.vstack([a, b]), 3)
    gap = np.linalg.norm(coords[:50].mean(axis=0) - coords[50:].mean(axis=0))
    spread = max(coords[:50].std(axis=0).max(), coords[50:].std(axis=0).max())  # within-cluster spread, per axis
    assert gap > 5 * spread


@pytest.mark.parametrize("data", [np.zeros((0, 4)), np.ones((1, 4)), np.ones((10, 4)), np.zeros((5, 0))])
def test_degenerate_inputs_give_zeros_not_errors(data):
    coords, explained = pca_project(data, 3)
    assert coords.shape == (data.shape[0], 3) and not coords.any() and explained == [0.0, 0.0, 0.0]


def test_fewer_dimensions_than_components_is_padded():
    data = np.random.default_rng(2).normal(size=(10, 2))
    coords, explained = pca_project(data, 3)
    assert coords.shape == (10, 3) and not coords[:, 2].any() and explained[2] == 0.0
