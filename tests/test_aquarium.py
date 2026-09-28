from rusrock.parsers import Song
from rusrock.sites.aquarium import (
    AlbumEntry,
    albums_tsv,
    disambiguate,
    parse_album,
    parse_grid_catalogue,
    parse_list_catalogue,
    section_kind,
)

BASE = "https://old.aquarium.ru/discography/index.html"

GRID = """
<html><body>
<p>(все тексты - в &quot;Книге Песен&quot;
(<a href="http://www.aquarium.ru/discography/songs_of_bg_book.zip">DOC</a>)</p>
<table width="600" border="0" cellspacing="4" cellpadding="0">
<tr>
    <td colspan="4"><h3>Естественные Альбомы Аквариума и БГ</h3></td>
</tr>
<tr>
    <td valign="top" align="center" width="145">
      <a href="first_alb1.html">
        <img src="images/t1.jpg" border="0"></a></p>
      </td>
      <td align="center" valign="top" width="145">
        <a href="second2.html"><img src="images/t2.jpg" border="0"></td>
      <td align="center" valign="top" width="145"></td>
</tr>
<tr>
      <td align="center" valign="top" width="145">1981&nbsp;Первый&nbsp;альбом</td>
      <td align="center" valign="top" width="145">1982 Второй
      альбом</td>
      <td align="center" valign="top" width="145"> </td>
</tr>
</table>
<table width="600" border="0" cellspacing="4" cellpadding="0">
      <tr ><td colspan=4><p>&nbsp;</p><h3>Синглы</td></tr>
      <tr>
      <td align="center"><a href="single3.html"><img src="images/t3.jpg"></a></td>
      <td align="center"><a href="first_alb1.html"><img src="images/t1.jpg"></a></td>
      </tr>
      <tr>
      <td align="center" valign="top">1990-Сборник.<br>Песни</td>
      <td align="center" valign="top">1981 Первый альбом</td>
      </tr>
</tr>
 <tr ><td colspan=4><p>&nbsp;</p><h3>Кооперация</td></tr>
      <tr><td align="center"><a href="nophoto4.html"><img src="images/nophoto.jpg"></a></td></tr>
      <tr><td align="center" valign="top">Без года</td></tr>
</table>
<p align="center"><a href="index2.html">далее...</a></p>
</body></html>
"""

LIST = """
<html><body><table><tr><td>
      <h3>Индивидуальное творчество</h3>
<p><a name="others" href="../documents/people/x.html">Иван Иванов</a><br>
      <img src="images/p.gif"><a href="ivanov_reka.html">2002-Река</a></p>
      <p><a href="../documents/people/y/index.html">Пётр Петров</a><br>
      <img src="images/p.gif"><a href="petrov_one.html">1989-&quot;Трио&quot;. Тишина</a><br>
      подробнее см. <a href="../documents/people/y/index.html#@albums">&quot;Альбомы&quot;</a></p>
<p align="center"><a href="index.html">...в начало</a></p>
</td></tr></table></body></html>
"""

ALBUM = """
<html><head><title>Первый альбом (1981)</title></head>
<body>
<table width="600"><tr>
    <td valign="top" align="left" width="100"><a href="pfirst1.html"><img src="x.jpg"></a></td>
    <td valign="top"><h2>Первый альбом (1981)</h2>
    <p>АКВАРИУМ:<br>
    Б.Г. - голос<br></p>
    <p>(с) Б.Г. 1981</p></td>
</tr></table>
<p align="center"><a name="top"></a></p>
<table width="600"><tr><td valign="top" align="left">
<blockquote><p align="left"><strong>Сторона 1</strong><br>
<br>
<a href="#@1">Песня раз</a><br>
<a href="#@2">Песня два</a></p>
</blockquote></td></tr></table>
<p align="center"><img src="hr.gif"></p>
<table width="600"><tr>
    <td valign="top" align="left"><a name="@1"></a> <h3>Песня
    раз</h3>
    <blockquote>
    <p>Первая строчка текста<br>
    вторая строчка текста,<br>
    </p>
    <p>Третья строчка<br>
    четвёртая&nbsp;строчка</p>
    </blockquote>
    <p align="right"><a href="#top"><font size="1">наверх</font></a><br>
    <img src="hr.gif" width="600" height="4"></p>
    <a name="@2"></a>
    <h3>Песня два</h3>
    <blockquote>
    <p>Одна строчка</p>
    </blockquote>
    <p align="right"><a href="#top"><font size="1">наверх</font></a></p>
</td></tr></table>
</body></html>
"""


def test_grid_catalogue_pairs_link_row_with_caption_row_under_sections() -> None:
    assert parse_grid_catalogue(GRID, base=BASE) == [
        AlbumEntry(
            "Первый альбом",
            1981,
            "Естественные Альбомы Аквариума и БГ",
            "https://old.aquarium.ru/discography/first_alb1.html",
        ),
        AlbumEntry(
            "Второй альбом",
            1982,
            "Естественные Альбомы Аквариума и БГ",
            "https://old.aquarium.ru/discography/second2.html",
        ),
        AlbumEntry(
            "Сборник. Песни", 1990, "Синглы", "https://old.aquarium.ru/discography/single3.html"
        ),
        AlbumEntry(
            "Первый альбом", 1981, "Синглы", "https://old.aquarium.ru/discography/first_alb1.html"
        ),
        AlbumEntry(
            "Без года", None, "Кооперация", "https://old.aquarium.ru/discography/nophoto4.html"
        ),
    ]


