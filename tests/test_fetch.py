from pathlib import Path

import pytest
import requests

from rusrock.fetch import CachedFetcher


def test_second_request_for_same_url_is_served_from_cache(tmp_path: Path) -> None:
    calls: list[str] = []

    def get(url: str) -> bytes:
        calls.append(url)
        return "Текст".encode("cp1251")

    fetch = CachedFetcher(tmp_path, delay=2.0, get=get, sleep=lambda _: None)
    assert fetch("https://example.org/a", "cp1251") == "Текст"
    assert fetch("https://example.org/a", "cp1251") == "Текст"
    assert calls == ["https://example.org/a"]


def test_sleeps_between_network_requests_but_not_before_first(tmp_path: Path) -> None:
    sleeps: list[float] = []
    fetch = CachedFetcher(tmp_path, delay=2.0, get=lambda _: b"x", sleep=sleeps.append)
    fetch("https://example.org/a", "utf-8")
    fetch("https://example.org/b", "utf-8")
    fetch("https://example.org/a", "utf-8")
    assert sleeps == [2.0]


def test_transient_network_error_is_retried_after_backoff(tmp_path: Path) -> None:
    attempts: list[str] = []
    sleeps: list[float] = []

    def flaky(url: str) -> bytes:
        attempts.append(url)
        if len(attempts) < 3:
            raise requests.Timeout("slow")
        return b"ok"

    fetch = CachedFetcher(tmp_path, delay=2.0, get=flaky, sleep=sleeps.append)
    assert fetch("https://example.org/a", "utf-8") == "ok"
    assert len(attempts) == 3
    assert sleeps == [30.0, 60.0]


def test_gives_up_after_retries_are_exhausted(tmp_path: Path) -> None:
    def down(url: str) -> bytes:
        raise requests.ConnectionError("down")

    fetch = CachedFetcher(tmp_path, delay=2.0, get=down, sleep=lambda _: None)
    with pytest.raises(requests.ConnectionError):
        fetch("https://example.org/a", "utf-8")
