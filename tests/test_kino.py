from rusrock.sites.kino import (
    Album,
    choose_album,
    is_chord_line,
    parse_index,
    parse_lyrics,
    parse_tracklist,
    pick_lyricist,
    title_key,
)

INDEX = """
<html><body>
<p><a href="../index.htm">ГЛАВНАЯ</a></p>
<table>
  <tr><td>№</td><td>Название песни</td><td>аккорды</td></tr>
  <tr><td>1.</td><td>
    <p style="margin-top: 0; margin-bottom: 0">&nbsp;</p>
    <p style="margin-top: 0; margin-bottom: 0"><a href="t1.htm">Первая
    песня</a></p></td><td><p>есть</td></tr>
  <tr><td>2.</td><td><p><a href="t2.htm">Вторая, песня</a></p></td><td><p>есть</td></tr>
  <tr><td>3.</td><td><p><a href="t1.htm">Первая песня</a></p></td><td></td></tr>
</table>
<a href="kinodisk.htm">ДИСКОГРАФИЯ</a>
</body></html>
"""

SONG_LINES_AS_PARAGRAPHS = """
<html><head><title>КиношниК->Первая песня</title></head>
<body bgcolor="#000000">
<p align="left"><a href="index.htm"><font size="1">Главная</font></a></p>
<p align="left"><a href="kinotext.htm"><font size="1">Назад</font></a></p>
<p align="center"><font size="1">&nbsp;</font></p>
<p align="center">
<font style="font-size: 8pt">Первая песня</font></p>
<p align="center">
<font style="font-size: 8pt">-----------------------------------------------------------</font></p>
<p align="center">
<font style="font-size: 8pt">Строка раз,</font></p>
<p align="center">
<font style="font-size: 8pt">Строка два.</font><span style="font-size: 8pt">
</span> </p>
<p align="center">&nbsp;</p>
<p align="center">
<font style="font-size: 8pt">Am&nbsp;&nbsp;&nbsp; C#m7&nbsp; F/G</font></p>
<p align="center">
<font style="font-size: 8pt">Припев: строка три</font></p>
<p align="center">&nbsp;</p>
<p align="center">&nbsp;</p>
<p align="center">
<font style="font-size: 8pt">Аккорды:</font></p>
<p align="center">1-e||--1-0-----|</p>
<p align="center">C&nbsp;&nbsp;&nbsp;&nbsp;\r\nAm</p>
<p align="center">Строка раз,</p>
<h3>Карта сайта</h3>
<p>)- Главная страница...</p>
</body></html>
"""

SONG_LINES_AS_BREAKS = """
<html><body>
<br><font size="1"></font>
<p align="center"><font size="2">Вторая песня<br>
-----------------------------------------------------<br>
Слово один.<br>
H7&nbsp; Hm<br>
Слово два.<br>
<br>
Слово три.<br>
</font></p>
<br><br>
<p align="center">Аккорды:</p>
<p align="center">Am G Слово один.</p>
<p align="right">Табы: Кто-то ( nobody@example.org )</p>
<h3>Карта сайта</h3>
</body></html>
"""

SONG_WITHOUT_TEXT = """
<html><body><p>Главная</p><p>Назад</p><p>Нет текста</p><h3>Карта сайта</h3></body></html>
"""

ALBUM_WITH_DURATIONS = """
<html><body>
<p class="MsoNormal" align="left"><a href="index.htm">Главная</a></p>
<p align="right"><span>&quot;Альбом&quot;, 1988</span></p>
<p align="right"><span>Записано в 1986-88 годах<br>Звукорежиссер - Некто</span></p>
<p align="left" style="margin-top: 0; margin-bottom: 0"><b><font
face="Book Antiqua"><span style="font-size: 10.0pt">1.
Первая песня 4:46</span></font></b></p>
<p align="left" style="margin-top: 0; margin-bottom: 0"><b><font
face="Book Antiqua"><span style="font-size: 10.0pt">2. Вторая
песня 4:04</span></font></b></p>
<p align="left"><b><span>10.
Десятая</span></b></p>
</tr></table><h3>Карта сайта</h3>
<p>)- 1. Не трек</p>
</body></html>
"""

