import pytest

from rusrock.openset import balanced_accuracy, best_threshold


def test_balanced_accuracy_weights_known_and_unknown_equally() -> None:
    known, unknown = [0.9, 0.8, 0.2, 0.7], [0.1, 0.5]
    # threshold 0.6: known accepted 3/4, unknown rejected 2/2
    assert balanced_accuracy(known, unknown, 0.6) == pytest.approx((0.75 + 1.0) / 2)


def test_best_threshold_separates_clean_scores() -> None:
    known, unknown = [0.6, 0.7, 0.8], [0.1, 0.2, 0.3]
    threshold, score = best_threshold(known, unknown)
    assert 0.3 < threshold <= 0.6
    assert score == pytest.approx(1.0)


def test_best_threshold_prefers_the_lower_of_equally_good_cuts() -> None:
    threshold, _ = best_threshold([0.5, 0.9], [0.1, 0.2])
    assert threshold == pytest.approx(0.5)
