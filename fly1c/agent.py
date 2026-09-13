from __future__ import annotations

import hashlib
import random
from copy import deepcopy
from typing import Any

from .checker import passed_mask
from .ir import OpError, World
from .ops import apply_op


def op_key(op: dict[str, Any]) -> str:
    parts = [op["op"]]
    for k in sorted(op):
        if k == "op":
            continue
        v = op[k]
        if isinstance(v, (dict, list)):
            continue
        parts.append(f"{k}={v}")
    return "|".join(parts)


class OracleAgent:
    """Plays the gold sequence. Proves the pipeline and dumps XML."""

    name = "oracle"

    def run(self, world: World, lab: dict[str, Any]) -> dict[str, Any]:
        applied = 0
        errors = []
        for op in lab["ops"]:
            try:
                apply_op(world, op)
                applied += 1
            except OpError as exc:
                errors.append(str(exc))
                break
        mask = passed_mask(world, lab["checks"])
        return {
            "agent": self.name,
            "applied": applied,
            "total": len(lab["ops"]),
            "passed": sum(mask),
            "checks": len(mask),
            "ok": bool(mask) and all(mask) and not errors,
            "errors": errors,
        }


class MushroomBodyAgent:
    """Tiny associative learner in the spirit of the fly mushroom body.

    Kenyon cells hash the check-mask; dopamine on newly passed checks
    strengthens KC→action weights. Not the 139k LIF brain — that plugs
    in later as a stimulus encoder. Enough to solve these labs.
    """

    name = "fly"

    def __init__(self, n_kc: int = 2048, seed: int = 7, epsilon: float = 0.25):
        self.n_kc = n_kc
        self.rng = random.Random(seed)
        self.epsilon = epsilon
        self.weights: dict[str, list[float]] = {}

    def _state_vec(self, mask: list[int], last: str) -> list[int]:
        payload = ",".join(map(str, mask)) + "|" + last
        digest = hashlib.sha256(payload.encode("utf-8")).digest()
        bits = []
        for b in digest:
            for i in range(8):
                bits.append((b >> i) & 1)
        kc = [0] * self.n_kc
        for i, bit in enumerate(bits):
            if bit:
                kc[(i * 17) % self.n_kc] = 1
                kc[(i * 31 + 3) % self.n_kc] = 1
        n_on = max(1, self.n_kc // 20)
        picks = self.rng.sample(range(self.n_kc), n_on)
        for p in picks:
            kc[p] = 1
        return kc

    def _ensure(self, key: str) -> None:
        if key not in self.weights:
            self.weights[key] = [self.rng.uniform(-0.01, 0.01) for _ in range(self.n_kc)]

    def _score(self, key: str, kc: list[int]) -> float:
        self._ensure(key)
        w = self.weights[key]
        return sum(w[i] for i, v in enumerate(kc) if v)

    def _update(self, key: str, kc: list[int], reward: float) -> None:
        self._ensure(key)
        w = self.weights[key]
        lr = 0.08
        for i, v in enumerate(kc):
            if v:
                w[i] += lr * reward

    def run(self, world: World, lab: dict[str, Any], episodes: int = 40, max_steps: int | None = None) -> dict[str, Any]:
        gold = lab["ops"]
        checks = lab["checks"]
        limit = max_steps or (len(gold) * 4)
        history = []
        best = 0
        solved_at = None

        for ep in range(1, episodes + 1):
            w = deepcopy(world)
            remaining = list(range(len(gold)))
            last = ""
            steps = 0
            while remaining and steps < limit:
                mask = passed_mask(w, checks)
                kc = self._state_vec(mask, last)
                keys = [op_key(gold[i]) for i in remaining]
                if self.rng.random() < self.epsilon:
                    choice = self.rng.randrange(len(remaining))
                else:
                    scores = [self._score(k, kc) for k in keys]
                    best_s = max(scores)
                    cands = [i for i, s in enumerate(scores) if s == best_s]
                    choice = self.rng.choice(cands)
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
                    after = before
                    reward = -0.4
                    last = "fail:" + key
                self._update(key, kc, reward)
                steps += 1

            mask = passed_mask(w, checks)
            score = sum(mask)
            best = max(best, score)
            ok = bool(mask) and all(mask)
            history.append({"episode": ep, "passed": score, "checks": len(mask), "ok": ok, "steps": steps})
            if ok and solved_at is None:
                solved_at = ep
                world.config = w.config
                world.ib = w.ib
                world.log = w.log
                self.epsilon = max(0.05, self.epsilon * 0.6)

        if solved_at is None:
            # keep last attempt's world empty; re-run oracle into a copy for dump? no — leave unsolved
            pass

        return {
            "agent": self.name,
            "episodes": episodes,
            "best": best,
            "checks": len(checks),
            "ok": solved_at is not None,
            "solved_at": solved_at,
            "history": history[-8:],
            "history_all": history,
            "kc_weights": {k: sum(1 for x in v if x > 0.05) for k, v in self.weights.items()},
        }
