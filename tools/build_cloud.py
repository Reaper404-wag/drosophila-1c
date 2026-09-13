"""Облако синапсов всего мозга с привязкой к нейропилям — для объёмной картинки.

Координаты синапсов лежат в synapse_coordinates.csv.gz, а к какому нейропилю относится
контакт — в connections.csv.gz. Соединяем их по паре (пресинапс, постсинапс) и красим
точки по отделам мозга: так на картинке проступают зрительные доли, антеннальные доли,
грибовидные тела и центральный комплекс, а не просто светящееся облако.

    python tools/build_cloud.py [--step 60]
"""
from __future__ import annotations

import argparse
import base64
import csv
import gzip
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "connectome"
OUT = ROOT / "assets" / "cloud.json"

# группы нейропилей: префикс имени -> (номер группы, как называется)
GROUPS = [
    ("ME", 0), ("LO", 0), ("LOP", 0), ("AME", 0),          # зрительные доли
    ("AL", 1),                                              # антеннальные доли
    ("MB", 2), ("CA", 2), ("PED", 2),                       # грибовидные тела
    ("FB", 3), ("EB", 3), ("PB", 3), ("NO", 3), ("AB", 3),  # центральный комплекс
    ("LH", 4),                                              # латеральный рог
    ("GNG", 5), ("PRW", 5), ("SAD", 5), ("AMMC", 5),        # подглоточная зона
]
GROUP_TITLES = [
    "зрительные доли", "антеннальные доли", "грибовидные тела",
    "центральный комплекс", "латеральный рог", "подглоточная зона", "остальной мозг",
]
OTHER = 6


def group_of(neuropil: str) -> int:
    name = (neuropil or "").upper()
    for prefix, gid in GROUPS:
        if name.startswith(prefix):
            return gid
    return OTHER


def connection_index() -> tuple[np.ndarray, np.ndarray]:
    """Пары (пре, пост) -> группа нейропиля, отсортированные для двоичного поиска."""
    pre, post, grp = [], [], []
    with gzip.open(DATA / "connections.csv.gz", "rt", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        next(reader)
        for row in reader:
            pre.append(int(row[0]))
            post.append(int(row[1]))
            grp.append(group_of(row[2]))
    pre = np.asarray(pre, dtype=np.int64)
    post = np.asarray(post, dtype=np.int64)
    grp = np.asarray(grp, dtype=np.uint8)
    # ключ пары: одно 64-битное число (id укладываются в 40 бит после сдвига базы)
    base = min(pre.min(), post.min())
    key = ((pre - base) << 24) ^ (post - base)
    order = np.argsort(key)
    return key[order], grp[order], base


def build(step: int) -> dict:
    keys, groups, base = connection_index()
    print(f"связей в индексе: {keys.size:,}".replace(",", " "), flush=True)

    xs: list[tuple[int, int, int]] = []
    gs: list[int] = []
    with gzip.open(DATA / "synapse_coordinates.csv.gz", "rt", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        next(reader)
        pre = post = 0
        for i, row in enumerate(reader):
            if row[0]:
                pre = int(row[0])
            if row[1]:
                post = int(row[1])
            if i % step:
                continue
            try:
                xs.append((int(row[2]), int(row[3]), int(row[4])))
            except (ValueError, IndexError):
                continue
            k = ((pre - base) << 24) ^ (post - base)
            j = np.searchsorted(keys, k)
            gs.append(int(groups[j]) if j < keys.size and keys[j] == k else OTHER)
            if i % 6_000_000 == 0 and i:
                print(f"  ...{i // 1_000_000} млн просмотрено, набрано {len(xs)}", flush=True)

    arr = np.asarray(xs, dtype=np.float64)
    lo, hi = arr.min(0), arr.max(0)
    span = np.maximum(hi - lo, 1.0)
    q = ((arr - lo) / span * 65535.0).astype(np.uint16)
    counts = np.bincount(np.asarray(gs, dtype=np.int64), minlength=OTHER + 1)
    for gid, title in enumerate(GROUP_TITLES):
        print(f"   {title:22} {counts[gid]:>8}")
    return {
        "n": int(arr.shape[0]),
        "lo": [round(float(v), 1) for v in lo],
        "span": [round(float(v), 1) for v in span],
        "titles": GROUP_TITLES,
        "p": base64.b64encode(q.tobytes()).decode("ascii"),
        "g": base64.b64encode(np.asarray(gs, dtype=np.uint8).tobytes()).decode("ascii"),
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", type=int, default=60, help="брать каждый N-й синапс")
    args = ap.parse_args()
    data = build(args.step)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    print(f"точек: {data['n']}   {OUT}  {OUT.stat().st_size // 1024} КБ")
    sys.exit(0)
