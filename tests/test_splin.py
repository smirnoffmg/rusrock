from rusrock.parsers import Song
from rusrock.sites.splin import (
    Album,
    albums_tsv,
    clean_title,
    parse_album_index,
    parse_album_page,
)

BASE = "https://splean.ru"

ALBUM_INDEX = """
<html><body><div class="content"><table class="albums__table">
<tr><td colspan="3"><div class="albums__album">
<div class="albums__album-image"><a href="/music/album/33/"><img src="/x.png"/></a></div>
<div class="albums__album-title"><div class="albums__container">
<h2><a href="/music/album/33/">Новый сингл</a></h2>
<span class="albums__copyright">Сплин, 2025</span>
</div></div></div></td></tr>
<tr><td colspan="3"><div class="albums__album">
<div class="albums__album-title"><div class="albums__container">
<h2><a href="/music/album/2/">Первый альбом</a></h2>
<span class="albums__copyright">Navigator Records, 1994</span>
</div></div></div></td></tr>
</table></div></body></html>
"""

ALBUM_PAGE = """
<html><body><div class="content">
<table class="albums__table"><tr><td><div class="albums__container">
<h2><a href="/music/album/2/">Первый альбом</a></h2>
<span class="albums__copyright">Navigator Records, 1994</span>
</div></td></tr></table>
<table class="songs-table">
<tr><td class="songs-table__td-song">
<a class="songs-table__show-lyrics" href="#">01. Первая песня</a>
<div class="songs-table__lyrics none">
<p>Строка первая <br/>Строка вторая<br/><br/><span>Строка третья</span><br/></p>
</div></td>
<td class="songs-table__td-buy"><a class="albums__buy-link-song" href="#">Купить</a></td></tr>
<tr><td class="songs-table__td-song">
<a class="songs-table__show-lyrics" href="#">Чужая</a>
<div class="songs-table__lyrics none">
<p>(Стихи И. Иванова)<br/>Строка чужая<br/>Ещё строка</p>
</div></td></tr>
<tr><td class="songs-table__td-song">
<a class="songs-table__show-lyrics" href="#">Подаренная</a>
<div class="songs-table__lyrics none">
<p>Строка подаренная<br/><br/>Автор текста - Петрова Анна<br/></p>
</div></td></tr>
<tr><td class="songs-table__td-song">
<a class="songs-table__show-lyrics" href="#">Слова песни</a>
<div class="songs-table__lyrics none">
<p>Слова, что сказаны<br/>Строка последняя</p>
</div></td></tr>
<tr><td class="songs-table__td-song">
<a class="songs-table__show-lyrics" href="#">Тишина</a>
<div class="songs-table__lyrics none"><p>.</p></div></td></tr>
</table></div></body></html>
"""

URL = f"{BASE}/music/album/2/"


def test_album_index_reads_title_year_and_url() -> None:
    assert parse_album_index(ALBUM_INDEX, base=BASE) == [
        Album("Новый сингл", 2025, f"{BASE}/music/album/33/"),
        Album("Первый альбом", 1994, f"{BASE}/music/album/2/"),
    ]


def test_album_page_reads_br_lines_and_album_title() -> None:
    songs = parse_album_page(ALBUM_PAGE, url=URL)
    assert songs[0] == Song(
        source="splean.ru",
        title="Первая песня",
        album="Первый альбом",
        credit="",
        lyricist="",
        text="Строка первая\nСтрока вторая\n\nСтрока третья",
        url=URL,
    )


def test_credit_line_at_start_moves_to_credit_and_lyricist() -> None:
    song = parse_album_page(ALBUM_PAGE, url=URL)[1]
    assert song.credit == "Стихи И. Иванова"
    assert song.lyricist == "И. Иванова"
    assert song.text == "Строка чужая\nЕщё строка"


def test_credit_line_at_end_moves_to_credit_and_lyricist() -> None:
    song = parse_album_page(ALBUM_PAGE, url=URL)[2]
    assert song.credit == "Автор текста - Петрова Анна"
    assert song.lyricist == "Петрова Анна"
    assert song.text == "Строка подаренная"


def test_lyric_line_starting_with_word_slova_is_not_a_credit() -> None:
    song = parse_album_page(ALBUM_PAGE, url=URL)[3]
    assert song.credit == ""
    assert song.text == "Слова, что сказаны\nСтрока последняя"


def test_dot_placeholder_becomes_empty_text() -> None:
    assert parse_album_page(ALBUM_PAGE, url=URL)[4].text == ""


def test_clean_title_strips_track_number_and_year() -> None:
    assert clean_title("02. Песня") == ("Песня", "")
    assert clean_title("Песня (1996)") == ("Песня", "")
    assert clean_title("Песня (Другое название) (1995)") == ("Песня (Другое название)", "")


def test_clean_title_moves_author_in_parentheses_to_credit() -> None:
    assert clean_title("Песня (И.Иванов)") == ("Песня", "И.Иванов")
    assert clean_title("Песня (Б.Г.)") == ("Песня", "Б.Г.")
    assert clean_title("Песня (стихи - Н.Петров)") == ("Песня", "стихи - Н.Петров")
    assert clean_title("Песня (первый снег)") == ("Песня (первый снег)", "")


def test_title_credit_names_words_author_only_for_stikhi() -> None:
    html = ALBUM_PAGE.replace("01. Первая песня", "Песня (стихи - Н.Петров)")
    song = parse_album_page(html, url=URL)[0]
    assert (song.title, song.credit, song.lyricist) == ("Песня", "стихи - Н.Петров", "Н.Петров")
    html = ALBUM_PAGE.replace("01. Первая песня", "Песня (И.Иванов)")
    song = parse_album_page(html, url=URL)[0]
    assert (song.credit, song.lyricist) == ("И.Иванов", "")


def test_album_page_without_track_table_gives_no_songs() -> None:
    assert parse_album_page("<html><body><h2>Пусто</h2></body></html>", url=URL) == []


def test_albums_tsv_uses_kind_table_and_marks_unknown_as_other() -> None:
    albums = [Album("Первый альбом", 1994, "u1"), Album("Неизвестный", 2000, "u2")]
    tsv = albums_tsv(albums, {"Первый альбом": "studio"}, header="# источник")
    assert tsv == (
        "# источник\nalbum\tyear\tkind\nПервый альбом\t1994\tstudio\nНеизвестный\t2000\tother\n"
    )
