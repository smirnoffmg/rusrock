import json
import re
import sys
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from rusrock.fetch import CachedFetcher
from rusrock.parsers import Song, normalize_text

SOURCE = "accords.site"
# The site's https certificate has expired; plain http serves the same pages.
BASE = "http://accords.site/"
INDEX_URL = urljoin(BASE, "txt.php?s=002")
DELAY = 2.0
OUT = Path("data/songs/alisa.jsonl")

# Chord roots include Cyrillic look-alikes (А В С Е Н): the site sometimes types them.
_ROOT = "[A-HАВСЕН][#b]?"
_CHORD = re.compile(
    rf"{_ROOT}(?:maj|min|m|dim|aug|sus|add)?[\d+\-#b]*"
    rf"(?:(?:maj|sus|add|dim)[\d+\-#b]*)*(?:/[A-Ha-hАВСЕН][#b]?)?"
)
_CREDIT = re.compile(r"^\(([^()]+)\)$")
_HEADING = re.compile(r"^(.*?)\s*\((\d{4})\)$")
_LATIN_TO_CYRILLIC = str.maketrans("aceopxyABCEHKMOPTX", "асеорхуАВСЕНКМОРТХ")


def parse_index(html: str, base: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    urls: dict[str, None] = {}
    for a in soup.find_all("a", href=re.compile(r"^txt\.php\?s=002&d=\d+$")):
        urls.setdefault(urljoin(base, str(a["href"])))
    return list(urls)


def split_album_heading(heading: str) -> tuple[str, int | None]:
    match = _HEADING.match(heading.strip())
    if match is None:
        return heading.strip(), None
    return match.group(1), int(match.group(2))


def is_chord_line(line: str) -> bool:
    tokens = line.split()
    return bool(tokens) and all(_CHORD.fullmatch(token) for token in tokens)


def fix_homoglyphs(text: str) -> str:
    def fix(match: re.Match[str]) -> str:
        word = match.group()
        if re.search("[а-яёА-ЯЁ]", word) and re.search("[A-Za-z]", word):
            return word.translate(_LATIN_TO_CYRILLIC)
        return word

    return re.sub(r"\w+", fix, text)


def clean_lyrics(raw: str) -> tuple[str, str, int]:
    lines = raw.replace("\r", "").split("\n")
    first = next((i for i, line in enumerate(lines) if line.strip()), None)
    credit = ""
    if first is not None and (match := _CREDIT.match(lines[first].strip())):
        credit = match.group(1).strip()
        del lines[first]
    kept = [line for line in lines if not is_chord_line(line)]
    return credit, normalize_text(fix_homoglyphs("\n".join(kept))), len(lines) - len(kept)


def words_author(credit: str) -> str:
    # The site writes "music - words"; a lone name there turned out to be the composer
    # (e.g. Кривозеркалье, whose words are by Утехин per Wikipedia), so it says nothing
    # about the words.
    if " - " not in credit:
        return ""
    words = credit.split(" - ", 1)[1]
    return re.sub(r"(?<=\.)\s+(?=\w)", "", words).strip()


def parse_album(html: str, url: str) -> list[Song]:
    soup = BeautifulSoup(html, "html.parser")
    blocks = soup.find_all("div", id=re.compile(r"^v\d+$"))
    if not blocks:
        return []
    heading = blocks[0].find_previous("h2")
    album, _ = split_album_heading(heading.get_text(strip=True) if heading else "")
    songs = []
    for block in blocks:
        pre = block.find("pre")
        title = block.find("b")
        if pre is None or title is None:
            print(f"no text: {url}#{block['id']}", file=sys.stderr)
            continue
        credit, text, _ = clean_lyrics(pre.get_text())
        songs.append(
            Song(
                source=SOURCE,
                title=fix_homoglyphs(title.get_text(strip=True)),
                album=album,
                credit=credit,
                lyricist=words_author(credit),
                text=text,
                url=f"{url}#{block['id']}",
            )
        )
    return songs


def scrape(fetch: CachedFetcher) -> list[Song]:
    songs = []
    for url in parse_index(fetch(INDEX_URL, "utf-8"), base=BASE):
        songs.extend(parse_album(fetch(url, "utf-8"), url=url))
    return songs


def main() -> None:
    songs = scrape(CachedFetcher(Path("data/raw"), delay=DELAY))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        for song in songs:
            f.write(json.dumps(asdict(song), ensure_ascii=False) + "\n")
    print(f"{len(songs)} songs -> {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
