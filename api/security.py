from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass
class RateLimitDecision:
    allowed: bool
    remaining: int
    retry_after_seconds: int


def parse_api_keys(raw: str) -> set[str]:
    keys = {k.strip() for k in raw.split(",") if k.strip()}
    return keys


class FixedWindowRateLimiter:
    def __init__(self, limit_per_minute: int) -> None:
        self.limit_per_minute = max(1, int(limit_per_minute))
        self._state: dict[str, tuple[int, int]] = {}
        self._lock = threading.Lock()

    def check(self, client_key: str, now: float | None = None) -> RateLimitDecision:
        if not client_key:
            client_key = "anonymous"

        now = time.time() if now is None else now
        window = int(now // 60)

        with self._lock:
            prev_window, count = self._state.get(client_key, (window, 0))
            if prev_window != window:
                prev_window, count = window, 0

            if count >= self.limit_per_minute:
                retry_after = int(((window + 1) * 60) - now)
                return RateLimitDecision(allowed=False, remaining=0, retry_after_seconds=max(retry_after, 1))

            count += 1
            self._state[client_key] = (prev_window, count)
            remaining = max(self.limit_per_minute - count, 0)
            return RateLimitDecision(allowed=True, remaining=remaining, retry_after_seconds=0)
