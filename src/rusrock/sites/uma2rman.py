import json
import re
import sys
from collections.abc import Callable, Iterable
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag

from rusrock.build import title_key
from rusrock.fetch import CachedFetcher
from rusrock.parsers import Song, normalize_text

# The band's own site (umaturman.com, also in its web.archive.org copies) publishes no
# lyrics. pesni.net has them (robots.txt allows all agents, checked 28.09.2026) but no
# album pages, so releases and track lists come from ru.wikipedia and Discogs.
SOURCE = "pesni.net"
BASE = "https://www.pesni.net/"
INDEX_URLS = (urljoin(BASE, "text/umaturman"), urljoin(BASE, "text/uma2rman"))
DELAY = 2.0
OUT = Path("data/songs/uma2rman.jsonl")

Releases = tuple[tuple[str, tuple[str, ...]], ...]

RELEASES: Releases = (
    # ru.wikipedia «В городе N», oldid=154749786
    (
        "В городе N",
        (
            "Прасковья",
            "Ночной Дозор",
            "Раненный в висок",
            "Ума Турман",
            "Стрела",
            "Ты ушла",
            "Здравствуй, дорогая",
            "Объясни мне",
            "Ад",
            "Дай",
            "Тайд",
            "Ни кола, ни дачки",
            "Проститься",
        ),
    ),
    # ru.wikipedia «А может это сон?…», oldid=154751853
    (
        "А может это сон?…",
        (
            "Письмо Уме",
            "Он придёт",
            "Всё будет хорошо",
            "Скажи",
            "Эй, толстый",
            "Китаец Чонь Суй",
            "Зачем",
            "Всё, как обычно",
            "Теннис",
            "Колыбельная",
            "А может это сон",
            "Ты далеко",
            "Кто-то в городе",
            "Птица счастья",
            "В голове моей Г",
            "Река",
        ),
    ),
    # ru.wikipedia «Куда приводят мечты (альбом)», oldid=154984833
    (
        "Куда приводят мечты",
        (
            "Не позвонишь",
            "В городе лето",
            "Припева нет",
            "Куда приводят мечты",
            "Че Гевара",
            "Папины дочки",
            "Записка",
            "Любовь на сноуборде",
            "Весеннее обострение",
            "Дождь",
            "Блюз",
            "Кажется",
            "Париж",
            "Калифорния",
            "Женщина",
            "Романс",
            "Дождись",
        ),
    ),
    # ru.wikipedia «1825 (альбом)», oldid=154690275: only the tracks missing above.
    ("1825", ("Кино", "Дайте сигарету!")),
    # ru.wikipedia «В этом городе все сумасшедшие», oldid=149431087
    (
        "В этом городе все сумасшедшие",
        (
            "Не поминайте лихом",
            "В городе дождь",
            "Русский колорит",
            "Мама",
            "Лузер",
            "Ты вернешься",
            "После седьмой",
            "В этом городе все сумасшедшие",
            "В твоих глазах",
            "В пролесье",
            "Оля из сети",
            "Разметало",
            "Не жди",
            "Тебе понравится",
            "Я так и не узнал",
            "А знаешь, всё ещё будет",
            "Свеча",
        ),
    ),
    # ru.wikipedia «Uma2rman», oldid=154819447, «Синглы»
    ("Гороскоп", ("Гороскоп",)),
    # Discogs release 6997568 (EP «Хэппи», 2015)
    ("Хэппи", ("Хэппи", "Муза", "Нарисованная")),
    # ru.wikipedia «Uma2rman», oldid=154819447, «Дискография» (as Discogs 8540591)
    (
        "Пой, весна!",
        (
            "Пой, весна",
            "Один на один",
            "Мои красавицы",
            "Камон",
            "Токсины",
            "На другом берегу зимы",
            "Небо",
            "Мысли",
            "Хэппи",
            "Налей мне",
            "Диджитал Раша",
            "На пороге весны",
            "Пятница",
            "Лети, ветер ледяной",
            "Где-то опять салют",
        ),
    ),
    # ru.wikipedia «Uma2rman», oldid=154819447, «Дискография» (as Discogs 24452906)
    (
        "Не нашего мира",
        (
            "В одну сторону",
            "Тили Бом",
            "Калория",
            "Молитва",
            "Собака без передней ноги",
            "За тобой",
            "С любимыми не расставайтесь",
            "Жюль Верн",
            "Любимый город",
        ),
    ),
    # Discogs release 28665724
    ("Папины дочки. Новые", ("Папины дочки. Новые",)),
)

