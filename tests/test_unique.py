from rusrock.unique import sampled_unique_counts, unique_lemmas


def test_unique_lemmas_belong_to_one_author_and_occur_in_two_of_their_songs() -> None:
    corpus = {
        "A": [["небо", "небо", "город"], ["небо", "река"], ["опечатка"]],
        "B": [["город"], ["город", "поле"], ["поле"]],
    }
    unique = unique_lemmas(corpus, function=frozenset())
    assert {lemma: (row.df, row.f) for lemma, row in unique["A"].items()} == {"небо": (2, 3)}
    assert set(unique["B"]) == {"поле"}


def test_function_words_are_never_unique() -> None:
    corpus = {"A": [["ибо"], ["ибо"]], "B": [["поле"], ["поле"]]}
    unique = unique_lemmas(corpus, function=frozenset({"ибо"}))
    assert unique["A"] == {}
    assert set(unique["B"]) == {"поле"}


def test_unique_lemmas_are_ranked_by_songs_then_frequency() -> None:
    corpus = {
        "A": [["x", "y", "y", "z"], ["x", "y", "z"], ["x", "z", "z"]],
        "B": [["q"]],
    }
    assert list(unique_lemmas(corpus, function=frozenset())["A"]) == ["z", "x", "y"]


def test_sampled_counts_compare_authors_on_equal_samples() -> None:
    # A has twice as much text of the same kind as B; on equal samples they tie.
    corpus = {
        "A": [["a1", "общее"], ["a1", "общее"]] * 2,
        "B": [["b1", "общее"], ["b1", "общее"]],
    }
    counts = sampled_unique_counts(corpus, n=4, reps=10, seed=0, function=frozenset())
    assert counts == {"A": (1.0, 0.0), "B": (1.0, 0.0)}
