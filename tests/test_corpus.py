from rusrock.corpus import dedupe, normalize_person, normalize_title
from rusrock.parsers import Song


def song(title: str, album: str, text: str = "т") -> Song:
    return Song(
        source="s",
        title=title,
        album=album,
        credit="",
        lyricist="И. Кормильцев",
        text=text,
        url="u",
    )


def test_title_variants_collapse_to_one_key() -> None:
    assert normalize_title("Кто ещё...") == normalize_title("кто ещё")
    assert normalize_title("Кто я?") == normalize_title("Кто  я")
    assert normalize_title("Кто ещё") != normalize_title("Кто я")


def test_person_initials_get_one_spacing() -> None:
    assert normalize_person("И.Кормильцев") == "И. Кормильцев"
    assert normalize_person("И. Кормильцев") == "И. Кормильцев"
    assert normalize_person(" Е.Летов ") == "Е. Летов"


def test_dedupe_keeps_best_ranked_text_and_lists_every_album() -> None:
    rank = {"Студийный": 0, "Концерт": 1}
    merged = dedupe(
        [
            song("Песня", "Концерт", text="живьём"),
            song("песня...", "Студийный", text="студия"),
            song("Другая", "Концерт"),
        ],
        rank=lambda s: (rank[s.album],),
    )
    assert [(m.song.title, m.song.text, m.albums) for m in merged] == [
        ("песня...", "студия", ("Концерт", "Студийный")),
        ("Другая", "т", ("Концерт",)),
    ]
