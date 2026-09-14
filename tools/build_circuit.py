"""Сборка данных для лаборатории коннектома: реальная анатомия отдельной цепи мухи.

Берём обонятельный путь и грибовидное тело — те самые нейроны, которыми муха решает
лабораторные, — и для каждого собираем:
  * облако точек из настоящих координат синапсов (это и есть форма нейрона),
  * список связей внутри цепи с числом синапсов и медиатором.

Дальше страница гоняет по этой цепи LIF прямо в браузере, поэтому напряжения и спайки
в инспекторе живые, а не записанные.

    python tools/build_circuit.py
"""
from __future__ import annotations

import base64
import csv
import gzip
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "connectome"
OUT = ROOT / "assets" / "circuit.json"

# сколько нейронов каждого типа берём в цепь и сколько точек оставляем на нейрон
GROUPS = {
    "olfactory": {"n": 120, "color": 0, "title": "обонятельные рецепторы"},
    "ALPN": {"n": 130, "color": 1, "title": "проекционные нейроны"},
    "Kenyon_Cell": {"n": 320, "color": 2, "title": "клетки Кеньона"},
    "MBON": {"n": 96, "color": 3, "title": "MBON (выход)"},
    "DAN": {"n": 90, "color": 4, "title": "дофаминовые"},
}
POINTS_PER_NEURON = 48
NT_SIGN = {"ACH": 1.0, "GABA": -1.0, "GLUT": -1.0, "DA": 0.15, "SER": 0.15, "OCT": 0.15}


