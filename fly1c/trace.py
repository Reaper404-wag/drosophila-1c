"""Запись прогона лабораторной: что горело в мозге и что при этом делалось в 1С."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import numpy as np

from .agent import OracleAgent
from .brain import get_brain
from .checker import run_checks
from .curriculum import BY_ID, TRACKS
from .ir import World

from .policy import train_policy

ROOT = Path(__file__).resolve().parent.parent

SECTIONS = [
    "Конфигурация",
    "Подсистемы",
    "Справочники",
    "Документы",
    "Перечисления",
    "РегистрыНакопления",
    "Отчёты",
]

_OWNER_SECTION = {
    "Catalog": "Справочники",
    "Document": "Документы",
    "Enum": "Перечисления",
    "AccumulationRegister": "РегистрыНакопления",
    "Report": "Отчёты",
}


def _owner(ref: str) -> tuple[str, str]:
    """'Catalog.Друзья' -> ('Справочники', 'Друзья')"""
    kind, _, name = ref.partition(".")
    return _OWNER_SECTION.get(kind, "Конфигурация"), name


def one_c_event(op: dict[str, Any]) -> dict[str, str]:
    """Во что операция мухи превращается в дереве метаданных и в логе конфигуратора."""
    kind = op["op"]
    name = op.get("name", "")
    if kind == "set_config_name":
        return {"section": "Конфигурация", "obj": name, "detail": "",
                "line": f"имя конфигурации = {name}"}
    if kind == "create_subsystem":
        return {"section": "Подсистемы", "obj": name, "detail": "",
                "line": f"создана подсистема {name}"}
    if kind == "create_catalog":
        return {"section": "Справочники", "obj": name, "detail": "",
                "line": f"создан справочник {name}"}
    if kind == "create_document":
        return {"section": "Документы", "obj": name, "detail": "",
                "line": f"создан документ {name}"}
    if kind == "copy_document":
        return {"section": "Документы", "obj": name, "detail": "",
                "line": f"документ {name} скопирован с {op.get('source', '')}"}
    if kind == "create_enum":
        return {"section": "Перечисления", "obj": name, "detail": "",
                "line": f"создано перечисление {name}"}
    if kind == "create_register":
        return {"section": "РегистрыНакопления", "obj": name, "detail": "",
                "line": f"создан регистр накопления {name}"}
    if kind == "create_report":
        return {"section": "Отчёты", "obj": name, "detail": "",
                "line": f"создан отчёт {name}"}
    if kind == "add_attribute":
        section, obj = _owner(op.get("object", ""))
        return {"section": section, "obj": obj, "detail": f"реквизит {name}",
                "line": f"{obj}: реквизит {name} ({op.get('type', '')})"}
    if kind == "create_tabular_section":
        section, obj = _owner(op.get("object", ""))
        return {"section": section, "obj": obj, "detail": f"ТЧ {name}",
                "line": f"{obj}: табличная часть {name}"}
    if kind == "add_dimension":
        reg = op.get("register", "")
        return {"section": "РегистрыНакопления", "obj": reg, "detail": f"измерение {name}",
                "line": f"{reg}: измерение {name}"}
    if kind == "add_resource":
        reg = op.get("register", "")
        return {"section": "РегистрыНакопления", "obj": reg, "detail": f"ресурс {name}",
                "line": f"{reg}: ресурс {name}"}
    if kind == "add_predefined":
        section, obj = _owner(op.get("object", ""))
        return {"section": section, "obj": obj, "detail": "предопределённые",
                "line": f"{obj}: предопределённые элементы"}
    if kind == "bind_register":
        doc, reg = op.get("document", ""), op.get("register", "")
        return {"section": "Документы", "obj": doc, "detail": f"движения → {reg}",
                "line": f"{doc}: движения по регистру {reg}"}
    if kind == "create_form":
        section, obj = _owner(op.get("object", ""))
        return {"section": section, "obj": obj, "detail": f"форма {name}",
                "line": f"{obj}: форма {name}"}
    if kind in {"write_form_module", "write_object_module"}:
        section, obj = _owner(op.get("object", ""))
        word = "модуль формы" if kind == "write_form_module" else "модуль объекта"
        return {"section": section, "obj": obj, "detail": word,
                "line": f"{obj}: написан {word}"}
    if kind == "fill_catalog":
        cat, n = op.get("catalog", ""), len(op.get("items", []))
        return {"section": "Справочники", "obj": cat, "detail": f"данные: {n}",
                "line": f"{cat}: введено элементов — {n}"}
    if kind == "fill_document":
        doc = op.get("document", "")
        n = op.get("count", len(op.get("docs", op.get("items", []))))
        return {"section": "Документы", "obj": doc, "detail": f"данные: {n}",
                "line": f"{doc}: введено документов — {n}"}
    if kind == "post_all":
        doc = op.get("document", "")
        return {"section": "Документы", "obj": doc, "detail": "проведены",
                "line": f"{doc}: документы проведены"}
    if kind == "run_report":
        rep = op.get("report", "")
        return {"section": "Отчёты", "obj": rep, "detail": "сформирован",
                "line": f"{rep}: отчёт сформирован"}
    if kind in {"set_synonym", "set_quick_choice", "set_object_presentation"}:
        section, obj = _owner(op.get("object", ""))
        return {"section": section, "obj": obj, "detail": "свойства",
                "line": f"{obj}: свойство {kind.replace('set_', '')}"}
    if kind == "set_subsystem_order":
        return {"section": "Подсистемы", "obj": "", "detail": "порядок",
                "line": "порядок подсистем в командном интерфейсе"}
    if kind == "set_desktop":
        return {"section": "Конфигурация", "obj": "Рабочий стол", "detail": "",
                "line": "настроен рабочий стол"}
    return {"section": "Конфигурация", "obj": name, "detail": kind, "line": kind}


KIND_BY_OP = {
    "create_subsystem": "subsystem", "create_catalog": "catalog",
    "create_document": "document", "copy_document": "document",
    "create_enum": "enum", "create_register": "register", "create_report": "report",
    "fill_catalog": "fill_catalog", "fill_document": "fill_document",
    "post_all": "post", "run_report": "run_report", "create_form": "form",
    "add_attribute": "attr", "create_tabular_section": "ts",
    "add_dimension": "dim", "add_resource": "res", "bind_register": "moves",
    "set_config_name": "config", "set_desktop": "desktop",
}


def _num(value) -> float:
    return float(value) if isinstance(value, (int, float)) else 0.0


def ui_payload(op: dict[str, Any], world: World) -> dict[str, Any]:
    """Что показать в окне 1С после этой операции: строки справочника, документы, отчёт."""
    kind = op["op"]
    ui: dict[str, Any] = {"kind": KIND_BY_OP.get(kind, "prop")}
    if kind == "fill_catalog":
        cat = op.get("catalog", "")
        ui["owner"] = cat
        ui["rows"] = [
            {"n": it.description, "f": bool(it.is_folder), "p": it.parent or ""}
            for it in world.ib.items if it.catalog == cat
        ][:14]
    elif kind in {"fill_document", "post_all"}:
        doc = op.get("document", "")
        ui["owner"] = doc
        rows = []
        for d in world.ib.documents:
            if d.document != doc:
                continue
            total = 0.0
            for lines in d.tabular.values():
                for line in lines:
                    for key, value in line.items():
                        if "умм" in key or "Цена" in key:
                            total += _num(value)
            rows.append({"n": d.number, "p": bool(d.posted), "s": round(total, 2)})
        ui["rows"] = rows[:14]
    elif kind == "run_report":
        rep = op.get("report", "")
        ui["owner"] = rep
        run = world.ib.report_runs[-1] if world.ib.report_runs else {}
        ui["rows"] = [{"n": k, "s": v} for k, v in list(run.items())[:8]] if isinstance(run, dict) else []
    elif kind == "add_attribute":
        ui["owner"] = op.get("object", "").split(".")[-1]
        ui["rows"] = [{"n": op.get("name", ""), "t": str(op.get("type", ""))}]
    return ui


def _neuron_sample(brain, kc_n: int = 1500, bg: int = 2500, seed: int = 3):
    """Нейроны для картинки: грибовидное тело, выходы, дофамин + фон мозга."""
    rng = np.random.default_rng(seed)
    kc = rng.choice(brain.pop.kenyon, size=min(kc_n, brain.pop.kenyon.size), replace=False)
    idx = np.unique(
        np.concatenate([kc, brain.pop.mbon, brain.pop.dan,
                        rng.choice(brain.n, size=bg, replace=False)])
    )
    pos = brain.positions()[idx]
    fin = np.isfinite(pos[:, 0]) & np.isfinite(pos[:, 1])
    idx, pos = idx[fin], pos[fin]
    x = (pos[:, 0] - pos[:, 0].min()) / np.ptp(pos[:, 0])
    y = (pos[:, 1] - pos[:, 1].min()) / np.ptp(pos[:, 1])
    kindv = np.zeros(idx.size, dtype=np.int8)
    kindv[np.isin(idx, brain.pop.kenyon)] = 1
    kindv[np.isin(idx, brain.pop.mbon)] = 2
    kindv[np.isin(idx, brain.pop.dan)] = 3
    return idx, x, y, kindv


def record(lab_id: str, episodes: int = 25, sample=None,
           policy_fly=None) -> dict[str, Any]:
    """Пишем НАСТОЯЩИЙ прогон решателя по шагам — то, что видно на сцене.

    Раньше здесь переигрывались эталонные операции методички, и муха выбирала лишь
    их порядок: промахнуться было негде, пространство состояло из одних правильных
    ходов. Теперь на сцену идёт та же политика и то же пространство ходов, на которых
    меряется качество в tools/train_fly.py, — с ловушками и ценой ошибки. Что муха
    выбрала, то и нарисовано, включая неудачные ходы.
    """
    lab = BY_ID[lab_id]
    brain = get_brain()

    # лаба продолжает конфигурацию предыдущих — доводим мир до её начала
    base = World()
    for prev in TRACKS[lab["track"]]:
        if prev == lab_id:
            break
        OracleAgent().run(base, BY_ID[prev])

    fly = policy_fly if policy_fly is not None else train_policy()

    idx, x, y, kindv = sample if sample is not None else _neuron_sample(brain)
    frames: list[dict[str, Any]] = []

    def on_step(op, failed, world, mask):
        # коннектом считается на состоянии задачи — это и есть панель активности
        key = "".join(map(str, mask)) + "|" + ("fail:" if failed else "") + op["op"]
        counts = brain.simulate(brain.odor(key))
        kc = brain.kc_response(key)
        act = counts[idx]
        event = one_c_event(op)
        frames.append({
            "op": event["line"],
            "section": event["section"],
            "obj": event["obj"],
            "detail": event["detail"],
            "ui": ui_payload(op, world) if not failed else {"kind": "fail"},
            "failed": failed,
            "mask": mask,
            "fire": [int(i) for i in np.flatnonzero(act > 0)],
            "spikes": int(counts.sum()),
            "kc": int((kc > 0).sum()),
        })

    result = fly.solve(lab, base, greedy=True, learn=False, on_step=on_step)
    w = result["world"]

    return {
        "lab": lab_id,
        "track": lab["track"],
        "title": lab["title"],
        "checks": [msg for _, msg in run_checks(w, lab["checks"])],
        "solved_at": None,
        "passed": result["passed"],
        "junk": result["junk"],
        "fails": result["fails"],
        "brain": brain.summary(),
        "sections": SECTIONS,
        "neurons": {
            "x": [round(float(v), 4) for v in x],
            "y": [round(float(v), 4) for v in y],
            "k": [int(v) for v in kindv],
        },
        "frames": frames,
    }


def write(lab_id: str, out: Path, episodes: int = 25) -> dict[str, Any]:
    data = record(lab_id, episodes=episodes)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return data
