import json
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urldefrag, urljoin

import requests
from bs4 import BeautifulSoup, Tag
from bs4.element import Comment, NavigableString, PageElement

from rusrock.fetch import CachedFetcher
from rusrock.parsers import Song, normalize_text

BASE = "https://www.mikenaumenko.ru/"
SOURCE = "www.mikenaumenko.ru"
ENCODING = "utf-8"
# robots.txt: "User-agent: * / Crawl-delay: 10".
CRAWL_DELAY = 10.0
OUT_PATH = Path("data/songs/zoopark.jsonl")

_CHORD = r"[A-H](?:#|b)?(?:maj|min|m|dim|aug|sus|add)?\d*(?:/[A-H](?:#|b)?)?"
_CHORD_LINE = re.compile(rf"^\s*{_CHORD}(?:\s+{_CHORD})*\s*$")
_CHORD_TOKEN = re.compile(rf"(?:^|\s){_CHORD}(?=\s|$)")
_BLOCK_TAGS = {"p", "blockquote", "div", "center", "ul"}
# Mike signs the album credit line with his nickname only.
_FULL_NAMES = {"Майк": "Майк Науменко"}


@dataclass
class AlbumParse:
    songs: list[Song] = field(default_factory=list)
    chord_lines_removed: int = 0
    mixed_lines: list[tuple[str, str]] = field(default_factory=list)


def parse_index(html: str, base: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    pages: dict[str, None] = {}
    for a in soup.find_all("a", href=re.compile(r"^album_\w+\.html?#", re.IGNORECASE)):
        pages.setdefault(urldefrag(urljoin(base, str(a["href"]))).url, None)
    return list(pages)


def is_chord_line(line: str) -> bool:
    return bool(_CHORD_LINE.match(line))


def has_inline_chords(line: str) -> bool:
    return not is_chord_line(line) and bool(_CHORD_TOKEN.search(line))


def strip_chord_lines(text: str) -> tuple[str, int]:
    lines = text.split("\n")
    kept = [line for line in lines if not is_chord_line(line)]
    return "\n".join(kept), len(lines) - len(kept)


def album_credit(header_text: str) -> str:
    match = re.search(r"музыка и тексты песен:[^.]*", header_text)
    return " ".join(match.group(0).split()) if match else ""


def lyricist_for(credit: str, track: str) -> str:
    if not credit:
        return ""
    names = credit.split(":", 1)[1]
    for number, name in re.findall(r"кроме #(\d+)\s*-\s*([^,.]+)", names):
        if number == track:
            return str(name).strip()
    main = names.split(",", 1)[0].strip()
    return _FULL_NAMES.get(main, main)


def _album_name(soup: BeautifulSoup) -> str:
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    return " ".join(title.rsplit("Альбомы:", 1)[-1].split())


def _header_text(soup: BeautifulSoup) -> str:
    first = soup.find("a", attrs={"name": True})
    parts = []
    for node in soup.descendants:
        if node is first:
            break
        if isinstance(node, NavigableString) and not isinstance(node, Comment):
            parts.append(str(node))
    return " ".join("".join(parts).split())


def _song_title(heading: Tag) -> str:
    return " ".join(heading.get_text(" ").split()).removesuffix("*").strip()


def _within(node: PageElement, name: str) -> bool:
    return any(parent.name == name for parent in node.parents)


def _raw_body(heading: Tag) -> tuple[str, str]:
    inside = {id(node) for node in heading.descendants}
    parts: list[str] = []
    notes: list[str] = []
    node: PageElement | None = heading.next_element
    while node is not None:
        if id(node) not in inside:
            if isinstance(node, Tag):
                if node.name == "hr" or (node.name == "a" and node.get("name")):
                    break
                if node.name == "br":
                    parts.append("\n")
                elif node.name in _BLOCK_TAGS:
                    parts.append("\n\n")
            elif isinstance(node, NavigableString) and not isinstance(node, Comment):
                # <small> carries the site's editorial note, e.g. which original a cover is of.
                (notes if _within(node, "small") else parts).append(re.sub(r"\s+", " ", str(node)))
        node = node.next_element
    note = " ".join("".join(notes).split()).removeprefix("-").strip()
    return "".join(parts), note


def _drop_footnotes(text: str) -> str:
    return "\n".join(line for line in text.split("\n") if not line.startswith("* "))


def parse_album(html: str, url: str) -> AlbumParse:
    soup = BeautifulSoup(html, "html.parser")
    album = _album_name(soup)
    credit = album_credit(_header_text(soup))
    result = AlbumParse()
    for anchor in soup.find_all("a", attrs={"name": True}):
        heading = anchor.parent
        if not isinstance(heading, Tag):
            continue
        title = _song_title(heading)
        body, note = _raw_body(heading)
        raw, removed = strip_chord_lines(_drop_footnotes(normalize_text(body)))
        text = normalize_text(raw)
        result.chord_lines_removed += removed
        result.mixed_lines += [
            (title, line) for line in text.split("\n") if has_inline_chords(line)
        ]
        track = str(anchor["name"])
        result.songs.append(
            Song(
                source=SOURCE,
                title=title,
                album=album,
                credit=note or credit,
                lyricist=lyricist_for(credit, track),
                text=text,
                url=f"{url}#{track}",
            )
        )
    return result


def scrape(fetch: CachedFetcher) -> list[Song]:
    songs: list[Song] = []
    removed = 0
    for url in parse_index(fetch(urljoin(BASE, "texts.htm"), ENCODING), base=BASE):
        try:
            html = fetch(url, ENCODING)
        except requests.HTTPError as error:
            print(f"skipped {url}: {error}", file=sys.stderr)
            continue
        result = parse_album(html, url=url)
        songs += result.songs
        removed += result.chord_lines_removed
        for title, line in result.mixed_lines:
            print(f"chords mixed with words in {title!r}: {line!r}", file=sys.stderr)
        print(
            f"{len(result.songs):3d} {result.songs[0].album if result.songs else url}",
            file=sys.stderr,
        )
    print(f"chord-only lines removed: {removed}", file=sys.stderr)
    titles = Counter(song.title.casefold() for song in songs)
    print(f"unique titles (case-insensitive): {len(titles)}", file=sys.stderr)
    return songs


def main() -> None:
    songs = scrape(CachedFetcher(Path("data/raw"), delay=CRAWL_DELAY))
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as f:
        for song in songs:
            f.write(json.dumps(asdict(song), ensure_ascii=False) + "\n")
    print(f"{len(songs)} songs -> {OUT_PATH}", file=sys.stderr)


if __name__ == "__main__":
    main()
