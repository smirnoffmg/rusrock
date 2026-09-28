import math

import numpy as np
import pytest

from rusrock.richness import growth_curve, heaps_fit, sample_run, sampled_ttr, ttr


def test_ttr_is_types_over_tokens() -> None:
    assert ttr(["а", "б", "а", "в"]) == 0.75


def test_sample_run_concatenates_whole_songs_and_truncates_the_last() -> None:
    songs = [["a"] * 3, ["b"] * 3, ["c"] * 3]
    run = sample_run(songs, 7, np.random.default_rng(0))
    assert sum(len(s) for s in run) == 7
    assert [len(s) for s in run] == [3, 3, 1]
    assert len({s[0] for s in run}) == 3


def test_sample_run_draws_songs_without_replacement() -> None:
    songs = [[str(i)] * 2 for i in range(10)]
    run = sample_run(songs, 20, np.random.default_rng(1))
    assert sorted(s[0] for s in run) == [str(i) for i in range(10)]


def test_sample_run_refuses_more_tokens_than_the_author_has() -> None:
    with pytest.raises(ValueError):
        sample_run([["a", "b"]], 3, np.random.default_rng(0))


def test_sampled_ttr_is_reproducible_and_has_no_spread_when_order_does_not_matter() -> None:
    songs = [["a", "b"], ["c", "d"]]
    assert sampled_ttr(songs, 4, reps=5, seed=3) == (1.0, 0.0)
    varied = [["a", "a"], ["b", "c"], ["d", "d"], ["e", "f"]]
    assert sampled_ttr(varied, 2, reps=20, seed=3) == sampled_ttr(varied, 2, reps=20, seed=3)
    mean, std = sampled_ttr(varied, 2, reps=200, seed=3)
    assert mean == pytest.approx(0.75, abs=0.05)
    assert std == pytest.approx(0.25, abs=0.02)


def test_growth_curve_counts_types_seen_so_far() -> None:
    assert growth_curve(["a", "b", "a", "c", "b"]).tolist() == [1, 2, 2, 3, 3]


def test_heaps_fit_recovers_k_and_beta_of_an_exact_power_law() -> None:
    n = np.arange(1, 10_001, dtype=float)
    v = 7.0 * n**0.6
    k, beta, r2 = heaps_fit(n, v)
    assert k == pytest.approx(7.0)
    assert beta == pytest.approx(0.6)
    assert r2 == pytest.approx(1.0)
    assert not math.isnan(r2)
