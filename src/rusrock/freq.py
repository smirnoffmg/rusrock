import csv
import json
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import astuple, dataclass, fields
from pathlib import Path

# Universal Dependencies tags that Natasha assigns to closed-class words.
FUNCTION_POS = frozenset({"ADP", "CCONJ", "SCONJ", "PART", "PRON", "DET", "AUX"})
# UD tags pronominal adverbs as ADV and «нет», «быть» as VERB; they are closed-class all the same.
FUNCTION_LEMMAS = frozenset(
    [
        "так",
        "там",
        "тут",
        "здесь",
        "где",
        "куда",
        "откуда",
        "туда",
        "сюда",
        "оттуда",
        "отсюда",
        "когда",
        "тогда",
        "всегда",
        "никогда",
        "иногда",
        "как",
        "зачем",
        "почему",
        "отчего",
        "оттого",
        "потому",
        "поэтому",
        "затем",
        "потом",
        "везде",
        "нигде",
        "никуда",
        "всюду",
        "уже",
        "еще",
        "вот",
        "вон",
        "нет",
        "да",
        "лишь",
        "только",
        "даже",
        "сам",
        "быть",
    ]
)


@dataclass(frozen=True)
class Row:
    lemma: str
    pos: str
    f: int
    ipm: float
    df: int
    function: bool


def frequency_table(songs: Iterable[tuple[list[str], list[str]]]) -> list[Row]:
    f: Counter[str] = Counter()
    df: Counter[str] = Counter()
    pos: defaultdict[str, Counter[str]] = defaultdict(Counter)
    for lemmas, tags in songs:
        f.update(lemmas)
        df.update(set(lemmas))
        for lemma, tag in zip(lemmas, tags, strict=True):
            pos[lemma][tag] += 1
    total = sum(f.values())
    rows = []
    for lemma, count in f.items():
        tag = pos[lemma].most_common(1)[0][0]
        rows.append(
            Row(
                lemma=lemma,
                pos=tag,
                f=count,
                ipm=count * 1_000_000 / total,
                df=df[lemma],
                function=tag in FUNCTION_POS or lemma in FUNCTION_LEMMAS,
            )
        )
    return sorted(rows, key=lambda r: (-r.df, -r.f, r.lemma))


def main() -> None:
    by_author: defaultdict[str, list[tuple[list[str], list[str]]]] = defaultdict(list)
    with Path("data/tokens.jsonl").open(encoding="utf-8") as f:
        for line in f:
            song = json.loads(line)
            by_author[song["author"]].append((song["lemmas"], song["pos"]))
    out = Path("data/freq")
    out.mkdir(parents=True, exist_ok=True)
    for author, songs in by_author.items():
        path = out / f"{author}.tsv"
        with path.open("w", encoding="utf-8", newline="") as dst:
            writer = csv.writer(dst, delimiter="\t")
            writer.writerow([field.name for field in fields(Row)])
            writer.writerows(astuple(row) for row in frequency_table(songs))
    print(f"{len(by_author)} dictionaries -> {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
