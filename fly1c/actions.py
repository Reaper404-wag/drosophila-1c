"""Пространство действий: что вообще можно сделать в 1С, зная только задание.

Раньше муха выбирала из готового списка операций лабораторной — то есть из ответа.
Здесь кандидаты собираются из самого задания (списка проверок) и текущего состояния
конфигурации: задание говорит, ЧТО должно получиться, а как и в каком порядке —
задача мухи. Сюда же попадают заведомо негодные ходы: преждевременные, к чужому
объекту, повторные. Их надо научиться не выбирать.
"""
from __future__ import annotations

import json
from typing import Any

from .ir import World

FORM_KIND = {
    "ФормаСписка": "list",
    "ФормаЭлемента": "object",
    "ФормаДокумента": "object",
    "ФормаОтчета": "report",
}


def _type_to_op(spec: str | None) -> str:
    """В проверках тип пишется как String(20), в операциях — как String:20."""
    if not spec:
        return "String:50"
    s = spec.strip()
    if "(" in s and s.endswith(")"):
        head, _, tail = s[:-1].partition("(")
        return f"{head}:{tail}"
    return s


def _owner_kind(path: str) -> str:
    return path.split(".", 1)[0] if path else ""


def _subsystems_for(name: str, checks: list[dict]) -> list[str]:
    return [c["subsystem"] for c in checks
            if c["check"] == "catalog_in_subsystem" and c.get("catalog") == name]


def _ref_type_for(name: str, world: World) -> str:
    """Тип измерения регистра задание не диктует: подбираем ссылку на похожий справочник."""
    for cat in world.config.catalogs:
        if cat.startswith(name) or name.startswith(cat[:-1] or cat):
            return f"CatalogRef.{cat}"
    return "String:50"


def _folders(catalog: str, checks: list[dict]) -> list[dict]:
    return [{"description": c["name"], "is_folder": True} for c in checks
            if c["check"] == "folder_exists" and c.get("catalog") == catalog]


def _for_check(ch: dict, checks: list[dict], world: World) -> list[dict]:
    kind = ch["check"]
    cfg = world.config

    if kind == "config_name":
        return [{"op": "set_config_name", "name": ch["equals"]}]
    if kind == "has_subsystem":
        op = {"op": "create_subsystem", "name": ch["name"]}
        if ch.get("parent"):
            op["parent"] = ch["parent"]
        return [op]
    if kind == "subsystem_order":
        return [{"op": "set_subsystem_order", "names": list(ch["names"])}]
    if kind == "has_catalog":
        op = {"op": "create_catalog", "name": ch["name"],
              "subsystems": _subsystems_for(ch["name"], checks)}
        if "description_length" in ch:
            op["description_length"] = ch["description_length"]
        if ch.get("hierarchical"):
            op["hierarchical"] = True
        return [op]
    if kind == "catalog_in_subsystem":
        return [{"op": "create_catalog", "name": ch["catalog"],
                 "subsystems": [ch["subsystem"]]}]
    if kind == "has_document":
        return [{"op": "create_document", "name": ch["name"], "subsystems": []}]
    if kind == "has_enum":
        return [{"op": "create_enum", "name": ch["name"], "values": list(ch["values"])}]
    if kind == "has_register":
        return [{"op": "create_register", "name": ch["name"], "subsystems": []}]
    if kind == "has_report":
        return [{"op": "create_report", "name": ch["name"], "subsystems": [],
                 "query_table": ch.get("query_table"), "fields": [], "resources": []}]
    if kind == "report_chart":
        return [{"op": "create_report", "name": ch["report"], "subsystems": [],
                 "chart": True, "chart_type": "Bar", "fields": [], "resources": []}]
    if kind == "report_variant":
        return [{"op": "add_report_variant", "report": ch["report"], "name": ch["name"]}]
    if kind == "report_run":
        return [{"op": "run_report", "report": ch["report"]}]
    if kind == "has_tabular_section":
        return [{"op": "create_tabular_section", "object": ch["object"], "name": ch["name"]}]
    if kind == "has_attribute":
        return [{"op": "add_attribute", "object": ch["object"], "name": ch["name"],
                 "type": _type_to_op(ch.get("type"))}]
    if kind == "has_predefined":
        return [{"op": "add_predefined", "catalog": ch["catalog"], "name": n, "description": n}
                for n in ch["names"]]
    if kind == "register_dimension":
        return [{"op": "add_dimension", "register": ch["register"], "name": ch["name"],
                 "type": _ref_type_for(ch["name"], world)}]
    if kind == "register_resource":
        return [{"op": "add_resource", "register": ch["register"], "name": ch["name"],
                 "type": "Number:10,2"}]
    if kind == "document_moves":
        return [{"op": "bind_register", "document": ch["document"],
                 "register": ch["register"], "movement": ch.get("movement", "Receipt")}]
    if kind == "has_form":
        return [{"op": "create_form", "object": ch["object"], "name": ch["name"],
                 "kind": FORM_KIND.get(ch["name"], "object")}]
    if kind == "quick_choice":
        return [{"op": "set_quick_choice", "catalog": ch["catalog"]}]
    if kind == "object_presentation":
        return [{"op": "set_object_presentation", "catalog": ch["catalog"],
                 "presentation": ch["equals"]}]
    if kind == "synonym":
        return [{"op": "set_synonym", "object": ch["object"], "synonym": ch["equals"]}]
    if kind == "module_contains":
        code = ch["needle"]
        if ch.get("document"):
            return [{"op": "write_object_module", "document": ch["document"], "code": code}]
        obj = f"Catalog.{ch['catalog']}" if ch.get("catalog") else ch.get("object", "")
        return [{"op": "write_form_module", "object": obj, "code": code}]
    if kind == "catalog_count":
        catalog = ch["catalog"]
        items = _folders(catalog, checks)
        n = int(ch.get("min", 1))
        base = len(items)
        items += [{"description": f"{catalog} {i + 1}"} for i in range(max(0, n - base))]
        return [{"op": "fill_catalog", "catalog": catalog, "items": items}]
    if kind == "folder_exists":
        return [{"op": "fill_catalog", "catalog": ch["catalog"],
                 "items": [{"description": ch["name"], "is_folder": True}]}]
    if kind == "document_count":
        return [{"op": "fill_document", "document": ch["document"],
                 "count": int(ch.get("min", 1))}]
    if kind == "posted_count":
        return [{"op": "post_all", "document": ch["document"]}]
    if kind == "register_movements":
        reg = ch["register"]
        docs = [name for name, doc in cfg.documents.items()
                if any(r[0] == reg for r in doc.register_records)]
        return [{"op": "post_all", "document": d} for d in docs]
    if kind == "desktop_set":
        left = [f"Catalog.{n}" for n in list(cfg.catalogs)[:1]]
        right = [f"Report.{n}" for n in list(cfg.reports)[:1]]
        return [{"op": "set_desktop", "layout": {"template": "TwoColumnsVariableWidth",
                                                 "left": left, "right": right}}]
    return []


