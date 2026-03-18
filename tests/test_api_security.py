from __future__ import annotations

import unittest

from api.observability import ApiMetrics
from api.security import FixedWindowRateLimiter, parse_api_keys


class TestApiSecurity(unittest.TestCase):
    def test_parse_api_keys(self) -> None:
        keys = parse_api_keys(" a, b ,,c ")
        self.assertEqual(keys, {"a", "b", "c"})

    def test_rate_limiter_window(self) -> None:
        limiter = FixedWindowRateLimiter(limit_per_minute=2)

        d1 = limiter.check("client", now=120.0)
        d2 = limiter.check("client", now=121.0)
        d3 = limiter.check("client", now=122.0)

        self.assertTrue(d1.allowed)
        self.assertTrue(d2.allowed)
        self.assertFalse(d3.allowed)
        self.assertGreaterEqual(d3.retry_after_seconds, 1)

        d4 = limiter.check("client", now=180.1)
        self.assertTrue(d4.allowed)


class TestApiObservability(unittest.TestCase):
    def test_metrics_snapshot(self) -> None:
        m = ApiMetrics()
        m.record(path="/v1/meta", status_code=200, latency_ms=10.0)
        m.record(path="/v1/meta", status_code=500, latency_ms=30.0)

        snap = m.snapshot()
        self.assertEqual(snap["total_requests"], 2)
        self.assertEqual(snap["total_errors"], 1)
        self.assertIn("/v1/meta", snap["path_counts"])
        self.assertIn("500", snap["status_counts"])


if __name__ == "__main__":
    unittest.main()
