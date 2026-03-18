from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import tempfile
from pathlib import Path

SKIP_FLAG_SUBSTRINGS = {
    "incertae_sedis",
    "unclassified",
    "environmental",
    "hidden",
    "major_rank_conflict",
    "extinct_inherited",
    "merged",
    "barren",
    "sibling_higher",
}


def parse_ott_line(line: str) -> tuple[int, int, str, str, str] | None:
    # OTT taxonomy.tsv format is pipe-delimited with tab padding, similar to NCBI dump.
    # Example: uid | parent_uid | name | rank | sourceinfo | uniqname | flags |
    parts = [p.strip() for p in line.rstrip("\n").split("|")]
    if len(parts) < 7:
        return None

    uid_raw, parent_raw, name, rank, _, _, flags = parts[:7]
    if not uid_raw or not parent_raw or not name:
        return None

    try:
        uid = int(uid_raw)
        parent_uid = int(parent_raw)
    except ValueError:
        return None

    return uid, parent_uid, name, rank or "no rank", flags


def load_nodes_to_sqlite(taxonomy_tsv: Path, db_path: Path, batch_size: int = 10000) -> None:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS nodes")
    cur.execute(
        """
        CREATE TABLE nodes (
          uid INTEGER PRIMARY KEY,
          parent_uid INTEGER,
          name TEXT,
          rank TEXT,
          flags TEXT
        )
        """
    )

    buffer: list[tuple[int, int, str, str, str]] = []
    with open(taxonomy_tsv, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            parsed = parse_ott_line(line)
            if not parsed:
                continue
            buffer.append(parsed)

            if len(buffer) >= batch_size:
                cur.executemany("INSERT OR REPLACE INTO nodes(uid, parent_uid, name, rank, flags) VALUES (?, ?, ?, ?, ?)", buffer)
                conn.commit()
                buffer.clear()

    if buffer:
        cur.executemany("INSERT OR REPLACE INTO nodes(uid, parent_uid, name, rank, flags) VALUES (?, ?, ?, ?, ?)", buffer)
        conn.commit()

    cur.execute("CREATE INDEX IF NOT EXISTS idx_nodes_parent ON nodes(parent_uid)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_nodes_rank ON nodes(rank)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_nodes_name ON nodes(name)")
    conn.commit()
    conn.close()


def resolve_metazoa_uid(conn: sqlite3.Connection, explicit_uid: int | None, explicit_name: str) -> tuple[int, str]:
    cur = conn.cursor()

    if explicit_uid is not None:
        row = cur.execute("SELECT uid, name FROM nodes WHERE uid = ?", (explicit_uid,)).fetchone()
        if not row:
            raise SystemExit(f"Could not find uid={explicit_uid} in taxonomy table.")
        return int(row[0]), str(row[1])

    candidate_names = [explicit_name, "Metazoa", "Animalia"]
    for name in candidate_names:
        row = cur.execute(
            """
            SELECT uid, name
            FROM nodes
            WHERE lower(name) = lower(?)
            ORDER BY CASE rank WHEN 'kingdom' THEN 0 WHEN 'phylum' THEN 1 ELSE 2 END, uid
            LIMIT 1
            """,
            (name,),
        ).fetchone()
        if row:
            return int(row[0]), str(row[1])

    raise SystemExit("Could not resolve Metazoa/Animalia node in taxonomy table.")


def fetch_subtree_rows(conn: sqlite3.Connection, root_uid: int, max_depth: int) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    rows = cur.execute(
        """
        WITH RECURSIVE subtree(uid, parent_uid, name, rank, flags, depth, path) AS (
          SELECT uid, parent_uid, name, rank, flags, 0 as depth, name as path
          FROM nodes
          WHERE uid = ?
          UNION ALL
          SELECT n.uid, n.parent_uid, n.name, n.rank, n.flags, subtree.depth + 1,
                 subtree.path || ' > ' || n.name
          FROM nodes n
          JOIN subtree ON n.parent_uid = subtree.uid
          WHERE subtree.depth < ?
        )
        SELECT uid, parent_uid, name, rank, flags, depth, path
        FROM subtree
        """,
        (root_uid, max_depth),
    ).fetchall()
    return rows


def should_skip(flags: str) -> bool:
    lowered = (flags or "").lower()
    return any(token in lowered for token in SKIP_FLAG_SUBSTRINGS)


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract Metazoa/Animalia phyla from OpenTree taxonomy dump.")
    parser.add_argument("--taxonomy-tsv", default="", help="Path to extracted OpenTree taxonomy.tsv.")
    parser.add_argument("--metadata", default="data/processed/opentree_release_metadata.json", help="Path to release metadata JSON.")
    parser.add_argument("--out-phyla", default="data/processed/opentree_metazoa_phyla.csv", help="Output phyla CSV path.")
    parser.add_argument("--out-subtree", default="data/interim/opentree/metazoa_subtree_nodes.csv", help="Optional subtree nodes CSV path.")
    parser.add_argument("--metazoa-name", default="Metazoa", help="Fallback name to resolve root node.")
    parser.add_argument("--metazoa-uid", type=int, default=None, help="Optional explicit root uid for Metazoa/Animalia.")
    parser.add_argument("--max-depth", type=int, default=80, help="Max recursion depth from Metazoa root.")
    args = parser.parse_args()

    taxonomy_tsv = Path(args.taxonomy_tsv) if args.taxonomy_tsv else None
    if taxonomy_tsv is None or not taxonomy_tsv.exists():
        meta_path = Path(args.metadata)
        if not meta_path.exists():
            raise SystemExit(f"Missing metadata file: {meta_path}")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        inferred = meta.get("extracted_files", {}).get("taxonomy.tsv")
        if not inferred:
            raise SystemExit("Metadata does not include extracted taxonomy.tsv path. Run fetch with --extract.")
        taxonomy_tsv = Path(inferred)

    if not taxonomy_tsv.exists():
        raise SystemExit(f"Missing taxonomy file: {taxonomy_tsv}")

    with tempfile.TemporaryDirectory(prefix="animaliaecon_ott_") as tmp:
        db_path = Path(tmp) / "ott.sqlite"
        load_nodes_to_sqlite(taxonomy_tsv, db_path)

        conn = sqlite3.connect(db_path)
        root_uid, root_name = resolve_metazoa_uid(conn, args.metazoa_uid, args.metazoa_name)
        subtree_rows = fetch_subtree_rows(conn, root_uid=root_uid, max_depth=args.max_depth)
        conn.close()

    subtree_out: list[dict[str, object]] = []
    phyla_out: list[dict[str, object]] = []
    seen_phylum_ids: set[int] = set()

    for row in subtree_rows:
        flags = str(row["flags"] or "")
        record = {
            "uid": int(row["uid"]),
            "parent_uid": int(row["parent_uid"]),
            "name": str(row["name"]),
            "rank": str(row["rank"]),
            "depth": int(row["depth"]),
            "flags": flags,
            "path": str(row["path"]),
        }
        subtree_out.append(record)

        if str(row["rank"]).lower() != "phylum":
            continue
        if should_skip(flags):
            continue

        uid = int(row["uid"])
        if uid in seen_phylum_ids:
            continue
        seen_phylum_ids.add(uid)

        phyla_out.append(
            {
                "phylum_uid": uid,
                "phylum_name": str(row["name"]),
                "depth_from_metazoa": int(row["depth"]),
                "flags": flags,
                "path_from_metazoa": str(row["path"]),
                "metazoa_uid": root_uid,
                "metazoa_name": root_name,
            }
        )

    phyla_out.sort(key=lambda r: str(r["phylum_name"]).lower())

    write_csv(
        Path(args.out_subtree),
        subtree_out,
        ["uid", "parent_uid", "name", "rank", "depth", "flags", "path"],
    )
    write_csv(
        Path(args.out_phyla),
        phyla_out,
        [
            "phylum_uid",
            "phylum_name",
            "depth_from_metazoa",
            "flags",
            "path_from_metazoa",
            "metazoa_uid",
            "metazoa_name",
        ],
    )

    print(f"Taxonomy source: {taxonomy_tsv}")
    print(f"Metazoa root: {root_name} (uid={root_uid})")
    print(f"Subtree nodes: {len(subtree_out)} -> {args.out_subtree}")
    print(f"Phyla extracted: {len(phyla_out)} -> {args.out_phyla}")


if __name__ == "__main__":
    main()
