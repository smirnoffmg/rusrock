from rusrock.parsers import Song
from rusrock.sites.piknik import (
    Album,
    albums_tsv,
    parse_album_index,
    parse_album_page,
    parse_song,
    parse_songs_listing,
)

BASE = "https://www.piknik.info"

ALBUM_INDEX = """
<html><body>
<section class="albums__popular"><div class="container">
<div class="albums__popular__element audio-track">
<a href="/albums/view/id/41"><img alt="" src="/x.jpg"/></a>
<a href="/albums/view/id/41">Новый альбом</a>
<span class="date">2026</span><p>2 песен</p>
</div>
</div></section>
<section class="albums__regular">
<span class="title">Официальная дискография - <strong>2001-2023</strong></span>
<div class="row albums__regular__list">
<div class="albums__regular__element audio-track">
<a href="/albums/view/id/41"><img alt="" src="/x.jpg"/></a>
<a href="/albums/view/id/41">Новый альбом</a>
<span class="date">2026</span><p>2 песен</p>
</div>
</div></section>
<section class="albums__regular">
<span class="title">Официальная дискография - <strong>1980-1989</strong></span>
<div class="row albums__regular__list">
<div class="albums__regular__element audio-track">
<a href="/albums/view/id/1"><img alt="" src="/y.jpg"/></a>
<a href="/albums/view/id/1">Старый альбом</a>
<span class="date">1982</span><p>8 песен</p>
</div>
</div></section>
<section class="albums__regular">
<span class="title">Сборники и Синглы</span>
<div class="row albums__regular__list">
<div class="albums__regular__element audio-track">
<a href="/albums/view/id/38"><img alt="" src="/z.jpg"/></a>
<a href="/albums/view/id/38">Песенка (Сингл)</a>
<span class="date">2020</span><p>1 песен</p>
</div>
<div class="albums__regular__element audio-track">
<a href="/albums/view/id/37"><img alt="" src="/w.jpg"/></a>
<a href="/albums/view/id/37">Лучшее (Избранное 1982 - 2012)</a>
<span class="date">2013</span><p>19 песен</p>
</div>
</div></section>
</body></html>
"""

ALBUM_PAGE = """
<html><body><section class="albums-selected"><div class="container">
<h1>Старый альбом <span>1982</span></h1>
<div class="album-songs"><div class="playlist">
<div class="playlist__item"><span class="number">1.</span><a class="play" href="#"></a>
<a class="name" href="/lyrics/index/song/2">Вторая</a><span class="time-left">7:00</span></div>
<div class="playlist__item"><span class="number">2.</span><a class="play" href="#"></a>
<a class="name" href="/lyrics/index/song/1">Первая</a><span class="time-left">5:15</span></div>
</div></div>
</div></section></body></html>
"""

SONGS_LISTING = """
<html><body>
<section class="song"><div class="song__controls"><a href="/lyrics/index/song/99">Предыдущая песня</a></div></section>
<section class="albums-list"><div class="albums-list__element">
<div class="title"><span>Старый альбом</span><span class="year">(1982)</span></div>
<ul>
<li class="top"><a href="/lyrics/index/song/2">Вторая</a></li>
<li><a href="/lyrics/index/song/1">Первая</a></li>
<!--li ><a href="#">Потерянный</a></li-->
</ul></div>
<div class="albums-list__element">
<div class="title"><span>Старый альбом</span><span class="year">(1982)</span></div>
<ul><li><a href="/lyrics/index/song/2">Вторая</a></li></ul></div>
</section></body></html>
"""

SONG_PAGE = """
<html><body><section class="song"><div class="container">
<div class="song__controls song__controls--previous">
<span class="album">Другой альбом</span><span>Соседняя</span>
<a href="/lyrics/index/song/1">Предыдущая песня</a></div>
<div class="song__content">
<h1>Вторая</h1>
<div class="text">
                <p>
                    Строка первая<br>
Строка вторая &mdash; с тире<br>
<br>
Строка третья<br>
                </p>
            </div>
<a class="download" href="https://band.link/x">Слушать песню</a>
<div class="author">
</div>
<div class="song-album">
<a href="/albums/view/id/1">представлено в альбоме «Старый альбом»</a>
<a href="/albums/view/id/1"><img alt="" src="/y.jpg"/></a>
</div>
</div>
<div class="song__controls song__controls--next">
<span class="album">Старый альбом</span><span>Третья</span>
<a href="/lyrics/index/song/3">Следущая песня</a></div>
</div></section></body></html>
"""

SONG_WITH_AUTHOR = """
<html><body><section class="song"><div class="song__content">
<h1>Чужая</h1>
<div class="text"><p>Одна строка<br></p><p>Другой абзац</p></div>
<div class="author">Слова: И. Иванов</div>
</div></section></body></html>
"""


def test_album_index_reads_regular_sections_with_kind() -> None:
    assert parse_album_index(ALBUM_INDEX, base=BASE) == [
        Album("Новый альбом", 2026, "studio", f"{BASE}/albums/view/id/41"),
        Album("Старый альбом", 1982, "studio", f"{BASE}/albums/view/id/1"),
        Album("Песенка (Сингл)", 2020, "single", f"{BASE}/albums/view/id/38"),
        Album("Лучшее (Избранное 1982 - 2012)", 2013, "compilation", f"{BASE}/albums/view/id/37"),
    ]


def test_album_page_lists_track_urls_in_order() -> None:
    assert parse_album_page(ALBUM_PAGE, base=BASE) == [
        f"{BASE}/lyrics/index/song/2",
        f"{BASE}/lyrics/index/song/1",
    ]


def test_songs_listing_takes_album_lists_only_without_duplicates() -> None:
    assert parse_songs_listing(SONGS_LISTING, base=BASE) == [
        f"{BASE}/lyrics/index/song/2",
        f"{BASE}/lyrics/index/song/1",
    ]


def test_song_page_uses_album_link_and_br_lines() -> None:
    assert parse_song(SONG_PAGE, url="u") == Song(
        source="piknik.info",
        title="Вторая",
        album="Старый альбом",
        credit="",
        lyricist="",
        text="Строка первая\nСтрока вторая — с тире\n\nСтрока третья",
        url="u",
    )


def test_song_page_keeps_stated_credit_and_paragraph_breaks() -> None:
    song = parse_song(SONG_WITH_AUTHOR, url="u")
    assert song is not None
    assert song.album == ""
    assert song.credit == "Слова: И. Иванов"
    assert song.text == "Одна строка\n\nДругой абзац"


def test_song_page_without_text_is_skipped() -> None:
    assert parse_song("<html><body><h1>Пусто</h1></body></html>", url="u") is None


def test_albums_tsv_has_comment_header_and_rows() -> None:
    tsv = albums_tsv([Album("Старый альбом", 1982, "studio", "x")], header="# источник")
    assert tsv == "# источник\nalbum\tyear\tkind\nСтарый альбом\t1982\tstudio\n"


def test_instrumental_placeholder_becomes_empty_text() -> None:
    html = SONG_WITH_AUTHOR.replace(
        "<p>Одна строка<br></p><p>Другой абзац</p>", "<p>Инструментальная композиция</p>"
    )
    song = parse_song(html, url="u")
    assert song is not None
    assert song.text == ""


def test_deleted_song_page_with_empty_title_is_skipped() -> None:
    html = SONG_WITH_AUTHOR.replace("<h1>Чужая</h1>", "<h1></h1>")
    assert parse_song(html, url="u") is None
