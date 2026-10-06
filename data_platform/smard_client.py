"""SMARD (Bundesnetzagentur) chart_data API: free, no key, weekly JSON chunks.

index:  {base}/{filter}/{region}/index_{resolution}.json -> {"timestamps": [chunk_start_ms, ...]}
chunk:  {base}/{filter}/{region}/{filter}_{region}_{resolution}_{chunk_start_ms}.json
        -> {"meta_data": {...}, "series": [[ts_ms, value_or_null], ...]}

Values are MWh per interval. Hours that are not published yet are ``null``.
"""

import json
import time
from pathlib import Path
from typing import Iterable, List, Optional, Protocol, Tuple

import httpx

from utils import get_logger, settings

logger = get_logger(__name__)

Point = Tuple[int, Optional[float]]
FIXTURE_DIR = Path(__file__).with_name("fixtures") / "smard"


class SmardSource(Protocol):
    def index(self, filter_id: int, region: str, resolution: str) -> List[int]: ...
    def chunk(self, filter_id: int, region: str, resolution: str, chunk_ts: int) -> List[Point]: ...


class HttpSmardSource:
    def __init__(self, base_url: Optional[str] = None, timeout_s: float = 30.0, retries: int = 3):
        self._base = (base_url or settings.data_platform.SMARD_BASE_URL).rstrip("/")
        self._client = httpx.Client(timeout=timeout_s)
        self._retries = retries

    def _get(self, url: str) -> dict:
        for attempt in range(1, self._retries + 1):
            try:
                response = self._client.get(url)
                response.raise_for_status()
                return response.json()
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                if attempt == self._retries:
                    raise
                logger.warning("SMARD request failed (%s), retry %d: %s", exc, attempt, url)
                time.sleep(2**attempt)
        raise AssertionError("unreachable")

    def index(self, filter_id, region, resolution):
        return self._get(f"{self._base}/{filter_id}/{region}/index_{resolution}.json")["timestamps"]

    def chunk(self, filter_id, region, resolution, chunk_ts):
        url = f"{self._base}/{filter_id}/{region}/{filter_id}_{region}_{resolution}_{chunk_ts}.json"
        return [(int(ts), value) for ts, value in self._get(url)["series"]]


class FixtureSmardSource:
    """Recorded SMARD responses. ``published_until_ms`` mimics the API's null padding
    for hours that are not published yet."""

    def __init__(
        self,
        fixture_dir: Path = FIXTURE_DIR,
        published_until_ms: Optional[int] = None,
        only_chunks: Optional[Iterable[int]] = None,
    ):
        self._dir = fixture_dir
        self.published_until_ms = published_until_ms
        self._only = set(only_chunks) if only_chunks is not None else None

    def index(self, filter_id, region, resolution):
        prefix = f"{filter_id}_{region}_{resolution}_"
        found = sorted(int(p.stem.removeprefix(prefix)) for p in self._dir.glob(f"{prefix}*.json"))
        return [c for c in found if self._only is None or c in self._only]

    def chunk(self, filter_id, region, resolution, chunk_ts):
        path = self._dir / f"{filter_id}_{region}_{resolution}_{chunk_ts}.json"
        series = json.loads(path.read_text(encoding="utf-8"))["series"]
        cutoff = self.published_until_ms
        return [
            (int(ts), None if cutoff is not None and ts > cutoff else value) for ts, value in series
        ]
