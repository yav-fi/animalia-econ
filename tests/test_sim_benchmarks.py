from __future__ import annotations

import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestSimulationBenchmarks(unittest.TestCase):
    def test_benchmark_suite_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "benchmark.csv"
            subprocess.run(
                [
                    sys.executable,
                    "benchmarks/simulation_realism.py",
                    "--dataset",
                    "data/processed/animaliaecon_taxon_priors.csv",
                    "--out",
                    str(out),
                ],
                cwd=ROOT,
                check=True,
            )
            with open(out, "r", newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertGreaterEqual(len(rows), 2)
            summary = rows[-1]
            self.assertEqual(summary["entity"], "__SUMMARY__")
            self.assertEqual(summary["status"], "pass")


if __name__ == "__main__":
    unittest.main()
