from rusrock.parsers import Song
from rusrock.sites.auktyon import (
    find_track,
    parse_album,
    parse_index,
    parse_txt_song,
    parse_txt_song_index,
)

INDEX = """
<html><body><table><tr><td><font size=-1>
Большинство текстов написал <b>Первый Автор</b>, остальные - <b>Второй</b>.
</td></tr><tr><td valign=top><br><font size=-1><img src="/gif/transp.gif"><br>
<a href="/text/pervyj.html">Первый альбом 1986</a><br>
<a href="/text/vtoroj.html">Д'второй 1990</a><br>
<a href="/teksty.html">Тексты</a>
<a href="http://design.example.ru/">Design</a>
</td></tr></table></body></html>
"""

ALBUM = """
<html><body bgcolor="#ffdd00">
<map name="menu"><area shape=rect coords="1,1,2,2" href="/teksty.html"></map>
<center><table><tr><td>
<h2 align=left>ПЕРВЫЙ АЛЬБОМ</h2>

<table width=100% cellpadding=0 cellspacing=0 border=0><tr><td valign=top><font size=-1>
(<a href="/covers/x/">подробности</a> | <a href="/muzyka/x/">послушать</a>)
<p><br>
<b>Песня раз</b> (исп. Кто-то Другой)
<p>
Выдуманная строка один,<br>
Строка два &mdash; тоже.
<p>
Второй куплет,<br>
<i>пр:</i><br>
&nbsp;&nbsp;Выдуманный припев.<br>
пр.


<p><br>
<b>Стихи А. Поэта:</b>
<p>
Стих без названия,<br>
ещё строка.
<p><br>
<b>*  *  *</b>
<p>
Третий стих.
<p><br>
<b>Пустая</b>
<p>

<p><br>
<b>Наигрыш</b>
<p>
(инструментал)


</td></tr></table>
</td></tr></table>
<font style="font-size: 13px">
Design: <a href="http://design.example.ru/">Studio</a> &copy; 2000
</body></html>
"""


def test_index_lists_albums_with_urls_in_page_order() -> None:
    assert parse_index(INDEX, base="http://auktyon.ru/") == [
        ("Первый альбом", "http://auktyon.ru/text/pervyj.html"),
        ("Д'второй", "http://auktyon.ru/text/vtoroj.html"),
    ]


def test_album_page_yields_songs_and_skips_empty_and_instrumental() -> None:
    url = "http://auktyon.ru/text/pervyj.html"

    def song(title: str, credit: str, text: str) -> Song:
        return Song(
            source="auktyon.ru",
            title=title,
            album="Первый альбом",
            credit=credit,
            lyricist="",
            text=text,
            url=url,
        )

    assert parse_album(ALBUM, url=url, album="Первый альбом") == [
        song(
            "Песня раз",
            "",
            "Выдуманная строка один,\nСтрока два — тоже.\n\nВторой куплет,\nВыдуманный припев.",
        ),
        song("Стихи А. Поэта", "Стихи А. Поэта", "Стих без названия,\nещё строка."),
        song("*  *  *", "Стихи А. Поэта", "Третий стих."),
    ]


TXT_ARTIST = """
<html><body><div class="song-list">
<a href="/song/auktsyon-pervaya">Первая песня</a>
<a href="/song/auktsyon-vtoraya">Вторая, песня</a>
<a href="/song/auktsyon-pervaya-2">Первая песня</a>
<a href="/song/drugie-auktsyon-chuzhaya">Чужая</a>
<a href="/artist/auktsyon">АукцЫон</a>
</div></body></html>
"""

TXT_SONG = """
<html><body><article class="song-card"><h1>АукцЫон — Первая песня</h1>
<div class="song-meta"><span><b>Исполнитель:</b> <a href="/artist/auktsyon">АукцЫон</a></span></div>
<div class="lyrics" data-song-panel="lyrics" id="lyrics-text"><p>Выдуманная строка,<br/>
Ещё одна<br/>Третья    <p>Второй куплет   </p></p></div>
<div class="faq-list">Кто исполняет эту песню?</div>
</article></body></html>
"""


def test_txt_song_index_maps_title_keys_to_first_url() -> None:
    assert parse_txt_song_index(TXT_ARTIST, base="https://txt-song.ru/") == {
        "первая песня": "https://txt-song.ru/song/auktsyon-pervaya",
        "вторая песня": "https://txt-song.ru/song/auktsyon-vtoraya",
        "чужая": "https://txt-song.ru/song/drugie-auktsyon-chuzhaya",
    }


def test_find_track_falls_back_to_title_without_parenthetical() -> None:
    index = {"заведующий": "u1", "фа фа это мама": "u2"}
    assert find_track(index, "Заведующий (Копорье)") == "u1"
    assert find_track(index, "Фа-фа (Это мама)") == "u2"
    assert find_track(index, "Нет такой") is None


def test_txt_song_page_yields_song_with_album_from_tracklist() -> None:
    url = "https://txt-song.ru/song/auktsyon-pervaya"
    assert parse_txt_song(TXT_SONG, url=url, album="Альбом", title="Первая песня") == Song(
        source="txt-song.ru",
        title="Первая песня",
        album="Альбом",
        credit="",
        lyricist="",
        text="Выдуманная строка,\nЕщё одна\nТретья\n\nВторой куплет",
        url=url,
    )


def test_txt_song_page_without_lyrics_is_skipped() -> None:
    assert parse_txt_song("<html><body></body></html>", url="u", album="А", title="Т") is None
