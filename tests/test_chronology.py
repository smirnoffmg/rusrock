import pytest

from rusrock.chronology import bootstrap_interval, decade, lexicon_rates


def test_decade_label() -> None:
    assert decade(1987) == "1980-е"
    assert decade(1990) == "1990-е"
    assert decade(2026) == "2020-е"


def test_rates_per_thousand_words_and_share_of_songs() -> None:
    songs = [["бог", "и", "я", "мы"], ["мы", "и", "они", "вы"]]
    per_thousand, share = lexicon_rates(songs, {"бог"})
    assert per_thousand == pytest.approx(1000 / 8)
    assert share == pytest.approx(0.5)


def test_bootstrap_interval_contains_point_estimate_and_is_reproducible() -> None:
    songs = [["бог", "x"], ["x", "x"], ["бог", "бог"], ["x"]]
    low, high = bootstrap_interval(songs, {"бог"}, n=500, seed=1)
    point, _ = lexicon_rates(songs, {"бог"})
    assert low <= point <= high
    assert (low, high) == bootstrap_interval(songs, {"бог"}, n=500, seed=1)