def test_list_catalogue_takes_only_year_prefixed_album_links() -> None:
    assert parse_list_catalogue(LIST, base=BASE) == [
        AlbumEntry(
            "Река",
            2002,
            "Индивидуальное творчество",
            "https://old.aquarium.ru/discography/ivanov_reka.html",
        ),
        AlbumEntry(
            '"Трио". Тишина',
            1989,
            "Индивидуальное творчество",
            "https://old.aquarium.ru/discography/petrov_one.html",
        ),
    ]


def test_section_kind_maps_catalogue_sections() -> None:
    assert section_kind("Естественные Альбомы Аквариума и БГ") == "studio"
    assert section_kind("Концертные Записи") == "live"
    assert section_kind("Синглы") == "single"
    assert section_kind("Антологии") == "compilation"
    assert section_kind("Кооперация") == "other"
    assert section_kind("Неизвестный раздел") == "other"


def test_disambiguate_drops_repeated_urls_and_renames_title_clashes() -> None:
    a = AlbumEntry("Альбом", 1989, "Синглы", "u1")
    b = AlbumEntry("Альбом", 1989, "Англоязычные Альбомы", "u2")
    again = AlbumEntry("Другое имя", 1989, "Винил", "u1")
    assert disambiguate([a, b, again]) == [a, b._replace(title="Альбом (Англоязычные Альбомы)")]


def test_album_page_splits_songs_at_anchors() -> None:
    songs = parse_album(ALBUM, url="https://x/first.html", album="Первый альбом")
    assert songs == [
        Song(
            source="old.aquarium.ru",
            title="Песня раз",
            album="Первый альбом",
            credit="",
            lyricist="",
            text="Первая строчка текста\nвторая строчка текста,\n\nТретья строчка\nчетвёртая строчка",
            url="https://x/first.html#@1",
        ),
        Song(
            source="old.aquarium.ru",
            title="Песня два",
            album="Первый альбом",
            credit="",
            lyricist="",
            text="Одна строчка",
            url="https://x/first.html#@2",
        ),
    ]


def test_album_page_without_anchored_songs_is_empty() -> None:
    assert parse_album("<html><body><h2>Нет текстов</h2></body></html>", url="u", album="A") == []


def test_albums_tsv_has_source_comment_and_header() -> None:
    tsv = albums_tsv([AlbumEntry("Альбом", None, "Кооперация", "u")], source="S", date="D")
    assert tsv.splitlines() == [
        "# Каталог S (D). kind выведен из раздела каталога (section).",
        "# kind: studio / live / compilation / single / other; пустой year — год не указан.",
        "album\tyear\tkind\tsection\turl",
        "Альбом\t\tother\tКооперация\tu",
    ]


def test_album_page_accepts_anchor_inside_heading_and_ignores_commented_songs() -> None:
    html = """<table><tr><td>
<a name="@01"></a><h3>Первая <a name="@01"></a></h3>
<blockquote><p>Строка первой</p></blockquote>
<h3>Вторая <a name="@02"></a></h3>
<blockquote><p>Строка второй</p></blockquote>
<!-- <a name="@b1"></a><h3>Скрытая</h3><blockquote><p>Скрыто</p></blockquote> -->
</td></tr></table>"""
    songs = parse_album(html, url="u", album="A")
    assert [(s.title, s.text, s.url) for s in songs] == [
        ("Первая", "Строка первой", "u#@01"),
        ("Вторая", "Строка второй", "u#@02"),
    ]


def _song_with_first_line(first: str) -> Song:
    html = f"""<a name="@1"></a><h3>Песня</h3>
<blockquote><p>{first}<br>Строка текста</p></blockquote>"""
    [song] = parse_album(html, url="u", album="A")
    return song


def test_credit_in_parentheses_is_taken_from_first_line_and_removed_from_text() -> None:
    song = _song_with_first_line("(И. Иванов)")
    assert (song.credit, song.lyricist, song.text) == ("И. Иванов", "И. Иванов", "Строка текста")


def test_music_and_words_credit_gives_words_author_after_separator() -> None:
    dash = _song_with_first_line("(П.Петров - Вл. Сидоров) Первая строка")
    assert (dash.credit, dash.lyricist) == ("П.Петров - Вл. Сидоров", "Вл. Сидоров")
    assert dash.text == "Первая строка\nСтрока текста"
    slash = _song_with_first_line("(П. Петров / С. Сидоров)")
    assert slash.lyricist == "С. Сидоров"


def test_verbal_credit_names_words_author() -> None:
    both = _song_with_first_line("Слова и музыка И. Иванова")
    assert (both.credit, both.lyricist) == ("Слова и музыка И. Иванова", "И. Иванова")
    split = _song_with_first_line("Слова С. Сидорова, музыка П. Петрова")
    assert split.lyricist == "С. Сидорова"
    assert split.text == "Строка текста"


def test_full_name_in_parentheses_is_not_a_credit() -> None:
    song = _song_with_first_line("(Иван Иванов)")
    assert (song.credit, song.lyricist) == ("", "")
    assert song.text == "(Иван Иванов)\nСтрока текста"


def test_unclosed_blockquote_wrapping_later_songs_is_not_taken_as_text() -> None:
    html = """<a name="@1"></a><h3>Первая</h3>
<blockquote><p>Строка первой<br>ещё строка</p>
<a name="@2"></a><h3>Вторая</h3>
<blockquote><p>Строка второй<br>ещё строка</p></blockquote>"""
    songs = parse_album(html, url="u", album="A")
    assert [(s.title, s.text) for s in songs] == [("Вторая", "Строка второй\nещё строка")]
