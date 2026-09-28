import json
import re
import sys
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from rusrock.build import title_key
from rusrock.fetch import CachedFetcher
from rusrock.parsers import Song, normalize_text

SOURCE = "auktyon.ru"
# The https certificate does not verify; the band's site is served as-is over http.
BASE = "http://auktyon.ru/"
INDEX_URL = urljoin(BASE, "teksty.html")
ENCODING = "cp1251"
DELAY = 2.0
OUT = Path("data/songs/auktyon.jsonl")

# The band's site stops at 2000; later albums come from a generic lyrics site
# (robots.txt allows all agents, checked 28.09.2026) that has no album pages, so
# the track lists below are taken from the ru.wikipedia album articles.
TXT_SOURCE = "txt-song.ru"
TXT_BASE = "https://txt-song.ru/"
TXT_ARTIST_URL = urljoin(TXT_BASE, "artist/auktsyon")
LATER_ALBUMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    # «Это мама», oldid=154553547
    (
        "Это мама",
        (
            "Якоря",
            "Зима",
            "Заведующий (Копорье)",
            "Стало",
            "Фа-фа (Это мама)",
            "Голова-нога",
            "Зимы не будет",
            "Осколки",
            "Самолёт",
            "О погоде",
        ),
    ),
    # «Девушки поют», oldid=152820442
    (
        "Девушки поют",
        (
            "Профукал",
            "Падал",
            "Ждать",
            "Роган Борн",
            "Там-дам",
            "Слова",
            "Дебил",
            "Возле меня",
            "Долги",
            "Девушки поют",
        ),
    ),
    # «Юла (альбом)», oldid=154567664
    (
        "Юла",
        (
            "Огонь",
            "Хомба",
            "Метели",
            "Шишки",
            "Полдень",
            "Природа",
            "Кожаный",
            "Мимо",
            "Летучая",
            "Карандаши и палочки",
            "Юла",
        ),
    ),
    # «На солнце», oldid=154994606
    (
        "На солнце",
        (
            "Сынок",
            "И день и ночь",
            "Пропал",
            "Луна упала",
            "Чайки",
            "Плыть",
            "На солнце",
            "Мир тает",
        ),
    ),
    # «Мечты (альбом)», oldid=152370854
    (
        "Мечты",
        (
            "Догоняя волны",
            "Сердце",
            "Мечты",
            "Очень белые глаза",
            "Спасательный круг",
            "Затаись и жди",
            "Каникулы",
            "Тиша",
            "Волны те",
        ),
    ),
    # «Сокровище (альбом)», oldid=153931048
    (
        "Сокровище",
        (
            "Борода",
            "Топ-топ",
            "Псалом 37",
            "Мусульманин",
            "Трам, пам-пам",
            "Юрочка",
            "Ты сказала мне",
            "Лето",
        ),
    ),
)

_ALBUM_LINK = re.compile(r"^/text/[\w-]+\.html$")
_YEAR_SUFFIX = re.compile(r"\s+\d{4}$")
_HEADING = re.compile(r"<b>(.*?)</b>", re.S | re.I)
_INSTRUMENTAL = re.compile(r"^\(инструментал\w*\)$")
# «пр:» opens a chorus and a lone «пр.» repeats it; neither is sung.
_CHORUS_MARK = re.compile(r"^[ \t\xa0]*пр[:.][ \t\xa0]*(?:\n|$)", re.M)


def parse_index(html: str, base: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    return [
        (_YEAR_SUFFIX.sub("", a.get_text(" ", strip=True)), urljoin(base, str(a["href"])))
        for a in soup.find_all("a", href=_ALBUM_LINK)
    ]


def _html_to_text(fragment: str) -> str:
    # Source newlines only wrap the markup; line breaks come from <br> and <p>.
    fragment = re.sub(r"\s*\n\s*", " ", fragment)
    fragment = re.sub(r"<br\s*/?>", "\n", fragment, flags=re.I)
    fragment = re.sub(r"<p\b[^>]*>", "\n\n", fragment, flags=re.I)
    return BeautifulSoup(fragment, "html.parser").get_text()


def _song_text(chunk: str) -> str:
    # Text after </b> up to the first <p> is a note on the heading line ("исп. ...").
    body = re.split(r"<p\b[^>]*>", chunk, maxsplit=1, flags=re.I)
    if len(body) < 2:
        return ""
    return normalize_text(_CHORUS_MARK.sub("", _html_to_text(body[1])))


def parse_album(html: str, url: str, album: str) -> list[Song]:
    # The page never closes its <p> tags, so a DOM walk nests every song inside the
    # previous one; splitting the raw markup on <b> headings is what stays reliable.
    start = html.find("</h2>")
    content = html[start:] if start >= 0 else html
    end = content.find("</td>")
    content = content[:end] if end >= 0 else content
    parts = _HEADING.split(content)
    songs = []
    section = ""
    for raw_title, chunk in zip(parts[1::2], parts[2::2], strict=True):
        title = BeautifulSoup(raw_title, "html.parser").get_text(" ", strip=True)
        if title.endswith(":"):
            title = title.rstrip(":").strip()
            section = title
        text = _song_text(chunk)
        if not text or _INSTRUMENTAL.match(text):
            print(f"no text: {url} {title}", file=sys.stderr)
            continue
        songs.append(
            Song(
                source=SOURCE,
                title=title,
                album=album,
                credit=section,
                lyricist="",
                text=text,
                url=url,
            )
        )
    return songs


def parse_txt_song_index(html: str, base: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    index: dict[str, str] = {}
    for a in soup.find_all("a", href=re.compile(r"^/song/[\w-]+$")):
        index.setdefault(title_key(a.get_text(" ", strip=True)), urljoin(base, str(a["href"])))
    return index


def find_track(index: dict[str, str], title: str) -> str | None:
    found = index.get(title_key(title))
    if found is None:
        found = index.get(title_key(re.sub(r"\s*\(.*?\)", "", title)))
    return found


def parse_txt_song(html: str, url: str, album: str, title: str) -> Song | None:
    lyrics = BeautifulSoup(html, "html.parser").select_one("div.lyrics")
    if lyrics is None:
        return None
    text = normalize_text(_html_to_text(lyrics.decode_contents()))
    if not text:
        return None
    return Song(
        source=TXT_SOURCE, title=title, album=album, credit="", lyricist="", text=text, url=url
    )


def scrape_later_albums(fetch: CachedFetcher) -> list[Song]:
    index = parse_txt_song_index(fetch(TXT_ARTIST_URL, "utf-8"), base=TXT_BASE)
    songs = []
    for album, titles in LATER_ALBUMS:
        for title in titles:
            url = find_track(index, title)
            song = parse_txt_song(fetch(url, "utf-8"), url, album, title) if url else None
            if song is None:
                print(f"not found: {album} / {title}", file=sys.stderr)
                continue
            songs.append(song)
    return songs


def scrape(fetch: CachedFetcher) -> list[Song]:
    songs = []
    for album, url in parse_index(fetch(INDEX_URL, ENCODING), base=BASE):
        songs.extend(parse_album(fetch(url, ENCODING), url=url, album=album))
    return songs + scrape_later_albums(fetch)


def main() -> None:
    songs = scrape(CachedFetcher(Path("data/raw"), delay=DELAY))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        for song in songs:
            f.write(json.dumps(asdict(song), ensure_ascii=False) + "\n")
    print(f"{len(songs)} songs -> {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
