from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestApplyOverrides(unittest.TestCase):
    def test_species_override_updates_value_and_intervals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            input_csv = t / "species.csv"
            ov_csv = t / "ov.csv"
            out_csv = t / "out.csv"
            audit_csv = t / "audit.csv"

            input_csv.write_text(
                "\n".join(
                    [
                        "species,risk_preference,risk_preference_lower,risk_preference_upper,temporal_discount_rate,temporal_discount_rate_lower,temporal_discount_rate_upper,effort_price_elasticity,effort_price_elasticity_lower,effort_price_elasticity_upper,cooperation_propensity,cooperation_propensity_lower,cooperation_propensity_upper,inequity_sensitivity,inequity_sensitivity_lower,inequity_sensitivity_upper,punishment_propensity,punishment_propensity_lower,punishment_propensity_upper,tokenization_capacity,tokenization_capacity_lower,tokenization_capacity_upper,uncertainty_sd,provenance_type,source_model",
                        "Alpha,1.0,0.8,1.2,0.5,0.3,0.7,-0.6,-0.8,-0.4,0.6,0.4,0.8,0.5,0.3,0.7,0.4,0.2,0.6,0.7,0.5,0.9,0.1,imputed_trait,model",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            ov_csv.write_text(
                "\n".join(
                    [
                        "species,param,value,active,note",
                        "Alpha,risk_preference,1.5,true,test",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            subprocess.run(
                [
                    sys.executable,
                    "pipeline/apply_overrides.py",
                    "--entity-kind",
                    "species",
                    "--in",
                    str(input_csv),
                    "--overrides",
                    str(ov_csv),
                    "--out",
                    str(out_csv),
                    "--audit-out",
                    str(audit_csv),
                ],
                cwd=ROOT,
                check=True,
            )

            with open(out_csv, "r", newline="", encoding="utf-8") as f:
                row = next(csv.DictReader(f))
            self.assertEqual(row["risk_preference"], "1.5")
            self.assertEqual(row["risk_preference_lower"], "1.304")
            self.assertEqual(row["risk_preference_upper"], "1.696")

            with open(audit_csv, "r", newline="", encoding="utf-8") as f:
                audit_rows = list(csv.DictReader(f))
            self.assertEqual(len(audit_rows), 1)
            self.assertEqual(audit_rows[0]["param"], "risk_preference")


class TestReleaseDataset(unittest.TestCase):
    def test_release_dataset_creates_manifest_checksums_and_changelog(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            f1 = t / "a.csv"
            f2 = t / "b.json"
            f1.write_text("x,y\n1,2\n", encoding="utf-8")
            f2.write_text('{"ok": true}\n', encoding="utf-8")

            snapshot_root = t / "releases"
            changelog = t / "CHANGELOG.md"

            subprocess.run(
                [
                    sys.executable,
                    "pipeline/release_dataset.py",
                    "--version",
                    "9.9.9-test",
                    "--snapshot-root",
                    str(snapshot_root),
                    "--changelog",
                    str(changelog),
                    "--notes",
                    "test release",
                    "--files",
                    f"{f1},{f2}",
                ],
                cwd=ROOT,
                check=True,
            )

            rel = snapshot_root / "9.9.9-test"
            self.assertTrue((rel / "a.csv").exists())
            self.assertTrue((rel / "b.json").exists())
            self.assertTrue((rel / "manifest.json").exists())
            self.assertTrue((rel / "checksums.sha256").exists())

            manifest = json.loads((rel / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["version"], "9.9.9-test")
            self.assertEqual(len(manifest["files"]), 2)

            cl = changelog.read_text(encoding="utf-8")
            self.assertIn("9.9.9-test", cl)
            self.assertIn("test release", cl)


class TestOverrideQueue(unittest.TestCase):
    def test_build_override_queue_flags_low_confidence_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            species_obs = t / "species_observed.csv"
            queue = t / "queue.csv"

            species_obs.write_text(
                "\n".join(
                    [
                        "species,common_name,class,family,row_confidence_score,uncertainty_sd,provenance_type",
                        "Alpha,Alpha,Mammalia,Hominidae,0.9,0.12,ai_estimated",
                        "Beta,Beta,Mammalia,Canidae,0.55,0.41,imputed_trait",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            subprocess.run(
                [
                    sys.executable,
                    "pipeline/build_override_queue.py",
                    "--species-observed",
                    str(species_obs),
                    "--out",
                    str(queue),
                ],
                cwd=ROOT,
                check=True,
            )

            with open(queue, "r", newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["species"], "Beta")
            self.assertIn("low_row_confidence", rows[0]["review_reasons"])


class TestVersionedPriors(unittest.TestCase):
    def test_build_versioned_priors_generates_history_and_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            releases = t / "releases" / "datasets"
            rel = releases / "1.0.0"
            rel.mkdir(parents=True, exist_ok=True)

            (rel / "animaliaecon_taxon_priors.csv").write_text(
                "\n".join(
                    [
                        "dataset_version,generated_at,entity_kind,rank,taxon,n_species,risk_preference,temporal_discount_rate,effort_price_elasticity,cooperation_propensity,inequity_sensitivity,punishment_propensity,tokenization_capacity,uncertainty_sd,provenance_type,source_model",
                        "1.0.0,now,taxon,class,Mammalia,2,1.0,0.8,-0.7,0.6,0.5,0.4,0.7,0.1,imputed_taxonomy,m1",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (rel / "animaliaecon_species_observed.csv").write_text(
                "\n".join(
                    [
                        "dataset_version,generated_at,species,common_name,class,family,risk_preference,temporal_discount_rate,effort_price_elasticity,cooperation_propensity,inequity_sensitivity,punishment_propensity,tokenization_capacity,uncertainty_sd,row_confidence_score,provenance_type,source_model",
                        "1.0.0,now,Alpha,Alpha,Mammalia,Hominidae,1.0,0.8,-0.7,0.6,0.5,0.4,0.7,0.1,0.8,imputed_trait,m1",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (rel / "manifest.json").write_text('{"released_at":"2026-01-01T00:00:00Z"}', encoding="utf-8")

            current_taxon = t / "current_taxon.csv"
            current_species = t / "current_species.csv"
            current_taxon.write_text(
                "\n".join(
                    [
                        "dataset_version,generated_at,entity_kind,rank,taxon,n_species,risk_preference,temporal_discount_rate,effort_price_elasticity,cooperation_propensity,inequity_sensitivity,punishment_propensity,tokenization_capacity,uncertainty_sd,provenance_type,source_model",
                        "1.0.1,now,taxon,class,Mammalia,2,1.1,0.8,-0.7,0.62,0.5,0.4,0.7,0.12,imputed_taxonomy,m2",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            current_species.write_text(
                "\n".join(
                    [
                        "dataset_version,generated_at,species,common_name,class,family,risk_preference,temporal_discount_rate,effort_price_elasticity,cooperation_propensity,inequity_sensitivity,punishment_propensity,tokenization_capacity,uncertainty_sd,row_confidence_score,provenance_type,source_model",
                        "1.0.1,now,Alpha,Alpha,Mammalia,Hominidae,1.1,0.8,-0.7,0.62,0.5,0.4,0.7,0.12,0.82,imputed_trait,m2",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            out_taxon = t / "taxon_history.csv"
            out_species = t / "species_history.csv"
            out_detail = t / "drift_detail.csv"
            out_summary = t / "drift_summary.csv"

            subprocess.run(
                [
                    sys.executable,
                    "pipeline/build_versioned_priors.py",
                    "--releases-root",
                    str(releases),
                    "--current-taxon",
                    str(current_taxon),
                    "--current-species",
                    str(current_species),
                    "--out-taxon-history",
                    str(out_taxon),
                    "--out-species-history",
                    str(out_species),
                    "--out-drift-detail",
                    str(out_detail),
                    "--out-drift-summary",
                    str(out_summary),
                ],
                cwd=ROOT,
                check=True,
            )

            with open(out_taxon, "r", newline="", encoding="utf-8") as f:
                tax_rows = list(csv.DictReader(f))
            self.assertEqual(len(tax_rows), 2)

            with open(out_summary, "r", newline="", encoding="utf-8") as f:
                summary_rows = list(csv.DictReader(f))
            self.assertTrue(summary_rows)


if __name__ == "__main__":
    unittest.main()
