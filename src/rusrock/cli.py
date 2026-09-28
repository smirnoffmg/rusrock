import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from rusrock.fetch import CachedFetcher
from rusrock.parsers import (
    Song,
    parse_gro_index,
    parse_gro_song,
    parse_nau_album,
    parse_nau_index,
)

GRO_BASE = "https://www.gr-oborona.ru"
NAU_BASE = "https://naunaunau.narod.ru"


def scrape_gro(fetch: CachedFetcher) -> list[Song]:
    index = parse_gro_index(fetch(f"{GRO_BASE}/texts/", "cp1251"), base=GRO_BASE)
    songs = []
    for number, (_, url) in enumerate(index, 1):
        song = parse_gro_song(fetch(url, "cp1251"), url=url)
        if song is None:
            print(f"no text: {url}", file=sys.stderr)
        else:
            songs.append(song)
        if number % 50 == 0:
            print(f"{number}/{len(index)}", file=sys.stderr)
    return songs


def scrape_nau(fetch: CachedFetcher) -> list[Song]:
    index = parse_nau_index(fetch(f"{NAU_BASE}/texts/", "utf-8"), base=NAU_BASE)
    songs = []
    for _, url in index:
        songs.extend(parse_nau_album(fetch(url, "utf-8"), url=url))
    return songs


SCRAPERS = {"gro": scrape_gro, "nau": scrape_nau}


def main() -> None:
    parser = argparse.ArgumentParser(description="Download lyrics into data/songs/<site>.jsonl")
    parser.add_argument("site", choices=sorted(SCRAPERS))
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--delay", type=float, default=2.0)
    args = parser.parse_args()

    fetch = CachedFetcher(args.data / "raw", delay=args.delay)
    songs = SCRAPERS[args.site](fetch)
    out = args.data / "songs" / f"{args.site}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for song in songs:
            f.write(json.dumps(asdict(song), ensure_ascii=False) + "\n")
    print(f"{len(songs)} songs -> {out}", file=sys.stderr)
