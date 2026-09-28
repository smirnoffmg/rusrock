import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from bs4.element import NavigableString

from rusrock.fetch import CachedFetcher
from rusrock.parsers import Song, normalize_text

SOURCE = "grob-hroniki.org"
INDEX_URL = "https://grob-hroniki.org/texts/yanka/"
# Pages are UTF-8 with a BOM; plain "utf-8" would leave U+FEFF in the markup.
ENCODING = "utf-8-sig"
YANKA = "Янка Дягилева"
DELAY = 2.5


@dataclass(frozen=True)
class IndexEntry:
    title: str
    url: str
    date: str
    note: str


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def parse_index(html: str, base: str) -> list[IndexEntry]:
    soup = BeautifulSoup(html, "html.parser")
    entries = []
    for row in soup.select("table#textdttb tr"):
        cells = row.find_all("td")
        link = cells[0].find("a", href=True) if cells else None
        if len(cells) < 5 or not isinstance(link, Tag):
            continue
        entries.append(
            IndexEntry(
                title=_clean(link.get_text()),
                url=urljoin(base, str(link["href"])),
                date=_clean(cells[2].get_text()),
                note=_clean(cells[4].get_text()),
            )
        )
    return entries


def date_year(text: str) -> int | None:
    match = re.match(r"(\d{4})", text)
    return int(match.group(1)) if match else None


def _header_parts(strong: Tag) -> tuple[str, str]:
    # Header reads "<strong>Title</strong> (Author[ — Co-author], date[, place])".
    rest = "".join(s.get_text() if isinstance(s, Tag) else str(s) for s in strong.next_siblings)
    inner = _clean(rest).removeprefix("(").removesuffix(")")
    credit, _, details = inner.partition(",")
    return _clean(credit), _clean(details)


def _header_strong(soup: BeautifulSoup) -> Tag | None:
    block = soup.select_one("div.pathbottom > div.block")
    header = block.find("p", recursive=False) if block else None
    strong = header.find("strong") if isinstance(header, Tag) else None
    return strong if isinstance(strong, Tag) else None


def header_details(html: str) -> str:
    strong = _header_strong(BeautifulSoup(html, "html.parser"))
    return _header_parts(strong)[1] if strong else ""


# "relcomment" holds editors' line variants and remarks; italic "i" holds
# dedications and epigraphs, which are not part of the text itself.
EDITORIAL_CLASSES = {"relcomment", "hr", "i"}


def _is_editorial(tag: Tag) -> bool:
    return tag.name == "sup" or bool(EDITORIAL_CLASSES & set(tag.get("class") or []))


def _stanza(container: Tag) -> str:
    parts: list[str] = []
    for node in container.descendants:
        if isinstance(node, Tag) and node.name == "br":
            parts.append("\n")
        elif isinstance(node, NavigableString) and not any(
            _is_editorial(parent) for parent in node.parents
        ):
            parts.append(str(node).replace("\n", "").replace("\xa0", " "))
    return normalize_text("".join(parts))


def _text_containers(block: Tag) -> list[Tag]:
    containers = []
    for child in block.find_all(["p", "table"], recursive=False)[1:]:
        if child.name == "table":
            # Side-by-side редакции: the first column is the book version.
            first = child.find("td")
            if isinstance(first, Tag):
                containers.append(first)
        elif not _is_editorial(child):
            containers.append(child)
    return containers


def parse_text(html: str, url: str) -> Song | None:
    soup = BeautifulSoup(html, "html.parser")
    block = soup.select_one("div.pathbottom > div.block")
    strong = _header_strong(soup)
    if block is None or strong is None:
        return None
    title = _clean(strong.get_text())
    credit = _header_parts(strong)[0]
    stanzas = [_stanza(c) for c in _text_containers(block)]
    sole = credit == YANKA
    return Song(
        source=SOURCE,
        title=title,
        album="",
        credit="" if sole else credit,
        lyricist="Я. Дягилева" if sole else "",
        text=normalize_text("\n\n".join(s for s in stanzas if s)),
        url=url,
    )


def page_kind(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    labels = [p.get_text() for p in soup.select("p.stihvers")]
    performed = any("релиз" in label or "концерт" in label for label in labels)
    return "song" if performed else "poem"


def _scrape_with_meta(fetch: CachedFetcher) -> list[tuple[Song, IndexEntry, str, str]]:
    result = []
    for entry in parse_index(fetch(INDEX_URL, ENCODING), base=INDEX_URL):
        html = fetch(entry.url, ENCODING)
        song = parse_text(html, url=entry.url)
        if song is None:
            print(f"no text: {entry.url}", file=sys.stderr)
            continue
        result.append((song, entry, page_kind(html), header_details(html)))
    return result


def scrape(fetch: CachedFetcher) -> list[Song]:
    return [song for song, *_ in _scrape_with_meta(fetch)]


def _write_tsv(path: Path, comment: str, header: list[str], rows: list[list[str]]) -> None:
    lines = [f"# {comment}", "\t".join(header), *("\t".join(row) for row in rows)]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    scraped = _scrape_with_meta(CachedFetcher(Path("data/raw"), delay=DELAY))
    out = Path("data/songs/yanka.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for song, *_ in scraped:
            f.write(json.dumps(asdict(song), ensure_ascii=False) + "\n")

    source = f"Источник: {INDEX_URL} (таблица «Янка Дягилева. Стихи»), выгружено {date.today()}."
    _write_tsv(
        Path("meta/yanka_dates.tsv"),
        f"{source} date — столбец «Дата» таблицы. Сайт его не подписывает; по этой дате "
        "упорядочен хронологический список текстов сайта (/text_date.html), "
        "поэтому date_kind = written (дата написания), вывод по косвенному признаку. "
        "page_date_place — дата и место из шапки страницы текста, как написано.",
        ["title", "date", "year", "date_kind", "page_date_place"],
        [
            [s.title, e.date, str(date_year(e.date) or ""), "written", details]
            for s, e, _, details in scraped
        ],
    )
    _write_tsv(
        Path("meta/yanka_lyricists.tsv"),
        f"{source} Тексты, у которых в шапке страницы автор не одна Янка Дягилева; "
        "note — столбец «Примечания» таблицы. Автора слов сайт отдельно не называет, "
        "поэтому lyricist в корпусе у них пуст.",
        ["title", "credit", "note", "url"],
        [[s.title, s.credit, e.note, s.url] for s, e, *_ in scraped if s.credit],
    )
    _write_tsv(
        Path("meta/yanka_kinds.tsv"),
        f"{source} kind = song, если на странице есть раздел «Присутствует на следующих "
        "релизах» или «Песня исполнялась на следующих концертах», иначе poem.",
        ["title", "kind"],
        [[s.title, kind] for s, _, kind, _ in scraped],
    )
    print(f"{len(scraped)} texts -> {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
