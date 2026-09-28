import json
from pathlib import Path

import numpy as np
import pytest

from rusrock.attribution import confused_pairs, load_songs, macro_f1_by_bucket, top_coefficients


def test_confused_pairs_merge_both_directions_and_skip_the_diagonal() -> None:
    labels = ["A", "B", "C"]
    cm = np.array([[9, 3, 1], [2, 7, 0], [0, 4, 5]])
    assert confused_pairs(cm, labels, k=2) == [("A", "B", 5), ("B", "C", 4)]


def test_top_coefficients_are_the_largest_positive_ones_per_class() -> None:
    coef = np.array([[0.5, -2.0, 1.5, 0.1], [-1.0, 3.0, 0.0, 2.0]])
    names = np.array(["w", "x", "y", "z"])
    top = top_coefficients(coef, names, ["A", "B"], k=2)
    assert top == {"A": [("y", 1.5), ("w", 0.5)], "B": [("x", 3.0), ("z", 2.0)]}


def test_macro_f1_by_bucket_scores_each_bucket_separately() -> None:
    y_true = ["A", "B", "A", "B"]
    y_pred = ["A", "B", "B", "A"]
    lengths = [10, 10, 200, 200]
    scores = macro_f1_by_bucket(y_true, y_pred, lengths)
    assert scores["<80"] == (2, pytest.approx(1.0))
    assert scores[">160"] == (2, pytest.approx(0.0))
    assert "80-160" not in scores


def test_load_songs_joins_tokens_with_cleaned_text(tmp_path: Path) -> None:
    song = {"author": "A", "title": "T", "group": "g:1", "genre": "song"}
    tokens = tmp_path / "tokens.jsonl"
    corpus = tmp_path / "corpus.jsonl"
    tokens.write_text(json.dumps(song | {"lemmas": ["x"], "pos": ["NOUN"]}) + "\n")
    corpus.write_text(json.dumps(song | {"text": "Припев:\nСтрока (2 раза)"}) + "\n")
    [loaded] = load_songs(tokens, corpus)
    assert loaded["text"] == "Строка"
    assert loaded["lemmas"] == ["x"]


def test_load_songs_refuses_misaligned_files(tmp_path: Path) -> None:
    tokens = tmp_path / "tokens.jsonl"
    corpus = tmp_path / "corpus.jsonl"
    tokens.write_text(json.dumps({"author": "A", "title": "T"}) + "\n")
    corpus.write_text(json.dumps({"author": "A", "title": "U", "text": ""}) + "\n")
    with pytest.raises(ValueError):
        load_songs(tokens, corpus)
