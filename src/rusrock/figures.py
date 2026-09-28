"""Figures for the write-up.

Dot charts on a common scale wherever values are compared: position is read more accurately
than length or colour (Cleveland & McGill, «Graphical Perception», JASA 1984, p. 532).
"""

import csv
import glob
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
import seaborn as sns  # noqa: E402
from matplotlib.axes import Axes  # noqa: E402

BLUE, ORANGE, GRAY, INK, MUTED = "#2a78d6", "#eb6834", "#a9a8a2", "#0b0b0b", "#52514e"
SURFACE = "#fcfcfb"
SHORT = {
    "Виктор Цой": "Цой",
    "Егор Летов": "Летов",
    "Борис Гребенщиков": "Гребенщиков",
    "Юрий Шевчук": "Шевчук",
    "Константин Кинчев": "Кинчев",
    "Илья Кормильцев": "Кормильцев",
    "Майк Науменко": "Майк Науменко",
    "Янка Дягилева": "Янка Дягилева",
    "Александр Башлачёв": "Башлачёв",
    "Эдмунд Шклярский": "Шклярский",
    "Андрей Лысиков": "Дельфин",
    "Александр Васильев": "Васильев",
    "Дмитрий Озерский": "Озерский",
    "Владимир Кристовский": "Кристовский",
}
RICH = {"Янка Дягилева", "Александр Башлачёв", "Юрий Шевчук", "Егор Летов"}
MODEL_NAMES = {
    "majority": "самый частый класс",
    "stratified": "случайно по долям классов",
    "nb_binary_lemmas": "наивный Байес, леммы",
    "lr_tfidf_lemmas": "лог. регрессия, леммы",
    "lr_function_words": "лог. регрессия, служебные слова",
    "lr_char_2_4": "лог. регрессия, буквенные n-граммы",
    "lr_char_plus_lemmas": "лог. регрессия, n-граммы + леммы",
    "delta_mfw150": "Delta Барроуза, 150 слов",
    "delta_mfw300": "Delta Барроуза, 300 слов",
    "delta_function150": "Delta Барроуза, служебные",
    "diag_lr_char_raw_punct": "n-граммы с пунктуацией (утечка)",
}
DATA, OUT = Path("data"), Path("figures")


def setup() -> None:
    sns.set_theme(style="whitegrid", font="DejaVu Sans")
    plt.rcParams.update(
        {
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "axes.edgecolor": GRAY,
            "axes.labelcolor": MUTED,
            "xtick.color": MUTED,
            "ytick.color": INK,
            "grid.color": "#e6e5e0",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.spines.left": False,
            "savefig.dpi": 200,
            "savefig.bbox": "tight",
        }
    )


def read_tsv(path: str | Path) -> pd.DataFrame:
    return pd.read_csv(path, sep="\t", quoting=csv.QUOTE_NONE)


def function_lemmas() -> set[str]:
    words: set[str] = set()
    for path in glob.glob(str(DATA / "freq" / "*.tsv")):
        table = read_tsv(path)
        words |= set(table.loc[table["function"], "lemma"])
    return words


def dot_chart(ax: Axes, values: pd.Series, errors: pd.Series | None, colors: list[str]) -> None:
    y = range(len(values))
    ax.hlines(y, 0, values, color="#e6e5e0", linewidth=2, zorder=1)
    if errors is not None:
        ax.errorbar(values, y, xerr=errors, fmt="none", ecolor=MUTED, elinewidth=1.5, zorder=2)
    ax.scatter(values, y, c=colors, s=70, zorder=3, edgecolors=SURFACE, linewidths=2)
    ax.set_yticks(list(y), list(values.index))
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)


def richness() -> None:
    table = read_tsv(DATA / "richness" / "richness.tsv").sort_values(
        "ttr_lemma_mean", ascending=False
    )
    values = table.set_index(table["author"].map(SHORT))["ttr_lemma_mean"]
    errors = table["ttr_lemma_std"].to_numpy()
    colors = [BLUE if a in RICH else ORANGE for a in table["author"]]
    fig, ax = plt.subplots(figsize=(7, 5.2))
    dot_chart(ax, values, pd.Series(errors, index=values.index), colors)
    ax.set_xlim(0, 0.45)
    ax.set_xlabel("доля разных лемм на выборке в 5 000 слов (среднее ± ст. откл., 100 выборок)")
    ax.set_title("Богатство словаря", loc="left", color=INK, fontsize=13)
    for label, color in (("богатая четвёрка", BLUE), ("остальные", ORANGE)):
        ax.scatter([], [], c=color, s=70, label=label)
    ax.legend(frameon=False, loc="lower right")
    fig.savefig(OUT / "richness.png")
    plt.close(fig)


