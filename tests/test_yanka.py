from rusrock.parsers import Song
from rusrock.sites.yanka import (
    IndexEntry,
    date_year,
    header_details,
    page_kind,
    parse_index,
    parse_text,
)

INDEX = """
<html><body><div class="pathbottom"><div class="block">
<table class="display artyear" id="textdttb">
<thead><tr>
<th>Название</th>
<th>Первая строка</th>
<th>Дата</th>
<th>Публикации</th>
<th>Примечания</th>
</tr></thead>
<tbody>
<tr>
<td><a href="alfa.html">Альфа </a></td>
<td>Выдуманная строка...</td>
<td>1987.06.xx</td>
<td class="notation">Сборник,\xa02003.</td>
<td class="notation"></td>
</tr>
<tr>
<td><a href="../go/x/beta.html">Бета</a></td>
<td>Другая строка...</td>
<td>1987</td>
<td class="notation">Сборник,\xa02003.</td>
<td class="notation">Некто Другой\xa0— Янка Дягилева</td>
</tr>
</tbody>
<tfoot><tr>
<th>Название</th>
<th>Первая строка</th>
<th>Дата</th>
<th>Публикации</th>
<th>Примечания</th>
</tr></tfoot>
</table>
</div></div></body></html>
"""

TEXT_PAGE = """
<html><body><div class="pathbottom">
<div class="block">
<p><strong>Альфа</strong> (Янка Дягилева, 1987)</p>
<p>Первая выдуманная строка<br/>Вторая строка<br/>
<span class="left100">Строка с отступом<sup class="reference" id="s1"><a href="#sup1">1</a></sup></span><br/>
<span class="left50">Короткая</span></p>
<p>Второй куплет<br/>Последняя строка</p>
<p class="hr grey"> </p>
<div class="reflist">
<p class="references relcomment" id="sup1">1<a class="bold" href="#s1">^</a> <em>Сноска</em> про строку.</p>
</div>
</div>
<div class="block" id="images"><p class="relblock">Изображения</p></div>
<div class="block">
<p class="relblock">Комментарии</p>
<p class="stihvers">Стихотворение опубликовано в книгах:</p>
<ul class="stihvers"><li>Сборник</li></ul>
<p class="stihvers">Присутствует на следующих релизах:</p>
<ul class="stihvers"><li>Альбом</li></ul>
</div>
</div></body></html>
"""

EDITORIAL_PAGE = """
<html><body><div class="pathbottom">
<div class="block">
<p><strong>Гамма</strong> (Янка Дягилева, 1988)</p>
<p><span class="left150 i">Выдуманный эпиграф</span><br/>
<br/>Строка после эпиграфа</p>
<p class="left150 i">Посвящение кому-то</p>
<p class="left50">Строфа с отступом</p>
<p class="w40em">Прозаический абзац.</p>
<p class="relcomment">Вариант 1-й строки: «Иначе»</p>
<div class="hr grey"></div>
</div>
</div></body></html>
"""

TWO_VERSIONS_PAGE = """
<html><body><div class="pathbottom">
<div class="block">
<p><strong>Дельта</strong> (Янка Дягилева, 1991)</p>
<table class="poem">
<tr>
<td>Первая редакция<br/>Её вторая строка</td>
<td>Вторая редакция<br/>Другая строка</td>
</tr>
<tr>
<td class="source">Вариант из книги А.</td>
<td class="source">Вариант из книги Б.</td>
</tr>
</table>
</div>
</div></body></html>
"""

POEM_PAGE = """
<html><body><div class="pathbottom">
<div class="block">
<p><strong>Бета</strong> (Некто Другой\xa0— Янка Дягилева, 1990.05.30)</p>
<p>Одна строка</p>
</div>
<div class="block">
<p class="relblock">Комментарии</p>
<p class="stihvers">Стихотворение опубликовано в книгах:</p>
<ul class="stihvers"><li>Сборник</li></ul>
</div>
</div></body></html>
"""


def test_index_reads_rows_and_skips_header_and_footer() -> None:
    assert parse_index(INDEX, base="https://example.org/texts/yanka/") == [
        IndexEntry(
            title="Альфа",
            url="https://example.org/texts/yanka/alfa.html",
            date="1987.06.xx",
            note="",
        ),
        IndexEntry(
            title="Бета",
            url="https://example.org/texts/go/x/beta.html",
            date="1987",
            note="Некто Другой — Янка Дягилева",
        ),
    ]


def test_text_by_yanka_alone_gets_lyricist_and_no_footnotes() -> None:
    assert parse_text(TEXT_PAGE, url="u") == Song(
        source="grob-hroniki.org",
        title="Альфа",
        album="",
        credit="",
        lyricist="Я. Дягилева",
        text=(
            "Первая выдуманная строка\nВторая строка\nСтрока с отступом\nКороткая\n\n"
            "Второй куплет\nПоследняя строка"
        ),
        url="u",
    )


def test_cowritten_text_keeps_raw_credit_and_leaves_lyricist_empty() -> None:
    song = parse_text(POEM_PAGE, url="u")
    assert song is not None
    assert (song.credit, song.lyricist, song.text) == (
        "Некто Другой — Янка Дягилева",
        "",
        "Одна строка",
    )


def test_editorial_notes_dedications_and_epigraphs_are_dropped() -> None:
    song = parse_text(EDITORIAL_PAGE, url="u")
    assert song is not None
    assert song.text == "Строка после эпиграфа\n\nСтрофа с отступом\n\nПрозаический абзац."


def test_side_by_side_versions_keep_only_the_first() -> None:
    song = parse_text(TWO_VERSIONS_PAGE, url="u")
    assert song is not None
    assert song.text == "Первая редакция\nЕё вторая строка"


DECORATED_HEADER_PAGE = """
<html><body><div class="pathbottom">
<div class="block">
<p><span style="font-size:larger">⊗</span> <strong> Эпсилон</strong> (Янка Дягилева, июнь 1987, Город)</p>
<p>Строка\xa0с неразрывным пробелом</p>
</div>
</div></body></html>
"""


def test_header_date_and_place_are_not_part_of_credit() -> None:
    song = parse_text(DECORATED_HEADER_PAGE, url="u")
    assert song is not None
    assert (song.title, song.credit, song.lyricist, song.text) == (
        "Эпсилон",
        "",
        "Я. Дягилева",
        "Строка с неразрывным пробелом",
    )
    assert header_details(DECORATED_HEADER_PAGE) == "июнь 1987, Город"


def test_page_without_text_block_is_none() -> None:
    assert parse_text("<html><body><p>404</p></body></html>", url="u") is None


def test_kind_is_song_only_when_releases_or_concerts_are_listed() -> None:
    assert (page_kind(TEXT_PAGE), page_kind(POEM_PAGE)) == ("song", "poem")


def test_year_is_taken_from_any_date_precision() -> None:
    assert [date_year(d) for d in ("1987.06.xx", "1989", "1990.05.30", "")] == [
        1987,
        1989,
        1990,
        None,
    ]
