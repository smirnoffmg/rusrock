import csv
import json
import sys
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt

SEED = 20260928
REPS = 100
SHUFFLES = 20
N = 5000


@dataclass(frozen=True)
class Song:
    lemmas: list[str]
    forms: list[str]
    genre: str


def ttr(tokens: Sequence[str]) -> float:
    return len(set(tokens)) / len(tokens)


def sample_run(songs: Sequence[list[str]], n: int, rng: np.random.Generator) -> list[list[str]]:
    """Whole songs in random order, without replacement, until exactly n tokens."""
    if sum(len(s) for s in songs) < n:
        raise ValueError(f"only {sum(len(s) for s in songs)} tokens, {n} requested")
    run, left = [], n
    for i in rng.permutation(len(songs)):
        if left == 0:
            break
        song = songs[i][:left]
        if song:
            run.append(song)
            left -= len(song)
    return run


def sampled_ttr(songs: Sequence[list[str]], n: int, reps: int, seed: int) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    values = [ttr([t for s in sample_run(songs, n, rng) for t in s]) for _ in range(reps)]
    return float(np.mean(values)), float(np.std(values, ddof=1)) if reps > 1 else 0.0


def growth_curve(tokens: Sequence[str]) -> npt.NDArray[np.int64]:
    seen: set[str] = set()
    curve = np.empty(len(tokens), dtype=np.int64)
    for i, token in enumerate(tokens):
        seen.add(token)
        curve[i] = len(seen)
    return curve


def mean_growth_curve(
    songs: Sequence[list[str]], shuffles: int, seed: int
) -> npt.NDArray[np.float64]:
    rng = np.random.default_rng(seed)
    curves = [
        growth_curve([t for i in rng.permutation(len(songs)) for t in songs[i]])
        for _ in range(shuffles)
    ]
    return np.mean(curves, axis=0)


def heaps_fit(n: npt.NDArray[np.float64], v: npt.NDArray[np.float64]) -> tuple[float, float, float]:
    """Least squares on log V = log k + beta log N; returns k, beta, R²."""
    x, y = np.log(n), np.log(v)
    beta, log_k = np.polyfit(x, y, 1)
    residual = y - (log_k + beta * x)
    r2 = 1 - float(residual @ residual) / float(((y - y.mean()) ** 2).sum())
    return float(np.exp(log_k)), float(beta), r2


def heaps_for_author(songs: Sequence[list[str]]) -> tuple[float, float, float]:
    curve = mean_growth_curve(songs, SHUFFLES, SEED)
    # A geometric grid keeps the long tail of the curve from outweighing its start.
    grid = np.unique(np.geomspace(100, len(curve), 50).astype(np.int64))
    return heaps_fit(grid.astype(np.float64), curve[grid - 1])


def is_word(lemma: str) -> bool:
    return any(ch.isalpha() for ch in lemma)


def load_corpus(path: Path) -> dict[str, list[Song]]:
    corpus: defaultdict[str, list[Song]] = defaultdict(list)
    with path.open(encoding="utf-8") as f:
        for line in f:
            song = json.loads(line)
            pairs = [(lem, form) for lem, form in zip(song["lemmas"], song["forms"], strict=True)]
            pairs = [(lem, form) for lem, form in pairs if is_word(lem)]
            if pairs:
                lemmas, forms = map(list, zip(*pairs, strict=True))
                corpus[song["author"]].append(Song(lemmas, forms, song["genre"]))
    return dict(corpus)


def function_lemmas(freq_dir: Path) -> frozenset[str]:
    """A lemma flagged closed-class for any author is closed-class for all of them."""
    found = set()
    for path in freq_dir.glob("*.tsv"):
        with path.open(encoding="utf-8") as f:
            found |= {
                r["lemma"] for r in csv.DictReader(f, delimiter="\t") if r["function"] == "True"
            }
    return frozenset(found)


def common_n(sizes: Sequence[int], wanted: int, step: int) -> int:
    smallest = min(sizes)
    return wanted if smallest >= wanted else smallest // step * step


def main() -> None:
    corpus = load_corpus(Path("data/tokens.jsonl"))
    function = function_lemmas(Path("data/freq"))
    lemmas = {a: [s.lemmas for s in songs] for a, songs in corpus.items()}
    forms = {a: [s.forms for s in songs] for a, songs in corpus.items()}
    content = {a: [[t for t in s if t not in function] for s in ss] for a, ss in lemmas.items()}
    sizes = {a: sum(map(len, ss)) for a, ss in lemmas.items()}
    n = common_n(list(sizes.values()), N, 1000)
    n_content = common_n([sum(map(len, ss)) for ss in content.values()], N, 1000)
    out = Path("data/richness")
    out.mkdir(parents=True, exist_ok=True)

    rows = []
    for author in sorted(corpus, key=lambda a: -sizes[a]):
        lm, ls = sampled_ttr(lemmas[author], n, REPS, SEED)
        fm, fs = sampled_ttr(forms[author], n, REPS, SEED)
        cm, cs = sampled_ttr(content[author], n_content, REPS, SEED)
        k, beta, r2 = heaps_for_author(lemmas[author])
        rows.append([author, sizes[author], lm, ls, fm, fs, cm, cs, k, beta, r2])
    with (out / "richness.tsv").open("w", encoding="utf-8", newline="") as dst:
        writer = csv.writer(dst, delimiter="\t")
        writer.writerow(
            ["author", "n_tokens", "ttr_lemma_mean", "ttr_lemma_std", "ttr_form_mean",
             "ttr_form_std", "ttr_content_mean", "ttr_content_std", "heaps_k", "heaps_beta",
             "heaps_r2"]
        )  # fmt: skip
        writer.writerows([r[0], r[1], *(f"{x:.4f}" for x in r[2:])] for r in rows)

    by_n = []
    for size in (1000, 2000, 3500, n, min(sizes.values()) // 1000 * 1000):
        for author in corpus:
            by_n.append([author, "lemma", size, *sampled_ttr(lemmas[author], size, REPS, SEED)])
    with (out / "ttr_by_n.tsv").open("w", encoding="utf-8", newline="") as dst:
        writer = csv.writer(dst, delimiter="\t")
        writer.writerow(["author", "unit", "n", "ttr_mean", "ttr_std"])
        writer.writerows(
            [*r[:3], f"{r[3]:.4f}", f"{r[4]:.4f}"] for r in dict.fromkeys(map(tuple, by_n))
        )

    genre_rows = []
    for author, songs in corpus.items():
        by_genre: defaultdict[str, list[list[str]]] = defaultdict(list)
        for s in songs:
            by_genre[s.genre].append(s.lemmas)
        if len(by_genre) < 2:
            continue
        g_n = common_n([sum(map(len, ss)) for ss in by_genre.values()], N, 500)
        for genre, ss in sorted(by_genre.items()):
            mean, std = sampled_ttr(ss, g_n, REPS, SEED)
            genre_rows.append([author, genre, sum(map(len, ss)), g_n, f"{mean:.4f}", f"{std:.4f}"])
    with (out / "genre.tsv").open("w", encoding="utf-8", newline="") as dst:
        writer = csv.writer(dst, delimiter="\t")
        writer.writerow(["author", "genre", "n_tokens", "n", "ttr_mean", "ttr_std"])
        writer.writerows(genre_rows)
    print(f"N={n}, N_content={n_content}; {len(rows)} authors -> {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