def keyness() -> None:
    skip = function_lemmas()
    authors = [a for a in SHORT if (DATA / "keyness" / f"{a}.tsv").exists()]
    fig, axes = plt.subplots(3, 5, figsize=(15, 9.5), sharex=True)
    for ax in axes.flat[len(authors) :]:
        ax.set_visible(False)
    for ax, author in zip(axes.flat, authors, strict=False):
        table = read_tsv(DATA / "keyness" / f"{author}.tsv")
        table = table[(table["df"] >= 3) & ~table["lemma"].isin(skip)].head(8)
        # Mike's «сладкая N» and «город N» survive lowercasing as «n».
        values = table.set_index(table["lemma"].replace({"n": "N"}))["z"]
        dot_chart(ax, values, None, [BLUE] * len(values))
        ax.set_title(SHORT[author], loc="left", color=INK, fontsize=12)
        ax.tick_params(axis="y", labelsize=10)
    rows, cols = axes.shape
    for i, ax in enumerate(axes.flat):
        below = i + cols
        if ax.get_visible() and (below >= rows * cols or not axes.flat[below].get_visible()):
            ax.set_xlabel("z-оценка log-odds")
            ax.tick_params(labelbottom=True)
    fig.suptitle(
        "Характерные слова: чем автор отличается от остальных",
        x=0.01,
        ha="left",
        color=INK,
        fontsize=14,
    )
    fig.tight_layout()
    fig.savefig(OUT / "keyness.png")
    plt.close(fig)


def models() -> None:
    table = read_tsv(DATA / "attribution" / "results.tsv").sort_values(
        "macro_f1_mean", ascending=False
    )
    values = table.set_index(table["model"].map(MODEL_NAMES))["macro_f1_mean"]
    errors = pd.Series(table["macro_f1_std"].to_numpy(), index=values.index)
    colors = [
        ORANGE if m == "diag_lr_char_raw_punct" else BLUE if m == "lr_char_plus_lemmas" else GRAY
        for m in table["model"]
    ]
    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    dot_chart(ax, values, errors, colors)
    ax.set_xlim(0, 1)
    ax.set_xlabel("macro-F1, проверка по альбомам (среднее ± ст. откл., 5 частей)")
    ax.set_title("Определение автора: сравнение моделей", loc="left", color=INK, fontsize=13)
    fig.savefig(OUT / "models.png")
    plt.close(fig)


def authors_f1() -> None:
    table = read_tsv(DATA / "attribution" / "per_class_lr_char_plus_lemmas.tsv").sort_values(
        "f1", ascending=False
    )
    values = table.set_index(table["author"].map(SHORT))["f1"]
    fig, ax = plt.subplots(figsize=(7, 4.2))
    dot_chart(ax, values, None, [BLUE] * len(values))
    ax.set_xlim(0, 1)
    ax.set_xlabel("F1 лучшей модели")
    ax.set_title("Кого модель узнаёт", loc="left", color=INK, fontsize=13)
    fig.savefig(OUT / "authors_f1.png")
    plt.close(fig)


def confusion() -> None:
    table = read_tsv(DATA / "attribution" / "confusion_lr_char_plus_lemmas.tsv").set_index(
        "true\\pred"
    )
    order = [a for a in SHORT if a in table.index]
    table = table.loc[order, order]
    shares = table.div(table.sum(axis=1), axis=0) * 100
    shares.index = [SHORT[a] for a in order]
    shares.columns = [SHORT[a] for a in order]
    fig, ax = plt.subplots(figsize=(10.5, 8.5))
    sns.heatmap(
        shares,
        cmap=sns.light_palette(BLUE, as_cmap=True),
        annot=True,
        fmt=".0f",
        linewidths=2,
        linecolor=SURFACE,
        cbar_kws={"label": "% песен автора"},
        ax=ax,
    )
    ax.set_xlabel("кому модель отдала песню")
    ax.set_ylabel("настоящий автор")
    ax.set_title("Кого с кем путает модель, % песен", loc="left", color=INK, fontsize=13)
    fig.savefig(OUT / "confusion.png")
    plt.close(fig)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    setup()
    richness()
    keyness()
    models()
    authors_f1()
    confusion()


if __name__ == "__main__":
    main()
