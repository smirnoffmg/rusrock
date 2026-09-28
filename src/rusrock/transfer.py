"""Style-transfer check: does the model trained with an extra author recognise a held-out text?

Run after `uv run python -m rusrock.build --extended` and
`uv run python -W ignore -m rusrock.preprocess data/extended/corpus.jsonl`:

    uv run python -W ignore -m rusrock.transfer <text file> "<expected author>"

The text file is not part of the repository (the lyrics are copyrighted).
"""

import csv
import sys
from pathlib import Path

import numpy as np

from rusrock.attribution import cross_validate, load_songs, models, per_class_rows
from rusrock.features import split_unknown_groups
from rusrock.preprocess import Analyzer, clean_text

DATA = Path("data/extended")
BEST = "lr_char_plus_lemmas"


def main() -> None:
    text_path, expected = Path(sys.argv[1]), sys.argv[2]
    songs = load_songs(DATA / "tokens.jsonl", DATA / "corpus.jsonl")
    y = [s["author"] for s in songs]
    groups = split_unknown_groups([s["group"] for s in songs])
    labels = sorted(set(y))

    result = cross_validate(models()[BEST], songs, y)
    rows = {r[0]: r for r in per_class_rows(y, list(result.y_pred), labels)}
    print(f"cross-validation macro-F1 {np.mean(result.f1):.3f}", file=sys.stderr)
    print(f"{expected} on own songs: F1 {rows[expected][3]}", file=sys.stderr)

    text = text_path.read_text(encoding="utf-8")
    analysis = Analyzer()(text)
    query = [{"text": clean_text(text), "lemmas": analysis.lemmas, "pos": analysis.pos}]
    model = models()[BEST].fit(songs, y, groups=groups)
    proba = model.predict_proba(query)[0]
    ranking = sorted(zip(model.classes_, proba, strict=True), key=lambda p: -p[1])
    out = DATA / "transfer.tsv"
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(["rank", "author", "probability"])
        writer.writerows([i, a, f"{p:.3f}"] for i, (a, p) in enumerate(ranking, 1))
    rank = [a for a, _ in ranking].index(expected) + 1
    print(f"{expected}: rank {rank} of {len(ranking)} -> {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
