"""Build data/state_shapes.json: one simple SVG outline per state, for the member spotlight cards.

The shapes come from us-atlas (states-albers-10m.json), which is built from the U.S. Census Bureau's cartographic
boundary files (public domain). Run once; the output is committed.

  npm install us-atlas@3
  python scripts/build_state_shapes.py node_modules/us-atlas/states-albers-10m.json

Each outline is scaled to fit a 100 by 100 box with its proportions kept, and small islands are dropped so the
silhouette stays readable at card size.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ui import STATES  # noqa: E402

OUT = ROOT / "data" / "state_shapes.json"
BOX = 100.0
MIN_SHARE = 0.002  # drop rings smaller than this share of the state's largest ring (tiny islands)


def decode_arcs(topo: dict) -> list[list[tuple[float, float]]]:
    (sx, sy), (tx, ty) = topo["transform"]["scale"], topo["transform"]["translate"]
    arcs = []
    for arc in topo["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in arc:
            x, y = x + dx, y + dy
            pts.append((x * sx + tx, y * sy + ty))
        arcs.append(pts)
    return arcs


def ring(arcs: list, ids: list[int]) -> list[tuple[float, float]]:
    pts: list[tuple[float, float]] = []
    for i in ids:
        a = arcs[i] if i >= 0 else arcs[~i][::-1]
        pts.extend(a if not pts else a[1:])
    return pts


def area(pts: list[tuple[float, float]]) -> float:
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]))) / 2


def outline(rings: list[list[tuple[float, float]]]) -> dict:
    biggest = max(area(r) for r in rings)
    rings = [r for r in rings if area(r) >= biggest * MIN_SHARE]
    xs = [x for r in rings for x, _ in r]
    ys = [y for r in rings for _, y in r]
    x0, y0 = min(xs), min(ys)
    k = BOX / max(max(xs) - x0, max(ys) - y0)
    w, h = (max(xs) - x0) * k, (max(ys) - y0) * k
    parts = []
    for r in rings:
        pts = []
        for x, y in r:
            p = (round((x - x0) * k, 1), round((y - y0) * k, 1))
            if not pts or p != pts[-1]:
                pts.append(p)
        if len(pts) >= 4:
            parts.append("M" + "L".join(f"{x:g},{y:g}" for x, y in pts) + "Z")
    return {"w": round(w, 1), "h": round(h, 1), "d": "".join(parts)}


def main() -> None:
    topo = json.loads(Path(sys.argv[1]).read_text())
    arcs = decode_arcs(topo)
    code = {name: c for c, name in STATES.items()}
    shapes = {}
    for g in topo["objects"]["states"]["geometries"]:
        polys = g["arcs"] if g["type"] == "MultiPolygon" else [g["arcs"]]
        rings = [ring(arcs, p[0]) for p in polys]  # outer rings only; holes don't matter at this size
        shapes[code.get(g["properties"]["name"], g["properties"]["name"])] = outline(rings)
    OUT.write_text(json.dumps(dict(sorted(shapes.items())), separators=(",", ":")) + "\n")
    print(f"{len(shapes)} states -> {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
