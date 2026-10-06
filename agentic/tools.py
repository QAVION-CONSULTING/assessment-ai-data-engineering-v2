"""Company register lookup over local fixtures (stand-in for Handelsregister / Bundesanzeiger)."""

import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional

FIXTURE_DIR = Path(__file__).with_name("fixtures") / "companies"


def _normalise(name: str) -> str:
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    name = re.sub(r"\b(gmbh|ag|se|kg|co|mbh|ug|haftungsbeschrankt)\b", " ", name)
    return re.sub(r"[^a-z0-9]+", " ", name).strip()


class CompanyResearchTool:
    def __init__(self, fixture_dir: Path = FIXTURE_DIR) -> None:
        self._records: List[Dict[str, Any]] = [
            json.loads(p.read_text(encoding="utf-8")) for p in sorted(fixture_dir.glob("*.json"))
        ]

    def lookup(self, company_name: str) -> Optional[Dict[str, Any]]:
        wanted = _normalise(company_name)
        if not wanted:
            return None
        for record in self._records:
            if _normalise(record["name"]) == wanted:
                return record
        for record in self._records:
            if wanted in _normalise(record["name"]):
                return record
        return None
