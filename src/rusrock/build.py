import csv
import json
import re
import sys
from collections import Counter
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path

from rusrock.parsers import Song

LATIN_LOOKALIKES = str.maketrans("aceopxykmthb", "асеорхукмтнв")
INSTRUMENTAL_MARKERS = ("инструментал", "текст временно отсутствует")


def title_key(title: str) -> str:
    title = title.lower().replace("ё", "е").translate(LATIN_LOOKALIKES)
    return " ".join(re.findall(r"[а-яa-z0-9]+", title))


def is_instrumental(text: str) -> bool:
    words = re.findall(r"[а-яёa-z]+", text.lower())
    if len(words) < 5:
        return True
    return len(words) < 8 and any(marker in text.lower() for marker in INSTRUMENTAL_MARKERS)


def is_foreign(text: str) -> bool:
    letters = re.findall(r"[A-Za-zА-Яа-яЁё]", text)
    latin = sum(1 for ch in letters if ch.isascii())
    return bool(letters) and latin / len(letters) > 0.3


def _is_sole(name: str, surname: str) -> bool:
    # A hyphen between two names ("Е.Летов-К.Рябинов") joins coauthors; inside a
    # surname ("Лебедев-Кумач") it does not, but such names are never the main author.
    joined = re.search(r"[а-яё][-—–]\s*[А-ЯЁ]|\s[-—–]\s", name)
    return surname in name and not joined and not re.search(r"[,/;&]| и ", name)


def resolve_author(lyricist: str, credit: str, surname: str, default_to_main: bool) -> bool:
    if lyricist:
        return _is_sole(lyricist, surname)
    if credit:
        # A bare name or a role list ("Шевчук Ю. - вокал, ..., автор") names one person.
        names = re.findall(r"[А-ЯЁ]\.\s?[А-ЯЁ][а-яё]+|[А-ЯЁ][а-яё]+ [А-ЯЁ]\.", credit)
        return surname in credit and len(names) <= 1
    return default_to_main


@dataclass(frozen=True)
class Candidate[T]:
    title: str
    album: str
    rank: tuple[int, ...]
    accepted: bool
    payload: T


@dataclass(frozen=True)
class MergedSong[T]:
    best: Candidate[T]
    albums: tuple[str, ...]


def merge_versions[T](versions: list[Candidate[T]]) -> MergedSong[T] | None:
    # One edition crediting someone else is enough to doubt the whole song.
    if not all(v.accepted for v in versions):
        return None
    return MergedSong(
        best=min(versions, key=lambda v: v.rank),
        albums=tuple(sorted({v.album for v in versions})),
    )


@dataclass(frozen=True)
class Artist:
    key: str
    author: str
    surname: str
    default_to_main: bool
    excluded_album_kinds: frozenset[str] = frozenset()
    albums_must_be_known: bool = False


ARTISTS = (
    Artist("kino", "Виктор Цой", "Цой", True),
    Artist("gro", "Егор Летов", "Летов", False),
    Artist("aquarium", "Борис Гребенщиков", "Гребенщиков", True, frozenset({"other"})),
    Artist("ddt", "Юрий Шевчук", "Шевчук", True),
    Artist("alisa", "Константин Кинчев", "Кинчев", True),
    Artist("nau", "Илья Кормильцев", "Кормильцев", False, frozenset({"tribute"}), True),
    Artist("zoopark", "Майк Науменко", "Науменко", True),
    Artist("yanka", "Янка Дягилева", "Дягилева", False),
    Artist("bashlachev", "Александр Башлачёв", "Башлачёв", True),
    Artist("piknik", "Эдмунд Шклярский", "Шклярский", True),
    Artist("delfin", "Андрей Лысиков", "Лысиков", True, frozenset({"audioplay"})),
    Artist("splin", "Александр Васильев", "Васильев", True),
    Artist("auktyon", "Дмитрий Озерский", "Озерский", True),
)

