"""NASA C-MAPSS turbofan degradation data (FD001..FD004), cached locally.

Source: NASA Open Data Portal, "CMAPSS Jet Engine Simulated Data"; downloaded from a
Hugging Face mirror because the NASA zip endpoint is intermittently unavailable.
"""

from pathlib import Path

import httpx
import pandas as pd

from utils import settings

SETTINGS = ["setting_1", "setting_2", "setting_3"]
SENSORS = [f"s_{i}" for i in range(1, 22)]
COLUMNS = ["unit", "cycle", *SETTINGS, *SENSORS]


def _cached(filename: str) -> Path:
    cache = Path(settings.industrial_ml.CACHE_DIR)
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / filename
    if not path.exists():
        url = f"{settings.industrial_ml.CMAPSS_BASE_URL}/{filename}"
        response = httpx.get(url, timeout=120, follow_redirects=True)
        response.raise_for_status()
        path.write_bytes(response.content)
    return path


def load_split(split: str, subset: str = "FD001") -> pd.DataFrame:
    """``split`` is ``train`` (run-to-failure) or ``test`` (truncated before failure)."""
    return pd.read_csv(_cached(f"{split}_{subset}.txt"), sep=r"\s+", header=None, names=COLUMNS)


def load_test_rul(subset: str = "FD001") -> pd.Series:
    """True remaining useful life after the last observed cycle of each test unit."""
    rul = pd.read_csv(_cached(f"RUL_{subset}.txt"), sep=r"\s+", header=None, names=["rul"])
    rul.index = rul.index + 1
    rul.index.name = "unit"
    return rul["rul"]
