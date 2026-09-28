from rusrock.freq import FUNCTION_POS, Row, frequency_table


def test_counts_occurrences_and_songs_separately() -> None:
    songs = [
        (["ночь", "ночь", "ночь", "город"], ["NOUN", "NOUN", "NOUN", "NOUN"]),
        (["город", "спать"], ["NOUN", "VERB"]),
    ]
    rows = {r.lemma: r for r in frequency_table(songs)}
    assert (rows["ночь"].f, rows["ночь"].df) == (3, 1)
    assert (rows["город"].f, rows["город"].df) == (2, 2)
    assert rows["спать"].ipm == 1_000_000 / 6


def test_rows_are_sorted_by_song_count_then_frequency() -> None:
    songs = [
        (["а", "а", "а", "б"], ["NOUN"] * 4),
        (["б", "в", "в"], ["NOUN"] * 3),
        (["в"], ["NOUN"]),
    ]
    assert [r.lemma for r in frequency_table(songs)] == ["в", "б", "а"]


def test_majority_part_of_speech_marks_function_words() -> None:
    songs = [(["на", "на", "на"], ["ADP", "ADP", "NOUN"])]
    [row] = frequency_table(songs)
    assert row == Row(lemma="на", pos="ADP", f=3, ipm=1_000_000.0, df=1, function=True)
    assert "ADP" in FUNCTION_POS and "NOUN" not in FUNCTION_POS


def test_pronominal_adverbs_and_particles_count_as_function_words() -> None:
    songs = [(["так", "нет", "быть", "небо"], ["ADV", "VERB", "VERB", "NOUN"])]
    rows = {r.lemma: r.function for r in frequency_table(songs)}
    assert rows == {"так": True, "нет": True, "быть": True, "небо": False}
