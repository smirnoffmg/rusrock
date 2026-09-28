import zipfile
from pathlib import Path

from rusrock.sites.bashlachev import (
    SOURCE,
    DateEntry,
    attach_titles,
    parse_book,
    parse_dates,
    poem_text,
)

CONTAINER = """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>"""


def opf(files: list[str]) -> str:
    items = "".join(
        f'<item id="i{n}" media-type="application/xhtml+xml" href="{f}"/>'
        for n, f in enumerate(files)
    )
    refs = "".join(f'<itemref idref="i{n}"/>' for n in range(len(files)))
    return (
        '<?xml version="1.0"?><package version="2.0" xmlns="http://www.idpf.org/2007/opf">'
        f"<manifest>{items}</manifest><spine>{refs}</spine></package>"
    )


def page(level: str, title: str, anchor: str, body: str = "") -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?><html xmlns="http://www.w3.org/1999/xhtml"><body>'
        f'<div class="section"/><div id="{anchor}" class="titleblock">'
        f'<div class="{level}"><p class="title">{title}</p></div></div>'
        f'{body}<div class="chapter_end"/></body></html>'
    )


def poem(*stanzas: list[str]) -> str:
    inner = "".join(
        '<div class="stanza">' + "".join(f"<p>{line}</p>" for line in stanza) + "</div>"
        for stanza in stanzas
    )
    return f'<div class="poem">{inner}</div>'


NOTE = '<a class="anchor" href="notes.xhtml#n_1">[1]</a>'
PAGE = '<a class="pagemarker" id="page_0"/>'


def test_poem_text_keeps_lines_and_stanzas_and_drops_note_markers() -> None:
    html = poem(["Альфа строка" + NOTE + ",", "бета строка" + PAGE], ["гамма строка"])
    assert poem_text(html) == "Альфа строка,\nбета строка\n\nгамма строка"


def write_epub(path: Path, pages: dict[str, str]) -> None:
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr("META-INF/container.xml", CONTAINER)
        zf.writestr("OEBPS/content.opf", opf(list(pages)))
        for name, html in pages.items():
            zf.writestr(f"OEBPS/{name}", html)


def test_parse_book_takes_poems_of_numbered_cycles_and_the_foreword_epigraph(
    tmp_path: Path,
) -> None:
    epub = tmp_path / "book.epub"
    write_epub(
        epub,
        {
            "a.xhtml": page(
                "h1",
                "Предисловие",
                "t1",
                "<p>Проза редактора.</p><p>Подпись</p>" + poem(["Первая эпиграфа", "вторая"]),
            ),
            "b.xhtml": page("h1", "I", "t2"),
            "c.xhtml": page("h2", "Песня один", "t3", poem(["раз", "два"], ["три"])),
            "d.xhtml": page("h1", "II", "t4"),
            "e.xhtml": page(
                "h2",
                "Складная (триптих)",
                "t5",
                '<p class="subtitle">I</p>'
                + poem(["часть один"])
                + '<p class="subtitle">II</p>'
                + poem(["часть два"]),
            ),
            "f.xhtml": page("h1", "Интервью", "t6"),
            "g.xhtml": page("h2", "Беседа", "t7", "<p>Вопрос и ответ.</p>"),
            "h.xhtml": page("h1", "Комментарии", "t8", poem(["вариант строфы"])),
        },
    )

    songs = parse_book(epub)

    assert [(s.title, s.album, s.url) for s in songs] == [
        ("Первая эпиграфа", "Эпиграф", "epub:OEBPS/a.xhtml"),
        ("Песня один", "Цикл I", "epub:OEBPS/c.xhtml#t3"),
        ("Складная (триптих)", "Цикл II", "epub:OEBPS/e.xhtml#t5"),
    ]
    assert songs[1].text == "раз\nдва\n\nтри"
    assert songs[2].text == "часть один\n\nчасть два"
    assert {(s.source, s.lyricist, s.credit) for s in songs} == {(SOURCE, "А. Башлачёв", "")}


COMMENTARY = page(
    "h1",
    "Комментарии",
    "t9",
    '<p class="subtitle">1900 — 1950</p><p>Вступление редактора.</p>'
    '<p class="subtitle">Песня один</p><p>стр. 13, (*); сентябрь 1984.</p>'
    '<p class="subtitle">«Строка без названия...»</p><p>стр. 9, (*); август 1987.</p>'
    '<p class="subtitle">Альфа, Бета и Гамма</p><p>стр. 61, январь 1986. Варианты названия.</p>'
    '<p class="subtitle">Долгая</p><p>стр. 152, (*); октябрь 1985 — январь 1986.</p>'
    '<p class="subtitle">Без точки</p><p>стр. 29, (*); весна 1986</p>'
    '<p class="subtitle">Слитно</p><p>стр.115, 1984. Вариант названия.</p>'
    '<p class="subtitle">Поезд (Поезд № 1)</p><p>стр. 171 (*); 1983.</p>'
    '<p class="subtitle">В основное собрание не включены</p><p>Надпись на кассете</p>',
)


def test_parse_dates_reads_the_date_after_the_page_reference() -> None:
    assert parse_dates(COMMENTARY) == [
        DateEntry("Песня один", "сентябрь 1984", 1984),
        DateEntry("«Строка без названия...»", "август 1987", 1987),
        DateEntry("Альфа, Бета и Гамма", "январь 1986", 1986),
        DateEntry("Долгая", "октябрь 1985 — январь 1986", 1986),
        DateEntry("Без точки", "весна 1986", 1986),
        DateEntry("Слитно", "1984", 1984),
        DateEntry("Поезд (Поезд № 1)", "1983", 1983),
    ]


def test_attach_titles_matches_commentary_spelling_to_book_headings() -> None:
    entries = [
        DateEntry("«Строка без названия...»", "август 1987", 1987),
        DateEntry("Альфа, Бета и Гамма", "январь 1986", 1986),
        DateEntry("Поезд (Поезд № 1)", "1983", 1983),
        DateEntry("Складная (Триптих)", "1986", 1986),
        DateEntry("Нет в книге", "1980", 1980),
    ]
    titles = ["Строка без названия, и дальше", "Альфа, Бета, Гамма", "Поезд", "Складная (триптих)"]

    matched, unmatched = attach_titles(entries, titles)

    assert [e.title for e in matched] == titles
    assert unmatched == [DateEntry("Нет в книге", "1980", 1980)]
