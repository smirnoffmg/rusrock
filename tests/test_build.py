from pathlib import Path

from rusrock.build import Candidate, is_instrumental, merge_versions, resolve_author, title_key


def test_explicit_sole_main_lyricist_is_accepted_in_any_spelling() -> None:
    assert resolve_author("К.Кинчев", "А.Шаталин - К.Кинчев", "Кинчев", default_to_main=True)
    assert resolve_author("Игорь Летов", "Игорь Летов", "Летов", default_to_main=False)


def test_coauthored_or_foreign_lyricist_is_rejected() -> None:
    assert not resolve_author("К.Кинчев, П.Самойлов", "", "Кинчев", default_to_main=True)
    assert not resolve_author("Е.Летов/К.Уо", "", "Летов", default_to_main=False)
    assert not resolve_author("И. Кормильцев, Е. Аникина", "", "Кормильцев", default_to_main=False)
    assert not resolve_author("А. Гуницкий", "", "Гребенщиков", default_to_main=True)


def test_missing_lyricist_falls_back_to_credit_then_default() -> None:
    assert resolve_author("", "К.Кинчев", "Кинчев", default_to_main=True)
    assert not resolve_author("", "В.Задерий", "Кинчев", default_to_main=True)
    assert resolve_author("", "", "Шклярский", default_to_main=True)
    assert not resolve_author("", "", "Кормильцев", default_to_main=False)


def test_ddt_generic_author_credit_counts_as_main() -> None:
    credit = "Шевчук Ю. - вокал, ак. гитара, автор"
    assert resolve_author("", credit, "Шевчук", default_to_main=True)


def test_title_key_ignores_case_yo_punctuation_and_latin_lookalikes() -> None:
    assert title_key("Ария Мистера X") == title_key("ария мистера Х")
    assert title_key("Ёлка...") == title_key("елка")
    assert title_key("Кто я?") == title_key("кто я")


def test_instrumental_markers_and_stubs_are_detected() -> None:
    assert is_instrumental("")
    assert is_instrumental("(инструментал)")
    assert is_instrumental("Инструментальная композиция")
    assert is_instrumental("(текст временно отсутствует)")
    assert is_instrumental("-")
    assert not is_instrumental("раз два три четыре пять шесть семь восемь девять десять")


def candidate(album: str, rank: int, accepted: bool) -> Candidate:
    return Candidate(title="Песня", album=album, rank=(rank,), accepted=accepted, payload=album)


def test_version_with_foreign_credit_vetoes_the_whole_song() -> None:
    merged = merge_versions([candidate("A", 0, True), candidate("B", 1, False)])
    assert merged is None


def test_best_ranked_version_wins_and_albums_are_collected() -> None:
    merged = merge_versions([candidate("Live", 2, True), candidate("Studio", 0, True)])
    assert merged is not None
    assert merged.best.album == "Studio"
    assert merged.albums == ("Live", "Studio")


def test_names_joined_by_bare_hyphen_or_dash_are_coauthors() -> None:
    assert not resolve_author("Е.Летов-К.Рябинов", "", "Летов", default_to_main=False)
    assert not resolve_author("Е. Летов — О. Судаков", "", "Летов", default_to_main=False)
    assert not resolve_author("К.Уо-Е.Летов", "", "Летов", default_to_main=False)


def test_mostly_latin_text_is_foreign() -> None:
    from rusrock.build import is_foreign

    assert is_foreign("I walk the line tonight\nand the radio plays")
    assert not is_foreign("Мы ждём перемен, мы ждём перемен\nИ снова играет наш rock'n'roll")


def test_song_album_table_overrides_scraped_album_year_and_group(tmp_path: Path) -> None:
    from rusrock.build import Artist, build_artist
    from rusrock.parsers import Song

    (tmp_path / "x_albums.tsv").write_text(
        "page\talbum\tyear\tkind\np\tПоздний концерт\t1999\tlive\n", encoding="utf-8"
    )
    (tmp_path / "x_song_albums.tsv").write_text(
        "# synthetic\ntitle\talbum\tyear\tnote\nПервая песня!\tРанний альбом\t1982\t\n",
        encoding="utf-8",
    )
    text = "раз два три четыре пять шесть семь восемь девять"
    songs = [
        Song("s", "Первая песня", "Поздний концерт", "", "", text, "u1"),
        Song("s", "Вторая песня", "Поздний концерт", "", "", text, "u2"),
    ]
    corpus = {
        s.title: s for s in build_artist(Artist("x", "Автор", "Автор", True), songs, tmp_path)
    }
    first, second = corpus["Первая песня"], corpus["Вторая песня"]
    assert (first.album, first.year, first.group) == ("Ранний альбом", 1982, "x:Ранний альбом")
    assert (second.album, second.year, second.group) == (
        "Поздний концерт",
        1999,
        "x:Поздний концерт",
    )
