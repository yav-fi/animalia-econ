from __future__ import annotations

import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestExpansion(unittest.TestCase):
    def test_expand_species_candidates_hits_targets_when_bank_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            seed = t / "seed.csv"
            targets = t / "targets.csv"
            bank = t / "bank.csv"
            out_species = t / "expanded.csv"
            out_coverage = t / "coverage.csv"

            seed.write_text(
                "\n".join(
                    [
                        "species,kingdom,phylum,class,order,family,genus,common_name,body_mass_kg,sociality_score,diet_breadth_score,activity_pattern,habitat_type,source_confidence",
                        "Alpha,Animalia,Chordata,Mammalia,Primates,Hominidae,Alpha,Alpha,10,0.8,0.6,diurnal,forest,high",
                        "Beta,Animalia,Chordata,Aves,Passeriformes,Corvidae,Beta,Beta,0.3,0.7,0.5,diurnal,forest,high",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            targets.write_text(
                "\n".join(
                    [
                        "rank,taxon,target_n,priority,notes",
                        "class,Mammalia,3,1,",
                        "class,Aves,2,1,",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            bank.write_text(
                "\n".join(
                    [
                        "species,kingdom,phylum,class,order,family,genus,common_name,body_mass_kg,sociality_score,diet_breadth_score,activity_pattern,habitat_type,source_confidence,candidate_source,source_citation",
                        "Gamma,Animalia,Chordata,Mammalia,Carnivora,Canidae,Gamma,Gamma,12,0.6,0.6,diurnal,forest,medium,bank,test",
                        "Delta,Animalia,Chordata,Mammalia,Primates,Cebidae,Delta,Delta,5,0.7,0.6,diurnal,forest,medium,bank,test",
                        "Epsilon,Animalia,Chordata,Aves,Passeriformes,Sturnidae,Epsilon,Epsilon,0.1,0.6,0.4,diurnal,urban,medium,bank,test",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            subprocess.run(
                [
                    sys.executable,
                    "pipeline/expand_species_candidates.py",
                    "--seed",
                    str(seed),
                    "--target-clades",
                    str(targets),
                    "--candidate-bank",
                    str(bank),
                    "--out-species",
                    str(out_species),
                    "--out-coverage",
                    str(out_coverage),
                ],
                cwd=ROOT,
                check=True,
            )

            with open(out_species, "r", newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 5)
            for r in rows:
                self.assertGreaterEqual(float(r["candidate_confidence_score"]), 0.0)
                self.assertLessEqual(float(r["candidate_confidence_score"]), 1.0)

            with open(out_coverage, "r", newline="", encoding="utf-8") as f:
                cov = {r["taxon"]: r for r in csv.DictReader(f)}
            self.assertEqual(cov["Mammalia"]["shortfall_n"], "0")
            self.assertEqual(cov["Aves"]["shortfall_n"], "0")


class TestBayesCalibrationEvidence(unittest.TestCase):
    def test_bayes_calibration_and_evidence_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            species = t / "species.csv"
            priors = t / "priors.csv"
            posterior = t / "posterior.csv"
            calibrated = t / "calibrated.csv"
            calibration = t / "calibration.csv"
            cal_audit = t / "calibration_audit.csv"
            behavior = t / "behavior.csv"
            taxonomy = t / "taxonomy.csv"
            signatures = t / "signatures.csv"
            taxon = t / "taxon.csv"
            ev_species = t / "ev_species.csv"
            ev_taxon = t / "ev_taxon.csv"

            species.write_text(
                "\n".join(
                    [
                        "species,kingdom,phylum,class,order,family,genus,common_name,body_mass_kg,sociality_score,diet_breadth_score,activity_pattern,habitat_type,source_confidence,is_seed,candidate_source,source_citation,candidate_confidence_score",
                        "Alpha,Animalia,Chordata,Mammalia,Primates,Hominidae,Alpha,Alpha,10,0.9,0.6,diurnal,forest,high,true,seed,test,0.9",
                        "Beta,Animalia,Chordata,Mammalia,Primates,Hominidae,Beta,Beta,8,0.8,0.6,diurnal,forest,high,true,seed,test,0.9",
                        "Gamma,Animalia,Chordata,Mammalia,Carnivora,Canidae,Gamma,Gamma,12,0.6,0.5,diurnal,forest,medium,false,bank,test,0.8",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            priors.write_text(
                "\n".join(
                    [
                        "species,risk_preference,temporal_discount_rate,effort_price_elasticity,cooperation_propensity,inequity_sensitivity,punishment_propensity,tokenization_capacity,uncertainty_sd,provenance_type,source_model,ai_prompt_version,ai_rationale_hash,evidence_sources,extraction_notes,row_confidence_score",
                        "Alpha,1.0,0.8,-0.7,0.6,0.5,0.4,0.7,0.12,imputed_trait,deterministic,pv,h1,src,note,0.8",
                        "Beta,1.1,0.9,-0.6,0.62,0.52,0.42,0.72,0.13,imputed_trait,deterministic,pv,h2,src,note,0.8",
                        "Gamma,0.9,0.7,-0.8,0.45,0.4,0.35,0.5,0.2,imputed_trait,deterministic,pv,h3,src,note,0.7",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            calibration.write_text(
                "\n".join(
                    [
                        "rank,taxon,param,target_mean,target_sd,n_studies,citation,note",
                        "class,Mammalia,cooperation_propensity,0.75,0.1,10,test_citation,test_note",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            behavior.write_text(
                "\n".join(
                    [
                        "species,task_family,evidence_text,evidence_confidence,source_name",
                        "Alpha,trust,Alpha evidence,0.6,beh_source",
                        "Beta,trust,Beta evidence,0.6,beh_source",
                        "Gamma,trust,Gamma evidence,0.6,beh_source",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            taxonomy.write_text(
                "\n".join(
                    [
                        "species,species_id,kingdom,phylum,class,order,family,genus,common_name,taxonomy_source,source_version,retrieved_at",
                        "Alpha,sp1,Animalia,Chordata,Mammalia,Primates,Hominidae,Alpha,Alpha,seed,v1,now",
                        "Beta,sp2,Animalia,Chordata,Mammalia,Primates,Hominidae,Beta,Beta,seed,v1,now",
                        "Gamma,sp3,Animalia,Chordata,Mammalia,Carnivora,Canidae,Gamma,Gamma,seed,v1,now",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            signatures.write_text(
                "\n".join(
                    [
                        "species,signature,prompt_version,updated_at,action",
                        "Alpha,s1,v2,now,recalculated",
                        "Beta,s2,v2,now,recalculated",
                        "Gamma,s3,v2,now,recalculated",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            subprocess.run(
                [
                    sys.executable,
                    "pipeline/fit_hierarchical_model.py",
                    "--species",
                    str(species),
                    "--priors",
                    str(priors),
                    "--out",
                    str(posterior),
                ],
                cwd=ROOT,
                check=True,
            )
            posterior_diag = posterior.with_name(f"{posterior.stem}_model_diagnostics.csv")
            posterior_ppc = posterior.with_name(f"{posterior.stem}_posterior_predictive_checks.csv")
            with open(posterior_diag, "r", newline="", encoding="utf-8") as f:
                diag_rows = list(csv.DictReader(f))
            self.assertTrue(diag_rows)
            self.assertIn("param", diag_rows[0])
            with open(posterior_ppc, "r", newline="", encoding="utf-8") as f:
                ppc_rows = list(csv.DictReader(f))
            self.assertTrue(ppc_rows)
            self.assertIn("species", ppc_rows[0])
            subprocess.run(
                [
                    sys.executable,
                    "pipeline/calibrate_priors_by_clade.py",
                    "--species",
                    str(species),
                    "--priors",
                    str(posterior),
                    "--calibration",
                    str(calibration),
                    "--out",
                    str(calibrated),
                    "--audit-out",
                    str(cal_audit),
                ],
                cwd=ROOT,
                check=True,
            )
            subprocess.run(
                [
                    sys.executable,
                    "pipeline/aggregate_taxon_priors.py",
                    "--species",
                    str(species),
                    "--priors",
                    str(calibrated),
                    "--out",
                    str(taxon),
                ],
                cwd=ROOT,
                check=True,
            )
            subprocess.run(
                [
                    sys.executable,
                    "pipeline/build_evidence_bundles.py",
                    "--species",
                    str(species),
                    "--taxonomy",
                    str(taxonomy),
                    "--behavior",
                    str(behavior),
                    "--priors-estimated",
                    str(priors),
                    "--signatures",
                    str(signatures),
                    "--species-posteriors",
                    str(calibrated),
                    "--taxon-priors",
                    str(taxon),
                    "--calibration-audit",
                    str(cal_audit),
                    "--out-species",
                    str(ev_species),
                    "--out-taxon",
                    str(ev_taxon),
                ],
                cwd=ROOT,
                check=True,
            )

            with open(calibrated, "r", newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertTrue(any(r["calibration_applied"] == "true" for r in rows))

            with open(ev_species, "r", newline="", encoding="utf-8") as f:
                ev_rows = list(csv.DictReader(f))
            self.assertEqual(len(ev_rows), 3)
            self.assertTrue(all(r["ai_rationale_hash"] for r in ev_rows))

            with open(ev_taxon, "r", newline="", encoding="utf-8") as f:
                tx_rows = list(csv.DictReader(f))
            self.assertGreater(len(tx_rows), 0)
            self.assertTrue(all(int(r["n_species_evidence"]) >= 1 for r in tx_rows))


if __name__ == "__main__":
    unittest.main()
