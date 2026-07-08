"""File-based JSON cache with TTL."""
import json
import time
from pathlib import Path


class Cache:
    def __init__(self, cache_dir: Path, max_age_hours: float = 6):
        self.dir = Path(cache_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.max_age_sec = max_age_hours * 3600

    def _path(self, key: str) -> Path:
        safe = key.replace("/", "_").replace(":", "_")
        return self.dir / f"{safe}.json"

    def get(self, key: str):
        p = self._path(key)
        if not p.exists():
            return None
        try:
            blob = json.loads(p.read_text(encoding="utf-8"))
            if time.time() - blob["ts"] < self.max_age_sec:
                return blob["data"]
        except Exception:
            pass
        return None

    def set(self, key: str, data) -> None:
        p = self._path(key)
        p.write_text(
            json.dumps({"ts": time.time(), "data": data}, default=str),
            encoding="utf-8",
        )

    def bust(self, key: str) -> None:
        p = self._path(key)
        if p.exists():
            p.unlink()
