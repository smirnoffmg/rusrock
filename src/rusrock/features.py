import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Self

import numpy as np
from numpy.typing import NDArray
from sklearn.base import BaseEstimator, ClassifierMixin, TransformerMixin

from rusrock.freq import frequency_table

Song = Mapping[str, Any]
Floats = NDArray[np.float64]


NON_LETTERS = re.compile(r"[^a-zа-я]+")


def letters_only(text: str) -> str:
    """Each author's lyrics come from one site, so punctuation, «ё» and dashes mark the site."""
    return NON_LETTERS.sub(" ", text.lower().replace("ё", "е")).strip()


def split_unknown_groups(groups: Sequence[str]) -> list[str]:
    """An unknown album is no album: each such song is its own group."""
    return [f"{g}#{i}" if g.endswith(":unknown") else g for i, g in enumerate(groups)]


def length_bucket(n_tokens: int) -> str:
    if n_tokens < 80:
        return "<80"
    return "80-160" if n_tokens <= 160 else ">160"


def most_frequent(
    docs: Iterable[tuple[list[str], list[str]]], n: int, *, function_only: bool
) -> list[str]:
    rows = [r for r in frequency_table(docs) if r.function or not function_only]
    return [r.lemma for r in sorted(rows, key=lambda r: (-r.f, r.lemma))[:n]]


def relative_frequencies(docs: Sequence[Sequence[str]], vocabulary: Sequence[str]) -> Floats:
    index = {word: j for j, word in enumerate(vocabulary)}
    out = np.zeros((len(docs), len(vocabulary)))
    for i, lemmas in enumerate(docs):
        for lemma in lemmas:
            if (j := index.get(lemma)) is not None:
                out[i, j] += 1
        out[i] /= max(len(lemmas), 1)
    return out


def delta_distances(z: Floats, centroids: Floats) -> Floats:
    """Burrows's Delta: mean absolute difference of z-scores, text × author."""
    return np.abs(z[:, None, :] - centroids[None, :, :]).mean(axis=2)


class MostFrequentWords(TransformerMixin, BaseEstimator):  # type: ignore[misc]
    """Relative frequencies of the n most frequent lemmas of the training songs."""

    def __init__(self, n_words: int = 150, function_only: bool = False) -> None:
        self.n_words = n_words
        self.function_only = function_only

    def fit(self, songs: Sequence[Song], y: object = None) -> Self:
        docs = ((s["lemmas"], s["pos"]) for s in songs)
        self.vocabulary_ = most_frequent(docs, self.n_words, function_only=self.function_only)
        return self

    def transform(self, songs: Sequence[Song]) -> Floats:
        return relative_frequencies([s["lemmas"] for s in songs], self.vocabulary_)

    def get_feature_names_out(self, input_features: object = None) -> NDArray[np.str_]:
        return np.asarray(self.vocabulary_)


class DeltaClassifier(ClassifierMixin, BaseEstimator):  # type: ignore[misc]
    """Nearest author centroid under Burrows's Delta (Burrows 2002; Evert et al. 2015, eq. Δ_B).

    z-scores use the mean and standard deviation of each word over the training texts.
    """

    def fit(self, x: Floats, y: Sequence[str]) -> Self:
        x = np.asarray(x, dtype=float)
        labels = np.asarray(y)
        self.mean_ = x.mean(axis=0)
        std = x.std(axis=0)
        self.scale_ = np.where(std > 0, std, 1.0)
        z = self._z(x)
        self.classes_ = np.unique(labels)
        self.centroids_ = np.stack([z[labels == c].mean(axis=0) for c in self.classes_])
        return self

    def _z(self, x: Floats) -> Floats:
        return (np.asarray(x, dtype=float) - self.mean_) / self.scale_

    def predict(self, x: Floats) -> NDArray[Any]:
        distances = delta_distances(self._z(x), self.centroids_)
        return self.classes_[distances.argmin(axis=1)]
