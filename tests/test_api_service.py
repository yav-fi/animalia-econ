from __future__ import annotations

import unittest

from api.service import (
    _current_dataset_version,
    build_species_id,
    dataset_stats,
    get_species_by_id,
    get_taxon,
    list_snapshot_versions,
    list_taxa,
    parse_species_id,
    random_species,
    search_species,
)


class TestApiService(unittest.TestCase):
    def test_dataset_stats_nonzero(self) -> None:
        stats = dataset_stats()
        self.assertGreater(stats["taxon_rows"], 0)

    def test_get_taxon_by_rank_name(self) -> None:
        row = get_taxon("class", "Mammalia")
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["rank"], "class")
        self.assertEqual(row["taxon"], "Mammalia")

    def test_list_taxa_filters(self) -> None:
        rows = list_taxa(rank="phylum", limit=10)
        self.assertGreater(len(rows), 0)
        for row in rows:
            self.assertEqual(row.get("rank"), "phylum")

    def test_species_search_returns_label_and_id(self) -> None:
        rows = search_species("chimp", dataset="inherited", limit=5)
        self.assertGreater(len(rows), 0)
        top = rows[0]
        self.assertIn("(", top["label"])
        self.assertIn(")", top["label"])
        self.assertTrue(top["id"])

    def test_species_id_round_trip(self) -> None:
        species_id = build_species_id("Pan troglodytes", dataset="inherited")
        version, dataset, species = parse_species_id(species_id)
        self.assertTrue(version in {None, "latest"} or isinstance(version, str))
        self.assertEqual(dataset, "inherited")
        self.assertEqual(species, "Pan troglodytes")

        payload = get_species_by_id(species_id)
        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(payload["row"]["species"], "Pan troglodytes")
        self.assertIn("dataset_version", payload)

    def test_random_species_bucket_or_fallback(self) -> None:
        hit = random_species(dataset="inherited", bucket="mammal")
        self.assertEqual(hit["dataset"], "inherited")
        self.assertIn("row", hit)
        self.assertTrue(hit["id"])
        self.assertTrue(hit["dataset_version"])

        fallback = random_species(dataset="inherited", bucket="fish")
        self.assertIn("row", fallback)
        self.assertTrue(fallback["row"]["species"])

    def test_dataset_stats_and_snapshots(self) -> None:
        stats = dataset_stats()
        self.assertTrue(stats["dataset_version"])
        self.assertIn("available_versions", stats)
        self.assertIn(_current_dataset_version(), stats["available_versions"])
        versions = list_snapshot_versions()
        self.assertIsInstance(versions, list)


if __name__ == "__main__":
    unittest.main()
