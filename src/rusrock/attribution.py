import csv
import json
import sys
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import GridSearchCV, StratifiedGroupKFold
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

from rusrock.features import (
    DeltaClassifier,
    MostFrequentWords,
    Song,
    length_bucket,
    letters_only,
    split_unknown_groups,
)
from rusrock.preprocess import clean_text

SEED = 20260928
N_FOLDS = 5
OUT = Path("data/attribution")
C_GRID = [0.1, 0.3, 1.0, 3.0, 10.0]
# Diagnostic rows: they show an artefact and never compete for the best model.
DIAGNOSTIC = {"majority", "stratified", "diag_lr_char_raw_punct"}


def load_songs(tokens_path: Path, corpus_path: Path) -> list[dict[str, Any]]:
    songs = []
    with tokens_path.open(encoding="utf-8") as tok, corpus_path.open(encoding="utf-8") as raw:
        for t_line, r_line in zip(tok, raw, strict=True):
            song, source = json.loads(t_line), json.loads(r_line)
            if (song["author"], song["title"]) != (source["author"], source["title"]):
                raise ValueError(f"tokens and corpus disagree at {song['title']!r}")
            songs.append(song | {"text": clean_text(source["text"])})
    return songs


def confused_pairs(
    cm: NDArray[np.int64], labels: Sequence[str], k: int
) -> list[tuple[str, str, int]]:
    pairs = [
        (labels[i], labels[j], int(cm[i, j] + cm[j, i]))
        for i in range(len(labels))
        for j in range(i + 1, len(labels))
    ]
    return sorted(pairs, key=lambda p: -p[2])[:k]


def top_coefficients(
    coef: NDArray[np.float64], names: NDArray[np.str_], classes: Sequence[str], k: int
) -> dict[str, list[tuple[str, float]]]:
    top = {}
    for label, row in zip(classes, coef, strict=True):
        order = np.argsort(-row)[:k]
        top[label] = [(str(names[j]), float(row[j])) for j in order if row[j] > 0]
    return top


def macro_f1_by_bucket(
    y_true: Sequence[str], y_pred: Sequence[str], lengths: Sequence[int]
) -> dict[str, tuple[int, float]]:
    buckets: defaultdict[str, list[int]] = defaultdict(list)
    for i, n in enumerate(lengths):
        buckets[length_bucket(n)].append(i)
    return {
        bucket: (
            len(idx),
            float(
                f1_score(
                    [y_true[i] for i in idx],
                    [y_pred[i] for i in idx],
                    average="macro",
                    zero_division=0,
                )
            ),
        )
        for bucket, idx in buckets.items()
    }


def lemmas_of(songs: Sequence[Song]) -> list[list[str]]:
    return [s["lemmas"] for s in songs]


def texts_of(songs: Sequence[Song]) -> list[str]:
    return [letters_only(s["text"]) for s in songs]


def raw_texts_of(songs: Sequence[Song]) -> list[str]:
    return [s["text"] for s in songs]


def as_tokens(lemmas: list[str]) -> list[str]:
    return lemmas


def lemma_tfidf() -> Pipeline:
    return Pipeline(
        [
            ("get", FunctionTransformer(lemmas_of)),
            ("vec", TfidfVectorizer(analyzer=as_tokens, min_df=2, sublinear_tf=True)),
        ]
    )


def char_tfidf(get_text: Any = texts_of) -> Pipeline:
    return Pipeline(
        [
            ("get", FunctionTransformer(get_text)),
            (
                "vec",
                TfidfVectorizer(
                    analyzer="char_wb", ngram_range=(2, 4), min_df=2, sublinear_tf=True
                ),
            ),
        ]
    )


def tuned_lr(features: list[tuple[str, Any]], grid: list[float]) -> GridSearchCV:
    """C is chosen by an inner grouped CV on the training folds only."""
    clf = LogisticRegression(class_weight="balanced", max_iter=3000)
    return GridSearchCV(
        Pipeline([*features, ("clf", clf)]),
        {"clf__C": grid},
        cv=StratifiedGroupKFold(n_splits=3, shuffle=True, random_state=SEED),
        scoring="f1_macro",
        n_jobs=-1,
    )


