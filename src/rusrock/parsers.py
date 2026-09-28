import re
from dataclasses import dataclass
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from bs4.element import NavigableString


@dataclass(frozen=True)
class Song:
    source: str
    title: str
    album: str
    credit: str
    lyricist: str
    text: str
    url: str


def normalize_text(raw: str) -> str:
    lines = [line.strip() for line in raw.replace("\r", "").split("\n")]
    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def parse_gro_index(html: str, base: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    return [
        (a.get_text(strip=True), urljoin(base, str(a["href"])))
        for a in soup.find_all("a", href=re.compile(r"^/texts/\d+\.html$"))
    ]


def _labelled_value(soup: BeautifulSoup, label: str) -> str:
    for strong in soup.find_all("strong"):
        if strong.get_text(strip=True) == label and isinstance(strong.parent, Tag):
            return strong.parent.get_text(strip=True).removeprefix(label).strip()
    return ""


def parse_gro_song(html: str, url: str) -> Song | None:
    soup = BeautifulSoup(html, "html.parser")
    pre = soup.select_one("pre.song")
    heading = soup.select_one("#headers h3")
    if pre is None or heading is None:
        return None
    credit = _labelled_value(soup, "Автор:")
    return Song(
        source="gr-oborona.ru",
        title=heading.get_text(strip=True),
        album=_labelled_value(soup, "Альбом:"),
        credit=credit,
        lyricist=credit,
        text=normalize_text(pre.get_text()),
        url=url,
    )


def parse_nau_index(html: str, base: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    seen: dict[str, str] = {}
    for a in soup.find_all("a", href=re.compile(r"^/texts/[\w-]+\.html$")):
        url = urljoin(base, str(a["href"]))
        seen.setdefault(url, a.get_text(strip=True))
    return [(title, url) for url, title in seen.items()]


def _words_author(credit: str) -> str:
    # The site writes credits as "music - words"; a single name means both.
    return credit.split(" - ", 1)[-1].strip()


def _song_body(heading: Tag) -> str:
    parts: list[str] = []
    for node in heading.next_siblings:
        if isinstance(node, Tag):
            if node.name in ("h3", "hr") or (node.name == "a" and node.get("href") == "#start"):
                break
            if node.name == "br":
                parts.append("\n")
                continue
            if node.name == "i" and "authors" in (node.get("class") or []):
                continue
            parts.append(node.get_text())
        elif isinstance(node, NavigableString):
            parts.append(str(node).replace("\n", ""))
    return normalize_text("".join(parts))


def parse_nau_album(html: str, url: str) -> list[Song]:
    soup = BeautifulSoup(html, "html.parser")
    album_tag = soup.select_one("div.info h2")
    album = album_tag.get_text(strip=True) if album_tag else ""
    songs = []
    for heading in soup.find_all("h3", id=re.compile(r"^track\d+$")):
        authors = heading.find_next_sibling(["i", "h3"])
        is_credit = (
            authors is not None
            and authors.name == "i"
            and "authors" in (authors.get("class") or [])
        )
        credit = authors.get_text(strip=True) if authors is not None and is_credit else ""
        if credit.startswith("(") and credit.endswith(")"):
            credit = credit[1:-1].strip()
        songs.append(
            Song(
                source="naunaunau.narod.ru",
                title=heading.get_text(strip=True),
                album=album,
                credit=credit,
                lyricist=_words_author(credit),
                text=_song_body(heading),
                url=url,
            )
        )
    return songs
