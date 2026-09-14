"""Канонический тест коннектома: looming слева -> гигантское волокно слева.

Это стандартная проверка калибровки для проектов на коннектоме дрозофилы.
Смысл: если стимулировать детекторы приближающегося объекта (LC4 и LPLC2) с
одной стороны головы, должно разрядиться гигантское волокно DNp01 **той же**
стороны — это команда прыжка, самая изученная цепь побега у мухи. Если не
стреляет или стреляет симметрично, значит сломана калибровка усиления, и всё
остальное в проекте считает шум.

    python tools/calibrate.py            проверить текущие настройки
    python tools/calibrate.py --sweep    перебрать усиление и рефрактерность

Проверка честная в том смысле, что цепь заранее не закладывалась: веса берутся
из карты синапсов, знак — из медиатора нейрона, и попадёт сигнал куда надо или
нет, решает сам датасет.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fly1c import cells                      # noqa: E402
from fly1c.brain import FlyBrain, get_brain   # noqa: E402

LOOM = ["LC4", "LPLC2"]
GF = "DNp01"


def probe(brain, steps: int = 20, drive: float = 2.0) -> dict:
    """Стимулируем каждую сторону по очереди и смотрим на обе стороны выхода."""
    ipsi = contra = 0.0
    weight_ipsi = weight_contra = 0.0
    for side, other in (("left", "right"), ("right", "left")):
        stim = cells.group(brain, LOOM, side=side)
        counts = brain.simulate(stim, steps=steps, drive=drive)
        ipsi += float(counts[cells.find(brain, GF, side)].sum())
        contra += float(counts[cells.find(brain, GF, other)].sum())
        weight_ipsi += float(brain.W[np.ix_(cells.find(brain, GF, side), stim)].sum())
        weight_contra += float(brain.W[np.ix_(cells.find(brain, GF, other), stim)].sum())
    quiet = brain.simulate(np.zeros(0, dtype=np.int32), steps=steps, drive=drive)
    return {
        "ipsi": ipsi, "contra": contra,
        "weight_ipsi": weight_ipsi, "weight_contra": weight_contra,
        "background": float(quiet[cells.find(brain, GF)].sum()),
        "spikes": float(counts.sum()),
    }


def passes(r: dict) -> bool:
    """Проходит, если сигнал идёт на свою сторону и заметно сильнее чужой."""
    return (r["weight_ipsi"] > 0 and r["ipsi"] > 0
            and r["background"] == 0 and r["ipsi"] >= 2 * r["contra"] + 1)


def report(r: dict) -> None:
    print(f"  вес   LC4+LPLC2 -> DNp01: своя сторона {r['weight_ipsi']:+.2f}, "
          f"чужая {r['weight_contra']:+.2f}")
    print(f"  спайки гигантского волокна: своя {r['ipsi']:.0f}, чужая {r['contra']:.0f}, "
          f"фон без стимула {r['background']:.0f}")
    print(f"  активность мозга: {r['spikes']:.0f} спайков за прогон")
    print("  ИТОГ:", "цепь побега работает" if passes(r) else "НЕ ПРОХОДИТ — калибровка сломана")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sweep", action="store_true", help="перебрать усиление и рефрактерность")
    args = ap.parse_args()

    if not args.sweep:
        brain = get_brain()
        print(f"усиление gain={brain.gain}, "
              f"рефрактерность {brain.refractory} тактов")
        r = probe(brain)
        report(r)
        return 0 if passes(r) else 1

    print(f"{'gain':>7} {'рефр':>5} | {'своя':>5} {'чужая':>6} {'фон':>4} | "
          f"{'спайков':>8} | итог")
    for gain in (2.0, 3.0, 5.0, 8.0, 12.0):
        for refractory in (0, 2, 4):
            brain = FlyBrain(gain=gain, refractory=refractory)
            r = probe(brain)
            print(f"{gain:7.1f} {refractory:5d} | {r['ipsi']:5.0f} {r['contra']:6.0f} "
                  f"{r['background']:4.0f} | {r['spikes']:8.0f} | "
                  f"{'ok' if passes(r) else '—'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
