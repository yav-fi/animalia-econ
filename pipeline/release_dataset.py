from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

DEFAULT_FILES = [
    "data/processed/animaliaecon_taxon_priors.csv",
    "data/processed/animaliaecon_species_inherited.csv",
    "data/processed/animaliaecon_species_observed.csv",
    "data/processed/animaliaecon_evidence_species.csv",
    "data/processed/animaliaecon_evidence_taxon.csv",
    "data/processed/opentree_metazoa_phyla.csv",
    "data/processed/opentree_release_metadata.json",
    "schema/api/v1/index.json",
    "schema/api/v1/contract.response.json",
    "schema/api/v1/meta.response.json",
    "schema/api/v1/taxon_priors.response.json",
    "schema/api/v1/simulate.request.json",
    "schema/api/v1/simulate.response.json",
    "docs/assets/metazoa_phyla_snapshot.png",
    "docs/assets/metazoa_hierarchy_complex.png",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def append_changelog(changelog_path: Path, version: str, notes: str, files: list[dict[str, str]]) -> None:
    if not changelog_path.exists():
        changelog_path.parent.mkdir(parents=True, exist_ok=True)
        changelog_path.write_text("# Dataset Changelog\n\n", encoding="utf-8")

    date_str = dt.date.today().isoformat()
    lines = [
        f"## {version} - {date_str}",
        "",
        notes.strip() or "- Snapshot release",
        "",
        "Files:",
    ]
    lines.extend([f"- `{f['path']}` ({f['sha256'][:12]}..., {f['size_bytes']} bytes)" for f in files])
    lines.append("")

    with open(changelog_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines))


def maybe_tag(version: str, tag_prefix: str) -> None:
    tag = f"{tag_prefix}{version}"
    existing = subprocess.run(["git", "tag", "-l", tag], capture_output=True, text=True, check=True).stdout.strip()
    if existing:
        raise SystemExit(f"Git tag already exists: {tag}")

    subprocess.run(["git", "tag", "-a", tag, "-m", f"Dataset release {version}"], check=True)
    print(f"Created git tag: {tag}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create dataset snapshot release with checksums and changelog.")
    parser.add_argument("--version", required=True, help="Dataset version string (for example 0.3.0).")
    parser.add_argument("--snapshot-root", default="releases/datasets", help="Snapshot root directory.")
    parser.add_argument("--changelog", default="data/CHANGELOG.md", help="Dataset changelog path.")
    parser.add_argument("--notes", default="", help="Release notes text.")
    parser.add_argument("--notes-file", default="", help="Optional file containing release notes.")
    parser.add_argument("--files", default=",".join(DEFAULT_FILES), help="Comma-separated list of files to snapshot.")
    parser.add_argument("--force", action="store_true", help="Overwrite snapshot dir if it already exists.")
    parser.add_argument("--tag", action="store_true", help="Create annotated git tag for this release.")
    parser.add_argument("--tag-prefix", default="dataset-v", help="Tag prefix when --tag is used.")
    args = parser.parse_args()

    notes = args.notes
    if args.notes_file:
        notes = Path(args.notes_file).read_text(encoding="utf-8")

    release_dir = Path(args.snapshot_root) / args.version
    if release_dir.exists():
        if not args.force:
            raise SystemExit(f"Release directory exists: {release_dir}. Use --force to overwrite.")
        shutil.rmtree(release_dir)

    release_dir.mkdir(parents=True, exist_ok=True)

    source_files = [Path(p.strip()) for p in args.files.split(",") if p.strip()]

    file_records: list[dict[str, str]] = []
    missing: list[str] = []

    for src in source_files:
        if not src.exists():
            missing.append(str(src))
            continue

        dst = release_dir / src.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

        digest = sha256_file(dst)
        size = dst.stat().st_size
        file_records.append(
            {
                "path": src.as_posix(),
                "snapshot_path": dst.as_posix(),
                "sha256": digest,
                "size_bytes": str(size),
            }
        )

    if missing:
        raise SystemExit("Missing required release files:\n- " + "\n- ".join(missing))

    manifest = {
        "version": args.version,
        "released_at": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "snapshot_dir": release_dir.as_posix(),
        "files": file_records,
    }

    (release_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    with open(release_dir / "checksums.sha256", "w", encoding="utf-8") as f:
        for rec in file_records:
            f.write(f"{rec['sha256']}  {Path(rec['snapshot_path']).name}\n")

    append_changelog(Path(args.changelog), args.version, notes, file_records)

    if args.tag:
        maybe_tag(args.version, args.tag_prefix)

    print(f"Release snapshot created: {release_dir}")
    print(f"Files snapshotted: {len(file_records)}")
    print(f"Manifest: {release_dir / 'manifest.json'}")
    print(f"Checksums: {release_dir / 'checksums.sha256'}")


if __name__ == "__main__":
    main()
