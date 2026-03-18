from __future__ import annotations

import importlib
import os
import unittest


class TestApiHttp(unittest.TestCase):
    def _client(self, api_keys: str = "", rate_limit: str = "240"):
        os.environ["ANIMALIA_ECON_API_KEYS"] = api_keys
        os.environ["ANIMALIA_ECON_RATE_LIMIT_PER_MINUTE"] = rate_limit

        import api.main as main_mod

        importlib.reload(main_mod)
        from fastapi.testclient import TestClient

        return TestClient(main_mod.app)

    def test_auth_enforced_when_keys_configured(self) -> None:
        client = self._client(api_keys="k1", rate_limit="240")

        r1 = client.get("/v1/meta")
        self.assertEqual(r1.status_code, 401)

        r2 = client.get("/v1/meta", headers={"X-API-Key": "k1"})
        self.assertEqual(r2.status_code, 200)

    def test_rate_limit_enforced(self) -> None:
        client = self._client(api_keys="k2", rate_limit="2")

        headers = {"X-API-Key": "k2"}
        self.assertEqual(client.get("/v1/meta", headers=headers).status_code, 200)
        self.assertEqual(client.get("/v1/meta", headers=headers).status_code, 200)
        r3 = client.get("/v1/meta", headers=headers)
        self.assertEqual(r3.status_code, 429)
        self.assertIn("Retry-After", r3.headers)

    def test_contract_header_present(self) -> None:
        client = self._client(api_keys="", rate_limit="240")
        r = client.get("/v1/contract")
        self.assertEqual(r.status_code, 200)
        self.assertIn("X-API-Contract-Version", r.headers)

    def test_species_search_and_by_id(self) -> None:
        client = self._client(api_keys="", rate_limit="240")
        search = client.get("/v1/species/search", params={"q": "chimp", "limit": 5})
        self.assertEqual(search.status_code, 200)
        body = search.json()
        self.assertGreaterEqual(body["count"], 1)
        first_id = body["rows"][0]["id"]
        self.assertTrue(body["rows"][0]["dataset_version"])

        by_id = client.get(f"/v1/species/by-id/{first_id}")
        self.assertEqual(by_id.status_code, 200)
        row = by_id.json()["row"]
        self.assertEqual(row["species"], "Pan troglodytes")

    def test_species_random_bucket(self) -> None:
        client = self._client(api_keys="", rate_limit="240")
        r = client.get("/v1/species/random", params={"bucket": "bird"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("row", body)
        self.assertTrue(body["row"]["species"])

    def test_dataset_version_pinning_and_snapshot_endpoints(self) -> None:
        client = self._client(api_keys="", rate_limit="240")

        snaps = client.get("/v1/snapshots")
        self.assertEqual(snaps.status_code, 200)
        versions = snaps.json()["available_versions"]
        self.assertGreaterEqual(len(versions), 1)
        version = versions[0]

        pinned = client.get("/v1/meta", params={"dataset_version": version})
        self.assertEqual(pinned.status_code, 200)
        self.assertEqual(pinned.json()["stats"]["dataset_version"], version)

        snap_taxa = client.get(f"/v1/snapshots/{version}/taxon-priors", params={"rank": "class", "limit": 5})
        self.assertEqual(snap_taxa.status_code, 200)
        self.assertGreaterEqual(snap_taxa.json()["count"], 1)


if __name__ == "__main__":
    unittest.main()
