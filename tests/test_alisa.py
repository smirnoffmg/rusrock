from rusrock.parsers import Song
from rusrock.sites.alisa import (
    clean_lyrics,
    fix_homoglyphs,
    is_chord_line,
    parse_album,
    parse_index,
    split_album_heading,
    words_author,
)

INDEX = """
<html><body><table><tr><td>
<a href="txt.php?s=002&amp;d=001">Певец, группа "Икс" - Первый (1984)</a><hr />
<a href="txt.php?s=002&amp;d=002">Второй (1985)</a><hr />
<a href="http://ru.wikipedia.org/?oldid=1" target=_blank>wikipedia.org</a>
<h2>Полный список песен</h2>
<ol>
<li><a href="txt.php?s=002&amp;d=002#v01">Песня раз</a></li>
<li><a href="txt.php?s=002&amp;d=001#v02">Песня два</a></li>
</ol>
</td></tr></table></body></html>
"""

ALBUM = """
<html><body><table><tr><td>
<a href="txt.php?s=002&amp;d=001">Певец, группа "Икс" - Первый (1984)</a><hr />
</td><td align="left" valign="top"><h2>Алиса</h2></td></tr>
<tr><td align="left" valign="top"><h2>Второй (1985)</h2>
<br />
<ol>
 <li><a href="#v01">Песня раз</a></li>
 <li><a href="#v02">Песня два</a></li>
</ol>
<hr />
<br />
<div id="v01"><b><u>Песня раз</u></b><br /><pre>
(А.Музыкант - Б.Поэт)
Am              C
Первая строка, выдуманная,
F/G       H7    Dm С
Вторая строка тоже.

   Em
   Припев с отступом.
</pre></div><input type="button" onclick="printDiv('v01')" value="&uarr;&nbsp;Print this song" /><br /><br />
<div id="v02"><b><u>Песня два</u></b><br /><pre>
Em
Строка без автоpа.
</pre></div><input type="button" onclick="printDiv('v02')" value="&uarr;&nbsp;Print this song" /><br /><br />
</td></tr></table></body></html>
"""


def test_index_lists_album_pages_once() -> None:
    assert parse_index(INDEX, base="http://accords.site/") == [
        "http://accords.site/txt.php?s=002&d=001",
        "http://accords.site/txt.php?s=002&d=002",
    ]


def test_album_heading_splits_off_year() -> None:
    assert split_album_heading("Кто-то - Альбом, часть 1 (1988)") == (
        "Кто-то - Альбом, часть 1",
        1988,
    )
    assert split_album_heading("Альбом без года") == ("Альбом без года", None)


def test_chord_lines() -> None:
    for line in [
        "Am              C",
        "F/G  H7   C#m7",
        "Dm С   Dm C",
        "A  A/g  A/f# F",
        "Am7-5 D7",
        "Gm+7",
        "Еm",
    ]:
        assert is_chord_line(line), line
    for line in ["", "   ", "А строка со словами", "В путь", "Rock-n-roll.", "20.12"]:
        assert not is_chord_line(line), line


def test_clean_lyrics_takes_credit_and_drops_chord_lines() -> None:
    raw = "\n(А.Музыкант - Б.Поэт)\nAm   C\nСлова раз,\n\n  Em\n  Слова два.\n"
    assert clean_lyrics(raw) == ("А.Музыкант - Б.Поэт", "Слова раз,\n\nСлова два.", 2)


def test_clean_lyrics_without_credit() -> None:
    assert clean_lyrics("\nEm\n(шёпотом) слова\n") == ("", "(шёпотом) слова", 1)


def test_homoglyphs_fixed_only_inside_cyrillic_words() -> None:
    assert fix_homoglyphs("Hо автоpа Rock'n'roll B") == "Но автора Rock'n'roll B"


def test_words_author_is_right_side_of_dash_only() -> None:
    assert words_author("А.Музыкант, В.Второй - Б.Поэт") == "Б.Поэт"
    assert words_author("А.Музыкант - Б. Поэт, В.Соавтор") == "Б.Поэт, В.Соавтор"
    assert words_author("А.Музыкант") == ""


def test_album_page_yields_songs_with_anchor_urls() -> None:
    url = "http://accords.site/txt.php?s=002&d=002"
    assert parse_album(ALBUM, url=url) == [
        Song(
            source="accords.site",
            title="Песня раз",
            album="Второй",
            credit="А.Музыкант - Б.Поэт",
            lyricist="Б.Поэт",
            text="Первая строка, выдуманная,\nВторая строка тоже.\n\nПрипев с отступом.",
            url=url + "#v01",
        ),
        Song(
            source="accords.site",
            title="Песня два",
            album="Второй",
            credit="",
            lyricist="",
            text="Строка без автора.",
            url=url + "#v02",
        ),
    ]
