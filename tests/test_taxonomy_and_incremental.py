from __future__ import annotations

import csv
import importlib.util
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PIPELINE_DIR = ROOT / "pipeline"


def load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module at {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestFetchOpenTree(unittest.TestCase):
    def test_resolve_latest_version_parses_redirect(self) -> None:
        mod = load_module("fetch_opentree_taxonomy", PIPELINE_DIR / "fetch_opentree_taxonomy.py")

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def geturl(self):
                return "https://tree.opentreeoflife.org/about/taxonomy-version/ott3.7.3"

        with patch.object(mod.urllib.request, "urlopen", return_value=FakeResponse()):
            version, archive_url = mod.resolve_latest_version()

        self.assertEqual(version, "ott3.7.3")
        self.assertEqual(archive_url, "https://files.opentreeoflife.org/ott/ott3.7.3/ott3.7.3.tgz")

    def test_extract_members_extracts_expected_files(self) -> None:
        mod = load_module("fetch_opentree_taxonomy", PIPELINE_DIR / "fetch_opentree_taxonomy.py")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            archive = tmp_path / "ott3.7.3.tgz"
            source_dir = tmp_path / "ott3.7.3"
            source_dir.mkdir()
            (source_dir / "taxonomy.tsv").write_text("test", encoding="utf-8")
            (source_dir / "version.txt").write_text("ott3.7.3", encoding="utf-8")

            with tarfile.open(archive, "w:gz") as tf:
                tf.add(source_dir / "taxonomy.tsv", arcname="ott3.7.3/taxonomy.tsv")
                tf.add(source_dir / "version.txt", arcname="ott3.7.3/version.txt")

            out_dir = tmp_path / "extracted"
            extracted = mod.extract_members(archive, out_dir, ["taxonomy.tsv", "version.txt"], force=True)

            self.assertIn("taxonomy.tsv", extracted)
            self.assertTrue((out_dir / "taxonomy.tsv").exists())
            self.assertTrue((out_dir / "version.txt").exists())


class TestBuildAndRenderTaxonomy(unittest.TestCase):
    def _write_sample_taxonomy(self, path: Path) -> None:
        lines = [
            "1\t|\t0\t|\tlife\t|\tno rank\t|\t\t|\t\t|\t\t|\n",
            "691846\t|\t1\t|\tMetazoa\t|\tkingdom\t|\t\t|\t\t|\t\t|\n",
            "125642\t|\t691846\t|\tChordata\t|\tphylum\t|\t\t|\t\t|\t\t|\n",
            "632179\t|\t691846\t|\tArthropoda\t|\tphylum\t|\t\t|\t\t|\t\t|\n",
            "211\t|\t125642\t|\tMammalia\t|\tclass\t|\t\t|\t\t|\t\t|\n",
            "212\t|\t211\t|\tCarnivora\t|\torder\t|\t\t|\t\t|\t\t|\n",
            "213\t|\t632179\t|\tInsecta\t|\tclass\t|\t\t|\t\t|\t\t|\n",
            "214\t|\t213\t|\tHymenoptera\t|\torder\t|\t\t|\t\t|\t\t|\n",
            "215\t|\t691846\t|\tDeprecatedPhylum\t|\tphylum\t|\t\t|\t\t|\tmerged\t|\n",
        ]
        path.write_text("".join(lines), encoding="utf-8")

    def test_build_and_render_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            taxonomy = tmp_path / "taxonomy.tsv"
            out_phyla = tmp_path / "opentree_metazoa_phyla.csv"
            out_subtree = tmp_path / "metazoa_subtree_nodes.csv"
            out_simple = tmp_path / "simple.png"
            out_complex = tmp_path / "complex.png"
            self._write_sample_taxonomy(taxonomy)

            subprocess.run(
                [
                    sys.executable,
                    "pipeline/build_metazoa_phyla.py",
                    "--taxonomy-tsv",
                    str(taxonomy),
                    "--out-phyla",
                    str(out_phyla),
                    "--out-subtree",
                    str(out_subtree),
                    "--metazoa-uid",
                    "691846",
                ],
                cwd=ROOT,
                check=True,
            )

            with open(out_phyla, "r", newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            names = {r["phylum_name"] for r in rows}
            self.assertIn("Chordata", names)
            self.assertIn("Arthropoda", names)
            self.assertNotIn("DeprecatedPhylum", names)

            env = dict(os.environ)
            env["MPLCONFIGDIR"] = str(tmp_path / "mpl")
            env["MPLBACKEND"] = "Agg"

            subprocess.run(
                [
                    sys.executable,
                    "pipeline/render_metazoa_tree.py",
                    "--phyla",
                    str(out_phyla),
                    "--out",
                    str(out_simple),
                ],
                cwd=ROOT,
                check=True,
                env=env,
            )
            subprocess.run(
                [
                    sys.executable,
                    "pipeline/render_metazoa_hierarchy.py",
                    "--subtree",
                    str(out_subtree),
                    "--phyla",
                    str(out_phyla),
                    "--out",
                    str(out_complex),
                    "--max-phyla",
                    "2",
                    "--max-classes-per-phylum",
                    "2",
                    "--max-orders-per-class",
                    "2",
                ],
                cwd=ROOT,
                check=True,
                env=env,
            )

            self.assertTrue(out_simple.exists())
            self.assertTrue(out_complex.exists())


class TestIncrementalSignatures(unittest.TestCase):
    def _write_species_traits(self, species_csv: Path, traits_csv: Path, sociality_a: str = "0.9") -> None:
        species_csv.write_text(
            "\n".join(
                [
                    "species,kingdom,phylum,class,order,family,genus,common_name,body_mass_kg,sociality_score,diet_breadth_score,activity_pattern,habitat_type,source_confidence",
                    f"Alpha,Animalia,Chordata,Mammalia,Primates,Hominidae,Alpha,Alpha animal,10,{sociality_a},0.6,diurnal,forest,high",
                    "Beta,Animalia,Arthropoda,Insecta,Hymenoptera,Apidae,Beta,Beta animal,0.01,0.4,0.2,diurnal,terrestrial,medium",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        traits_csv.write_text(
            "\n".join(
                [
                    "species,mass_scaled,sociality_score,diet_breadth_score,activity_score,habitat_complexity_score,source_confidence",
                    f"Alpha,0.6,{sociality_a},0.6,1.0,0.8,high",
                    "Beta,0.3,0.4,0.2,1.0,0.6,medium",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

    def test_incremental_reuses_unchanged_and_recalculates_changed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            species_csv = tmp_path / "species.csv"
            traits_csv = tmp_path / "traits.csv"
            out_csv = tmp_path / "priors.csv"
            sig_csv = tmp_path / "priors_signatures.csv"

            self._write_species_traits(species_csv, traits_csv, sociality_a="0.9")

            subprocess.run(
                [
                    sys.executable,
                    "pipeline/quantify_priors_ai.py",
                    "--species",
                    str(species_csv),
                    "--traits",
                    str(traits_csv),
                    "--out",
                    str(out_csv),
                    "--signature-out",
                    str(sig_csv),
                    "--update-mode",
                    "full",
                ],
                cwd=ROOT,
                check=True,
            )

            subprocess.run(
                [
                    sys.executable,
                    "pipeline/quantify_priors_ai.py",
                    "--species",
                    str(species_csv),
                    "--traits",
                    str(traits_csv),
                    "--out",
                    str(out_csv),
                    "--signature-out",
                    str(sig_csv),
                    "--update-mode",
                    "incremental",
                ],
                cwd=ROOT,
                check=True,
            )

            with open(sig_csv, "r", newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual({r["action"] for r in rows}, {"reused"})

            self._write_species_traits(species_csv, traits_csv, sociality_a="0.2")
            subprocess.run(
                [
                    sys.executable,
                    "pipeline/quantify_priors_ai.py",
                    "--species",
                    str(species_csv),
                    "--traits",
                    str(traits_csv),
                    "--out",
                    str(out_csv),
                    "--signature-out",
                    str(sig_csv),
                    "--update-mode",
                    "incremental",
                ],
                cwd=ROOT,
                check=True,
            )

            with open(sig_csv, "r", newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))

            actions = {r["species"]: r["action"] for r in rows}
            self.assertEqual(actions["Alpha"], "recalculated")
            self.assertEqual(actions["Beta"], "reused")

    def _write_species_traits_shared_family(
        self,
        species_csv: Path,
        traits_csv: Path,
        sociality_alpha: str = "0.9",
    ) -> None:
        species_csv.write_text(
            "\n".join(
                [
                    "species,kingdom,phylum,class,order,family,genus,common_name,body_mass_kg,sociality_score,diet_breadth_score,activity_pattern,habitat_type,source_confidence",
                    f"Alpha,Animalia,Chordata,Mammalia,Primates,Hominidae,Alpha,Alpha animal,10,{sociality_alpha},0.6,diurnal,forest,high",
                    "Beta,Animalia,Chordata,Mammalia,Primates,Hominidae,Beta,Beta animal,7,0.7,0.6,diurnal,forest,high",
                    "Gamma,Animalia,Chordata,Mammalia,Carnivora,Canidae,Gamma,Gamma animal,12,0.5,0.5,diurnal,forest,medium",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        traits_csv.write_text(
            "\n".join(
                [
                    "species,mass_scaled,sociality_score,diet_breadth_score,activity_score,habitat_complexity_score,source_confidence",
                    f"Alpha,0.6,{sociality_alpha},0.6,1.0,0.8,high",
                    "Beta,0.55,0.7,0.6,1.0,0.8,high",
                    "Gamma,0.7,0.5,0.5,1.0,0.7,medium",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

    def test_incremental_recalculates_species_sharing_taxon_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            species_csv = tmp_path / "species.csv"
            traits_csv = tmp_path / "traits.csv"
            out_csv = tmp_path / "priors.csv"
            sig_csv = tmp_path / "priors_signatures.csv"

            self._write_species_traits_shared_family(species_csv, traits_csv, sociality_alpha="0.9")
            subprocess.run(
                [
                    sys.executable,
                    "pipeline/quantify_priors_ai.py",
                    "--species",
                    str(species_csv),
                    "--traits",
                    str(traits_csv),
                    "--out",
                    str(out_csv),
                    "--signature-out",
                    str(sig_csv),
                    "--update-mode",
                    "full",
                ],
                cwd=ROOT,
                check=True,
            )

            self._write_species_traits_shared_family(species_csv, traits_csv, sociality_alpha="0.2")
            subprocess.run(
                [
                    sys.executable,
                    "pipeline/quantify_priors_ai.py",
                    "--species",
                    str(species_csv),
                    "--traits",
                    str(traits_csv),
                    "--out",
                    str(out_csv),
                    "--signature-out",
                    str(sig_csv),
                    "--update-mode",
                    "incremental",
                ],
                cwd=ROOT,
                check=True,
            )

            with open(sig_csv, "r", newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            actions = {r["species"]: r["action"] for r in rows}
            self.assertEqual(actions["Alpha"], "recalculated")
            self.assertEqual(actions["Beta"], "recalculated")
            self.assertEqual(actions["Gamma"], "reused")

            with open(out_csv, "r", newline="", encoding="utf-8") as f:
                prior_rows = {r["species"]: r for r in csv.DictReader(f)}
            self.assertEqual(prior_rows["Alpha"]["deterministic_anchor_rank"], "family")
            self.assertEqual(prior_rows["Beta"]["deterministic_anchor_rank"], "family")


if __name__ == "__main__":
    unittest.main()