def models() -> dict[str, Any]:
    bag = [
        ("get", FunctionTransformer(lemmas_of)),
        ("vec", CountVectorizer(analyzer=as_tokens, binary=True)),
    ]
    return {
        "majority": DummyClassifier(strategy="most_frequent"),
        "stratified": DummyClassifier(strategy="stratified", random_state=SEED),
        "nb_binary_lemmas": Pipeline([*bag, ("clf", MultinomialNB())]),
        "lr_tfidf_lemmas": tuned_lr([("feat", lemma_tfidf())], C_GRID),
        "lr_function_words": tuned_lr(
            [
                ("feat", MostFrequentWords(n_words=150, function_only=True)),
                ("scale", StandardScaler()),
            ],
            [0.01, 0.1, 1.0],
        ),
        "lr_char_2_4": tuned_lr([("feat", char_tfidf())], C_GRID),
        "diag_lr_char_raw_punct": tuned_lr([("feat", char_tfidf(raw_texts_of))], C_GRID),
        "delta_mfw150": Pipeline(
            [("feat", MostFrequentWords(n_words=150)), ("clf", DeltaClassifier())]
        ),
        "delta_mfw300": Pipeline(
            [("feat", MostFrequentWords(n_words=300)), ("clf", DeltaClassifier())]
        ),
        "delta_function150": Pipeline(
            [
                ("feat", MostFrequentWords(n_words=150, function_only=True)),
                ("clf", DeltaClassifier()),
            ]
        ),
        "lr_char_plus_lemmas": tuned_lr(
            [("feat", FeatureUnion([("char", char_tfidf()), ("lemma", lemma_tfidf())]))],
            C_GRID,
        ),
    }


@dataclass(frozen=True)
class CvResult:
    y_pred: list[str]
    f1: list[float]
    accuracy: list[float]
    params: list[str]


def cross_validate(model: Any, songs: list[dict[str, Any]], y: list[str]) -> CvResult:
    groups = split_unknown_groups([s["group"] for s in songs])
    folds = StratifiedGroupKFold(n_splits=N_FOLDS, shuffle=True, random_state=SEED)
    y_arr = np.asarray(y)
    y_pred = np.empty(len(y), dtype=object)
    f1s, accs, params = [], [], []
    for train, test in folds.split(songs, y_arr, groups):
        x_train = [songs[i] for i in train]
        x_test = [songs[i] for i in test]
        if isinstance(model, GridSearchCV):
            model.fit(x_train, y_arr[train], groups=[groups[i] for i in train])
            params.append(str(model.best_params_["clf__C"]))
        else:
            model.fit(x_train, y_arr[train])
        pred = model.predict(x_test)
        y_pred[test] = pred
        f1s.append(float(f1_score(y_arr[test], pred, average="macro", zero_division=0)))
        accs.append(float(accuracy_score(y_arr[test], pred)))
    return CvResult([str(p) for p in y_pred], f1s, accs, params)