def _class_index() -> dict[str, list[int]]:
    by_class: dict[str, list[int]] = {}
    with gzip.open(DATA / "classification.csv.gz", "rt", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            by_class.setdefault(row["class"], []).append(int(row["root_id"]))
    return by_class


def _neuron_nt() -> dict[int, str]:
    """Медиатор нейрона, а не отдельного синапса.

    Посинапсовые предсказания шумные: у холинергического LC4 больше половины
    синапсов размечены глутаматом, и знак связи выходил обратным. По закону
    Дейла медиатор у нейрона один — берём сводное предсказание FlyWire.
    """
    out: dict[int, str] = {}
    with gzip.open(DATA / "neurons.csv.gz", "rt", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            value = (row.get("nt_type") or "").strip()
            if value:
                out[int(row["root_id"])] = value
    return out


def _all_connections() -> list[tuple[int, int, int, str]]:
    out = []
    with gzip.open(DATA / "connections.csv.gz", "rt", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        next(reader)
        nt = _neuron_nt()
        for row in reader:
            pre = int(row[0])
            out.append((pre, int(row[1]), int(row[3]), nt.get(pre, row[4])))
    return out


def pick_neurons(seed: int = 5) -> tuple[dict[int, dict], dict[str, int], list]:
    """Цепь набирается по связям, а не наугад: рецепторы -> те, кто их слышит -> и так далее.

    Случайная выборка из классов рвёт путь — проекционные нейроны оказываются
    не теми, что слушают выбранные рецепторы, и до грибовидного тела ничего не доходит.
    """
    rng = np.random.default_rng(seed)
    by_class = _class_index()
    conns = _all_connections()
    totals = {c: len(by_class.get(c, [])) for c in GROUPS}

    orns = list(rng.choice(by_class["olfactory"], size=GROUPS["olfactory"]["n"], replace=False))
    orn_set = set(int(x) for x in orns)

    def best_targets(sources: set[int], cls: str, k: int) -> list[int]:
        pool = set(by_class.get(cls, []))
        score: dict[int, int] = {}
        for pre, post, syn, _ in conns:
            if pre in sources and post in pool:
                score[post] = score.get(post, 0) + syn
        ranked = sorted(score, key=score.get, reverse=True)[:k]
        return ranked

    pns = best_targets(orn_set, "ALPN", GROUPS["ALPN"]["n"])
    kcs = best_targets(set(pns), "Kenyon_Cell", GROUPS["Kenyon_Cell"]["n"])
    mbons = by_class.get("MBON", [])[: GROUPS["MBON"]["n"]]
    dans = best_targets(set(kcs) | set(mbons), "DAN", GROUPS["DAN"]["n"])
    if len(dans) < GROUPS["DAN"]["n"]:
        rest = [d for d in by_class.get("DAN", []) if d not in dans]
        dans += rest[: GROUPS["DAN"]["n"] - len(dans)]

    meta: dict[int, dict] = {}
    for cls, ids in (("olfactory", orns), ("ALPN", pns), ("Kenyon_Cell", kcs),
                     ("MBON", mbons), ("DAN", dans)):
        for rid in ids:
            meta[int(rid)] = {"cls": cls, "color": GROUPS[cls]["color"]}
    print("в цепи:", {c: sum(1 for m in meta.values() if m["cls"] == c) for c in GROUPS})
    return meta, totals, conns


def collect_points(ids: set[int]) -> dict[int, list[tuple[int, int, int]]]:
    """Координаты синапсов нейрона очерчивают его отростки — это и рисуем."""
    pts: dict[int, list[tuple[int, int, int]]] = {i: [] for i in ids}
    keep = {i: 0 for i in ids}
    path = DATA / "synapse_coordinates.csv.gz"
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        next(reader)
        pre = post = 0
        for n, row in enumerate(reader):
            # в файле повторяющиеся id опущены: пустая ячейка = та же пара, что выше
            if row[0]:
                pre = int(row[0])
            if row[1]:
                post = int(row[1])
            for rid in (pre, post):
                if rid in pts and len(pts[rid]) < POINTS_PER_NEURON * 6:
                    keep[rid] += 1
                    if keep[rid] % 3 == 0:  # прореживаем на лету
                        pts[rid].append((int(row[2]), int(row[3]), int(row[4])))
            if n % 4_000_000 == 0 and n:
                print(f"  ...{n // 1_000_000} млн синапсов просмотрено", flush=True)
    return pts


def collect_edges(meta: dict[int, dict], conns: list) -> list[tuple[int, int, int, float]]:
    index = {rid: i for i, rid in enumerate(meta)}
    edges: dict[tuple[int, int], list[float]] = {}
    for pre, post, syn, nt in conns:
        a = index.get(pre)
        b = index.get(post)
        if a is None or b is None:
            continue
        key = (a, b)
        if key in edges:
            edges[key][0] += syn
        else:
            edges[key] = [syn, NT_SIGN.get(nt, 0.3)]
    return [(a, b, int(v[0]), float(v[1])) for (a, b), v in edges.items()]


def build() -> dict:
    meta, totals, conns = pick_neurons()
    print(f"нейронов в цепи: {len(meta)} (из {sum(totals.values())} в этих классах)")
    print("собираю координаты синапсов…", flush=True)
    pts = collect_points(set(meta))
    print("собираю связи внутри цепи…", flush=True)
    edges = collect_edges(meta, conns)
    print(f"связей: {len(edges)}, синапсов: {sum(e[2] for e in edges)}")

    ids = list(meta)
    coords = []
    offsets = []
    for rid in ids:
        p = pts.get(rid) or []
        if len(p) > POINTS_PER_NEURON:
            step = len(p) / POINTS_PER_NEURON
            p = [p[int(i * step)] for i in range(POINTS_PER_NEURON)]
        offsets.append(len(p))
        coords.extend(p)
    arr = np.asarray(coords, dtype=np.float64) if coords else np.zeros((0, 3))
    lo = arr.min(0) if arr.size else np.zeros(3)
    span = np.maximum(arr.max(0) - lo, 1.0) if arr.size else np.ones(3)
    q = np.round((arr - lo) / span * 65535.0).astype(np.uint16) if arr.size else arr.astype(np.uint16)

    return {
        "source": "FlyWire v783 (CC-BY-4.0): synapse_coordinates + connections",
        "groups": [{"cls": c, "title": g["title"], "color": g["color"], "total": totals[c]}
                   for c, g in GROUPS.items()],
        "neurons": [{"id": str(rid), "cls": meta[rid]["cls"], "c": meta[rid]["color"],
                     "n": offsets[i]} for i, rid in enumerate(ids)],
        "edges": [[a, b, s, round(sign, 2)] for a, b, s, sign in edges],
        "synapses": int(sum(e[2] for e in edges)),
        "lo": [round(float(x), 1) for x in lo],
        "span": [round(float(x), 1) for x in span],
        "points": base64.b64encode(q.tobytes()).decode("ascii"),
    }


if __name__ == "__main__":
    data = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    total_pts = sum(n["n"] for n in data["neurons"])
    print(f"точек анатомии: {total_pts}")
    print(f"{OUT}  {OUT.stat().st_size // 1024} КБ")
    sys.exit(0)
