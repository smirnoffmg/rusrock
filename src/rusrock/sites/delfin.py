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

BASE = "https://dolphinfanclub.net"
SOURCE = "dolphinfanclub.net"
WIKI_OLDID = 154902945
MAIN_AUTHOR = "Дельфин (Андрей Лысиков)"

# Releases of the «Дельфин» project and the side projects whose words the site credits
# to him alone. «Мальчишник», «Мишины Дельфины», «Механический пёс» and the Depeche Mode
# tribute are left out: the site names no sole author of their words.
SCOPE = {
    "ne-v-fokuse": "studio",
    "glubina-rezkosti": "studio",
    "plavniki": "studio",
    "tkani": "studio",
    "zvezda": "studio",
    "yunost": "studio",
    "sushchestvo": "studio",
    "andrej": "studio",
    "ona": "studio",
    "442": "studio",
    "kraj": "studio",
    "proshaj-oruzhie": "studio",
    "ya-budu-zhit": "live",
    "zapis-kontserta-19-11-04": "live",
    "lyubimye-pesni-fanatov-del-fina": "compilation",
    "andrej-deluxe-edition-remastered-2015": "compilation",
    "klinskoe-prodvizhenie": "compilation",
    "ost-dazhe-ne-dumaj": "compilation",
    "ost-dazhe-ne-dumaj-2": "compilation",
    "ost-zhest": "compilation",
    "grand-theft-auto-iv-vladivostok-fm": "compilation",
    "singl-glaza": "single",
    "mne-nuzhen-vrag-ost-voin-single": "single",
    "pomni-single": "single",
    "idu-iskat-single": "single",
    "ladoni-single": "single",
    "voprosy-single": "single",
    "gn-z11-single": "single",
    "prekrasno-single": "single",
    "mest-single": "single",
    "kto-tvoy-drug-single": "single",
    "tunnel-": "audioplay",  # аудиоспектакль к «Метро 2034», не песни
    "sovmestnye-raboty-i-neizdannoe": "other",
    "dubovyj-gaaj-stop-killing-dolphins": "other",
    "dubovyj-gaaj-sinyaya-lirika-2": "other",
}

# The site dates both «Дубовый Гаайъ» records 1996; Wikipedia gives the release years.
YEAR_OVERRIDES = {
    "dubovyj-gaaj-stop-killing-dolphins": 1994,
    "dubovyj-gaaj-sinyaya-lirika-2": 1995,
}


@dataclass(frozen=True)
class Album:
    title: str
    year: int | None
    slug: str
    url: str


@dataclass(frozen=True)
class Track:
    url: str
    credit: str


def parse_album_index(html: str, base: str) -> list[Album]:
    soup = BeautifulSoup(html, "html.parser")
    albums = []
    for block in soup.select("div.disco-album div.disco-title"):
        link = block.find("a")
        if not isinstance(link, Tag):
            continue
        href = str(link["href"])
        year = re.search(r"\((\d{4})\)\s*$", block.get_text(" ", strip=True))
        albums.append(
            Album(
                title=link.get_text(" ", strip=True),
                year=int(year.group(1)) if year else None,
                slug=href.rstrip("/").rsplit("/", 1)[-1],
                url=urljoin(base, href),
            )
        )
    return albums


def _split_credit(label: str) -> str:
    match = re.search(r"\(([^()]*слова[^()]*)\)\s*$", label)
    return match.group(1).strip() if match else ""


def parse_album_page(html: str, base: str) -> list[Track]:
    soup = BeautifulSoup(html, "html.parser")
    tracks: dict[str, str] = {}
    for link in soup.select("div.disco-tracklist a[href]"):
        url = urljoin(base, str(link["href"]))
        tracks.setdefault(url, _split_credit(link.get_text(" ", strip=True)))
    return [Track(url, credit) for url, credit in tracks.items()]


VERSION_MARK = re.compile(
    r"\s*(?:[(\[](?:radio edit|global mix|радиоверсия|полная первая версия|dolphin mix|\d{4})"
    r"[)\]]|remix by .+)$",
    re.IGNORECASE,
)


def clean_title(raw: str) -> str:
    # Editions of one song must share a title, or the builder counts them twice.
    title = re.sub(r"\s*\([^()]*слова[^()]*\)\s*$", "", raw.strip())
    title = re.sub(r"^(?:Дельфин|Dolphin) - ", "", title)
    title = re.sub(r"^bonus track \((.+)\)$", r"\1", title, flags=re.IGNORECASE)
    return VERSION_MARK.sub("", title).strip()


def words_author(credit: str) -> str:
    match = re.search(r"слова\s+(.+)$", credit)
    if match is None:
        return ""
    names = match.group(1).strip()
    return MAIN_AUTHOR if names == "Дельфина" else names


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


def parse_song(html: str, url: str, credit: str) -> Song | None:
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.select_one("#middleColumn > h1") or soup.find("h1")
    if not isinstance(heading, Tag) or not heading.get_text(strip=True):
        return None
    album = soup.select_one("div.disco-title h2")
    block = soup.select_one("div.songLyrics")
    return Song(
        source=SOURCE,
        title=clean_title(heading.get_text(" ", strip=True)),
        album=album.get_text(" ", strip=True) if album else "",
        credit=credit,
        lyricist=words_author(credit),
        text=_lyrics(block) if block else "",
        url=url,
    )


def albums_tsv(rows: list[tuple[str, int | None, str]], header: str) -> str:
    lines = [header, "album\tyear\tkind"]
    lines += [f"{title}\t{year if year else ''}\t{kind}" for title, year, kind in rows]
    return "\n".join(lines) + "\n"


def scrape_albums(fetch: CachedFetcher) -> list[Album]:
    albums = parse_album_index(fetch(f"{BASE}/discography", "utf-8"), base=BASE)
    for album in albums:
        if album.slug not in SCOPE:
            print(f"out of scope: {album.slug}", file=sys.stderr)
    return [a for a in albums if a.slug in SCOPE]


def scrape(fetch: CachedFetcher) -> list[Song]:
    tracks = [
        track
        for album in scrape_albums(fetch)
        for track in parse_album_page(fetch(album.url, "utf-8"), base=BASE)
    ]
    songs = []
    for number, track in enumerate(tracks, 1):
        song = parse_song(fetch(track.url, "utf-8"), url=track.url, credit=track.credit)
        if song is None:
            print(f"no song: {track.url}", file=sys.stderr)
        else:
            songs.append(song)
        if number % 50 == 0:
            print(f"{number}/{len(tracks)}", file=sys.stderr)
    return songs


def main() -> None:
    fetch = CachedFetcher(Path("data/raw"), delay=2.0)
    albums = scrape_albums(fetch)
    rows = [(a.title, YEAR_OVERRIDES.get(a.slug, a.year), SCOPE[a.slug]) for a in albums]
    header = (
        f"# Альбомы и годы со страницы {BASE}/discography ({date.today().isoformat()}); "
        "годы «Дубового Гаайъ» и список студийных альбомов по разделу «Дискография» "
        "https://ru.wikipedia.org/wiki/Дельфин_(музыкант) "
        f"(oldid={WIKI_OLDID}). kind задан вручную в SCOPE (src/rusrock/sites/delfin.py)."
    )
    meta = Path("meta/delfin_albums.tsv")
    meta.parent.mkdir(parents=True, exist_ok=True)
    meta.write_text(albums_tsv(rows, header), encoding="utf-8")

    songs = scrape(fetch)
    out = Path("data/songs/delfin.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for song in songs:
            f.write(json.dumps(asdict(song), ensure_ascii=False) + "\n")
    print(f"{len(songs)} songs -> {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
