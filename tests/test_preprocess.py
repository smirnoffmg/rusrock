import pymorphy3
import pytest

from rusrock.preprocess import (
    clean_text,
    combine_lemma,
    is_word,
    lower_line_initials,
    normalize_lemma,
)


def test_chorus_and_interlude_markers_are_dropped() -> None:
    text = "Строка один\nПрипев:\nПрипев 2: *2\nПрипев:*3\nПроигрыш\nСтрока два"
    assert clean_text(text) == "Строка один\nСтрока два"


def test_chorus_prefix_before_lyrics_is_stripped() -> None:
    assert clean_text("Припев: и снова в путь") == "и снова в путь"


def test_speaker_labels_are_stripped_but_speech_is_kept() -> None:
    text = "Майк: сегодня он здесь\nБоб: а я там\nОна сказала: нет"
    assert clean_text(text) == "сегодня он здесь\nа я там\nОна сказала: нет"


def test_repeat_notes_are_removed() -> None:
    text = "мы здесь ( 2 раза )\nне надо - 2раза\nи так далее (и т.д.)\nещё раз (2 раза)"
    assert clean_text(text) == "мы здесь\nне надо\nи так далее\nещё раз"


def test_words_are_letters_with_inner_hyphens_or_apostrophes() -> None:
    assert is_word("кто-то")
    assert is_word("Rock'n'roll")
    assert not is_word("—")
    assert not is_word("1987")
    assert not is_word("...")


def test_lemma_normalization_folds_yo_and_case() -> None:
    assert normalize_lemma("Ещё") == "еще"


def test_latin_lookalikes_inside_cyrillic_words_become_cyrillic() -> None:
    assert clean_text("Меpтвые нe тлеют") == "Мертвые не тлеют"
    assert clean_text("Rock'n'roll и E-95") == "Rock'n'roll и E-95"


@pytest.fixture(scope="module")
def analyzer() -> pymorphy3.MorphAnalyzer:
    return pymorphy3.MorphAnalyzer()


@pytest.mark.parametrize(
    ("form", "natasha_lemma", "natasha_pos", "expected"),
    [
        ("их", "их", "DET", "они"),
        ("ее", "ее", "DET", "она"),
        ("страшно", "страшный", "ADJ", "страшно"),
        ("сильней", "сильней", "ADJ", "сильный"),
        ("раскрытых", "раскрыть", "VERB", "раскрытый"),
        ("вязнут", "вязнут", "VERB", "вязнуть"),
        ("горе", "горе", "NOUN", "горе"),
        ("пошли", "пойти", "VERB", "пойти"),
    ],
)
def test_combined_lemma_follows_agreed_conventions(
    analyzer: pymorphy3.MorphAnalyzer,
    form: str,
    natasha_lemma: str,
    natasha_pos: str,
    expected: str,
) -> None:
    assert combine_lemma(form, natasha_lemma, natasha_pos, analyzer.parse(form)) == expected


def test_line_initial_capital_is_lowered_unless_proper_name(
    analyzer: pymorphy3.MorphAnalyzer,
) -> None:
    text = "А снег идёт\nИван пришёл\n— И что?"
    assert lower_line_initials(text, analyzer) == "а снег идёт\nИван пришёл\n— и что?"


def test_latin_n_inside_rock_n_roll_becomes_cyrillic() -> None:
    assert clean_text("играй рок-n-ролл") == "играй рок-н-ролл"


def test_known_dictionary_errors_are_corrected(analyzer: pymorphy3.MorphAnalyzer) -> None:
    assert combine_lemma("далью", "далья", "NOUN", analyzer.parse("далью")) == "даль"


@pytest.mark.parametrize(
    "marker",
    [
        "Припев (2 раза):",
        "[Припев]",
        "[Припев]:",
        "Припев.",
        "ПРИПЕВ( Уматурман):",
        "Припев (2 раза).",
    ],
)
def test_chorus_marker_variants_are_dropped(marker: str) -> None:
    assert clean_text(f"строка\n{marker}\nещё строка") == "строка\nещё строка"


def test_lyrics_mentioning_a_chorus_are_kept() -> None:
    line = "Мы споём этот припев вдвоём"
    assert clean_text(line) == line
