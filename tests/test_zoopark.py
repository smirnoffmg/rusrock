from rusrock.parsers import Song
from rusrock.sites.zoopark import (
    has_inline_chords,
    is_chord_line,
    lyricist_for,
    parse_album,
    parse_index,
    strip_chord_lines,
)

BASE = "https://www.mikenaumenko.ru/"

INDEX = """
<html><body>
<map><area href="album.htm"><area href="texts.htm"></map>
<table><tr><td>
<a HREF="mike.zip">Аккорды</a>
<a HREF="album_one.htm#9">Песня девять</a>
<a href="pnm://example.invalid/x.rm"><img src="r.gif"></a><br>
<a HREF="album_two.htm#1">Песня раз</a><br>
<a HREF="album_one.htm#2">Песня два</a><br>
<a href="album_other.html#4">Опечатка в ссылке</a><br>
</td></tr></table>
<a HREF="index.htm">назад</a>
</body></html>
"""

# Lowercase markup, lyrics inside <blockquote>, album credit line in the header.
ALBUM_LOWER = """
<html><head><title>Альбомы: Первый Альбом</title></head><body>
<table><tr><td>
<span>Имя ФАМИЛИЯ — голос<br>
музыка и тексты песен: Майк, 1983 год, кроме #2 - Иван Другой. Диск издан в 1997 году.</span>
<hr SIZE="1">
<ul><p align="center"><font COLOR="#408080"><a HREF="#1">Раз</a><br><a HREF="#2">Два</a></font></p></ul>
<hr SIZE="1">
<ul>
  <p align="center"><a NAME="1"></a><font SIZE="+1" COLOR="#FF0000">Песня
  Раз</font><font COLOR="#408080"> <a href="/mp3/01.mp3"><img src="mp3.gif" alt="2:45"></a></font></p>
  <blockquote>
    <p>Am   C  F/G<br>
    Первая строчка куплета <br>
    длинная строка, перенесённая
    в исходнике.<br>
    Строка с Am аккордом внутри</p>
    <p>Второй куплет.<br>
    &nbsp;&nbsp; </p>
  </blockquote>
  <p align="center"><a NAME="2"></a><font SIZE="+1" COLOR="#FF0000">Песня Два *</font></p>
  <blockquote><p>Одна строка второй песни.<br>
  <br>
  * Примечание редактора.</p></blockquote>
</ul>
<div ALIGN="right"><hr SIZE="1"><a HREF="album.htm"><img SRC="back.gif"></a></div>
</td></tr></table></body></html>
"""

# Uppercase markup with unclosed <P>, heading wrapped in <CENTER>, no credit line.
ALBUM_UPPER = """
<HTML><HEAD><TITLE>Альбомы: Blues de Test</TITLE></HEAD><BODY>
<HR SIZE=1 NOSHADE><B>«Blues de Test» '81</B>
<HR SIZE=1 NOSHADE>
<CENTER><P><A NAME="1"></A><FONT COLOR="#FF0000"><FONT SIZE=+1>Первая</FONT></FONT><A HREF="http://example.invalid/"><IMG SRC="x.gif"></A></P></CENTER>
<P align="center"><A HREF="x.rm"><IMG SRC="r.gif"></A><SMALL>- песня Test Song группы Test Band.</SMALL></P>

<P>Строка A<BR>
Строка B
<P>Строка C<BR>

<P align="center"><A NAME="28"></A><FONT SIZE=+1>Без Цвета ("Подзаголовок")</FONT></P>
<P>Текст без красного заголовка<BR>
Ещё строка</P>

<DIV ALIGN=right><P>
<HR SIZE=1 NOSHADE WIDTH="100%"><A HREF="album.htm"><IMG SRC="back.gif"></A></P></DIV>
</BODY></HTML>
"""


def test_parse_index_returns_unique_album_pages_in_order() -> None:
    assert parse_index(INDEX, base=BASE) == [
        BASE + "album_one.htm",
        BASE + "album_two.htm",
        BASE + "album_other.html",
    ]


def test_is_chord_line() -> None:
    assert is_chord_line("Am   C  F/G")
    assert is_chord_line("C#m7 H7 Bb Dsus4")
    assert not is_chord_line("Строка с Am аккордом внутри")
    assert not is_chord_line("Blues De Moscou")
    assert not is_chord_line("")


def test_has_inline_chords() -> None:
    assert has_inline_chords("Строка с Am аккордом внутри")
    assert not has_inline_chords("Blues De Moscou, часть 2")
    assert not has_inline_chords("Am C")


def test_strip_chord_lines_counts_removed() -> None:
    text, removed = strip_chord_lines("Am C\nСлова\n  G7  \nЕщё слова")
    assert text == "Слова\nЕщё слова"
    assert removed == 2


def test_lyricist_for_reads_album_credit_with_exception() -> None:
    credit = "музыка и тексты песен: Майк, 1983 год, кроме #6 - Александр Храбунов"
    assert lyricist_for(credit, "1") == "Майк Науменко"
    assert lyricist_for(credit, "6") == "Александр Храбунов"
    assert lyricist_for("музыка и тексты песен: Майк, 1982 год", "3") == "Майк Науменко"
    assert lyricist_for("", "1") == ""


def test_parse_album_lowercase_blockquote_layout() -> None:
    url = BASE + "album_one.htm"
    result = parse_album(ALBUM_LOWER, url=url)
    credit = "музыка и тексты песен: Майк, 1983 год, кроме #2 - Иван Другой"
    assert result.songs == [
        Song(
            source="www.mikenaumenko.ru",
            title="Песня Раз",
            album="Первый Альбом",
            credit=credit,
            lyricist="Майк Науменко",
            text=(
                "Первая строчка куплета\n"
                "длинная строка, перенесённая в исходнике.\n"
                "Строка с Am аккордом внутри\n"
                "\n"
                "Второй куплет."
            ),
            url=url + "#1",
        ),
        Song(
            source="www.mikenaumenko.ru",
            title="Песня Два",
            album="Первый Альбом",
            credit=credit,
            lyricist="Иван Другой",
            text="Одна строка второй песни.",
            url=url + "#2",
        ),
    ]
    assert result.chord_lines_removed == 1
    assert result.mixed_lines == [("Песня Раз", "Строка с Am аккордом внутри")]


def test_parse_album_uppercase_unclosed_paragraphs() -> None:
    url = BASE + "album_two.htm"
    songs = parse_album(ALBUM_UPPER, url=url).songs
    assert [(s.title, s.album, s.credit, s.lyricist, s.url) for s in songs] == [
        ("Первая", "Blues de Test", "песня Test Song группы Test Band.", "", url + "#1"),
        ('Без Цвета ("Подзаголовок")', "Blues de Test", "", "", url + "#28"),
    ]
    assert songs[0].text == "Строка A\nСтрока B\n\nСтрока C"
    assert songs[1].text == "Текст без красного заголовка\nЕщё строка"
