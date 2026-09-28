import csv
import json
import re
import sys
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from bs4.element import NavigableString

from rusrock.fetch import CachedFetcher
from rusrock.parsers import Song, normalize_text

SOURCE = "kinoshnik.narod.ru"
BASE = "http://kinoshnik.narod.ru/"
INDEX_URL = urljoin(BASE, "txt/kinotext.htm")
ENCODING = "utf-8"
DEFAULT_LYRICIST = "В. Цой"
META = Path("meta")

BLOCK_TAGS = {"p", "div", "tr", "td", "table", "h1", "h2", "h3", "li", "ul", "ol"}
KIND_RANK = {"studio": 0, "live": 1, "compilation": 2, "other": 3}
CHORD = re.compile(r"[A-H](?:#|b)?(?:maj|min|m|dim|aug|sus|add)?\d*[+-]?(?:/[A-H](?:#|b)?)?")
LATIN_LOOKALIKES = str.maketrans("aceopxyk", "асеорхук")


@dataclass(frozen=True)
class Album:
    name: str
    year: int | None
    kind: str


def title_key(title: str) -> str:
    folded = title.casefold().replace("ё", "е").translate(LATIN_LOOKALIKES)
    return " ".join(re.sub(r"[^\w]+", " ", folded).split())


def is_chord_line(line: str) -> bool:
    tokens = line.split()
    return bool(tokens) and all(CHORD.fullmatch(token) for token in tokens)


def parse_index(html: str, base: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    seen: dict[str, str] = {}
    for a in soup.find_all("a", href=re.compile(r"^t\d+\.htm$")):
        url = urljoin(base, str(a["href"]))
        seen.setdefault(url, " ".join(a.get_text().split()))
    return [(title, url) for url, title in seen.items()]


def _page_lines(soup: BeautifulSoup) -> list[str]:
    # A <br> always ends a line (an empty one is a stanza break); a block tag
    # ends one only if it holds something, so markup whitespace between
    # paragraphs does not become blank lines, while a &nbsp; paragraph does.
    lines: list[str] = []
    buffer: list[str] = []

    def flush(hard: bool) -> None:
        text = "".join(buffer)
        if hard or text.strip(" "):
            lines.append(text.replace("\xa0", " ").strip())
        buffer.clear()

    def walk(node: Tag) -> bool:
        for child in node.children:
            if isinstance(child, Tag):
                if child.name == "h3":
                    return True
                if child.name in ("script", "style"):
                    continue
                if child.name == "br":
                    flush(hard=True)
                    continue
                block = child.name in BLOCK_TAGS
                if block:
                    flush(hard=False)
                stopped = walk(child)
                if block:
                    flush(hard=False)
                if stopped:
                    return True
            elif isinstance(child, NavigableString):
                buffer.append(re.sub(r"[ \t\r\n]+", " ", str(child)))
        return False

    walk(soup.body or soup)
    flush(hard=False)
    return lines


def parse_lyrics(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    lines = _page_lines(soup)
    start = next((i for i, line in enumerate(lines) if re.fullmatch(r"-{5,}", line)), None)
    if start is None:
        return None
    body = lines[start + 1 :]
    if "Аккорды:" in body:
        body = body[: body.index("Аккорды:")]
    text = normalize_text("\n".join(line for line in body if not is_chord_line(line)))
    return text or None


def parse_tracklist(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    titles = []
    for p in soup.find_all("p"):
        if p.find_previous("h3") is not None:
            break
        match = re.match(r"(\d{1,2})\s*\.\s*(.+)", " ".join(p.get_text(" ").split()))
        if match is None:
            continue
        italic = p.find("i")
        if italic is not None:
            titles.append(" ".join(italic.get_text(" ").split()))
        else:
            titles.append(re.sub(r"\s+\d{1,2}:\d{2}$", "", match.group(2)))
    return titles


def pick_lyricist(title: str, exceptions: Mapping[str, str]) -> str:
    return exceptions.get(title_key(title), DEFAULT_LYRICIST)


def choose_album(
    title: str,
    tracklists: Mapping[str, list[str]],
    albums: Mapping[str, Album],
    aliases: Mapping[str, str],
) -> str:
    key = title_key(aliases.get(title_key(title), title))
    pages = [
        page
        for page, tracks in tracklists.items()
        if page in albums and key in {title_key(track) for track in tracks}
    ]
    if not pages:
        return ""
    order = list(tracklists)

    def rank(page: str) -> tuple[int, bool, int, int]:
        album = albums[page]
        return (KIND_RANK[album.kind], album.year is None, album.year or 0, order.index(page))

    return albums[min(pages, key=rank)].name


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as f:
        rows = [line for line in f if line.strip() and not line.startswith("#")]
    return list(csv.DictReader(rows, delimiter="\t"))


def load_albums(path: Path) -> dict[str, Album]:
    return {
        row["page"]: Album(row["album"], int(row["year"]) if row["year"] else None, row["kind"])
        for row in _read_tsv(path)
    }


def load_title_map(path: Path, value: str) -> dict[str, str]:
    return {title_key(row["title"]): row[value] for row in _read_tsv(path)}


def scrape(fetch: CachedFetcher) -> list[Song]:
    albums = load_albums(META / "kino_albums.tsv")
    lyricists = load_title_map(META / "kino_lyricists.tsv", "lyricist")
    aliases = load_title_map(META / "kino_title_aliases.tsv", "album_title")
    tracklists = {
        page: parse_tracklist(fetch(urljoin(BASE, f"{page}.htm"), ENCODING)) for page in albums
    }
    songs = []
    for title, url in parse_index(fetch(INDEX_URL, ENCODING), base=INDEX_URL):
        text = parse_lyrics(fetch(url, ENCODING))
        if text is None:
            print(f"no text: {url}", file=sys.stderr)
            continue
        songs.append(
            Song(
                source=SOURCE,
                title=title,
                album=choose_album(title, tracklists, albums, aliases),
                credit="",
                lyricist=pick_lyricist(title, lyricists),
                text=text,
                url=url,
            )
        )
    return songs


def main() -> None:
    songs = scrape(CachedFetcher(Path("data/raw"), delay=2.0))
    out = Path("data/songs/kino.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for song in songs:
            f.write(json.dumps(asdict(song), ensure_ascii=False) + "\n")
    print(f"{len(songs)} songs -> {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
