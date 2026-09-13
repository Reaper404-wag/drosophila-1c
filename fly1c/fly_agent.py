"""Агент, которым рулит настоящий коннектом мухи.

Состояние лабораторной подаётся мухе как запах: ток в обонятельные рецепторы.
Дальше считает реальная проводка FlyWire — ORN → проекционные нейроны → грибовидное тело.
Спайки клеток Кеньона и есть признаки, по которым выбирается следующая операция в 1С.

Пластичность ровно там, где она у живой мухи: синапсы KC → выход (MBON),
подкрепление дофаминовое — награда за каждую новую сошедшуюся проверку.
"""
from __future__ import annotations

import random
from copy import deepcopy
from typing import Any

import numpy as np

from .agent import op_key
from .brain import get_brain
from .checker import passed_mask
from .ir import OpError, World
from .ops import apply_op


def full_op_key(op: dict[str, Any], idx: int) -> str:
    """Ключ действия: имя операции + её позиция в задании, чтобы два одинаковых
    по названию шага (например, два run_report) не делили один синапс."""
    return f"{op_key(op)}#{idx}"


class ConnectomeAgent:
    """Тот же интерфейс, что у OracleAgent, но решает мозг дрозофилы."""

    name = "flywire"

    def __init__(self, seed: int = 7, epsilon: float = 0.25, lr: float = 0.08,
                 steps: int = 20, drive: float = 2.0):
        self.brain = get_brain()
        self.rng = random.Random(seed)
        self.epsilon = epsilon
        self.lr = lr
        self.steps = steps
        self.drive = drive
        self.n_kc = int(self.brain.pop.kenyon.size)
        self.weights: dict[str, np.ndarray] = {}
        self.spikes_seen = 0.0

    # --- KC → действие --------------------------------------------------
    def _w(self, key: str) -> np.ndarray:
        w = self.weights.get(key)
        if w is None:
            w = np.zeros(self.n_kc, dtype=np.float32)
            self.weights[key] = w
        return w

    def _kc(self, mask: list[int], last: str) -> np.ndarray:
        key = "".join(map(str, mask)) + "|" + last
        kc = self.brain.kc_response(key, steps=self.steps)
        self.spikes_seen += float(kc.sum())
        return kc

    def run(self, world: World, lab: dict[str, Any], episodes: int = 40,
            max_steps: int | None = None) -> dict[str, Any]:
        gold = lab["ops"]
        checks = lab["checks"]
        limit = max_steps or (len(gold) * 4)
        history: list[dict[str, Any]] = []
        best = 0
        solved_at = None
        # все эпизоды стартуют из одного и того же состояния мира;
        # решённый мир запоминается отдельно и отдаётся наружу в конце
        start = deepcopy(world)
        solved_world = None

        for ep in range(1, episodes + 1):
            w = deepcopy(start)
            remaining = list(range(len(gold)))
            last = ""
            steps = 0
            while remaining and steps < limit:
                mask = passed_mask(w, checks)
                kc = self._kc(mask, last)
                keys = [full_op_key(gold[i], i) for i in remaining]
                if self.rng.random() < self.epsilon:
                    choice = self.rng.randrange(len(remaining))
                else:
                    scores = [float(self._w(k) @ kc) for k in keys]
                    top = max(scores)
                    choice = self.rng.choice([i for i, s in enumerate(scores) if s == top])
                idx = remaining[choice]
                key = keys[choice]
                before = sum(mask)
                try:
                    apply_op(w, gold[idx])
                    remaining.pop(choice)
                    last = key
                    after = sum(passed_mask(w, checks))
                    reward = (after - before) + 0.05
                except OpError:
                    reward = -0.4
                    last = "fail:" + key
                # дофамин: подкрепляются только те KC, что сейчас разрядились
                active = kc > 0
                self._w(key)[active] += self.lr * reward * kc[active]
                steps += 1

            mask = passed_mask(w, checks)
            score = sum(mask)
            best = max(best, score)
            ok = bool(mask) and all(mask)
            history.append({"episode": ep, "passed": score, "checks": len(mask), "ok": ok,
                            "steps": steps})
            if ok and solved_at is None:
                solved_at = ep
                solved_world = w
            if ok:
                # решение найдено — постепенно перестаём случайничать и закрепляем порядок
                self.epsilon = max(0.02, self.epsilon * 0.85)

        if solved_world is not None:
            world.config = solved_world.config
            world.ib = solved_world.ib
            world.log = solved_world.log

        return {
            "agent": self.name,
            "episodes": episodes,
            "best": best,
            "checks": len(checks),
            "ok": solved_at is not None,
            "solved_at": solved_at,
            "history": history[-8:],
            "history_all": history,
            "kc_weights": {k: int((v > 0.05).sum()) for k, v in self.weights.items()},
            "spikes": self.spikes_seen,
            "brain": self.brain.summary(),
        }
