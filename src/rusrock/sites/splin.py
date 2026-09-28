import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from bs4.element import Comment, NavigableString

from rusrock.fetch import CachedFetcher
from rusrock.parsers import Song, normalize_text

BASE = "https://splean.ru"
SOURCE = "splean.ru"
EMPTY_PLACEHOLDERS = {"", ".", "-"}
TRACK_NUMBER = re.compile(r"^\d+\.\s*")
YEAR_SUFFIX = re.compile(r"\s*\(\d{4}\)$")
AUTHOR_SUFFIX = re.compile(r"\s*\(((?:стихи\s*-\s*)?[А-ЯЁ]\.\s?[А-ЯЁ][^()]*)\)$")
WORDS_PREFIX = re.compile(r"^стихи\s*-\s*", re.I)
# A lone line like "(Стихи В. Маяковского)" or "Автор текста - ..." at the start or end.
CREDIT_LINE = re.compile(
    r"^\(?\s*((?:Стихи|Слова|Автор текста)(?:\s*[-–—:]\s*|\s+)([А-ЯЁ].*?))\s*\)?$"
)

# ru.wikipedia «Сплин (группа)», раздел «Дискография» (oldid=153849126), keyed by the site's
# album titles. «Тайком» is a mini-album of new songs, so it ranks with studio albums.
KINDS = {
    "Пыльная быль": "studio",
    "Коллекционер оружия": "studio",
    "Фонарь под глазом": "studio",
    "Гранатовый альбом": "studio",
    "Альтависта": "studio",
    "25-й кадр": "studio",
    "Новые люди": "studio",
    "Реверсивная хроника событий": "studio",
    "Раздвоение личности": "studio",
    "Сигнал из космоса": "studio",
    "Обман зрения": "studio",
    "Резонанс, часть 1": "studio",
    "Резонанс, часть 2": "studio",
    "Ключ к шифру": "studio",
    "Встречная полоса": "studio",
    "Вира и Майна": "studio",
    "Тайком": "studio",
    "Тепло родного дома": "single",
    "Передайте это Гарри Поттеру, если вдруг его встретите": "single",
    "За семью печатями": "single",
    "Вирус": "single",
    "Я был влюблён в Вас": "single",
    "Топай!": "single",
    "Летучий голландец": "single",
    "Черновики": "solo",
    "Павловский парк": "solo",
}


@dataclass(frozen=True)
class Album:
    title: str
    year: int
    url: str


def parse_album_index(html: str, base: str) -> list[Album]:
    soup = BeautifulSoup(html, "html.parser")
    albums = []
    for box in soup.select("div.albums__container"):
        link = box.select_one("h2 a")
        label = box.select_one(".albums__copyright")
        year = re.search(r"\d{4}", label.get_text()) if label else None
        if link is None or year is None:
            continue
        albums.append(
            Album(link.get_text(strip=True), int(year.group()), urljoin(base, str(link["href"])))
        )
    return albums


def clean_title(raw: str) -> tuple[str, str]:
    title = YEAR_SUFFIX.sub("", TRACK_NUMBER.sub("", raw.strip()))
    match = AUTHOR_SUFFIX.search(title)
    if match is None:
        return title, ""
    return title[: match.start()].strip(), match.group(1).strip()


def _lyrics(block: Tag) -> str:
    # Lines end with <br>; newlines in the HTML source are only markup layout.
    parts: list[str] = []
    for node in block.descendants:
        if isinstance(node, Tag) and node.name in ("br", "p"):
            parts.append("\n")
        elif isinstance(node, NavigableString) and not isinstance(node, Comment):
            parts.append(re.sub(r"\s*\n\s*", " ", str(node)))
    return normalize_text("".join(parts))


def _split_credit(text: str) -> tuple[str, str, str]:
    lines = text.split("\n")
    for index in (0, len(lines) - 1):
        match = CREDIT_LINE.match(lines[index])
        if match:
            rest = lines[:index] + lines[index + 1 :]
            return normalize_text("\n".join(rest)), match.group(1), match.group(2)
    return text, "", ""


def _song(cell: Tag, album: str, url: str) -> Song | None:
    heading = cell.select_one("a.songs-table__show-lyrics")
    block = cell.select_one("div.songs-table__lyrics")
    if heading is None or block is None:
        return None
    title, credit = clean_title(heading.get_text(strip=True))
    lyricist = WORDS_PREFIX.sub("", credit) if WORDS_PREFIX.match(credit) else ""
    text, text_credit, text_lyricist = _split_credit(_lyrics(block))
    return Song(
        source=SOURCE,
        title=title,
        album=album,
        credit=credit or text_credit,
        lyricist=lyricist or text_lyricist,
        text="" if text in EMPTY_PLACEHOLDERS else text,
        url=url,
    )


def parse_album_page(html: str, url: str) -> list[Song]:
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.select_one("div.albums__container h2")
    album = heading.get_text(strip=True) if heading else ""
    cells = soup.select("table.songs-table td.songs-table__td-song")
    return [song for cell in cells if (song := _song(cell, album, url)) is not None]


def albums_tsv(albums: list[Album], kinds: dict[str, str], header: str) -> str:
    rows = [header, "album\tyear\tkind"]
    rows += [f"{a.title}\t{a.year}\t{kinds.get(a.title, 'other')}" for a in albums]
    return "\n".join(rows) + "\n"


def scrape_albums(fetch: CachedFetcher) -> list[Album]:
    return parse_album_index(fetch(f"{BASE}/music/", "utf-8"), base=BASE)


def scrape(fetch: CachedFetcher) -> list[Song]:
    songs = []
    for album in scrape_albums(fetch):
        found = parse_album_page(fetch(album.url, "utf-8"), url=album.url)
        if not found:
            print(f"no tracks: {album.title} {album.url}", file=sys.stderr)
        songs += found
    return songs


def main() -> None:
    fetch = CachedFetcher(Path("data/raw"), delay=2.0)
    header = (
        f"# Альбомы и годы со страницы {BASE}/music/ (2026-09-28). kind по разделу «Дискография» "
        "https://ru.wikipedia.org/wiki/Сплин_(группа) (oldid=153849126): студийные → studio "
        "(мини-альбом «Тайком» тоже studio), синглы → single, «Сольные проекты» → solo."
    )
    meta = Path("meta/splin_albums.tsv")
    meta.parent.mkdir(parents=True, exist_ok=True)
    meta.write_text(albums_tsv(scrape_albums(fetch), KINDS, header), encoding="utf-8")

    songs = scrape(fetch)
    out = Path("data/songs/splin.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for song in songs:
            f.write(json.dumps(asdict(song), ensure_ascii=False) + "\n")
    print(f"{len(songs)} songs -> {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
