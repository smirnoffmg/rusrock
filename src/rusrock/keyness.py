import csv
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path


def log_odds_z(
    target: Counter[str], rest: Counter[str], prior: Counter[str], alpha0: float
) -> dict[str, float]:
    """Log-odds ratio with informative Dirichlet prior, as a z-score.

    Monroe, Colaresi, Quinn, «Fightin' Words» (2008), eq. 23: alpha_w = alpha0 * p(w) in the
    background; Jurafsky & Martin, SLP, eq. 23.9–23.11 for delta and its variance.
    """
    n_target, n_rest, n_prior = target.total(), rest.total(), prior.total()
    scores = {}
    for word in target.keys() | rest.keys():
        aw = alpha0 * prior[word] / n_prior
        yt, yr = target[word] + aw, rest[word] + aw
        delta = math.log(yt / (n_target + alpha0 - yt)) - math.log(yr / (n_rest + alpha0 - yr))
        scores[word] = delta / math.sqrt(1 / yt + 1 / yr)
    return scores


def dunning_g2(target: Counter[str], rest: Counter[str]) -> dict[str, float]:
    """Log-likelihood G², signed: positive when the word is relatively more frequent in target."""
    n_target, n_rest = target.total(), rest.total()
    total = n_target + n_rest
    scores = {}
    for word in target.keys() | rest.keys():
        a, b = target[word], rest[word]
        expected_a = n_target * (a + b) / total
        expected_b = n_rest * (a + b) / total
        g2 = 2 * sum(o * math.log(o / e) for o, e in ((a, expected_a), (b, expected_b)) if o)
        scores[word] = g2 if a / n_target >= b / n_rest else -g2
    return scores


def main() -> None:
    counts: defaultdict[str, Counter[str]] = defaultdict(Counter)
    df: defaultdict[str, Counter[str]] = defaultdict(Counter)
    with Path("data/tokens.jsonl").open(encoding="utf-8") as f:
        for line in f:
            song = json.loads(line)
            counts[song["author"]].update(song["lemmas"])
            df[song["author"]].update(set(song["lemmas"]))
    everything: Counter[str] = sum(counts.values(), Counter())
    alpha0 = everything.total() / len(counts)
    out = Path("data/keyness")
    out.mkdir(parents=True, exist_ok=True)
    for author, target in counts.items():
        rest = everything - target
        z = log_odds_z(target, rest, everything, alpha0)
        g2 = dunning_g2(target, rest)
        rows = sorted(target, key=lambda w: -z[w])
        with (out / f"{author}.tsv").open("w", encoding="utf-8", newline="") as dst:
            writer = csv.writer(dst, delimiter="\t")
            writer.writerow(["lemma", "z", "g2", "f", "df", "f_rest"])
            writer.writerows(
                [w, f"{z[w]:.3f}", f"{g2[w]:.3f}", target[w], df[author][w], rest[w]] for w in rows
            )
    print(f"alpha0={alpha0:.0f}; {len(counts)} tables -> {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
