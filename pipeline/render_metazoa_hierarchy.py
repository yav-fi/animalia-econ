from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
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


def should_skip(flags: str) -> bool:
    lowered = (flags or "").lower()
    return any(token in lowered for token in SKIP_FLAG_SUBSTRINGS)


def read_phyla(path: Path) -> list[str]:
    with open(path, "r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return [r["phylum_name"] for r in rows if r.get("phylum_name")]


def find_phylum_in_path(path_tokens: list[str], phylum_set: set[str]) -> str | None:
    for tok in path_tokens:
        if tok in phylum_set:
            return tok
    return None


def build_hierarchy(
    subtree_csv: Path,
    phyla_csv: Path,
    max_phyla: int,
    max_classes_per_phylum: int,
    max_orders_per_class: int,
) -> tuple[list[str], dict[str, list[str]], dict[tuple[str, str], list[str]]]:
    phyla = read_phyla(phyla_csv)
    phylum_set = set(phyla)

    class_to_phylum: dict[str, str] = {}
    classes_by_phylum: dict[str, set[str]] = defaultdict(set)

    # Pass 1: collect classes and parent phyla.
    with open(subtree_csv, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("rank", "").lower() != "class":
                continue
            if should_skip(row.get("flags", "")):
                continue

            tokens = [t.strip() for t in row.get("path", "").split(">") if t.strip()]
            phylum_name = find_phylum_in_path(tokens, phylum_set)
            class_name = row.get("name", "").strip()
            if not phylum_name or not class_name:
                continue

            key = f"{phylum_name}::{class_name}"
            class_to_phylum[key] = phylum_name
            classes_by_phylum[phylum_name].add(class_name)

    class_names_by_phylum = {p: set(v) for p, v in classes_by_phylum.items()}

    # Pass 2: collect orders under discovered classes.
    orders_by_class: dict[tuple[str, str], set[str]] = defaultdict(set)
    with open(subtree_csv, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("rank", "").lower() != "order":
                continue
            if should_skip(row.get("flags", "")):
                continue

            order_name = row.get("name", "").strip()
            tokens = [t.strip() for t in row.get("path", "").split(">") if t.strip()]
            if not order_name or not tokens:
                continue

            phylum_name = find_phylum_in_path(tokens, phylum_set)
            if not phylum_name:
                continue

            class_name = None
            possible_classes = class_names_by_phylum.get(phylum_name, set())
            for tok in reversed(tokens[:-1]):
                if tok in possible_classes:
                    class_name = tok
                    break

            if not class_name:
                continue

            orders_by_class[(phylum_name, class_name)].add(order_name)

    # Rank phyla by complexity score.
    phylum_scores: list[tuple[float, str]] = []
    for phylum in phyla:
        classes = classes_by_phylum.get(phylum, set())
        order_total = sum(len(orders_by_class.get((phylum, c), set())) for c in classes)
        score = len(classes) + 0.25 * order_total
        phylum_scores.append((score, phylum))

    phylum_scores.sort(reverse=True)
    selected_phyla = [p for _, p in phylum_scores[:max_phyla]]

    selected_classes: dict[str, list[str]] = {}
    selected_orders: dict[tuple[str, str], list[str]] = {}

    for phylum in selected_phyla:
        classes = list(classes_by_phylum.get(phylum, set()))
        classes.sort(key=lambda c: len(orders_by_class.get((phylum, c), set())), reverse=True)
        classes = classes[:max_classes_per_phylum]
        selected_classes[phylum] = classes

        for cls in classes:
            orders = sorted(list(orders_by_class.get((phylum, cls), set())))
            selected_orders[(phylum, cls)] = orders[:max_orders_per_class]

    return selected_phyla, selected_classes, selected_orders


def render_hierarchy(
    out_path: Path,
    selected_phyla: list[str],
    selected_classes: dict[str, list[str]],
    selected_orders: dict[tuple[str, str], list[str]],
    title: str,
) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise SystemExit("matplotlib is required to render hierarchy image.") from exc

    fig = plt.figure(figsize=(20, 20), dpi=180)
    ax = fig.add_subplot(111)
    ax.set_aspect("equal")
    ax.axis("off")

    center = (0.0, 0.0)
    r_phylum = 1.2
    r_class = 2.5
    r_order = 4.0

    # Complexity weights allocate wider arcs to denser phyla.
    weights = []
    for phylum in selected_phyla:
        cls_count = len(selected_classes.get(phylum, []))
        ord_count = sum(len(selected_orders.get((phylum, c), [])) for c in selected_classes.get(phylum, []))
        weights.append(max(1.0, cls_count + ord_count / 8.0))

    total_weight = sum(weights) if weights else 1.0

    ax.scatter([0], [0], s=500, color="#1d5f8c", zorder=4)

    start_angle = -math.pi / 2

    phylum_positions: dict[str, tuple[float, float, float, float]] = {}
    # name -> (theta_center, theta_start, theta_end, radius)
    for phylum, w in zip(selected_phyla, weights):
        span = 2 * math.pi * (w / total_weight)
        theta_start = start_angle
        theta_end = start_angle + span
        theta_center = (theta_start + theta_end) / 2.0

        x = r_phylum * math.cos(theta_center)
        y = r_phylum * math.sin(theta_center)
        ax.plot([0, x], [0, y], color="#8fb3c6", linewidth=1.1, alpha=0.8, zorder=1)
        ax.scatter([x], [y], s=90, color="#2e7d32", zorder=3)

        lx = (r_phylum + 0.25) * math.cos(theta_center)
        ly = (r_phylum + 0.25) * math.sin(theta_center)
        ax.text(lx, ly, phylum, fontsize=9.5, ha=("left" if lx >= 0 else "right"), va="center", color="#123")

        phylum_positions[phylum] = (theta_center, theta_start, theta_end, r_phylum)
        start_angle = theta_end

    # Classes.
    class_positions: dict[tuple[str, str], tuple[float, float, float]] = {}
    for phylum in selected_phyla:
        classes = selected_classes.get(phylum, [])
        if not classes:
            continue

        _, theta_start, theta_end, _ = phylum_positions[phylum]
        span = theta_end - theta_start
        for i, cls in enumerate(classes):
            theta = theta_start + span * ((i + 1) / (len(classes) + 1))
            px = r_phylum * math.cos((theta_start + theta_end) / 2)
            py = r_phylum * math.sin((theta_start + theta_end) / 2)
            x = r_class * math.cos(theta)
            y = r_class * math.sin(theta)

            ax.plot([px, x], [py, y], color="#9cc5df", linewidth=0.9, alpha=0.7, zorder=1)
            ax.scatter([x], [y], s=24, color="#8e44ad", zorder=2)

            # Label every other class for readability while keeping complexity high.
            if i % 2 == 0:
                ax.text(
                    (r_class + 0.16) * math.cos(theta),
                    (r_class + 0.16) * math.sin(theta),
                    cls,
                    fontsize=6.2,
                    ha=("left" if math.cos(theta) >= 0 else "right"),
                    va="center",
                    color="#1f1f1f",
                )

            class_positions[(phylum, cls)] = (theta, x, y)

    # Orders.
    for phylum in selected_phyla:
        for cls in selected_classes.get(phylum, []):
            orders = selected_orders.get((phylum, cls), [])
            if not orders:
                continue

            cls_theta, cx, cy = class_positions[(phylum, cls)]
            local_span = 0.18 + min(0.45, 0.01 * len(orders))
            start = cls_theta - local_span
            end = cls_theta + local_span

            for j, _order_name in enumerate(orders):
                theta = start + (end - start) * ((j + 1) / (len(orders) + 1))
                ox = r_order * math.cos(theta)
                oy = r_order * math.sin(theta)
                ax.plot([cx, ox], [cy, oy], color="#c9dbe7", linewidth=0.5, alpha=0.35, zorder=0)
                ax.scatter([ox], [oy], s=8, color="#f39c12", alpha=0.8, zorder=1)

    ax.set_title(title, fontsize=18, pad=28)
    subtitle = (
        f"Phyla={len(selected_phyla)} | "
        f"Classes={sum(len(v) for v in selected_classes.values())} | "
        f"Orders={sum(len(v) for v in selected_orders.values())}"
    )
    ax.text(0, -4.7, subtitle, ha="center", va="center", fontsize=11, color="#233")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a deeper Metazoa hierarchy chart (phylum/class/order).")
    parser.add_argument("--subtree", default="data/interim/opentree/metazoa_subtree_nodes.csv", help="Input Metazoa subtree CSV.")
    parser.add_argument("--phyla", default="data/processed/opentree_metazoa_phyla.csv", help="Input filtered phyla CSV.")
    parser.add_argument("--out", default="docs/assets/metazoa_hierarchy_complex.png", help="Output chart path.")
    parser.add_argument("--max-phyla", type=int, default=14, help="Maximum number of phyla to include.")
    parser.add_argument("--max-classes-per-phylum", type=int, default=18, help="Maximum classes per selected phylum.")
    parser.add_argument("--max-orders-per-class", type=int, default=12, help="Maximum orders per selected class.")
    parser.add_argument("--title", default="OpenTree Metazoa Hierarchy (Phylum-Class-Order)", help="Chart title.")
    args = parser.parse_args()

    selected_phyla, selected_classes, selected_orders = build_hierarchy(
        subtree_csv=Path(args.subtree),
        phyla_csv=Path(args.phyla),
        max_phyla=args.max_phyla,
        max_classes_per_phylum=args.max_classes_per_phylum,
        max_orders_per_class=args.max_orders_per_class,
    )

    render_hierarchy(
        out_path=Path(args.out),
        selected_phyla=selected_phyla,
        selected_classes=selected_classes,
        selected_orders=selected_orders,
        title=args.title,
    )

    print(
        "Rendered hierarchy chart -> "
        f"{args.out} (phyla={len(selected_phyla)}, "
        f"classes={sum(len(v) for v in selected_classes.values())}, "
        f"orders={sum(len(v) for v in selected_orders.values())})"
    )


if __name__ == "__main__":
    main()