COMPILATION = """
<html><body>
<p align="right"><b><u><font size="2">1.</font></u></b><font
size="2"><i><u>Первая
Песня</u></i><br>
Альбом: Альбом<br>
<b>Некто</b> - вокал<br>
Запись студии 1985</font>
<p align="right"><b><u><font size="2">2.</font></u></b><font
size="2"><i><u>Вторая Песня</u></i><br>
Альбом: 45 <b>Некто</b> - вокал</font>
<h3>Карта сайта</h3>
</body></html>
"""


def test_index_keeps_song_links_once_in_order() -> None:
    assert parse_index(INDEX, base="http://example.org/txt/kinotext.htm") == [
        ("Первая песня", "http://example.org/txt/t1.htm"),
        ("Вторая, песня", "http://example.org/txt/t2.htm"),
    ]


def test_lyrics_between_dashes_and_chords_section() -> None:
    assert parse_lyrics(SONG_LINES_AS_PARAGRAPHS) == (
        "Строка раз,\nСтрока два.\n\nПрипев: строка три"
    )


def test_lyrics_from_single_paragraph_with_breaks() -> None:
    assert parse_lyrics(SONG_LINES_AS_BREAKS) == "Слово один.\nСлово два.\n\nСлово три."


def test_page_without_separator_has_no_lyrics() -> None:
    assert parse_lyrics(SONG_WITHOUT_TEXT) is None


def test_chord_lines() -> None:
    for line in ["Am", "C#m7  F/G", "H7 Hm Em", "Dsus4 Cmaj7 Bb", "A7+ E5"]:
        assert is_chord_line(line), line
    for line in ["", "Аккорды:", "Am строка", "A я иду", "Good-bye!", "1-e||--1-0--|"]:
        assert not is_chord_line(line), line


def test_tracklist_strips_numbers_and_durations() -> None:
    assert parse_tracklist(ALBUM_WITH_DURATIONS) == ["Первая песня", "Вторая песня", "Десятая"]


def test_tracklist_of_compilation_takes_italic_title() -> None:
    assert parse_tracklist(COMPILATION) == ["Первая Песня", "Вторая Песня"]


def test_title_key_ignores_case_yo_punctuation_and_latin_lookalikes() -> None:
    assert title_key("Ария Мистера X") == title_key("ария мистера Х")
    assert title_key("Звёзды останутся здесь!") == title_key("Звезды останутся здесь")
    assert title_key("Разреши мне...") == title_key("Разреши мне")
    assert title_key("Любовь- это не шутка") == title_key("Любовь — это не шутка")


def test_lyricist_defaults_to_tsoi_unless_listed() -> None:
    exceptions = {title_key("Чужая песня"): "А. Другой"}
    assert pick_lyricist("Чужая песня.", exceptions) == "А. Другой"
    assert pick_lyricist("Своя песня", exceptions) == "В. Цой"


def test_album_prefers_studio_then_earliest_year() -> None:
    albums = {
        "d1": Album("Сборник", 1980, "compilation"),
        "d2": Album("Второй", 1986, "studio"),
        "d3": Album("Первый", 1984, "studio"),
        "d4": Album("Концерт", 1983, "live"),
        "d5": Album("Без года", None, "studio"),
    }
    tracklists = {
        "d1": ["Песня"],
        "d2": ["Песня"],
        "d3": ["песня!"],
        "d4": ["Песня", "Живая"],
        "d5": ["Песня", "Живая"],
    }
    assert choose_album("Песня", tracklists, albums, aliases={}) == "Первый"
    assert choose_album("Живая", tracklists, albums, aliases={}) == "Без года"
    assert choose_album("Нигде", tracklists, albums, aliases={}) == ""


def test_album_follows_alias_to_tracklist_title() -> None:
    albums = {"d1": Album("Первый", 1984, "studio")}
    tracklists = {"d1": ["Короткое имя"]}
    aliases = {title_key("Длинное имя (короткое)"): "Короткое имя"}
    assert choose_album("Длинное имя (короткое)", tracklists, albums, aliases) == "Первый"