# pesni.net index titles that differ from the track lists above.
INDEX_ALIASES = {
    "он прийдет": "он придет",
    "а в городе лето": "в городе лето",
    "happy": "хэппи",
    "дайте дайте сигарету": "дайте сигарету",
}

# «Липкий пульс» (Symbol & Uma2rman, 2026) is the held-out test text of the study: it
# must never reach the training corpus, whatever the spelling of its title. Any other
# collaboration with Symbol is dropped along with it.
HELD_OUT_KEYS = ("липкий пульс", "симбол")
# title_key maps Latin look-alike letters to Cyrillic, so the band name is matched raw.
HELD_OUT_LATIN = "symbol"

# Keys go through title_key too: it turns Latin look-alikes ("Happy") into Cyrillic.
_ALIASES = {title_key(raw): title_key(fixed) for raw, fixed in INDEX_ALIASES.items()}
_ARTIST_LINK = re.compile(r"^/text/[\w-]+/")
_COUNTER_SUFFIX = re.compile(r"\s+\d$")
_PARENTHESES = re.compile(r"\s*\(.*?\)")


def _index_key(title: str) -> str:
    key = title_key(_COUNTER_SUFFIX.sub("", title.strip()))
    return _ALIASES.get(key, key)


def parse_index(html: str, base: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    index: dict[str, str] = {}
    for song_list in soup.select("div.song-list"):
        for a in song_list.find_all("a", href=_ARTIST_LINK):
            url = urljoin(base, str(a["href"]))
            title = a.get_text(" ", strip=True)
            index.setdefault(_index_key(title), url)
            index.setdefault(_index_key(_PARENTHESES.sub("", title)), url)
    return index


def find_track(index: dict[str, str], title: str) -> str | None:
    return index.get(title_key(title))


def _lyrics(block: Tag) -> str:
    # Source newlines only wrap the markup; lines end with <br>.
    parts: list[str] = []
    for node in block.descendants:
        if isinstance(node, Tag) and node.name == "br":
            parts.append("\n")
        elif isinstance(node, NavigableString):
            parts.append(re.sub(r"\s*\n\s*", " ", str(node)))
    return normalize_text("".join(parts))


def parse_song(html: str, url: str, album: str, title: str) -> Song | None:
    block = BeautifulSoup(html, "html.parser").select_one("div.song-block-text")
    text = _lyrics(block) if block is not None else ""
    if not text:
        return None
    return Song(source=SOURCE, title=title, album=album, credit="", lyricist="", text=text, url=url)


def is_held_out(title: str) -> bool:
    key = title_key(title)
    return HELD_OUT_LATIN in title.lower() or any(held in key for held in HELD_OUT_KEYS)


def drop_held_out(songs: Iterable[Song]) -> list[Song]:
    return [song for song in songs if not is_held_out(song.title)]


def scrape(
    fetch: CachedFetcher | Callable[[str, str], str], releases: Releases = RELEASES
) -> list[Song]:
    index: dict[str, str] = {}
    for index_url in INDEX_URLS:
        for key, page in parse_index(fetch(index_url, "utf-8"), base=BASE).items():
            index.setdefault(key, page)
    songs = []
    for album, titles in releases:
        for title in titles:
            if is_held_out(title):
                continue
            url = find_track(index, title)
            song = parse_song(fetch(url, "utf-8"), url, album, title) if url else None
            if song is None:
                print(f"not found: {album} / {title}", file=sys.stderr)
                continue
            songs.append(song)
    return drop_held_out(songs)


def main() -> None:
    songs = scrape(CachedFetcher(Path("data/raw"), delay=DELAY))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        for song in songs:
            f.write(json.dumps(asdict(song), ensure_ascii=False) + "\n")
    print(f"{len(songs)} songs -> {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
