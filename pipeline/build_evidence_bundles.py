from __future__ import annotations

import argparse
import hashlib
from collections import defaultdict

from common import ProgressPrinter, read_csv, stable_id, utc_now_iso, write_csv


def _hash_joined(values: list[str]) -> str:
    payload = "|".join(sorted(v for v in values if v))
    if not payload:
        return ""
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _join_unique(values: list[str]) -> str:
    uniq = sorted({v.strip() for v in values if v and v.strip()})
    return "|".join(uniq)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build audit-oriented evidence bundles for species and taxon priors.")
    parser.add_argument("--species", required=True, help="Expanded species CSV.")
    parser.add_argument("--taxonomy", required=True, help="Taxonomy backbone CSV.")
    parser.add_argument("--behavior", required=True, help="Behavior evidence CSV.")
    parser.add_argument("--priors-estimated", required=True, help="Estimated priors CSV.")
    parser.add_argument("--signatures", required=True, help="Estimated prior signatures CSV.")
    parser.add_argument("--species-posteriors", required=True, help="Final species posterior CSV (post calibration/curation).")
    parser.add_argument("--taxon-priors", required=True, help="Final taxon priors CSV.")
    parser.add_argument("--calibration-audit", required=True, help="Calibration audit CSV.")
    parser.add_argument("--out-species", required=True, help="Species evidence output CSV.")
    parser.add_argument("--out-taxon", required=True, help="Taxon evidence output CSV.")
    args = parser.parse_args()

    species_rows = read_csv(args.species)
    taxonomy_rows = {r["species"]: r for r in read_csv(args.taxonomy)}
    behavior_rows = {r["species"]: r for r in read_csv(args.behavior)}
    estimated_rows = {r["species"]: r for r in read_csv(args.priors_estimated)}
    signature_rows = {r["species"]: r for r in read_csv(args.signatures)}
    posterior_rows = {r["species"]: r for r in read_csv(args.species_posteriors)}
    taxon_rows = read_csv(args.taxon_priors)
    calibration_rows = read_csv(args.calibration_audit)

    calibration_citations_by_taxon: dict[tuple[str, str], list[str]] = defaultdict(list)
    cal_progress = ProgressPrinter(total=len(calibration_rows), label="evidence_bundles:calibration")
    for row in calibration_rows:
        if row.get("status", "") != "applied":
            cal_progress.tick()
            continue
        key = (row.get("rank", "").strip(), row.get("taxon", "").strip())
        citation = row.get("citation", "").strip()
        if key[0] and key[1] and citation:
            calibration_citations_by_taxon[key].append(citation)
        cal_progress.tick()
    cal_progress.finish()

    generated_at = utc_now_iso()
    species_evidence: list[dict[str, object]] = []

    species_progress = ProgressPrinter(total=len(species_rows), label="evidence_bundles:species")
    for srow in species_rows:
        species = srow["species"]
        post = posterior_rows.get(species)
        if not post:
            species_progress.tick()
            continue

        behavior = behavior_rows.get(species, {})
        tax = taxonomy_rows.get(species, {})
        est = estimated_rows.get(species, {})
        sig = signature_rows.get(species, {})

        calibration_refs = [x for x in post.get("calibration_refs", "").split("|") if x]
        citations = _join_unique(
            [
                srow.get("source_citation", ""),
                behavior.get("source_name", ""),
                *calibration_refs,
            ]
        )
        ai_hash = est.get("ai_rationale_hash", "")
        if not ai_hash:
            ai_hash = _hash_joined([sig.get("signature", ""), post.get("source_model", ""), species])

        species_evidence.append(
            {
                "entity_kind": "species",
                "entity_id": stable_id(species, prefix="sp"),
                "species": species,
                "common_name": srow.get("common_name", ""),
                "class": srow.get("class", ""),
                "family": srow.get("family", ""),
                "is_seed": srow.get("is_seed", ""),
                "candidate_confidence_score": srow.get("candidate_confidence_score", ""),
                "provenance_type": post.get("provenance_type", ""),
                "source_model": post.get("source_model", ""),
                "taxonomy_source": tax.get("taxonomy_source", ""),
                "evidence_sources": _join_unique(
                    [
                        srow.get("candidate_source", ""),
                        behavior.get("source_name", ""),
                        post.get("source_model", ""),
                    ]
                ),
                "source_citations": citations,
                "extraction_notes": behavior.get("evidence_text", ""),
                "ai_rationale_hash": ai_hash,
                "prior_signature": sig.get("signature", ""),
                "calibration_applied": post.get("calibration_applied", "false"),
                "calibration_refs": post.get("calibration_refs", ""),
                "generated_at": generated_at,
            }
        )
        species_progress.tick()
    species_progress.finish()

    species_ids_by_rank_taxon: dict[tuple[str, str], list[str]] = defaultdict(list)
    species_evidence_by_name = {r["species"]: r for r in species_evidence}
    index_progress = ProgressPrinter(total=len(species_rows), label="evidence_bundles:index")
    for s in species_rows:
        species = s["species"]
        if species not in species_evidence_by_name:
            index_progress.tick()
            continue
        sp_id = species_evidence_by_name[species]["entity_id"]
        for rank in ["phylum", "class", "order", "family", "genus"]:
            taxon = s.get(rank, "").strip()
            if taxon:
                species_ids_by_rank_taxon[(rank, taxon)].append(sp_id)
        index_progress.tick()
    index_progress.finish()

    taxon_evidence: list[dict[str, object]] = []
    taxon_progress = ProgressPrinter(total=len(taxon_rows), label="evidence_bundles:taxon")
    for row in taxon_rows:
        rank = row.get("rank", "").strip()
        taxon = row.get("taxon", "").strip()
        if not rank or not taxon:
            taxon_progress.tick()
            continue
        member_ids = sorted(set(species_ids_by_rank_taxon.get((rank, taxon), [])))
        member_species = {
            r["species"]
            for r in species_evidence
            if r["entity_id"] in member_ids
        }
        member_hashes = [
            r["ai_rationale_hash"]
            for r in species_evidence
            if r["entity_id"] in member_ids and r.get("ai_rationale_hash")
        ]
        member_citations = [
            r["source_citations"]
            for r in species_evidence
            if r["entity_id"] in member_ids and r.get("source_citations")
        ]
        cal_refs = calibration_citations_by_taxon.get((rank, taxon), [])
        all_citations = _join_unique(member_citations + cal_refs)

        taxon_evidence.append(
            {
                "entity_kind": "taxon",
                "entity_id": stable_id(f"{rank}:{taxon}", prefix="tx"),
                "rank": rank,
                "taxon": taxon,
                "n_species_evidence": len(member_species),
                "provenance_type": row.get("provenance_type", ""),
                "source_model": row.get("source_model", ""),
                "evidence_sources": "species_evidence_aggregation",
                "source_citations": all_citations,
                "extraction_notes": f"Aggregated from {len(member_species)} species posterior rows.",
                "ai_rationale_hash": _hash_joined(member_hashes),
                "member_species_ids": "|".join(member_ids),
                "calibration_applied": "true" if cal_refs else "false",
                "generated_at": generated_at,
            }
        )
        taxon_progress.tick()
    taxon_progress.finish()

    write_csv(
        args.out_species,
        species_evidence,
        [
            "entity_kind",
            "entity_id",
            "species",
            "common_name",
            "class",
            "family",
            "is_seed",
            "candidate_confidence_score",
            "provenance_type",
            "source_model",
            "taxonomy_source",
            "evidence_sources",
            "source_citations",
            "extraction_notes",
            "ai_rationale_hash",
            "prior_signature",
            "calibration_applied",
            "calibration_refs",
            "generated_at",
        ],
    )
    write_csv(
        args.out_taxon,
        taxon_evidence,
        [
            "entity_kind",
            "entity_id",
            "rank",
            "taxon",
            "n_species_evidence",
            "provenance_type",
            "source_model",
            "evidence_sources",
            "source_citations",
            "extraction_notes",
            "ai_rationale_hash",
            "member_species_ids",
            "calibration_applied",
            "generated_at",
        ],
    )

    print(f"Wrote species evidence bundle: {len(species_evidence)} -> {args.out_species}")
    print(f"Wrote taxon evidence bundle: {len(taxon_evidence)} -> {args.out_taxon}")


if __name__ == "__main__":
    main()
