"""Пересчёт всех чисел, которыми проект хвастается в README.

Каждая строка таблицы «кто выбирает ходы» — это не легенда, а результат прогона,
и получить его должно быть можно одной командой:

    python tools/audit.py               полная таблица, 5 зёрен
    python tools/audit.py --seeds 8     точнее и дольше

Зачем зёрна. У линейной политики на каждом шаге много ходов с одинаковой оценкой,
и выбор между ними делается случайно. Один прогон поэтому ничего не доказывает:
на одной и той же лабе с одними и теми же весами выходило и 5 проверок из 16,
и 13 — разница только в том, как легли ничьи. Поэтому здесь всё меряется разбросом
по зёрнам, а в отчёт идут среднее и границы.

Результат печатается и кладётся в report/audit.md готовой markdown-таблицей.
"""
from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fly1c import brain as brain_mod            # noqa: E402
from fly1c.agent import OracleAgent             # noqa: E402
from fly1c.checker import run_checks            # noqa: E402
from fly1c.curriculum import BY_ID, LABS, TRACKS  # noqa: E402
from fly1c.actions import candidates            # noqa: E402
from fly1c.ir import OpError, World             # noqa: E402
from fly1c.ops import apply_op                  # noqa: E402
from fly1c.policy import GeneralFly             # noqa: E402
from fly1c.score import junk                    # noqa: E402

ALL = [lab["id"] for lab in LABS]
TRAIN = ["00_uchebnaya", "10_ms_lab1", "11_ms_lab2", "12_ms_lab3",
         "20_ds_lab1", "21_ds_lab2", "22_ds_lab3"]
TEST = ["13_ms_lab4", "14_ms_lab5", "23_ds_lab4", "24_ds_lab5", "25_ds_lab6"]
OUT = ROOT / "report" / "audit.md"


def start_world(lab_id: str) -> World:
    lab = BY_ID[lab_id]
    base = World()
    for prev in TRACKS[lab["track"]]:
        if prev == lab_id:
            break
        OracleAgent().run(base, BY_ID[prev])
    return base


def random_run(lab: dict, base: World, seed: int) -> dict:
    """Нижняя планка: ходы из того же пространства, но выбираются наугад.

    Без неё любая цифра политики бессмысленна — непонятно, что она обогнала.
    """
    rng = random.Random(seed)
    world = base
    checks = lab["checks"]
    base_junk = set(junk(base, checks))
    done: set[str] = set()
    for _ in range(60):
        results = run_checks(world, checks)
        if all(ok for ok, _ in results):
            break
        acts = [op for op in candidates(world, checks)
                if repr(sorted(op.items(), key=str)) not in done]
        if not acts:
            break
        op = rng.choice(acts)
        done.add(repr(sorted(op.items(), key=str)))
        try:
            apply_op(world, op)
        except OpError:
            pass
    results = run_checks(world, checks)
    return {"passed": sum(1 for ok, _ in results if ok),
            "checks": len(checks),
            "junk": len(junk(world, checks, base_junk))}


def untrained_solver(seed: int):
    """Честный базис: ТОТ ЖЕ цикл решения, но веса нулевые.

    Все оценки ходов равны, значит выбор каждый раз падает на случайный из
    допустимых. Это и есть контроль, с которым надо сравнивать обучение: он
    отличается от обученной политики ровно одним — политикой.

    Прежний базис (`random_run` ниже) был другим циклом: без отсева уже
    сделанных и уже провалившихся ходов, без предела топтания. Он давал 82.8 и
    делал обучение красивее, чем оно есть. Такой базис сравнивает не политики,
    а обвязку среды.
    """
    fly = GeneralFly(seed=seed)

    def run(lab, base, _seed):
        res = fly.solve(lab, base, greedy=True, learn=False)
        return {"passed": res["passed"], "checks": res["checks"], "junk": res["junk"]}
    return run


def train(mode: str, seed: int, epochs: int = 6) -> GeneralFly:
    fly = GeneralFly(seed=seed, mode=mode)
    best_w, best = fly.w.copy(), -1
    for _ in range(epochs):
        for lab_id in TRAIN:
            fly.solve(BY_ID[lab_id], start_world(lab_id))
        fly.epsilon = max(0.05, fly.epsilon * 0.88)
        got = sum(fly.solve(BY_ID[i], start_world(i), greedy=True, learn=False)["passed"]
                  for i in TRAIN)
        if got > best:
            best, best_w = got, fly.w.copy()
    fly.w = best_w
    return fly