def write_tsv(path: Path, header: Sequence[str], rows: Sequence[Sequence[Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as dst:
        writer = csv.writer(dst, delimiter="\t")
        writer.writerow(header)
        writer.writerows(rows)


def per_class_rows(y: Sequence[str], y_pred: Sequence[str], labels: list[str]) -> list[list[Any]]:
    report = classification_report(y, y_pred, labels=labels, output_dict=True, zero_division=0)
    return [
        [
            label,
            f"{report[label]['precision']:.3f}",
            f"{report[label]['recall']:.3f}",
            f"{report[label]['f1-score']:.3f}",
            int(report[label]["support"]),
        ]
        for label in labels
    ]


def write_model_outputs(name: str, y: list[str], result: CvResult, labels: list[str]) -> None:
    cm = confusion_matrix(y, result.y_pred, labels=labels)
    write_tsv(
        OUT / f"confusion_{name}.tsv",
        ["true\\pred", *labels],
        [[label, *row] for label, row in zip(labels, cm.tolist(), strict=True)],
    )
    write_tsv(
        OUT / f"per_class_{name}.tsv",
        ["author", "precision", "recall", "f1", "support"],
        per_class_rows(y, result.y_pred, labels),
    )


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def main() -> None:
    songs = load_songs(Path("data/tokens.jsonl"), Path("data/corpus.jsonl"))
    y = [s["author"] for s in songs]
    labels = sorted(set(y), key=lambda a: -Counter(y)[a])
    unknown = sum(s["group"].endswith(":unknown") for s in songs)
    log(
        f"{len(songs)} songs, {len({s['group'] for s in songs})} groups, "
        f"{unknown} songs with an unknown album -> singleton groups"
    )
    OUT.mkdir(parents=True, exist_ok=True)

    results: dict[str, CvResult] = {}
    rows = []
    for name, model in models().items():
        result = cross_validate(model, songs, y)
        results[name] = result
        write_model_outputs(name, y, result, labels)
        rows.append(
            [
                name,
                f"{np.mean(result.f1):.3f}",
                f"{np.std(result.f1):.3f}",
                f"{np.mean(result.accuracy):.3f}",
                ",".join(result.params),
            ]
        )
        log("\t".join(rows[-1]))
    write_tsv(
        OUT / "results.tsv",
        ["model", "macro_f1_mean", "macro_f1_std", "accuracy_mean", "chosen_C"],
        rows,
    )

    best = max((n for n in results if n not in DIAGNOSTIC), key=lambda n: np.mean(results[n].f1))
    log(f"best: {best}")
    best_pred = results[best].y_pred

    lengths = [len(s["lemmas"]) for s in songs]
    buckets = macro_f1_by_bucket(y, best_pred, lengths)
    write_tsv(
        OUT / f"length_buckets_{best}.tsv",
        ["bucket", "songs", "macro_f1"],
        [[b, *buckets[b]] for b in ("<80", "80-160", ">160") if b in buckets],
    )

    cm = confusion_matrix(y, best_pred, labels=labels)
    write_tsv(
        OUT / f"confused_pairs_{best}.tsv",
        ["author_a", "author_b", "confusions"],
        confused_pairs(cm, labels, k=10),
    )

    no_poems = [s for s in songs if s["genre"] != "poem"]
    y_no_poems = [s["author"] for s in no_poems]
    genre = cross_validate(models()[best], no_poems, y_no_poems)
    write_model_outputs(f"{best}_no_yanka_poems", y_no_poems, genre, labels)
    full_f1 = {r[0]: r[3] for r in per_class_rows(y, best_pred, labels)}
    cut_f1 = {r[0]: r[3] for r in per_class_rows(y_no_poems, genre.y_pred, labels)}
    write_tsv(
        OUT / f"genre_check_{best}.tsv",
        ["author", "f1_all_texts", "f1_without_yanka_poems"],
        [[a, full_f1[a], cut_f1[a]] for a in labels],
    )
    log(f"without Yanka's poems: macro-F1 {np.mean(genre.f1):.3f} ± {np.std(genre.f1):.3f}")

    search = models()["lr_tfidf_lemmas"]
    groups = split_unknown_groups([s["group"] for s in songs])
    search.fit(songs, y, groups=groups)
    pipe = search.best_estimator_
    names = pipe.named_steps["feat"].named_steps["vec"].get_feature_names_out()
    clf = pipe.named_steps["clf"]
    top = top_coefficients(clf.coef_, names, list(clf.classes_), k=15)
    write_tsv(
        OUT / "top_coefficients_lr_tfidf_lemmas.tsv",
        ["author", "rank", "lemma", "coef"],
        [[a, i, w, f"{c:.3f}"] for a in labels for i, (w, c) in enumerate(top[a], 1)],
    )
    log(f"coefficients from C={search.best_params_['clf__C']} fitted on all songs -> {OUT}")


if __name__ == "__main__":
    main()
