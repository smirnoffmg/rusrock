import json
import re
import sys
from dataclasses import asdict, replace
from pathlib import Path
from urllib.parse import urldefrag, urljoin

from bs4 import BeautifulSoup, Tag
from bs4.element import Comment, NavigableString

from rusrock.fetch import CachedFetcher
from rusrock.parsers import Song, normalize_text

BASE = "http://ddtmusiclib.narod.ru/"
SOURCE = "ddtmusiclib.narod.ru"
# uCoz serves the archive re-encoded to UTF-8 without declaring a charset.
ENCODING = "utf-8"
CREDITS_PATH = Path("meta/ddt_credits.tsv")
OUT_PATH = Path("data/songs/ddt.jsonl")

Credits = dict[tuple[str, str], tuple[str, str]]


def parse_index(html: str, base: str) -> list[tuple[str, int, str]]:
    soup = BeautifulSoup(html, "html.parser")
    albums = []
    for anchor in soup.find_all("a", attrs={"name": re.compile(r"^alb\d{4}$")}):
        heading = anchor.find("h4")
        songs = anchor.find_next_sibling("ul")
        link = songs.find("a", href=True) if songs is not None else None
        if heading is None or link is None:
            continue
        page = urldefrag(urljoin(base, str(link["href"]))).url
        year = int(str(anchor["name"]).removeprefix("alb"))
        albums.append((heading.get_text(strip=True), year, page))
    return albums


def _song_text(anchor: Tag) -> str:
    # Every line in the source ends with "<br>\r\n", so source newlines carry the
    # line structure and <br> itself contributes nothing.
    parts: list[str] = []
    for node in anchor.next_siblings:
        if isinstance(node, Comment):
            break
        if isinstance(node, Tag):
            if node.name == "a" and node.has_attr("name"):
                break
            parts.append(node.get_text())
        elif isinstance(node, NavigableString):
            parts.append(str(node))
    # One line in texts85.html has a malformed "br>" tag left as text.
    return normalize_text(re.sub(r"(?m)br>\r?$", "", "".join(parts)))


def parse_album(html: str, url: str, album: str) -> list[Song]:
    soup = BeautifulSoup(html, "html.parser")
    songs = []
    for anchor in soup.find_all("a", attrs={"name": re.compile(r"^\d+$")}):
        heading = anchor.find("h4")
        if heading is None:
            continue
        songs.append(
            Song(
                source=SOURCE,
                title=heading.get_text(strip=True),
                album=album,
                credit="",
                lyricist="",
                text=_song_text(anchor),
                url=f"{url}#{anchor['name']}",
            )
        )
    return songs


def parse_credits(tsv: str) -> Credits:
    rows = [line.split("\t") for line in tsv.splitlines() if line and not line.startswith("#")]
    return {(album, title): (credit, lyricist) for album, title, credit, lyricist in rows[1:]}


def apply_credits(song: Song, credits: Credits) -> Song:
    found = credits.get((song.album, song.title)) or credits.get((song.album, ""))
    if found is None:
        return song
    credit, lyricist = found
    return replace(song, credit=credit, lyricist=lyricist)


def scrape(fetch: CachedFetcher) -> list[Song]:
    credits = parse_credits(CREDITS_PATH.read_text(encoding="utf-8"))
    songs = []
    for album, _, page in parse_index(fetch(urljoin(BASE, "texts.html"), ENCODING), base=BASE):
        for song in parse_album(fetch(page, ENCODING), url=page, album=album):
            if not song.text:
                print(f"no text: {song.url} {song.title}", file=sys.stderr)
                continue
            songs.append(apply_credits(song, credits))
    return songs


def main() -> None:
    songs = scrape(CachedFetcher(Path("data/raw"), delay=2.0))
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as f:
        for song in songs:
            f.write(json.dumps(asdict(song), ensure_ascii=False) + "\n")
    print(f"{len(songs)} songs -> {OUT_PATH}", file=sys.stderr)


if __name__ == "__main__":
    main()
