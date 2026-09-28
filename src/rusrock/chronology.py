"""Lexicon by decade for one author: pre-registered religious word lists plus exploratory keyness.

Hypothesis and word lists were fixed before the computation (vault note «Словарь русского рока —
хронология Кинчева и Гребенщикова»); do not edit the lists after looking at the results.
"""

import csv
import json
import sys
from collections import Counter, defaultdict
from collections.abc import Sequence
from pathlib import Path

import numpy as np

from rusrock.keyness import log_odds_z

CHRISTIAN = frozenset(
    [
        "бог",
        "господь",
        "господень",
        "господний",
        "христос",
        "иисус",
        "спаситель",
        "спас",
        "богородица",
        "крест",
        "распятие",
        "храм",
        "церковь",
        "икона",
        "молитва",
        "молиться",
        "помолиться",
        "псалом",
        "аминь",
        "аллилуйя",
        "литургия",
        "пасха",
        "троица",
        "причастие",
        "покаяние",
        "каяться",
        "благодать",
        "благословить",
        "святой",
        "свят",
        "ангел",
        "архангел",
        "рай",
        "ад",
        "грех",
        "грешный",
        "грешник",
        "бес",
        "сатана",
        "дьявол",
        "воскресение",
        "воскреснуть",
        "воскресать",
        "апостол",
        "пророк",
        "евангелие",
        "мессия",
    ]
)
EASTERN = frozenset(
    [
        "будда",
        "дхарма",
        "мантра",
        "нирвана",
        "карма",
        "дзен",
        "кришна",
        "бодхисаттва",
        "лама",
        "тао",
        "сансара",
        "шива",
        "рама",
        "харе",
        "ом",
    ]
)
AUTHORS = ("Константин Кинчев", "Борис Гребенщиков")
SEED = 20260928


def decade(year: int) -> str:
    return f"{year // 10 * 10}-е"


def lexicon_rates(
    songs: Sequence[Sequence[str]], lexicon: frozenset[str] | set[str]
) -> tuple[float, float]:
    hits = sum(sum(1 for w in s if w in lexicon) for s in songs)
    words = sum(len(s) for s in songs)
    with_hit = sum(1 for s in songs if any(w in lexicon for w in s))
    return hits * 1000 / words, with_hit / len(songs)


def bootstrap_interval(
    songs: Sequence[Sequence[str]],
    lexicon: frozenset[str] | set[str],
    n: int = 2000,
    seed: int = SEED,
) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    hits = np.array([sum(1 for w in s if w in lexicon) for s in songs])
    words = np.array([len(s) for s in songs])
    idx = rng.integers(0, len(songs), size=(n, len(songs)))
    rates = hits[idx].sum(axis=1) * 1000 / words[idx].sum(axis=1)
    low, high = np.percentile(rates, [2.5, 97.5])
    return float(low), float(high)


def main() -> None:
    by_period: defaultdict[tuple[str, str], list[list[str]]] = defaultdict(list)
    with Path("data/tokens.jsonl").open(encoding="utf-8") as f:
        for line in f:
            song = json.loads(line)
            if song["author"] in AUTHORS and song["year"]:
                by_period[(song["author"], decade(song["year"]))].append(song["lemmas"])
    out = Path("data/chronology")
    out.mkdir(parents=True, exist_ok=True)
    with (out / "religious.tsv").open("w", encoding="utf-8", newline="") as dst:
        writer = csv.writer(dst, delimiter="\t")
        writer.writerow(
            ["author", "decade", "songs", "words", "lexicon", "per_1000", "low", "high", "share"]
        )
        for (author, period), songs in sorted(by_period.items()):
            for name, lexicon in (("христианская", CHRISTIAN), ("восточная", EASTERN)):
                rate, share = lexicon_rates(songs, lexicon)
                low, high = bootstrap_interval(songs, lexicon)
                writer.writerow(
                    [
                        author,
                        period,
                        len(songs),
                        sum(map(len, songs)),
                        name,
                        f"{rate:.2f}",
                        f"{low:.2f}",
                        f"{high:.2f}",
                        f"{share:.3f}",
                    ]
                )
    for author in AUTHORS:
        periods = {p: s for (a, p), s in by_period.items() if a == author}
        everything: Counter[str] = Counter(w for s in periods.values() for song in s for w in song)
        with (out / f"{author}.tsv").open("w", encoding="utf-8", newline="") as dst:
            writer = csv.writer(dst, delimiter="\t")
            writer.writerow(["decade", "lemma", "z", "f", "df"])
            for period, songs in sorted(periods.items()):
                target: Counter[str] = Counter(w for song in songs for w in song)
                df: Counter[str] = Counter(w for song in songs for w in set(song))
                z = log_odds_z(target, everything - target, everything, target.total())
                # As in the main keyness lists: a word from one or two songs is a chorus.
                ranked = [w for w in sorted(target, key=lambda w: -z[w]) if df[w] >= 3]
                for w in ranked[:40]:
                    writer.writerow([period, w, f"{z[w]:.2f}", target[w], df[w]])
    print(f"-> {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