def measure(make, seeds: int, labs: list[str]) -> dict:
    """Один жадный проход на каждое зерно — без «лучшей из трёх попыток»."""
    totals, junks = [], []
    total_checks = sum(len(BY_ID[i]["checks"]) for i in labs)
    for seed in range(seeds):
        solver = make(seed)
        got = dirt = 0
        for lab_id in labs:
            res = solver(BY_ID[lab_id], start_world(lab_id), seed)
            got += res["passed"]
            dirt += res["junk"]
        totals.append(got)
        junks.append(dirt)
    return {"mean": sum(totals) / len(totals), "min": min(totals), "max": max(totals),
            "total": total_checks, "junk": sum(junks) / len(junks)}


def policy_solver(mode: str, damage: str | None):
    def make(seed: int):
        if damage:
            b = brain_mod.FlyBrain()
            if damage == "shuffled":
                rng = np.random.default_rng(3)
                data = b.W.data.copy()
                rng.shuffle(data)
                b.W.data = data
            elif damage == "zeroed":
                b.W.data[:] = 0.0
            b._cache, b._base = {}, None
            brain_mod._BRAIN = b
        fly = train(mode, seed)

        def run(lab, base, _seed):
            res = fly.solve(lab, base, greedy=True, learn=False)
            return {"passed": res["passed"], "checks": res["checks"], "junk": res["junk"]}
        return run
    return make


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--quick", action="store_true", help="только случайный выбор и признаки")
    args = ap.parse_args()

    variants = [
        ("тот же цикл, выбор наугад", lambda: untrained_solver),
        ("обучение на признаках", lambda: policy_solver("features", None)),
    ]
    if not args.quick:
        variants += [
            ("для сравнения: более слабый цикл наугад", lambda: (lambda seed: (
                lambda lab, base, s: random_run(lab, base, s * 97 + seed)))),
            ("нисходящие нейроны (канон. схема)", lambda: policy_solver("descending", None)),
            ("нисходящие, связи перемешаны", lambda: policy_solver("descending", "shuffled")),
            ("нисходящие, связи обнулены", lambda: policy_solver("descending", "zeroed")),
            ("код грибовидного тела (коннектом)", lambda: policy_solver("connectome", None)),
            ("грибовидное, связи перемешаны", lambda: policy_solver("connectome", "shuffled")),
            ("грибовидное, связи обнулены", lambda: policy_solver("connectome", "zeroed")),
        ]

    print(f"зёрен на вариант: {args.seeds}; лабораторных: {len(ALL)}\n", flush=True)
    rows = []
    for title, build in variants:
        t0 = time.time()
        res = measure(build(), args.seeds, ALL)
        rows.append((title, res))
        print(f"  {title:36} {res['mean']:5.1f}/{res['total']} "
              f"({res['min']}–{res['max']}), мусор {res['junk']:.1f}, "
              f"{time.time() - t0:.0f} c", flush=True)
        brain_mod._BRAIN = None          # следующему варианту нужен целый мозг

    held = measure(policy_solver("features", None), args.seeds, TEST)
    print(f"\n  незнакомые лабы (обучения на них не было): "
          f"{held['mean']:.1f}/{held['total']} ({held['min']}–{held['max']})")

    lines = ["| кто выбирает ходы | проверок из %d | разброс | мусор |" % rows[0][1]["total"],
             "|---|---|---|---|"]
    for title, r in rows:
        lines.append(f"| {title} | {r['mean']:.1f} | {r['min']}–{r['max']} | {r['junk']:.1f} |")
    lines.append("")
    lines.append(f"Незнакомые лабораторные: **{held['mean']:.1f} из {held['total']}** "
                 f"(разброс {held['min']}–{held['max']}).")
    lines.append("")
    lines.append(f"Замер: {args.seeds} зёрен, один жадный проход на каждое, "
                 "без повторных попыток.")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nтаблица: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
