from rusrock.parsers import Song
from rusrock.sites.ddt import apply_credits, parse_album, parse_credits, parse_index

BASE = "http://ddtmusiclib.narod.ru/"

INDEX = """
<script>var junk = 1;</script><!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0 Transitional//EN">
<HTML><BODY><TABLE><TR><TD>
		<A HREF="#alb2000"><FONT>Нав альбом</FONT></A>&nbsp;<BR>
		<!-- Главное окно -->
		<ul>
			<li><A HREF="#alb2000">Второй альбом</A></li>
			<li><A HREF="#alb1982">Первый альбом</A></li>
		</ul>
		<a name="alb2000"><h4>Второй альбом</h4></a>
		<ul class="LINE">
			<li><A HREF="texts00.html#01">Песня А</A></li>
			<li><A HREF="texts00.html#02">Песня Б</A></li>
		</ul>
		<a name="alb1982"><h4>Первый альбом</h4></a>
		<ul class="LINE">
			<li><A HREF="texts82.html#01">Песня В</A></li>
		</ul>
</TD></TR></TABLE></BODY></HTML>
"""

ALBUM = """
<HTML><BODY><TABLE><TR><TD><FONT COLOR="Black">

		<!-- Главное окно -->
		<ul>
			<li><A HREF="#01">Песня А</A></li>
			<li><A HREF="#02">Песня Б</A></li>
			<li><A HREF="#03">Песня В</A></li>
		</ul>
\t\t\r
<a name="01"><h4>Песня А</h4></a>\r
Строка один, <br>\r
Строка два -<br>\r
<br>\r
Припев:br>\r
Строка три.<br>\r
\r
\r
<a name="02"><h4>Инструментал</h4></a>\r
\r
\r
<a name="03"><h4>Песня В</h4></a>\r
Последняя строка<br>\r
\r
\t\t<!-- Конец главного окна -->
</FONT></TD></TR></TABLE></BODY></HTML>
"""

CREDITS = """# comment line
album\ttitle\tcredit\tlyricist
Первый альбом\t\tСлова и музыка - Автор А.\tА. Автор
Первый альбом\tПесня В\tБ. Другой автор слов "Песня В"\tБ. Другой
Второй альбом\t\tАвтор Б. - вокал, автор\t
"""


def test_parse_index_lists_albums_with_year_and_page():
    assert parse_index(INDEX, base=BASE) == [
        ("Второй альбом", 2000, "http://ddtmusiclib.narod.ru/texts00.html"),
        ("Первый альбом", 1982, "http://ddtmusiclib.narod.ru/texts82.html"),
    ]


def test_parse_album_splits_songs_by_anchor_and_keeps_source_lines():
    url = BASE + "texts82.html"
    songs = parse_album(ALBUM, url=url, album="Первый альбом")
    assert [s.title for s in songs] == ["Песня А", "Инструментал", "Песня В"]
    assert songs[0] == Song(
        source="ddtmusiclib.narod.ru",
        title="Песня А",
        album="Первый альбом",
        credit="",
        lyricist="",
        text="Строка один,\nСтрока два -\n\nПрипев:\nСтрока три.",
        url=url + "#01",
    )
    assert songs[1].text == ""
    assert songs[2].text == "Последняя строка"
    assert songs[2].url == url + "#03"


def test_apply_credits_prefers_song_row_over_album_row():
    credits = parse_credits(CREDITS)
    songs = parse_album(ALBUM, url=BASE + "texts82.html", album="Первый альбом")
    first, _, last = (apply_credits(s, credits) for s in songs)
    assert (first.credit, first.lyricist) == ("Слова и музыка - Автор А.", "А. Автор")
    assert (last.credit, last.lyricist) == ('Б. Другой автор слов "Песня В"', "Б. Другой")


def test_apply_credits_keeps_empty_lyricist_and_unknown_album():
    credits = parse_credits(CREDITS)
    song = parse_album(ALBUM, url=BASE + "texts00.html", album="Второй альбом")[0]
    credited = apply_credits(song, credits)
    assert (credited.credit, credited.lyricist) == ("Автор Б. - вокал, автор", "")
    other = parse_album(ALBUM, url=BASE + "texts99.html", album="Нет в таблице")[0]
    assert apply_credits(other, credits) == other