KIND_RANK = {"studio": 0, "solo": 1, "single": 2, "live": 3, "compilation": 4, "other": 5}


@dataclass(frozen=True)
class CorpusSong:
    author: str
    artist: str
    title: str
    album: str
    albums: tuple[str, ...]
    year: int | None
    genre: str
    group: str
    text: str
    url: str


def read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return list(csv.DictReader((ln for ln in lines if not ln.startswith("#")), delimiter="\t"))


def _album_key(album: str) -> str:
    return album.strip().rstrip(".").lower()


def _to_year(value: str) -> int | None:
    return int(value) if value.strip().isdigit() else None


def build_artist(artist: Artist, songs: Iterable[Song], meta: Path) -> list[CorpusSong]:
    albums = {_album_key(r["album"]): r for r in read_tsv(meta / f"{artist.key}_albums.tsv")}
    aliases = {
        _album_key(r["alias"]): r["album"]
        for r in read_tsv(meta / "album_aliases.tsv")
        if r["artist"] == artist.key
    }
    foreign = {title_key(r["title"]) for r in read_tsv(meta / f"{artist.key}_lyricists.tsv")}
    dates = {title_key(r["title"]): r for r in read_tsv(meta / f"{artist.key}_dates.tsv")}
    genres = {title_key(r["title"]): r["kind"] for r in read_tsv(meta / f"{artist.key}_kinds.tsv")}
    first_releases = {
        title_key(r["title"]): r for r in read_tsv(meta / f"{artist.key}_song_albums.tsv")
    }

    groups: dict[str, list[Candidate[Song]]] = {}
    for song in songs:
        album = aliases.get(_album_key(song.album), song.album)
        info = albums.get(_album_key(album))
        if artist.albums_must_be_known and info is None:
            continue
        kind = info["kind"] if info else "other" if artist.albums_must_be_known else "studio"
        excluded = kind in artist.excluded_album_kinds
        if excluded or is_instrumental(song.text) or is_foreign(song.text):
            continue
        key = title_key(song.title)
        accepted = key not in foreign and resolve_author(
            song.lyricist, song.credit, artist.surname, artist.default_to_main
        )
        year = _to_year(info["year"]) if info else None
        rank = (KIND_RANK.get(kind, 5), year or 9999)
        groups.setdefault(key, []).append(
            Candidate(title=song.title, album=album, rank=rank, accepted=accepted, payload=song)
        )

    corpus = []
    for key, versions in groups.items():
        merged = merge_versions(versions)
        if merged is None:
            continue
        best = merged.best
        info = albums.get(_album_key(best.album))
        year = _to_year(info["year"]) if info else None
        if key in dates:
            year = _to_year(dates[key]["year"])
        album = best.album
        if key in first_releases:
            album = first_releases[key]["album"]
            year = _to_year(first_releases[key]["year"])
        group = album or (str(year) if year else "unknown")
        corpus.append(
            CorpusSong(
                author=artist.author,
                artist=artist.key,
                title=best.title,
                album=album,
                albums=merged.albums,
                year=year,
                genre=genres.get(key, "song" if artist.key != "bashlachev" else "unknown"),
                group=f"{artist.key}:{group}",
                text=best.payload.text,
                url=best.payload.url,
            )
        )
    return corpus


def load_songs(path: Path) -> list[Song]:
    with path.open(encoding="utf-8") as f:
        return [Song(**json.loads(line)) for line in f]


def main() -> None:
    data, meta = Path("data"), Path("meta")
    corpus = []
    for artist in ARTISTS:
        songs = load_songs(data / "songs" / f"{artist.key}.jsonl")
        corpus.extend(build_artist(artist, songs, meta))
    out = data / "corpus.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for song in corpus:
            f.write(json.dumps(asdict(song), ensure_ascii=False) + "\n")
    counts = Counter(song.author for song in corpus)
    print(f"{len(corpus)} songs, {len(counts)} authors -> {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
