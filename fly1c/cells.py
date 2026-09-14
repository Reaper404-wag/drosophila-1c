"""Именованные типы клеток: LC4, DNp01, PAM, PPL1 — по имени, а не по индексу.

Канонические проекты на коннектоме устроены так: стимулируют **именованные**
сенсорные нейроны, гоняют LIF по настоящему графу и читают **именованные**
нисходящие (descending) нейроны. Всё, что между, — это провода из EM, их не учат.
Чтобы так делать, нужна адресация по типу клетки и по стороне тела, иначе
«стимулируем LC4 слева» написать невозможно.

Типы берутся из `consolidated_cell_types.csv.gz` (primary_type), сторона —
из `classification.csv.gz` (поле side). Оба файла качает tools/fetch_data.py.
"""
from __future__ import annotations

import csv
import gzip
from functools import lru_cache
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "connectome"

# Что за что отвечает — из литературы, ссылки в ATTRIBUTION.md.
# Вход: чем можно ткнуть муху.
SENSORY = {
    "looming": ["LC4", "LPLC2"],        # приближающийся объект, угроза
    "reward": ["PAM"],                  # дофамин награды
    "punish": ["PPL1"],                 # дофамин наказания
}
# Выход: что муха «говорит» телом.
DESCENDING = {
    "escape": ["DNp01"],                # гигантское волокно, прыжок
    "turn": ["DNa02"],                  # поворот, читается как L минус R
    "forward": ["DNa01", "DNg100"],     # вперёд
    "backward": ["MDN"],                # назад
    "reach": ["DNp09"],                 # остановка/захват
}


@lru_cache(maxsize=1)
def _tables() -> tuple[dict[int, str], dict[int, str]]:
    """root_id -> primary_type и root_id -> сторона тела."""
    types: dict[int, str] = {}
    with gzip.open(DATA / "consolidated_cell_types.csv.gz", "rt", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        next(reader)
        for row in reader:
            if len(row) > 1 and row[1]:
                types[int(row[0])] = row[1]
    sides: dict[int, str] = {}
    with gzip.open(DATA / "classification.csv.gz", "rt", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        col = header.index("side")
        for row in reader:
            if len(row) > col and row[col]:
                sides[int(row[0])] = row[col]
    return types, sides


@lru_cache(maxsize=256)
def _by_type(prefix: str, exact: bool) -> tuple[tuple[int, str], ...]:
    types, sides = _tables()
    out = []
    for root_id, name in types.items():
        hit = (name == prefix) if exact else name.startswith(prefix)
        if hit:
            out.append((root_id, sides.get(root_id, "")))
    return tuple(out)


def find(brain, name: str, side: str | None = None, exact: bool | None = None) -> np.ndarray:
    """Индексы нейронов этого типа в матрице мозга.

    name — имя типа («DNp01») или префикс семейства («PAM»); exact по умолчанию
    определяется сам: если в датасете есть точное совпадение, берём только его.
    side — 'left' / 'right' / None.
    """
    if exact is None:
        exact = bool(_by_type(name, True))
    rows = _by_type(name, exact)
    ids = brain.body_ids()
    pos = {int(b): i for i, b in enumerate(ids)}
    out = [pos[r] for r, s in rows
           if r in pos and (side is None or s == side)]
    return np.asarray(sorted(out), dtype=np.int32)


def group(brain, names: list[str], side: str | None = None) -> np.ndarray:
    parts = [find(brain, n, side) for n in names]
    parts = [p for p in parts if p.size]
    return np.unique(np.concatenate(parts)) if parts else np.zeros(0, dtype=np.int32)


def census(brain) -> dict[str, int]:
    """Сколько нашлось каждого типа — для проверки, что датасет тот и целый."""
    out: dict[str, int] = {}
    for table in (SENSORY, DESCENDING):
        for names in table.values():
            for n in names:
                out[n] = int(find(brain, n).size)
    return out
