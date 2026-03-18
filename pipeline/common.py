from __future__ import annotations

import csv
import datetime as dt
import hashlib
from pathlib import Path
from typing import Iterable


def utc_now_iso() -> str:
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def stable_id(value: str, prefix: str = "tx") -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{digest}"


def read_csv(path: str | Path) -> list[dict[str, str]]:
    with open(path, "r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: str | Path, rows: Iterable[dict[str, object]], fieldnames: list[str]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


class ProgressPrinter:
    def __init__(self, total: int, label: str, step_percent: int = 10) -> None:
        self.total = max(int(total), 0)
        self.label = label.strip() or "progress"
        self.step_percent = max(1, min(int(step_percent), 50))
        self.current = 0
        self.next_pct = self.step_percent

    def tick(self, count: int = 1) -> None:
        if self.total <= 0:
            return
        self.current = min(self.total, self.current + max(1, int(count)))
        pct = int((self.current * 100) / self.total)
        reached = min((pct // self.step_percent) * self.step_percent, 100)
        if reached >= self.next_pct:
            print(f"[{self.label}] {reached}% ({self.current}/{self.total})")
            self.next_pct = reached + self.step_percent

    def finish(self) -> None:
        if self.total <= 0:
            return
        if self.next_pct <= 100:
            print(f"[{self.label}] 100% ({self.total}/{self.total})")
            self.next_pct = 101
