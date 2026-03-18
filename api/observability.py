from __future__ import annotations

import threading
from collections import defaultdict


class ApiMetrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.total_requests = 0
        self.total_errors = 0
        self.path_counts: dict[str, int] = defaultdict(int)
        self.status_counts: dict[str, int] = defaultdict(int)
        self.latency_ms_sum = 0.0

    def record(self, path: str, status_code: int, latency_ms: float) -> None:
        with self._lock:
            self.total_requests += 1
            self.path_counts[path] += 1
            self.status_counts[str(status_code)] += 1
            self.latency_ms_sum += max(latency_ms, 0.0)
            if status_code >= 500:
                self.total_errors += 1

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            avg_latency = self.latency_ms_sum / self.total_requests if self.total_requests > 0 else 0.0
            return {
                "total_requests": self.total_requests,
                "total_errors": self.total_errors,
                "avg_latency_ms": round(avg_latency, 3),
                "path_counts": dict(self.path_counts),
                "status_counts": dict(self.status_counts),
            }
