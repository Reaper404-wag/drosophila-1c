"""Сборка данных для сцены: все лабораторные в одном файле, нейроны — один раз на всех.

Активность каждого кадра пакуется в битовую маску (base64), иначе страница со всеми
двенадцатью лабами весила бы мегабайты.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import numpy as np

from .brain import get_brain
from .curriculum import BY_ID, LABS, TRACKS
from . import trace

ROOT = Path(__file__).resolve().parent.parent

TRACK_TITLES = {
    "uchebnaya": "Учебная",
    "moi_sobytiya": "Мои события",
    "uchet_ds": "Учёт ДС",
}


def pack_bits(indices: list[int], n: int) -> str:
    bits = np.zeros(n, dtype=bool)
    if indices:
        bits[np.asarray(indices, dtype=np.int64)] = True
    return base64.b64encode(np.packbits(bits).tobytes()).decode("ascii")


def collect(episodes: int = 25, lab_ids: list[str] | None = None) -> dict[str, Any]:
    brain = get_brain()
    idx, x, y, kindv = trace._neuron_sample(brain, kc_n=900, bg=1500)
    n = int(idx.size)
    labs: list[dict[str, Any]] = []
    for lab_id in lab_ids or [lab["id"] for lab in LABS]:
        data = trace.record(lab_id, episodes=episodes, sample=(idx, x, y, kindv))
        frames = []
        for f in data["frames"]:
            frames.append(
                {
                    "op": f["op"],
                    "section": f["section"],
                    "obj": f["obj"],
                    "detail": f["detail"],
                    "ui": f["ui"],
                    "failed": f["failed"],
                    "mask": f["mask"],
                    "fire": pack_bits([i for i in f["fire"] if i < n], n),
                    "spikes": f["spikes"],
                    "kc": f["kc"],
                }
            )
        labs.append(
            {
                "id": lab_id,
                "title": data["title"],
                "track": data["track"],
                "trackTitle": TRACK_TITLES.get(data["track"], data["track"]),
                "checks": data["checks"],
                "solved_at": data["solved_at"],
                "frames": frames,
                "ops": len(BY_ID[lab_id]["ops"]),
            }
        )
    return {
        "brain": brain.summary(),
        "sections": trace.SECTIONS,
        "neurons": {
            "n": n,
            "x": [round(float(v), 4) for v in x],
            "y": [round(float(v), 4) for v in y],
            "k": [int(v) for v in kindv],
        },
        "labs": labs,
        "tracks": {t: TRACK_TITLES.get(t, t) for t in TRACKS},
    }


def write(out: Path, episodes: int = 25, lab_ids: list[str] | None = None) -> dict[str, Any]:
    data = collect(episodes=episodes, lab_ids=lab_ids)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return data
