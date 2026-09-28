import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from rusrock.parsers import Song


@dataclass(frozen=True)
class Merged:
    song: Song
    albums: tuple[str, ...]


def normalize_title(title: str) -> str:
    title = re.sub(r"[.!?…]+$", "", title.strip().lower())
    return re.sub(r"\s+", " ", title).strip()


def normalize_person(name: str) -> str:
    return re.sub(r"\.\s*", ". ", name.strip()).strip()


def dedupe(songs: Iterable[Song], rank: Callable[[Song], tuple[int, ...]]) -> list[Merged]:
    groups: dict[str, list[Song]] = {}
    for s in songs:
        groups.setdefault(normalize_title(s.title), []).append(s)
    return [
        Merged(
            song=min(group, key=rank),
            albums=tuple(sorted({s.album for s in group})),
        )
        for group in groups.values()
    ]
