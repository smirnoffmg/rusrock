from rusrock.parsers import Song
from rusrock.sites.delfin import (
    Album,
    Track,
    albums_tsv,
    clean_title,
    parse_album_index,
    parse_album_page,
    parse_song,
    words_author,
)

BASE = "https://dolphinfanclub.net"

ALBUM_INDEX = """
<html><body><div id="middleColumn"><article>
<h1>Дискография</h1>
<div class="albums-list">
<div class="floatLeft disco-album">
<div class="disco-cover"><a href="/discography/novyj-singl"><img src="/a.jpg"></a></div>
<div class="disco-title">
<a href="/discography/novyj-singl">Новый - Single</a>
<br>(2024)
</div></div>
<div class="floatLeft disco-album">
<div class="disco-cover"><a href="/discography/pervyj"><img src="/b.jpg"></a></div>
<div class="disco-title">
<a href="/discography/pervyj">ПЕРВЫЙ АЛЬБОМ </a>
<br>(1997)
</div></div>
<div class="floatLeft disco-album">
<div class="disco-cover"><a href="/discography/raznoe"><img src="/c.jpg"></a></div>
<div class="disco-title">
<a href="/discography/raznoe">Разное</a>
</div></div>
</div>
</article></div></body></html>
"""

ALBUM_PAGE = """
<html><body><div id="middleColumn"><article>
<div class="disco-tracklist">
<div class="disco-title"><h1>Первый альбом <span class="small">(1997)</span></h1></div>
01.
<a href="/discography/pervyj/nachalo">Начало</a>
<br>
02.
Чужая группа - Чужая песня
<br>
03.
<a href="/discography/pervyj/vdvoem">Вдвоём (музыка и слова Дельфина и Гостьи Примерной)</a>
<br>
04.
<a href="/discography/pervyj/odin">Один (музыка и слова Дельфина)</a>
<br>
05.
<a href="/discography/pervyj/nachalo">Начало</a>
<br>
</div>
</article></div></body></html>
"""

SONG_PAGE = """
<html><body><div id="middleColumn">
<div class="floatRight"><p>Поделиться:</p></div>
<div class="disco-cover"><a href="/x.jpg"><img alt="Первый альбом" src="/x.jpg"></a></div>
<div class="disco-title">
<h2>
    Первый альбом
</h2>
<span class="small">(1997)</span>
</div>
<h1>
    Начало
</h1>
<div class="songLyrics">
<p>
    Строка первая выдумана тут<br>
    строка вторая
    тоже выдумана<br>
</p>

<p>
    Припев придуманный для теста
</p>
</div>
<p class="back">&larr; <a href="/discography/pervyj">Назад к альбому</a></p>
</div></body></html>
"""

EMPTY_SONG_PAGE = """
<html><body><div id="middleColumn">
<div class="disco-title"><h2>Первый альбом</h2></div>
<h1>Трек 1</h1>
<div class="songLyrics">
</div>
</div></body></html>
"""


def test_parse_album_index_reads_title_year_and_slug() -> None:
    assert parse_album_index(ALBUM_INDEX, base=BASE) == [
        Album("Новый - Single", 2024, "novyj-singl", f"{BASE}/discography/novyj-singl"),
        Album("ПЕРВЫЙ АЛЬБОМ", 1997, "pervyj", f"{BASE}/discography/pervyj"),
        Album("Разное", None, "raznoe", f"{BASE}/discography/raznoe"),
    ]


def test_parse_album_page_keeps_linked_tracks_once_with_credit() -> None:
    assert parse_album_page(ALBUM_PAGE, base=BASE) == [
        Track(f"{BASE}/discography/pervyj/nachalo", ""),
        Track(
            f"{BASE}/discography/pervyj/vdvoem",
            "музыка и слова Дельфина и Гостьи Примерной",
        ),
        Track(f"{BASE}/discography/pervyj/odin", "музыка и слова Дельфина"),
    ]


def test_words_author_maps_sole_pseudonym_to_real_name() -> None:
    assert words_author("музыка и слова Дельфина") == "Дельфин (Андрей Лысиков)"
    assert words_author("музыка и слова Дельфина и Гостьи Примерной") == (
        "Дельфина и Гостьи Примерной"
    )
    assert words_author("") == ""


def test_parse_song_joins_br_lines_and_paragraphs() -> None:
    url = f"{BASE}/discography/pervyj/nachalo"
    assert parse_song(SONG_PAGE, url=url, credit="") == Song(
        source="dolphinfanclub.net",
        title="Начало",
        album="Первый альбом",
        credit="",
        lyricist="",
        text=(
            "Строка первая выдумана тут\nстрока вторая тоже выдумана\n\n"
            "Припев придуманный для теста"
        ),
        url=url,
    )


def test_parse_song_passes_credit_to_lyricist() -> None:
    song = parse_song(SONG_PAGE, url="u", credit="музыка и слова Дельфина")
    assert song is not None
    assert song.credit == "музыка и слова Дельфина"
    assert song.lyricist == "Дельфин (Андрей Лысиков)"


def test_parse_song_keeps_empty_text_for_instrumental() -> None:
    song = parse_song(EMPTY_SONG_PAGE, url="u", credit="")
    assert song is not None
    assert song.text == ""


def test_parse_song_without_title_is_none() -> None:
    assert parse_song("<html><body></body></html>", url="u", credit="") is None


def test_albums_tsv_writes_header_and_kinds() -> None:
    rows = [("Первый альбом", 1997, "studio"), ("Разное", None, "other")]
    assert albums_tsv(rows, "# header") == (
        "# header\nalbum\tyear\tkind\nПервый альбом\t1997\tstudio\nРазное\t\tother\n"
    )


def test_clean_title_drops_performer_credit_and_version_marks() -> None:
    assert clean_title("Один (музыка и слова Дельфина)") == "Один"
    assert clean_title("Дельфин - Начало") == "Начало"
    assert clean_title("Dolphin - Начало") == "Начало"
    assert clean_title("Bonus track (Начало)") == "Начало"
    assert clean_title("Начало (Radio edit)") == "Начало"
    assert clean_title("Начало (Global mix)") == "Начало"
    assert clean_title("Начало (радиоверсия)") == "Начало"
    assert clean_title("Начало (полная первая версия)") == "Начало"
    assert clean_title("Начало remix by someone") == "Начало"
    assert clean_title("Гость - Начало [dolphin mix]") == "Гость - Начало"
    assert clean_title("Начало (2009)") == "Начало"


def test_clean_title_keeps_collaborations_and_plain_titles() -> None:
    assert clean_title("Дельфин и Гость - Начало") == "Дельфин и Гость - Начало"
    assert clean_title("Bonus Track") == "Bonus Track"
    assert clean_title("Ты (Суп)") == "Ты (Суп)"


def test_parse_song_cleans_title_from_heading() -> None:
    html = SONG_PAGE.replace("    Начало\n</h1>", "    Дельфин - Начало (Radio edit)\n</h1>")
    song = parse_song(html, url="u", credit="")
    assert song is not None
    assert song.title == "Начало"
