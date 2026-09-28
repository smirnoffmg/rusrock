import math
from collections import Counter

import pytest

from rusrock.keyness import dunning_g2, log_odds_z


def test_log_odds_z_is_antisymmetric() -> None:
    a, b = Counter({"x": 30, "y": 70}), Counter({"x": 10, "y": 90})
    prior = Counter({"x": 40, "y": 160})
    za = log_odds_z(a, b, prior, alpha0=50)
    zb = log_odds_z(b, a, prior, alpha0=50)
    assert za["x"] > 0
    assert za["x"] == pytest.approx(-zb["x"])


def test_equal_proportions_give_zero() -> None:
    a, b = Counter({"x": 5, "y": 95}), Counter({"x": 50, "y": 950})
    z = log_odds_z(a, b, a + b, alpha0=100)
    assert z["x"] == pytest.approx(0.0, abs=1e-9)


def test_prior_shrinks_rare_words_below_frequent_ones_with_same_ratio() -> None:
    # Same 3:1 ratio of proportions; the rare word carries far less evidence.
    a = Counter({"rare": 3, "common": 300, "rest": 697})
    b = Counter({"rare": 1, "common": 100, "rest": 899})
    z = log_odds_z(a, b, a + b, alpha0=200)
    assert 0 < z["rare"] < z["common"]


def test_matches_the_textbook_formula() -> None:
    a, b = Counter({"x": 20, "y": 80}), Counter({"x": 30, "y": 170})
    prior = a + b
    alpha0 = 60
    aw = alpha0 * prior["x"] / prior.total()
    delta = math.log((20 + aw) / (100 + alpha0 - 20 - aw)) - math.log(
        (30 + aw) / (200 + alpha0 - 30 - aw)
    )
    sigma = math.sqrt(1 / (20 + aw) + 1 / (30 + aw))
    assert log_odds_z(a, b, prior, alpha0)["x"] == pytest.approx(delta / sigma)


def test_dunning_g2_is_signed_and_zero_without_difference() -> None:
    a, b = Counter({"x": 30, "y": 70}), Counter({"x": 10, "y": 90})
    g = dunning_g2(a, b)
    assert g["x"] > 0 > g["y"]
    even = dunning_g2(Counter({"x": 5, "y": 5}), Counter({"x": 50, "y": 50}))
    assert even["x"] == pytest.approx(0.0, abs=1e-9)
