import copy
import json
import re
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from bs4.element import NavigableString

from rusrock.fetch import CachedFetcher
from rusrock.parsers import Song, normalize_text

SOURCE = "old.aquarium.ru"
BASE = "https://old.aquarium.ru/discography/"
GRID_PAGES = ("index.html", "index2.html")
LIST_PAGES = ("index3.html",)
ENCODING = "koi8-r"
DELAY = 2.0

SECTION_KINDS = {
    "Естественные Альбомы Аквариума и БГ": "studio",
    "Англоязычные Альбомы": "studio",
    "Альбомы 70-х лет": "studio",
    "Синглы": "single",
    "Концертные Записи": "live",
    "Антологии": "compilation",
    "Компиляции": "compilation",
    "Чужие Сборники": "compilation",
}

_ALBUM_HREF = re.compile(r"^(?!index)[\w.-]+\.html?$")
_CAPTION = re.compile(r"^(\d{4})\s*-?\s*(.*)$")


class AlbumEntry(NamedTuple):
    title: str
    year: int | None
    section: str
    url: str


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _split_caption(caption: str) -> tuple[str, int | None]:
    match = _CAPTION.match(caption)
    if match is None:
        return caption, None
    return match.group(2), int(match.group(1))


def _album_href(cell: Tag) -> str | None:
    link = cell.find("a", href=_ALBUM_HREF)
    return str(link["href"]) if isinstance(link, Tag) else None


def _own_heading(row: Tag) -> Tag | None:
    heading = row.find("h3")
    if isinstance(heading, Tag) and heading.find_parent("tr") is row:
        return heading
    return None


def parse_grid_catalogue(html: str, base: str) -> list[AlbumEntry]:
    """Covers are one table row, captions "YEAR Title" the next row, aligned by column."""
    soup = BeautifulSoup(html, "html.parser")
    section = ""
    links: list[str | None] | None = None
    entries = []
    for row in soup.find_all("tr"):
        heading = _own_heading(row)
        if heading is not None:
            section, links = _clean(heading.get_text(" ")), None
            continue
        cells = row.find_all("td", recursive=False)
        hrefs = [_album_href(cell) for cell in cells]
        if any(hrefs):
            links = hrefs
            continue
        if links is None:
            continue
        for href, cell in zip(links, cells, strict=False):
            if href is not None:
                title, year = _split_caption(_clean(cell.get_text(" ")))
                entries.append(AlbumEntry(title, year, section, urljoin(base, href)))
        links = None
    return entries


def parse_list_catalogue(html: str, base: str) -> list[AlbumEntry]:
    soup = BeautifulSoup(html, "html.parser")
    entries = []
    for link in soup.find_all("a", href=_ALBUM_HREF):
        title, year = _split_caption(_clean(link.get_text(" ")))
        if year is None:
            continue
        heading = link.find_previous("h3")
        section = _clean(heading.get_text(" ")) if heading is not None else ""
        entries.append(AlbumEntry(title, year, section, urljoin(base, str(link["href"]))))
    return entries


def section_kind(section: str) -> str:
    return SECTION_KINDS.get(section, "other")


def disambiguate(entries: list[AlbumEntry]) -> list[AlbumEntry]:
    """One entry per page; a title already taken by another page gets its section appended."""
    seen_urls: set[str] = set()
    titles: set[str] = set()
    result = []
    for entry in entries:
        if entry.url in seen_urls:
            continue
        seen_urls.add(entry.url)
        if entry.title in titles:
            entry = entry._replace(title=f"{entry.title} ({entry.section})")
        titles.add(entry.title)
        result.append(entry)
    return result


def _blockquote_text(original: Tag) -> str:
    block = copy.copy(original)
    for string in list(block.find_all(string=True)):
        string.replace_with(re.sub(r"\s+", " ", str(string)))
    for br in block.find_all("br"):
        br.replace_with("\n")
    for paragraph in block.find_all("p"):
        paragraph.append(NavigableString("\n\n"))
    return normalize_text(block.get_text())


