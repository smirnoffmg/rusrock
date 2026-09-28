"""Threshold for «none of the known authors».

The best closed-set model always names one of the known authors. Its top probability is lower
for authors it has never seen; the threshold separating the two is chosen on data where the
answer is known: cross-validated songs of known authors vs. each author held out entirely.
"""

import csv
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedGroupKFold, cross_val_predict
from sklearn.pipeline import FeatureUnion, Pipeline

from rusrock.attribution import SEED, char_tfidf, lemma_tfidf, load_songs
from rusrock.features import split_unknown_groups

C = 1.0  # the value chosen most often by the inner search for the best model


def balanced_accuracy(known: Sequence[float], unknown: Sequence[float], threshold: float) -> float:
    accepted = np.mean(np.asarray(known) >= threshold)
    rejected = np.mean(np.asarray(unknown) < threshold)
    return float((accepted + rejected) / 2)


def best_threshold(known: Sequence[float], unknown: Sequence[float]) -> tuple[float, float]:
    candidates = sorted(set(known) | set(unknown))
    scores = [(balanced_accuracy(known, unknown, t), -t) for t in candidates]
    score, neg_threshold = max(scores)
    return -neg_threshold, score


def model() -> Pipeline:
    return Pipeline(
        [
            ("feat", FeatureUnion([("char", char_tfidf()), ("lemma", lemma_tfidf())])),
            ("clf", LogisticRegression(C=C, class_weight="balanced", max_iter=3000)),
        ]
    )


def known_scores(songs: list[dict[str, Any]], y: np.ndarray, groups: list[str]) -> np.ndarray:
    cv = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=SEED)
    proba = cross_val_predict(model(), songs, y, groups=groups, cv=cv, method="predict_proba")
    return np.asarray(proba).max(axis=1)


def unknown_scores(songs: list[dict[str, Any]], y: np.ndarray) -> dict[str, np.ndarray]:
    scores = {}
    for author in sorted(set(y)):
        train = [s for s, a in zip(songs, y, strict=True) if a != author]
        test = [s for s, a in zip(songs, y, strict=True) if a == author]
        fitted = model().fit(train, y[y != author])
        scores[author] = np.asarray(fitted.predict_proba(test)).max(axis=1)
        print(f"held out {author}", file=sys.stderr)
    return scores


def main() -> None:
    songs = load_songs(Path("data/tokens.jsonl"), Path("data/corpus.jsonl"))
    y = np.array([s["author"] for s in songs])
    groups = split_unknown_groups([s["group"] for s in songs])
    known = known_scores(songs, y, groups)
    held_out = unknown_scores(songs, y)
    unknown = np.concatenate(list(held_out.values()))
    threshold, score = best_threshold(known.tolist(), unknown.tolist())
    out = Path("data/attribution/openset.tsv")
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["author", "role", "n", "median_top_proba", "share_accepted"])
        w.writerow(
            [
                "все",
                "известные",
                len(known),
                f"{np.median(known):.3f}",
                f"{np.mean(known >= threshold):.3f}",
            ]
        )
        for author, s in held_out.items():
            w.writerow(
                [
                    author,
                    "исключён из обучения",
                    len(s),
                    f"{np.median(s):.3f}",
                    f"{np.mean(s >= threshold):.3f}",
                ]
            )
    print(f"threshold={threshold:.3f} balanced_accuracy={score:.3f} -> {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
