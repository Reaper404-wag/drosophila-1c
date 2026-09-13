"""Обучение мухи работе с 1С и честная проверка на лабах, которых она не видела.

    python tools/train_fly.py            обучить и проверить
    python tools/train_fly.py --ablation те же замеры на сломанном мозге

Обучающие и проверочные лабораторные не пересекаются: если муха просто запоминает,
на проверочных она провалится.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from copy import deepcopy
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fly1c import brain as brain_mod  # noqa: E402
from fly1c.agent import OracleAgent  # noqa: E402
from fly1c.curriculum import BY_ID, LABS, TRACKS  # noqa: E402
from fly1c.ir import World  # noqa: E402
from fly1c.policy import GeneralFly  # noqa: E402

TRAIN = ["00_uchebnaya", "10_ms_lab1", "11_ms_lab2", "12_ms_lab3",
         "20_ds_lab1", "21_ds_lab2", "22_ds_lab3"]
TEST = ["13_ms_lab4", "14_ms_lab5", "23_ds_lab4", "24_ds_lab5", "25_ds_lab6"]
WEIGHTS = ROOT / "assets" / "fly_policy.npz"


def start_world(lab_id: str) -> World:
    lab = BY_ID[lab_id]
    base = World()
    for prev in TRACKS[lab["track"]]:
        if prev == lab_id:
            break
        OracleAgent().run(base, BY_ID[prev])
    return base


def evaluate(fly: GeneralFly, lab_ids: list[str], tries: int = 3) -> tuple[int, int, list[str]]:
    """Жадный проход плюс пара попыток с малым разбросом — студент тоже пробует не раз."""
    ok = total = 0
    lines = []
    saved_eps = fly.epsilon
    for lab_id in lab_ids:
        best = fly.solve(BY_ID[lab_id], start_world(lab_id), greedy=True, learn=False)
        first = best["passed"]
        fly.epsilon = 0.12
        for _ in range(tries - 1):
            res = fly.solve(BY_ID[lab_id], start_world(lab_id), learn=False)
            if res["passed"] > best["passed"]:
                best = res
        fly.epsilon = saved_eps
        ok += best["passed"]
        total += best["checks"]
        lines.append(f"    {lab_id:14} {best['passed']:>2}/{best['checks']:<2} "
                     f"(с первого захода {first}) шагов {best['steps']:>2}, "
                     f"промахов {best['fails']}")
    return ok, total, lines


def train(epochs: int = 6, seed: int = 11, quiet: bool = False) -> GeneralFly:
    """Учим и держим лучшие веса: линейная политика гуляет, последняя эпоха не лучшая."""
    fly = GeneralFly(seed=seed)
    best_w, best_score = fly.w.copy(), -1
    for epoch in range(1, epochs + 1):
        t0 = time.time()
        got = tot = 0
        for lab_id in TRAIN:
            res = fly.solve(BY_ID[lab_id], start_world(lab_id))
            got += res["passed"]
            tot += res["checks"]
        fly.epsilon = max(0.05, fly.epsilon * 0.88)
        # честная оценка эпохи — жадным проходом, без обучения
        score = sum(fly.solve(BY_ID[i], start_world(i), greedy=True, learn=False)["passed"]
                    for i in TRAIN)
        if score > best_score:
            best_score, best_w = score, fly.w.copy()
        if not quiet:
            print(f"  эпоха {epoch}: поиск {got}/{tot}, жадно {score}/{tot}, "
                  f"{time.time() - t0:.0f} c", flush=True)
    fly.w = best_w
    return fly


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--epochs", type=int, default=6)
    p.add_argument("--ablation", action="store_true")
    args = p.parse_args()

    if not args.ablation:
        print("обучение на:", ", ".join(TRAIN))
        print("проверка на: ", ", ".join(TEST), "(их муха не видит при обучении)\n")
        fly = train(args.epochs)
        tr_ok, tr_tot, tr_lines = evaluate(fly, TRAIN)
        te_ok, te_tot, te_lines = evaluate(fly, TEST)
        print("\nобучающие лабы:")
        print("\n".join(tr_lines))
        print(f"    итого {tr_ok}/{tr_tot}")
        print("\nпроверочные лабы (не видела):")
        print("\n".join(te_lines))
        print(f"    итого {te_ok}/{te_tot}")
        WEIGHTS.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(WEIGHTS, w=fly.w)
        print(f"\nвеса сохранены: {WEIGHTS}")
        return 0

    # абляция: то же обучение на испорченном мозге
    variants = {
        "настоящий коннектом": None,
        "связи перемешаны": "shuffled",
        "связи обнулены": "zeroed",
    }
    for title, kind in variants.items():
        b = brain_mod.FlyBrain()
        if kind == "shuffled":
            rng = np.random.default_rng(3)
            data = b.W.data.copy()
            rng.shuffle(data)
            b.W.data = data
        elif kind == "zeroed":
            b.W.data[:] = 0.0
        b._cache = {}
        b._base = None
        brain_mod._BRAIN = b
        fly = train(args.epochs, quiet=True)
        tr_ok, tr_tot, _ = evaluate(fly, TRAIN)
        te_ok, te_tot, _ = evaluate(fly, TEST)
        print(f"{title:22} обучающие {tr_ok}/{tr_tot}   проверочные {te_ok}/{te_tot}",
              flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