_NAME = r"[А-ЯЁA-Z][а-яёa-z]{0,2}\.\s?(?:[А-ЯЁA-Z]\.\s?)?[А-ЯЁA-Z][а-яёa-z-]+"
_PAREN_CREDIT = re.compile(rf"^\(({_NAME}(?:\s*[-/]\s*{_NAME})*)\)\s*")
_WORDS_AND_MUSIC = re.compile(rf"^Слова и музыка ({_NAME})$")
_WORDS_THEN_MUSIC = re.compile(rf"^Слова ({_NAME}), музыка {_NAME}$")


def split_credit(text: str) -> tuple[str, str, str]:
    """(credit, lyricist, text) from a first line like "(Music - Words)" or "Слова X, музыка Y"."""
    first, _, rest = text.partition("\n")
    paren = _PAREN_CREDIT.match(first)
    if paren is not None:
        credit = paren.group(1)
        lyricist = re.split(r"\s+[-/]\s+|\s*/\s*", credit)[-1]
        return credit, lyricist, normalize_text(first[paren.end() :] + "\n" + rest)
    verbal = _WORDS_AND_MUSIC.match(first) or _WORDS_THEN_MUSIC.match(first)
    if verbal is not None:
        return first, verbal.group(1), normalize_text(rest)
    return "", "", text


def parse_album(html: str, url: str, album: str) -> list[Song]:
    """Each song is an `<a name="@N">` anchor (before or inside an h3 title), then a blockquote.

    Songs the site commented out (e.g. unreleased bonus tracks) stay invisible to the parser.
    """
    soup = BeautifulSoup(html, "html.parser")
    songs = []
    anchor: str | None = None
    title: str | None = None
    for node in soup.find_all(["a", "h3", "blockquote"]):
        if node.name == "a":
            name = str(node.get("name") or "")
            if name.startswith("@") and node.find_parent("h3") is None:
                anchor, title = name, None
        elif node.name == "h3":
            inner = node.find("a", attrs={"name": re.compile("^@")})
            if isinstance(inner, Tag):
                anchor, title = str(inner["name"]), _clean(node.get_text(" "))
            elif anchor is not None and title is None:
                title = _clean(node.get_text(" "))
        elif node.name == "blockquote" and title is not None and node.find("h3") is None:
            credit, lyricist, text = split_credit(_blockquote_text(node))
            songs.append(
                Song(
                    source=SOURCE,
                    title=title,
                    album=album,
                    credit=credit,
                    lyricist=lyricist,
                    text=text,
                    url=f"{url}#{anchor}",
                )
            )
            anchor, title = None, None
    return songs


def catalogue(fetch: CachedFetcher) -> list[AlbumEntry]:
    entries = []
    for page in GRID_PAGES:
        url = urljoin(BASE, page)
        entries.extend(parse_grid_catalogue(fetch(url, ENCODING), base=url))
    for page in LIST_PAGES:
        url = urljoin(BASE, page)
        entries.extend(parse_list_catalogue(fetch(url, ENCODING), base=url))
    return disambiguate(entries)


def scrape(fetch: CachedFetcher) -> list[Song]:
    songs = []
    for entry in catalogue(fetch):
        album_songs = parse_album(fetch(entry.url, ENCODING), url=entry.url, album=entry.title)
        if not album_songs:
            print(f"no texts: {entry.url} ({entry.title})", file=sys.stderr)
        songs.extend(album_songs)
    return songs


def albums_tsv(entries: list[AlbumEntry], source: str, date: str) -> str:
    lines = [
        f"# Каталог {source} ({date}). kind выведен из раздела каталога (section).",
        "# kind: studio / live / compilation / single / other; пустой year — год не указан.",
        "album\tyear\tkind\tsection\turl",
    ]
    for entry in entries:
        year = "" if entry.year is None else str(entry.year)
        lines.append(
            "\t".join([entry.title, year, section_kind(entry.section), entry.section, entry.url])
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    fetch = CachedFetcher(Path("data/raw"), delay=DELAY)
    meta = Path("meta/aquarium_albums.tsv")
    meta.parent.mkdir(parents=True, exist_ok=True)
    source = ", ".join(urljoin(BASE, page) for page in GRID_PAGES + LIST_PAGES)
    meta.write_text(albums_tsv(catalogue(fetch), source, date.today().isoformat()), "utf-8")
    songs = scrape(fetch)
    out = Path("data/songs/aquarium.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for song in songs:
            f.write(json.dumps(asdict(song), ensure_ascii=False) + "\n")
    print(f"{len(songs)} songs -> {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
