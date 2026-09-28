import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

MARKER_LINE = re.compile(
    r"^(припев|проигрыш|куплет|соло|кода)\s*\d*\s*:?\s*(\*\s*\d+)?\s*$", re.IGNORECASE
)
MARKER_PREFIX = re.compile(r"^припев\s*\d*\s*:\s*", re.IGNORECASE)
SPEAKER_PREFIX = re.compile(r"^(майк|боб|бг|б\.\s?г\.)\s*:\s*", re.IGNORECASE)
REPEAT_NOTE = re.compile(
    r"\s*(\(\s*\d+\s*раза?\s*\)|-?\s*\d+\s*раза?\b|\(\s*и\s+т\.\s*д\.?\s*\))", re.IGNORECASE
)
LOOKALIKES = str.maketrans("aceopxykmtbABCEHKMOPTXY", "асеорхукмтвАВСЕНКМОРТХУ")
MIXED_WORD = re.compile(r"[A-Za-zА-Яа-яЁё]+")
WORD = re.compile(r"[а-яёa-z]+(?:['’-][а-яёa-z]+)*", re.IGNORECASE)


def fix_mixed_script(match: re.Match[str]) -> str:
    word = match.group()
    if re.search("[A-Za-z]", word) and re.search("[А-Яа-яЁё]", word):
        return word.translate(LOOKALIKES)
    return word


def clean_line(line: str) -> str:
    line = MIXED_WORD.sub(fix_mixed_script, line.strip())
    line = re.sub(r"(?<=[а-яё])-[nN]-(?=[а-яё])", "-н-", line)
    if MARKER_LINE.match(line):
        return ""
    line = MARKER_PREFIX.sub("", line)
    line = SPEAKER_PREFIX.sub("", line)
    return REPEAT_NOTE.sub("", line).strip()


def clean_text(text: str) -> str:
    lines = [clean_line(line) for line in text.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(line for line in lines if line)).strip()


def is_word(token: str) -> bool:
    return WORD.fullmatch(token) is not None


def normalize_lemma(lemma: str) -> str:
    return lemma.lower().replace("ё", "е")


PROPER_NOUN_TAGS = frozenset({"Name", "Surn", "Patr", "Geox", "Orgn", "Trad"})
LINE_INITIAL = re.compile(r"^(\W*)([А-ЯЁ][а-яё-]*)")


def lower_line_initials(text: str, analyzer: Any) -> str:
    """Verse capitalizes every line; Natasha then tags line-initial «А», «И» as proper nouns."""
    lines = []
    for line in text.split("\n"):
        match = LINE_INITIAL.match(line)
        if match and not PROPER_NOUN_TAGS & set(analyzer.parse(match.group(2))[0].tag.grammemes):
            start = match.start(2)
            line = line[:start] + line[start].lower() + line[start + 1 :]
        lines.append(line)
    return "\n".join(lines)


POSSESSIVES = {"его": "он", "ее": "она", "их": "они"}
# Both lemmatizers get these wrong regardless of context (checked on the corpus).
LEMMA_FIXES = {"далья": "даль"}
PYMORPHY_WINS = {"ADVB", "PRED", "COMP"}


def _participle_lemma(parse: Any) -> str | None:
    # pymorphy normalizes a participle to the infinitive; the agreed lemma is the participle.
    form = parse.inflect({"nomn", "sing", "masc"})
    return normalize_lemma(form.word) if form else None


def combine_lemma(form: str, natasha_lemma: str, natasha_pos: str, parses: list[Any]) -> str:
    """Natasha's contextual lemma, corrected by the conventions agreed in the lemma review."""
    lemma = _combine(form, natasha_lemma, natasha_pos, parses)
    return LEMMA_FIXES.get(lemma, lemma)


def _combine(form: str, natasha_lemma: str, natasha_pos: str, parses: list[Any]) -> str:
    natasha_lemma = normalize_lemma(natasha_lemma)
    if natasha_lemma in POSSESSIVES and natasha_pos in ("DET", "PRON"):
        return POSSESSIVES[natasha_lemma]
    if natasha_pos == "VERB":
        for parse in parses:
            if parse.tag.POS in ("PRTF", "PRTS") and (lemma := _participle_lemma(parse)):
                return lemma
    if parses and parses[0].tag.POS in PYMORPHY_WINS:
        return normalize_lemma(parses[0].normal_form)
    # Natasha echoes the form when its tag matches no dictionary parse.
    known_lemma = any(normalize_lemma(p.normal_form) == form for p in parses)
    if natasha_lemma == form and parses and not known_lemma:
        return normalize_lemma(parses[0].normal_form)
    return natasha_lemma


@dataclass(frozen=True)
class TokenizedSong:
    author: str
    artist: str
    title: str
    group: str
    genre: str
    year: int | None
    forms: list[str]
    pos: list[str]
    lemmas: list[str]
    lemmas_natasha: list[str]
    lemmas_pymorphy: list[str]


def main() -> None:
    import pymorphy3
    from natasha import Doc, MorphVocab, NewsEmbedding, NewsMorphTagger, Segmenter

    segmenter, vocab = Segmenter(), MorphVocab()
    tagger = NewsMorphTagger(NewsEmbedding())
    analyzer = pymorphy3.MorphAnalyzer()

    corpus = Path("data/corpus.jsonl")
    out = Path("data/tokens.jsonl")
    with corpus.open(encoding="utf-8") as src, out.open("w", encoding="utf-8") as dst:
        for number, line in enumerate(src, 1):
            song = json.loads(line)
            doc = Doc(lower_line_initials(clean_text(song["text"]), analyzer))
            doc.segment(segmenter)
            doc.tag_morph(tagger)
            words = [t for t in doc.tokens if is_word(t.text)]
            for token in words:
                token.lemmatize(vocab)
            forms = [t.text.lower() for t in words]
            parses = [analyzer.parse(form) for form in forms]
            tokenized = TokenizedSong(
                author=song["author"],
                artist=song["artist"],
                title=song["title"],
                group=song["group"],
                genre=song["genre"],
                year=song["year"],
                forms=forms,
                pos=[t.pos for t in words],
                lemmas=[
                    combine_lemma(normalize_lemma(f), t.lemma, t.pos, p)
                    for f, t, p in zip(forms, words, parses, strict=True)
                ],
                lemmas_natasha=[normalize_lemma(t.lemma) for t in words],
                lemmas_pymorphy=[normalize_lemma(p[0].normal_form) for p in parses],
            )
            dst.write(json.dumps(asdict(tokenized), ensure_ascii=False) + "\n")
            if number % 200 == 0:
                print(number, file=sys.stderr)
    print(f"{number} songs -> {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
