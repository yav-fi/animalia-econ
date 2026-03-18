from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import tarfile
import urllib.request
from pathlib import Path

LATEST_URL = "https://tree.opentreeoflife.org/about/taxonomy-version"
FILES_BASE = "https://files.opentreeoflife.org/ott"


def now_iso() -> str:
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def resolve_latest_version() -> tuple[str, str]:
    req = urllib.request.Request(LATEST_URL, method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        final_url = resp.geturl()

    match = re.search(r"(ott\d+\.\d+\.\d+)", final_url)
    if not match:
        raise RuntimeError(f"Could not parse OTT version from redirected URL: {final_url}")

    version = match.group(1)
    archive_url = f"{FILES_BASE}/{version}/{version}.tgz"
    return version, archive_url


def download_archive(url: str, out_path: Path, force: bool = False) -> None:
    if out_path.exists() and not force:
        return

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=120) as resp, open(out_path, "wb") as f:
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)


def extract_members(archive_path: Path, extract_dir: Path, members: list[str], force: bool = False) -> dict[str, str]:
    extract_dir.mkdir(parents=True, exist_ok=True)
    extracted: dict[str, str] = {}

    with tarfile.open(archive_path, "r:gz") as tf:
        names = {m.name: m for m in tf.getmembers()}
        for member in members:
            target = extract_dir / member
            if target.exists() and not force:
                extracted[member] = str(target)
                continue

            internal_name = None
            # Archive entries are usually prefixed with version dir, e.g. ott3.7.3/taxonomy.tsv
            for name in names:
                if name.endswith(f"/{member}") or name == member:
                    internal_name = name
                    break

            if not internal_name:
                continue

            tf.extract(internal_name, path=extract_dir)
            candidate = extract_dir / internal_name
            target.parent.mkdir(parents=True, exist_ok=True)
            candidate.replace(target)

            # Clean up now-empty version directory if created.
            parent = candidate.parent
            if parent != extract_dir:
                try:
                    parent.rmdir()
                except OSError:
                    pass

            extracted[member] = str(target)

    return extracted


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch latest OpenTree taxonomy release and extract core files.")
    parser.add_argument("--raw-root", default="data/raw/opentree", help="Directory to store downloaded archives.")
    parser.add_argument("--interim-root", default="data/interim/opentree", help="Directory to store extracted files and metadata.")
    parser.add_argument("--metadata-out", default="data/processed/opentree_release_metadata.json", help="Path for release metadata JSON.")
    parser.add_argument("--download", action="store_true", help="Download archive (enabled in taxonomy-refresh target).")
    parser.add_argument("--extract", action="store_true", help="Extract taxonomy files from archive.")
    parser.add_argument("--force", action="store_true", help="Force re-download and re-extract.")
    args = parser.parse_args()

    version, archive_url = resolve_latest_version()

    archive_path = Path(args.raw_root) / version / f"{version}.tgz"
    extracted: dict[str, str] = {}

    if args.download:
        download_archive(archive_url, archive_path, force=args.force)

    if args.extract:
        if not archive_path.exists():
            raise SystemExit(f"Archive missing: {archive_path}. Run with --download first.")
        extracted = extract_members(
            archive_path=archive_path,
            extract_dir=Path(args.interim_root) / version,
            members=["taxonomy.tsv", "synonyms.tsv", "version.txt"],
            force=args.force,
        )

    meta = {
        "source": "Open Tree of Life",
        "resolved_from": LATEST_URL,
        "release_version": version,
        "archive_url": archive_url,
        "archive_path": str(archive_path),
        "downloaded": bool(args.download),
        "extracted": bool(args.extract),
        "extracted_files": extracted,
        "generated_at": now_iso(),
    }

    out = Path(args.metadata_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(f"Resolved release: {version}")
    print(f"Archive URL: {archive_url}")
    print(f"Metadata: {out}")
    if extracted:
        print("Extracted files:")
        for k, v in extracted.items():
            print(f"- {k}: {v}")


if __name__ == "__main__":
    main()
