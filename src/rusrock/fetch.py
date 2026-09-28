import hashlib
import time
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlparse

import requests

USER_AGENT = "rusrock-corpus/0.1 (personal research)"
RETRY_BACKOFF = (30.0, 60.0)


def cache_path(cache_dir: Path, url: str) -> Path:
    digest = hashlib.sha1(url.encode()).hexdigest()
    return cache_dir / urlparse(url).netloc / f"{digest}.html"


def http_get(url: str) -> bytes:
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    response.raise_for_status()
    return response.content


class CachedFetcher:
    def __init__(
        self,
        cache_dir: Path,
        delay: float,
        get: Callable[[str], bytes] = http_get,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._cache_dir = cache_dir
        self._delay = delay
        self._get = get
        self._sleep = sleep
        self._fetched_any = False

    def __call__(self, url: str, encoding: str) -> str:
        path = cache_path(self._cache_dir, url)
        if not path.exists():
            if self._fetched_any:
                self._sleep(self._delay)
            content = self._get_with_retries(url)
            self._fetched_any = True
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        return path.read_bytes().decode(encoding)

    def _get_with_retries(self, url: str) -> bytes:
        for backoff in RETRY_BACKOFF:
            try:
                return self._get(url)
            except (requests.Timeout, requests.ConnectionError):
                self._sleep(backoff)
        return self._get(url)
