from rusrock.parsers import Song
from rusrock.sites.uma2rman import (
    drop_held_out,
    find_track,
    parse_index,
    parse_song,
    scrape,
)

BASE = "https://www.pesni.net/"

INDEX = """
<html><body><div class="container py-4">
<h1>Тексты песен Группа</h1>
<div class="card mb-3"><div class="list-group list-group-flush song-list">
<a class="list-group-item list-group-item-action" href="/text/gruppa/pervaya">Первая песня</a>
<a class="list-group-item list-group-item-action" href="/text/gruppa/vtoraya">Вторая 1</a>
<a class="list-group-item list-group-item-action" href="/text/gruppa/tretya-ost">Третья (OST Кино)</a>
<a class="list-group-item list-group-item-action" href="/text/gruppa/opechatka">Он прийдет</a>
<a class="list-group-item list-group-item-action" href="/text/gruppa/happy">Happy</a>
<a class="list-group-item list-group-item-action" href="/text/gruppa/pervaya-dubl">Первая песня</a>
</div></div>
<div class="top-songs"><a href="/text/drugoy/chuzhaya">Чужая</a></div>
</div></body></html>
"""

SONG = """
<html><body><div class="song-page">
<h1>Текст песни <a class="song-page-artist" href="/text/gruppa">Группа</a> - Первая</h1>
<div class="oes2">Здесь вы найдете слова песни.</div>
<div class="song-block-text">
Выдуманная строка раз<br>
  Выдуманная строка два<br>
<br>
Третья строка<br>
</div>
<div class="song-meaning"><h2>О чём эта песня</h2></div>
</div></body></html>
"""

EMPTY_SONG = '<html><body><div class="song-block-text"> <br> </div></body></html>'


def test_index_maps_title_keys_to_urls_of_the_artist_only() -> None:
    index = parse_index(INDEX, base=BASE)
    assert index["первая песня"] == f"{BASE}text/gruppa/pervaya"
    assert "чужая" not in index


def test_index_drops_trailing_duplicate_counter() -> None:
    assert parse_index(INDEX, base=BASE)["вторая"] == f"{BASE}text/gruppa/vtoraya"


def test_index_fixes_known_misspelled_titles() -> None:
    assert parse_index(INDEX, base=BASE)["он придет"] == f"{BASE}text/gruppa/opechatka"


def test_index_maps_latin_title_to_russian_track_title() -> None:
    assert find_track(parse_index(INDEX, base=BASE), "Хэппи") == f"{BASE}text/gruppa/happy"


def test_find_track_falls_back_to_title_without_parentheses() -> None:
    index = parse_index(INDEX, base=BASE)
    assert find_track(index, "Третья") == f"{BASE}text/gruppa/tretya-ost"
    assert find_track(index, "Он придёт") == f"{BASE}text/gruppa/opechatka"
    assert find_track(index, "Нет такой") is None


def test_song_reads_br_lines() -> None:
    url = f"{BASE}text/gruppa/pervaya"
    assert parse_song(SONG, url, album="Альбом", title="Первая") == Song(
        source="pesni.net",
        title="Первая",
        album="Альбом",
        credit="",
        lyricist="",
        text="Выдуманная строка раз\nВыдуманная строка два\n\nТретья строка",
        url=url,
    )


def test_song_without_text_is_none() -> None:
    assert parse_song(EMPTY_SONG, "u", album="А", title="Т") is None


def _song(title: str) -> Song:
    return Song("pesni.net", title, "А", "", "", "строка", "u")


def test_held_out_text_is_dropped_under_any_title_variant() -> None:
    songs = [
        _song("Липкий пульс"),
        _song("ЛИПКИЙ ПУЛЬС (feat. Кто-то)"),
        _song("Липкий Пульс"),
        _song("Symbol & Uma2rman - Другая"),
        _song("Своя песня"),
    ]
    assert [s.title for s in drop_held_out(songs)] == ["Своя песня"]


def test_scrape_follows_release_tracklists_and_skips_missing_tracks() -> None:
    pages = {
        f"{BASE}text/umaturman": INDEX,
        f"{BASE}text/uma2rman": "<html></html>",
        f"{BASE}text/gruppa/pervaya": SONG,
        f"{BASE}text/gruppa/tretya-ost": SONG,
    }
    releases = (
        ("Альбом", ("Первая песня", "Нет такой")),
        ("Сингл", ("Третья", "Липкий пульс")),
    )
    songs = scrape(lambda url, encoding: pages[url], releases=releases)
    assert [(s.album, s.title) for s in songs] == [("Альбом", "Первая песня"), ("Сингл", "Третья")]
