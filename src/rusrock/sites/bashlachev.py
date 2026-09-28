import json
import re
import sys
import zipfile
from dataclasses import asdict, dataclass, replace
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree

from bs4 import BeautifulSoup, Tag

from rusrock.parsers import Song, normalize_text

SOURCE = "Как по лезвию (2006)"
LYRICIST = "А. Башлачёв"
EPUB = Path.home() / ".corpus/data/books/uploads/Башлачев А.Н._Как по лезвию.epub"
EPIGRAPH = "Эпиграф"
COMMENTARY_TITLE = "Комментарии"

CONTAINER_NS = {"c": "urn:oasis:names:tc:opendocument:xmlns:container"}
OPF_NS = {"opf": "http://www.idpf.org/2007/opf"}
ROMAN = re.compile(r"^[IVX]+$")
DATE = re.compile(r"^стр\.\s*\d+,?\s*(?:\(\*\);\s*)?([^.]*\d{4})")
YEAR = re.compile(r"\d{4}")


@dataclass(frozen=True)
class DateEntry:
    title: str
    date: str
    year: int | None


def spine_paths(zf: zipfile.ZipFile) -> list[str]:
    container = ElementTree.fromstring(zf.read("META-INF/container.xml"))
    rootfile = container.find(".//c:rootfile", CONTAINER_NS)
    if rootfile is None:
        raise ValueError("container.xml has no rootfile")
    opf_path = PurePosixPath(rootfile.attrib["full-path"])
    package = ElementTree.fromstring(zf.read(str(opf_path)))
    hrefs = {
        item.attrib["id"]: item.attrib["href"]
        for item in package.iterfind("opf:manifest/opf:item", OPF_NS)
    }
    return [
        str(opf_path.parent / hrefs[ref.attrib["idref"]])
        for ref in package.iterfind("opf:spine/opf:itemref", OPF_NS)
    ]


def poem_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for marker in soup.select("a.anchor"):
        marker.decompose()
    poems = soup.select("div.poem")
    stanzas = [
        "\n".join(line.get_text().strip() for line in stanza.find_all("p"))
        for poem in poems
        for stanza in poem.select("div.stanza")
    ]
    return normalize_text("\n\n".join(stanzas))


def _heading(soup: BeautifulSoup) -> tuple[str, str, str] | None:
    block = soup.select_one("div.titleblock")
    title = soup.select_one("div.titleblock p.title")
    if not isinstance(block, Tag) or title is None:
        return None
    level = next((c for c in ("h1", "h2") if block.select_one(f"div.{c}")), "")
    return level, title.get_text(strip=True), str(block.get("id", ""))


def parse_book(epub: Path) -> list[Song]:
    songs: list[Song] = []
    # None before the first numbered cycle (foreword), "" after the cycles end (interviews, notes).
    album: str | None = None
    with zipfile.ZipFile(epub) as zf:
        for path in spine_paths(zf):
            html = zf.read(path).decode("utf-8")
            soup = BeautifulSoup(html, "html.parser")
            heading = _heading(soup)
            if heading is None:
                continue
            level, title, anchor = heading
            if level == "h1":
                if ROMAN.match(title):
                    album = f"Цикл {title}"
                elif album is None and soup.select_one("div.poem"):
                    # The foreword closes with an untitled author poem, dated in the commentary.
                    text = poem_text(html)
                    songs.append(_song(text.split("\n", 1)[0], EPIGRAPH, text, f"epub:{path}"))
                else:
                    album = album and ""
                continue
            if album and soup.select_one("div.poem"):
                songs.append(_song(title, album, poem_text(html), f"epub:{path}#{anchor}"))
    return songs


def _song(title: str, album: str, text: str, url: str) -> Song:
    return Song(
        source=SOURCE, title=title, album=album, credit="", lyricist=LYRICIST, text=text, url=url
    )


def parse_dates(html: str) -> list[DateEntry]:
    soup = BeautifulSoup(html, "html.parser")
    entries = []
    for subtitle in soup.select("p.subtitle"):
        note = subtitle.find_next_sibling("p")
        match = DATE.match(note.get_text(strip=True)) if note is not None else None
        if match is None:
            continue
        date = match.group(1).strip()
        years = YEAR.findall(date)
        entries.append(
            DateEntry(subtitle.get_text(strip=True), date, int(years[-1]) if years else None)
        )
    return entries


def _title_key(title: str) -> str:
    words = re.findall(r"\w+", title.lower().replace("ё", "е"))
    return " ".join(w for w in words if w != "и")


def attach_titles(
    entries: list[DateEntry], titles: list[str]
) -> tuple[list[DateEntry], list[DateEntry]]:
    by_key = {_title_key(t): t for t in titles}
    matched, unmatched = [], []
    for entry in entries:
        bare = re.sub(r"\s*\([^)]*\)\s*$", "", entry.title)
        title = by_key.get(_title_key(entry.title)) or by_key.get(_title_key(bare))
        if title is None and entry.title.rstrip("»").endswith(("...", "…")):
            # An untitled text is cited by its first words; the book heading may run longer.
            prefix = _title_key(entry.title)
            title = next((t for k, t in by_key.items() if k.startswith(prefix)), None)
        if title is None:
            unmatched.append(entry)
        else:
            matched.append(replace(entry, title=title))
    return matched, unmatched


def read_commentary(epub: Path) -> str:
    with zipfile.ZipFile(epub) as zf:
        for path in spine_paths(zf):
            html = zf.read(path).decode("utf-8")
            heading = _heading(BeautifulSoup(html, "html.parser"))
            if heading is not None and heading[1] == COMMENTARY_TITLE:
                return html
    raise ValueError(f"no «{COMMENTARY_TITLE}» chapter in {epub}")


def write_dates(entries: list[DateEntry], out: Path) -> None:
    header = (
        "# А. Башлачёв, «Как по лезвию» (М.: Время, 2006), раздел «Комментарии»: дата написания "
        "как в книге.\n"
        "# year — последний год, названный в дате (для диапазонов — год окончания). "
        "title совпадает с Song.title в data/songs/bashlachev.jsonl.\n"
        "title\tdate\tyear\n"
    )
    rows = "".join(f"{e.title}\t{e.date}\t{e.year if e.year else ''}\n" for e in entries)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(header + rows, encoding="utf-8")


def main() -> None:
    songs = parse_book(EPUB)
    out = Path("data/songs/bashlachev.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for song in songs:
            f.write(json.dumps(asdict(song), ensure_ascii=False) + "\n")
    print(f"{len(songs)} songs -> {out}", file=sys.stderr)

    matched, unmatched = attach_titles(parse_dates(read_commentary(EPUB)), [s.title for s in songs])
    write_dates(matched, Path("meta/bashlachev_dates.tsv"))
    for entry in unmatched:
        print(f"date without text: {entry.title}", file=sys.stderr)


if __name__ == "__main__":
    main()
