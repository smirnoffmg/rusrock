import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from bs4.element import Comment, NavigableString

from rusrock.fetch import CachedFetcher
from rusrock.parsers import Song, normalize_text

BASE = "https://www.piknik.info"
SOURCE = "piknik.info"
SONG_HREF = re.compile(r"^/lyrics/index/song/\d+$")
COMPILATIONS_SECTION = "Сборники и Синглы"
INSTRUMENTAL_PLACEHOLDER = "Инструментальная композиция"


@dataclass(frozen=True)
class Album:
    title: str
    year: int
    kind: str
    url: str


def _album_kind(section_title: str, album_title: str) -> str:
    if section_title != COMPILATIONS_SECTION:
        return "studio"
    return "single" if "сингл" in album_title.lower() else "compilation"


def parse_album_index(html: str, base: str) -> list[Album]:
    soup = BeautifulSoup(html, "html.parser")
    albums = []
    for section in soup.select("section.albums__regular"):
        heading = section.select_one("span.title")
        section_title = heading.get_text(strip=True) if heading else ""
        for element in section.select("div.albums__regular__element"):
            link = next(
                (
                    a
                    for a in element.select("a[href*='/albums/view/id/']")
                    if a.get_text(strip=True)
                ),
                None,
            )
            year = element.select_one("span.date")
            if link is None or year is None:
                continue
            title = link.get_text(strip=True)
            albums.append(
                Album(
                    title=title,
                    year=int(year.get_text(strip=True)),
                    kind=_album_kind(section_title, title),
                    url=urljoin(base, str(link["href"])),
                )
            )
    return albums


def _unique_song_urls(links: list[Tag], base: str) -> list[str]:
    return list(dict.fromkeys(urljoin(base, str(a["href"])) for a in links))


def parse_album_page(html: str, base: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    return _unique_song_urls(soup.select("div.playlist a.name"), base)


def parse_songs_listing(html: str, base: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    return _unique_song_urls(
        [a for a in soup.select("section.albums-list a") if SONG_HREF.match(str(a["href"]))], base
    )


def _paragraph_text(block: Tag) -> str:
    # Lines end with <br>; the newlines in the HTML source are only markup layout.
    parts: list[str] = []
    for node in block.descendants:
        if isinstance(node, Tag) and node.name == "br":
            parts.append("\n")
        elif isinstance(node, NavigableString) and not isinstance(node, Comment):
            parts.append(re.sub(r"\s*\n\s*", " ", str(node)))
    return normalize_text("".join(parts))


def _lyrics(block: Tag) -> str:
    paragraphs = block.find_all("p") or [block]
    return normalize_text("\n\n".join(_paragraph_text(p) for p in paragraphs))


def _album_title(content: Tag) -> str:
    link = content.select_one("div.song-album a")
    if link is None:
        return ""
    match = re.search(r"«(.*)»", link.get_text(strip=True))
    return match.group(1).strip() if match else ""


def parse_song(html: str, url: str) -> Song | None:
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one("section.song .song__content")
    if content is None:
        return None
    heading = content.find("h1")
    block = content.select_one("div.text")
    if heading is None or block is None or not heading.get_text(strip=True):
        return None
    text = _lyrics(block)
    author = content.select_one("div.author")
    return Song(
        source=SOURCE,
        title=heading.get_text(strip=True),
        album=_album_title(content),
        credit=author.get_text(" ", strip=True) if author else "",
        lyricist="",
        text="" if text == INSTRUMENTAL_PLACEHOLDER else text,
        url=url,
    )


def albums_tsv(albums: list[Album], header: str) -> str:
    rows = [header, "album\tyear\tkind"]
    rows += [f"{a.title}\t{a.year}\t{a.kind}" for a in albums]
    return "\n".join(rows) + "\n"


def scrape_albums(fetch: CachedFetcher) -> list[Album]:
    return parse_album_index(fetch(f"{BASE}/albums", "utf-8"), base=BASE)


def scrape(fetch: CachedFetcher) -> list[Song]:
    track_lists = [parse_album_page(fetch(a.url, "utf-8"), base=BASE) for a in scrape_albums(fetch)]
    listed = parse_songs_listing(fetch(f"{BASE}/songs", "utf-8"), base=BASE)
    urls = list(dict.fromkeys([url for tracks in track_lists for url in tracks] + listed))
    songs = []
    for number, url in enumerate(urls, 1):
        song = parse_song(fetch(url, "utf-8"), url=url)
        if song is None:
            print(f"no text: {url}", file=sys.stderr)
        else:
            songs.append(song)
        if number % 50 == 0:
            print(f"{number}/{len(urls)}", file=sys.stderr)
    return songs


def main() -> None:
    fetch = CachedFetcher(Path("data/raw"), delay=2.0)
    albums = scrape_albums(fetch)
    header = (
        f"# Альбомы и годы со страницы {BASE}/albums ({date.today().isoformat()}). "
        "kind: разделы «Официальная дискография» → studio; «Сборники и Синглы» → single "
        "(«сингл» в названии) или compilation."
    )
    meta = Path("meta/piknik_albums.tsv")
    meta.parent.mkdir(parents=True, exist_ok=True)
    meta.write_text(albums_tsv(albums, header), encoding="utf-8")

    songs = scrape(fetch)
    out = Path("data/songs/piknik.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for song in songs:
            f.write(json.dumps(asdict(song), ensure_ascii=False) + "\n")
    print(f"{len(songs)} songs -> {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
