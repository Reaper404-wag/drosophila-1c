"""Прогон лабораторных с записью телеметрии: что муха выучила и что прошло."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .agent import MushroomBodyAgent, OracleAgent
from .fly_agent import ConnectomeAgent
from .checker import run_checks
from .curriculum import BY_ID, LABS, TRACKS
from .ir import World
from . import ones_real

ROOT = Path(__file__).resolve().parent.parent


AGENTS = {"fly": MushroomBodyAgent, "flywire": ConnectomeAgent}


def run_track(track: str, episodes: int = 30, seed: int = 7,
              agent: str = "flywire") -> list[dict[str, Any]]:
    """Муха проходит трек подряд, мир переносится из лабы в лабу — как в методичке."""
    world = World()
    fly = AGENTS[agent](seed=seed)
    out = []
    for lab_id in TRACKS[track]:
        lab = BY_ID[lab_id]
        t0 = time.time()
        res = fly.run(world, lab, episodes=episodes)
        fell_back = False
        if not res["ok"]:
            # муха не добила — доигрывает оракул, иначе следующая лаба стартует с пустого мира
            OracleAgent().run(world, lab)
            fell_back = True
        checks = run_checks(world, lab["checks"])
        out.append(
            {
                "id": lab_id,
                "track": track,
                "title": lab["title"],
                "n_ops": len(lab["ops"]),
                "n_checks": len(lab["checks"]),
                "solved_at": res.get("solved_at"),
                "episodes": episodes,
                "fell_back_to_oracle": fell_back,
                "seconds": round(time.time() - t0, 2),
                "agent": fly.name,
                "spikes": int(res.get("spikes", 0)),
                "curve": [h["passed"] for h in res.get("history_all", [])],
                "kc_weights": res.get("kc_weights", {}),
                "checks": [{"ok": ok, "msg": msg} for ok, msg in checks],
                "objects": snapshot(world),
            }
        )
    return out


def brain_map(brain, sample: int = 9000, seed: int = 3) -> dict[str, list]:
    """Срез мозга с активностью: координаты нейронов + сколько раз кто разрядился."""
    import numpy as np

    counts = brain.simulate(brain.odor("состояние лабораторной"), steps=20, drive=2.0)
    pos = brain.positions()
    rng = np.random.default_rng(seed)
    special = np.concatenate([brain.pop.kenyon, brain.pop.mbon, brain.pop.dan])
    rest = rng.choice(brain.n, size=sample, replace=False)
    idx = np.unique(np.concatenate([special, rest]))
    x, y = pos[idx, 0], pos[idx, 1]
    fin = np.isfinite(x) & np.isfinite(y)
    idx, x, y = idx[fin], x[fin], y[fin]
    act = counts[idx]
    kind = np.zeros(idx.size, dtype=np.int8)
    kind[np.isin(idx, brain.pop.kenyon)] = 1
    kind[np.isin(idx, brain.pop.mbon)] = 2
    kind[np.isin(idx, brain.pop.dan)] = 3
    return {
        "x": [round(float(v), 1) for v in (x - x.min()) / (x.max() - x.min()) * 1000],
        "y": [round(float(v), 1) for v in (y - y.min()) / (y.max() - y.min()) * 500],
        "a": [int(v) for v in np.minimum(act, 9)],
        "k": [int(v) for v in kind],
    }


def snapshot(world: World) -> dict[str, int]:
    cfg = world.config
    return {
        "подсистемы": len(cfg.subsystems),
        "справочники": len(cfg.catalogs),
        "документы": len(cfg.documents),
        "перечисления": len(cfg.enums),
        "регистры": len(cfg.registers),
        "отчёты": len(cfg.reports),
        "элементы": len(world.ib.items),
        "проведено": sum(1 for d in world.ib.documents if d.posted),
    }


def collect(episodes: int = 30, tracks: list[str] | None = None,
            agent: str = "flywire") -> dict[str, Any]:
    data: dict[str, Any] = {
        "generated": time.strftime("%Y-%m-%d %H:%M"),
        "platform": ones_real.status(),
        "agent": agent,
        "labs": [],
    }
    if agent == "flywire":
        from .brain import get_brain

        brain = get_brain()
        data["brain"] = brain.summary()
        data["brain_map"] = brain_map(brain)
        data["brain_activity"] = brain.activity("состояние лабораторной", steps=20)
    for track in tracks or list(TRACKS):
        data["labs"] += run_track(track, episodes=episodes, agent=agent)
    data["total_checks"] = sum(l["n_checks"] for l in data["labs"])
    data["passed_checks"] = sum(sum(1 for c in l["checks"] if c["ok"]) for l in data["labs"])
    data["solved_by_fly"] = sum(1 for l in data["labs"] if not l["fell_back_to_oracle"])
    return data


def write(path: Path, episodes: int = 30, agent: str = "flywire") -> dict[str, Any]:
    data = collect(episodes=episodes, agent=agent)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return data
