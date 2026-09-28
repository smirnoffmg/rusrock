import csv
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from rusrock.richness import REPS, SEED, N, common_n, function_lemmas, load_corpus, sample_run

MIN_DF = 2
TOP = 30


@dataclass(frozen=True)
class Unique:
    df: int
    f: int


def unique_lemmas(
    corpus: Mapping[str, Sequence[list[str]]], function: frozenset[str]
) -> dict[str, dict[str, Unique]]:
    """Content lemmas of one author only, in at least MIN_DF of their songs; by df, then f."""
    f = {a: Counter(t for s in songs for t in s) for a, songs in corpus.items()}
    df = {a: Counter(t for s in songs for t in set(s)) for a, songs in corpus.items()}
    owners = Counter(t for counts in f.values() for t in counts)
    result = {}
    for author in corpus:
        found = [
            t for t, d in df[author].items() if d >= MIN_DF and owners[t] == 1 and t not in function
        ]
        found.sort(key=lambda t: (-df[author][t], -f[author][t], t))
        result[author] = {t: Unique(df[author][t], f[author][t]) for t in found}
    return result


def sampled_unique_counts(
    corpus: Mapping[str, Sequence[list[str]]],
    n: int,
    reps: int,
    seed: int,
    function: frozenset[str],
) -> dict[str, tuple[float, float]]:
    """Unique-lemma counts when every author contributes a random run of exactly n tokens."""
    rng = np.random.default_rng(seed)
    counts: dict[str, list[int]] = {a: [] for a in corpus}
    for _ in range(reps):
        sample = {a: sample_run(songs, n, rng) for a, songs in corpus.items()}
        for author, found in unique_lemmas(sample, function).items():
            counts[author].append(len(found))
    return {
        a: (float(np.mean(c)), float(np.std(c, ddof=1)) if reps > 1 else 0.0)
        for a, c in counts.items()
    }


def main() -> None:
    songs = {a: [s.lemmas for s in ss] for a, ss in load_corpus(Path("data/tokens.jsonl")).items()}
    function = function_lemmas(Path("data/freq"))
    sizes = {a: sum(map(len, ss)) for a, ss in songs.items()}
    types = {a: len({t for s in ss for t in s}) for a, ss in songs.items()}
    n = common_n(list(sizes.values()), N, 1000)
    unique = unique_lemmas(songs, function)
    sampled = sampled_unique_counts(songs, n, REPS, SEED, function)
    out = Path("data/unique")
    out.mkdir(parents=True, exist_ok=True)
    for author, found in unique.items():
        with (out / f"{author}.tsv").open("w", encoding="utf-8", newline="") as dst:
            writer = csv.writer(dst, delimiter="\t")
            writer.writerow(["lemma", "df", "f"])
            writer.writerows([t, u.df, u.f] for t, u in found.items())
    with (out / "summary.tsv").open("w", encoding="utf-8", newline="") as dst:
        writer = csv.writer(dst, delimiter="\t")
        writer.writerow(
            ["author", "n_tokens", "n_types", "unique", "unique_share", "unique_per_10k",
             "sample_n", "unique_sample_mean", "unique_sample_std", f"top{TOP}"]
        )  # fmt: skip
        for author in sorted(songs, key=lambda a: -sizes[a]):
            count = len(unique[author])
            mean, std = sampled[author]
            writer.writerow(
                [author, sizes[author], types[author], count, f"{count / types[author]:.4f}",
                 f"{count * 10_000 / sizes[author]:.1f}", n, f"{mean:.1f}", f"{std:.1f}",
                 " ".join(list(unique[author])[:TOP])]
            )  # fmt: skip
    print(f"N={n}; {len(unique)} authors -> {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
