import numpy as np
import pytest

from rusrock.features import (
    DeltaClassifier,
    MostFrequentWords,
    delta_distances,
    length_bucket,
    letters_only,
    most_frequent,
    relative_frequencies,
    split_unknown_groups,
)


def test_unknown_groups_become_singletons_and_known_ones_stay() -> None:
    groups = ["a:X", "a:unknown", "a:X", "a:unknown", "b:unknown"]
    out = split_unknown_groups(groups)
    assert out[0] == out[2] == "a:X"
    assert len({out[1], out[3], out[4]}) == 3
    assert not {out[1], out[3], out[4]} & {"a:X"}


@pytest.mark.parametrize(
    ("n", "bucket"), [(0, "<80"), (79, "<80"), (80, "80-160"), (160, "80-160"), (161, ">160")]
)
def test_length_bucket_edges(n: int, bucket: str) -> None:
    assert length_bucket(n) == bucket


def test_most_frequent_ranks_by_token_count_and_can_keep_only_function_words() -> None:
    docs = [
        (["небо", "небо", "небо", "и", "и"], ["NOUN", "NOUN", "NOUN", "CCONJ", "CCONJ"]),
        (["в", "небо", "так"], ["ADP", "NOUN", "ADV"]),
    ]
    assert most_frequent(docs, 2, function_only=False) == ["небо", "и"]
    assert most_frequent(docs, 5, function_only=True) == ["и", "в", "так"]


def test_relative_frequencies_divide_by_song_length_and_ignore_other_words() -> None:
    freqs = relative_frequencies([["и", "и", "небо", "в"], []], ["и", "в"])
    np.testing.assert_allclose(freqs, [[0.5, 0.25], [0.0, 0.0]])


def test_most_frequent_words_learns_its_vocabulary_from_fit_data_only() -> None:
    train = [{"lemmas": ["а", "а", "б"], "pos": ["CCONJ", "CCONJ", "ADP"]}]
    test = [{"lemmas": ["в", "в", "а"], "pos": ["ADP", "ADP", "CCONJ"]}]
    mfw = MostFrequentWords(n_words=2, function_only=True).fit(train)
    assert mfw.vocabulary_ == ["а", "б"]
    np.testing.assert_allclose(mfw.transform(test), [[1 / 3, 0.0]])


def test_delta_is_mean_absolute_difference_of_z_scores() -> None:
    z = np.array([[1.0, -1.0], [0.0, 2.0]])
    centroids = np.array([[0.0, 0.0], [1.0, 1.0]])
    np.testing.assert_allclose(delta_distances(z, centroids), [[1.0, 1.0], [1.0, 1.0]])
    np.testing.assert_allclose(delta_distances(z[:1], centroids[:1] + 3), [[3.0]])


def test_delta_classifier_standardizes_on_training_texts_and_picks_nearest_author() -> None:
    # Second feature has a huge scale; without z-scores it would decide alone.
    x = np.array([[0.10, 100.0], [0.12, 300.0], [0.50, 110.0], [0.52, 290.0]])
    y = np.array(["A", "A", "B", "B"])
    clf = DeltaClassifier().fit(x, y)
    np.testing.assert_allclose(clf.mean_, x.mean(axis=0))
    np.testing.assert_allclose(clf.scale_, x.std(axis=0))
    assert list(clf.predict(np.array([[0.11, 290.0], [0.49, 100.0]]))) == ["A", "B"]


def test_delta_classifier_tolerates_a_constant_feature() -> None:
    x = np.array([[0.0, 1.0], [0.0, 2.0]])
    clf = DeltaClassifier().fit(x, np.array(["A", "B"]))
    assert list(clf.predict(np.array([[0.0, 1.9]]))) == ["B"]


def test_letters_only_drops_transcription_habits_of_the_source_site() -> None:
    # Punctuation, «ё» and dash style differ by lyrics site, i.e. by artist, not by author.
    assert letters_only("Ёлки — палки;\nКто-то «там»…") == "елки палки кто то там"
