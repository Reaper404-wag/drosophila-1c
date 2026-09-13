"""Оценка работы с ценой ошибки: за лишнее в конфигурации снимают баллы.

Важно проверять не имена, а места. Ловушка «реквизит Телефон у справочника События»
использует те же слова, что и правильный ход «Телефон у Друзей», — если сравнивать
словарь имён, подмена не видна. Поэтому требования разбираются в пары
(объект, имя): реквизит засчитан, только если задание просило его именно там.
"""
from __future__ import annotations

from typing import Any

from .ir import World


def required(checks: list[dict[str, Any]]) -> dict[str, set]:
    """Что именно задание просит — по местам, а не просто по словам."""
    req: dict[str, set] = {
        "catalog": set(), "document": set(), "register": set(),
        "report": set(), "subsystem": set(), "enum": set(),
        "attr": set(), "ts": set(), "dim": set(), "res": set(), "moves": set(),
    }
    for ch in checks:
        kind = ch["check"]
        if kind == "has_catalog":
            req["catalog"].add(ch["name"])
        elif kind in {"catalog_count", "folder_exists", "quick_choice",
                      "object_presentation", "has_predefined", "module_contains"}:
            if ch.get("catalog"):
                req["catalog"].add(ch["catalog"])
            if ch.get("document"):
                req["document"].add(ch["document"])
        elif kind in {"has_document", "document_count", "posted_count"}:
            req["document"].add(ch.get("name") or ch.get("document"))
        elif kind == "has_register":
            req["register"].add(ch["name"])
        elif kind in {"has_report", "report_run", "report_chart", "report_variant"}:
            req["report"].add(ch.get("name") if kind == "has_report" else ch.get("report"))
        elif kind == "has_subsystem":
            req["subsystem"].add(ch["name"])
        elif kind == "subsystem_order":
            req["subsystem"].update(ch.get("names", []))
        elif kind == "catalog_in_subsystem":
            req["catalog"].add(ch["catalog"])
            req["subsystem"].add(ch["subsystem"])
        elif kind == "has_enum":
            req["enum"].add(ch["name"])
        elif kind == "has_attribute":
            req["attr"].add((ch["object"], ch["name"]))
        elif kind == "has_tabular_section":
            req["ts"].add((ch["object"], ch["name"]))
        elif kind == "register_dimension":
            req["dim"].add((ch["register"], ch["name"]))
            req["register"].add(ch["register"])
        elif kind == "register_resource":
            req["res"].add((ch["register"], ch["name"]))
            req["register"].add(ch["register"])
        elif kind in {"document_moves", "register_movements"}:
            if ch.get("document"):
                req["moves"].add((ch["document"], ch["register"]))
            req["register"].add(ch["register"])
    req["catalog"].discard(None)
    req["document"].discard(None)
    req["report"].discard(None)
    return req


def junk(world: World, checks: list[dict[str, Any]],
         baseline: set[str] | None = None) -> list[str]:
    """Что появилось в конфигурации, хотя задание этого не просило.

    baseline — то, что уже было до начала работы: предыдущие лабораторные оставили
    объекты, которых нет в задании текущей, и за них спрашивать нельзя.
    """
    req = required(checks)
    cfg = world.config
    out: list[str] = []

    for name, cat in cfg.catalogs.items():
        path = f"Catalog.{name}"
        if name not in req["catalog"]:
            out.append(f"лишний справочник {name}")
            continue
        out += [f"{name}: лишний реквизит {a.name}" for a in cat.attributes
                if (path, a.name) not in req["attr"]]
        for ts in cat.tabular_sections:
            if (path, ts.name) not in req["ts"]:
                out.append(f"{name}: лишняя табличная часть {ts.name}")
                continue
            ts_path = f"{path}.TabularSection.{ts.name}"
            out += [f"{name}.{ts.name}: лишний реквизит {a.name}" for a in ts.attributes
                    if (ts_path, a.name) not in req["attr"]]

    for name, doc in cfg.documents.items():
        path = f"Document.{name}"
        if name not in req["document"]:
            out.append(f"лишний документ {name}")
            continue
        out += [f"{name}: лишний реквизит {a.name}" for a in doc.attributes
                if (path, a.name) not in req["attr"]]
        for ts in doc.tabular_sections:
            if (path, ts.name) not in req["ts"]:
                out.append(f"{name}: лишняя табличная часть {ts.name}")
        for reg, _ in doc.register_records:
            if (name, reg) not in req["moves"]:
                out.append(f"{name}: движения по чужому регистру {reg}")

    for name, reg in cfg.registers.items():
        if name not in req["register"]:
            out.append(f"лишний регистр {name}")
            continue
        out += [f"{name}: лишнее измерение {d.name}" for d in reg.dimensions
                if (name, d.name) not in req["dim"]]
        out += [f"{name}: лишний ресурс {r.name}" for r in reg.resources
                if (name, r.name) not in req["res"]]

    out += [f"лишний отчёт {n}" for n in cfg.reports if n not in req["report"]]
    out += [f"лишняя подсистема {n}" for n in cfg.subsystems if n not in req["subsystem"]]
    out += [f"лишнее перечисление {n}" for n in cfg.enums if n not in req["enum"]]

    if baseline:
        out = [x for x in out if x not in baseline]
    return out


PENALTY = 0.5


def score(world: World, checks: list[dict[str, Any]],
          baseline: set[str] | None = None) -> dict[str, Any]:
    """Итог: сошедшиеся проверки минус штраф за то лишнее, что добавила муха."""
    from .checker import run_checks

    passed = sum(1 for ok, _ in run_checks(world, checks) if ok)
    trash = junk(world, checks, baseline)
    return {
        "passed": passed,
        "checks": len(checks),
        "junk": len(trash),
        "junk_items": trash[:12],
        "score": round(passed - PENALTY * len(trash), 2),
    }
