from rusrock.parsers import (
    Song,
    parse_gro_index,
    parse_gro_song,
    parse_nau_album,
    parse_nau_index,
)

GRO_INDEX = """
<html><body><div id="cont"><ul>
<li><a href="/texts/111.html">Первая песня</a></li>
<li><a href="/texts/222.html">Вторая песня</a></li>
<li><a href="/pub/discography/x.html">Не текст</a></li>
</ul></div></body></html>
"""

GRO_SONG = """
<html><body>
<div id="headers"><h3>Первая песня</h3></div>
<div id="cont">
<script>var ad = 1;</script><p><strong>Автор:</strong> Е.Летов</p><p><strong>Альбом:</strong> Тестовый альбом</p><pre class='song'>Строка один
Строка два

   Припев с отступом
</pre><p><strong>Другие песни</strong></p><ul><li><a href="/texts/222.html">Вторая</a></li></ul>
</div></body></html>
"""

NAU_INDEX = """
<html><body><div class="info">
<a href="/misc/intro.htm">Вступление</a>
<a href="/texts/alpha.html">Альфа</a>
<a href="/texts/beta.html">Бета</a>
<a href="/texts/alpha.html">Альфа</a>
</div></body></html>
"""

NAU_ALBUM = """
<html><body><div class="info">
<h2>Альфа</h2>
<hr>
<ol class="songs"><li><a href="#track1">Раз</a><li><a href="#track2">Два</a></ol>
<hr>

<h3 id="track1">Раз</h3>
<i class="authors">В. Бутусов - И. Кормильцев</i>

Первая строка,<br>
Вторая строка &mdash; тире.<br>
<br>
Третья строка
<br><br>
<a href="#start">В начало страницы &#9650;</a><hr>

<h3 id="track2">Два</h3>
<i class="authors">В. Бутусов</i>

Одна строка
<br><br>
<a href="#start">В начало страницы &#9650;</a><hr>
</div></body></html>
"""


def test_gro_index_keeps_only_text_links() -> None:
    assert parse_gro_index(GRO_INDEX, base="https://www.gr-oborona.ru") == [
        ("Первая песня", "https://www.gr-oborona.ru/texts/111.html"),
        ("Вторая песня", "https://www.gr-oborona.ru/texts/222.html"),
    ]


def test_gro_song_extracts_credit_album_and_text() -> None:
    song = parse_gro_song(GRO_SONG, url="u")
    assert song == Song(
        source="gr-oborona.ru",
        title="Первая песня",
        album="Тестовый альбом",
        credit="Е.Летов",
        lyricist="Е.Летов",
        text="Строка один\nСтрока два\n\nПрипев с отступом",
        url="u",
    )


def test_gro_song_without_text_block_is_none() -> None:
    assert parse_gro_song("<html><body><h3>X</h3></body></html>", url="u") is None


def test_nau_index_deduplicates_album_links() -> None:
    assert parse_nau_index(NAU_INDEX, base="https://naunaunau.narod.ru") == [
        ("Альфа", "https://naunaunau.narod.ru/texts/alpha.html"),
        ("Бета", "https://naunaunau.narod.ru/texts/beta.html"),
    ]


def test_nau_album_splits_songs_and_takes_words_author_after_dash() -> None:
    songs = parse_nau_album(NAU_ALBUM, url="u")
    assert [(s.title, s.credit, s.lyricist) for s in songs] == [
        ("Раз", "В. Бутусов - И. Кормильцев", "И. Кормильцев"),
        ("Два", "В. Бутусов", "В. Бутусов"),
    ]
    assert songs[0].album == "Альфа"
    assert songs[0].text == "Первая строка,\nВторая строка — тире.\n\nТретья строка"
    assert songs[1].text == "Одна строка"


def test_nau_song_without_credit_does_not_borrow_next_songs_credit() -> None:
    html = """<div class="info"><h2>A</h2>
<h3 id="track1">Без авторов</h3>Строка<br><a href="#start">В начало</a><hr>
<h3 id="track2">С авторами</h3><i class="authors">X - Y</i>Строка<br><a href="#start">В начало</a><hr>
</div>"""
    songs = parse_nau_album(html, url="u")
    assert [(s.title, s.credit) for s in songs] == [("Без авторов", ""), ("С авторами", "X - Y")]


def test_nau_credit_in_parentheses_is_unwrapped() -> None:
    html = """<div class="info"><h2>A</h2>
<h3 id="track1">Песня</h3><i class="authors">(В.Бутусов - И.Кормильцев)</i>Строка<br><a href="#start">В начало</a><hr>
</div>"""
    [song] = parse_nau_album(html, url="u")
    assert (song.credit, song.lyricist) == ("В.Бутусов - И.Кормильцев", "И.Кормильцев")