def _key(op: dict[str, Any]) -> str:
    return json.dumps(op, ensure_ascii=False, sort_keys=True)


def _implicit_objects(checks: list[dict], world: World) -> list[dict]:
    """Объекты, которые задание упоминает вскользь.

    В методичке часто нет отдельного пункта «создайте справочник Друзья» — есть
    «у Друзей должен быть реквизит Телефон». Значит, сам справочник тоже надо создать.
    """
    cfg = world.config
    want_cat: set[str] = set()
    want_doc: set[str] = set()
    want_reg: set[str] = set()
    want_rep: set[str] = set()

    def note(path: str) -> None:
        kind, _, rest = path.partition(".")
        name = rest.split(".", 1)[0]
        if not name:
            return
        if kind == "Catalog":
            want_cat.add(name)
        elif kind == "Document":
            want_doc.add(name)
        elif kind == "AccumulationRegister":
            want_reg.add(name)
        elif kind == "Report":
            want_rep.add(name)

    for ch in checks:
        if ch.get("object"):
            note(ch["object"])
        want_cat.update(x for k, x in ch.items() if k == "catalog")
        want_doc.update(x for k, x in ch.items() if k == "document")
        want_reg.update(x for k, x in ch.items() if k == "register")
        want_rep.update(x for k, x in ch.items() if k == "report")

    ops: list[dict] = []
    for name in sorted(want_cat - set(cfg.catalogs)):
        ops.append({"op": "create_catalog", "name": name,
                    "subsystems": _subsystems_for(name, checks)})
    for name in sorted(want_doc - set(cfg.documents)):
        ops.append({"op": "create_document", "name": name, "subsystems": []})
    for name in sorted(want_reg - set(cfg.registers)):
        ops.append({"op": "create_register", "name": name, "subsystems": []})
    for name in sorted(want_rep - set(cfg.reports)):
        ops.append({"op": "create_report", "name": name, "subsystems": [],
                    "fields": [], "resources": []})
    return ops


def candidates(world: World, checks: list[dict], with_traps: bool = True) -> list[dict]:
    """Все ходы, которые имеет смысл рассмотреть в этом состоянии (плюс ловушки)."""
    out: dict[str, dict] = {}
    for ch in checks:
        for op in _for_check(ch, checks, world):
            out.setdefault(_key(op), op)
    for op in _implicit_objects(checks, world):
        out.setdefault(_key(op), op)
    if with_traps:
        for op in _traps(list(out.values())):
            out.setdefault(_key(op), op)
    return list(out.values())


def _traps(ops: list[dict]) -> list[dict]:
    """Похожие, но негодные ходы: чужой объект, чужой регистр, чужое имя.

    Без них задача вырождается: любой ход из списка рано или поздно нужен,
    и выбирать по сути не из чего.
    """
    traps: list[dict] = []
    attrs = [o for o in ops if o["op"] == "add_attribute"]
    for a, b in zip(attrs, attrs[1:]):
        traps.append({**a, "object": b["object"]})
        traps.append({**a, "name": b["name"], "type": b["type"]})
    binds = [o for o in ops if o["op"] == "bind_register"]
    for a, b in zip(binds, binds[1:]):
        traps.append({**a, "document": b["document"]})
        traps.append({**a, "movement": "Expense" if a.get("movement") == "Receipt" else "Receipt"})
    fills = [o for o in ops if o["op"] == "fill_catalog"]
    for a, b in zip(fills, fills[1:]):
        traps.append({**a, "catalog": b["catalog"]})
    posts = [o for o in ops if o["op"] == "post_all"]
    docs = [o["name"] for o in ops if o["op"] == "create_document"]
    for p in posts[:3]:
        for d in docs[:2]:
            if d != p.get("document"):
                traps.append({"op": "post_all", "document": d})
    return traps
