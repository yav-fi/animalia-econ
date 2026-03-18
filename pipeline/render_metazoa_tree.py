from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path


def load_phyla(path: Path) -> list[str]:
    with open(path, "r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    names = sorted({r["phylum_name"].strip() for r in rows if r.get("phylum_name", "").strip()})
    return names


def render_radial(phyla: list[str], out_path: Path, title: str) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise SystemExit("matplotlib is required to render tree image. Install requirements first.") from exc

    if not phyla:
        raise SystemExit("No phyla found to render.")

    fig = plt.figure(figsize=(14, 14), dpi=150)
    ax = fig.add_subplot(111)
    ax.set_aspect("equal")
    ax.axis("off")

    center = (0.0, 0.0)
    radius = 1.0

    ax.scatter([center[0]], [center[1]], s=350, color="#2f6f63", zorder=3)
    ax.text(center[0], center[1], "Metazoa", color="white", ha="center", va="center", fontsize=11, weight="bold")

    n = len(phyla)
    for i, name in enumerate(phyla):
        theta = (2 * math.pi * i / n) - math.pi / 2
        x = radius * math.cos(theta)
        y = radius * math.sin(theta)

        ax.plot([center[0], x], [center[1], y], color="#97b5ad", linewidth=0.8, alpha=0.9, zorder=1)
        ax.scatter([x], [y], s=60, color="#1f4f8c", zorder=2)

        label_radius = 1.12
        lx = label_radius * math.cos(theta)
        ly = label_radius * math.sin(theta)
        ha = "left" if lx >= 0 else "right"
        ax.text(lx, ly, name, fontsize=8.2, ha=ha, va="center", color="#0e2230")

    ax.set_title(title, fontsize=16, pad=20)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a phylum-level Metazoa tree snapshot for README.")
    parser.add_argument("--phyla", default="data/processed/opentree_metazoa_phyla.csv", help="Input phyla CSV path.")
    parser.add_argument("--out", default="docs/assets/metazoa_phyla_snapshot.png", help="Output image path.")
    parser.add_argument("--title", default="OpenTree Metazoa Phyla (filtered)", help="Figure title.")
    args = parser.parse_args()

    phyla = load_phyla(Path(args.phyla))
    render_radial(phyla, Path(args.out), title=args.title)
    print(f"Rendered phyla snapshot with {len(phyla)} phyla -> {args.out}")


if __name__ == "__main__":
    main()
