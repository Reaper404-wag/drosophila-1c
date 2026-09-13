from __future__ import annotations

from typing import Any

from .ir import World


def run_checks(world: World, checks: list[dict[str, Any]]) -> list[tuple[bool, str]]:
    results = []
    for chk in checks:
        try:
            ok, msg = _one(world, chk)
        except (AttributeError, KeyError, TypeError, IndexError) as exc:
            # проверки приходят и из разбора методички — кривую не считаем аварией
            ok, msg = False, f"{chk.get('check', '?')}: неприменимая проверка ({exc})"
        results.append((ok, msg))
    return results


def passed_mask(world: World, checks: list[dict[str, Any]]) -> list[int]:
    return [1 if ok else 0 for ok, _ in run_checks(world, checks)]


def all_passed(world: World, checks: list[dict[str, Any]]) -> bool:
    return all(ok for ok, _ in run_checks(world, checks))


def _one(world: World, chk: dict[str, Any]) -> tuple[bool, str]:
    cfg, ib = world.config, world.ib
    kind = chk["check"]
    if kind == "config_name":
        ok = cfg.name == chk["equals"]
        return ok, f"имя конфигурации {cfg.name!r} == {chk['equals']!r}"
    if kind == "has_subsystem":
        ok = chk["name"] in cfg.subsystems
        if ok and chk.get("parent") is not None:
            ok = cfg.subsystems[chk["name"]].parent == chk["parent"]
        if ok and chk.get("picture"):
            ok = cfg.subsystems[chk["name"]].picture
        return ok, f"подсистема {chk['name']}"
    if kind == "subsystem_order":
        ok = cfg.subsystem_order[: len(chk["names"])] == chk["names"]
        return ok, f"порядок подсистем {cfg.subsystem_order}"
    if kind == "has_catalog":
        cat = cfg.catalogs.get(chk["name"])
        if cat is None:
            return False, f"нет справочника {chk['name']}"
        if "description_length" in chk and cat.description_length != chk["description_length"]:
            return False, f"{chk['name']} длина наименования {cat.description_length}"
        if chk.get("hierarchical") and not cat.hierarchical:
            return False, f"{chk['name']} не иерархический"
        return True, f"справочник {chk['name']}"
    if kind == "catalog_in_subsystem":
        sub = cfg.subsystems.get(chk["subsystem"])
        if sub is None:
            return False, f"нет подсистемы {chk['subsystem']}"
        ok = f"Catalog.{chk['catalog']}" in sub.content
        return ok, f"{chk['catalog']} в {chk['subsystem']}"
    if kind == "has_tabular_section":
        owner = _owner(cfg, chk["object"])
        if owner is None:
            return False, f"нет {chk['object']}"
        ok = any(ts.name == chk["name"] for ts in owner.tabular_sections)
        return ok, f"ТЧ {chk['name']} у {chk['object']}"
    if kind == "has_attribute":
        owner = _owner(cfg, chk["object"])
        if owner is None:
            return False, f"нет {chk['object']}"
        attrs = getattr(owner, "attributes", [])
        found = next((a for a in attrs if a.name == chk["name"]), None)
        if found is None:
            return False, f"нет реквизита {chk['name']}"
        if "type" in chk and found.type.key() != chk["type"] and found.type.kind != chk["type"]:
            want = chk["type"]
            if found.type.key() != want and not found.type.key().startswith(str(want)):
                return False, f"{chk['name']} тип {found.type.key()} != {want}"
        return True, f"реквизит {chk['name']}"
    if kind == "has_predefined":
        cat = cfg.catalogs.get(chk["catalog"])
        if cat is None:
            return False, f"нет {chk['catalog']}"
        have = {p["name"] for p in cat.predefined}
        need = set(chk["names"])
        ok = need <= have
        return ok, f"предопределённые {need} ⊆ {have}"
    if kind == "has_enum":
        en = cfg.enums.get(chk["name"])
        if en is None:
            return False, f"нет перечисления {chk['name']}"
        if "values" in chk and en.values != chk["values"]:
            return False, f"значения {en.values}"
        return True, f"перечисление {chk['name']}"
    if kind == "has_document":
        ok = chk["name"] in cfg.documents
        return ok, f"документ {chk['name']}"
    if kind == "has_register":
        reg = cfg.registers.get(chk["name"])
        if reg is None:
            return False, f"нет регистра {chk['name']}"
        return True, f"регистр {chk['name']}"
    if kind == "register_dimension":
        reg = cfg.registers.get(chk["register"])
        if reg is None:
            return False, f"нет регистра {chk['register']}"
        ok = any(d.name == chk["name"] for d in reg.dimensions)
        return ok, f"измерение {chk['name']}"
    if kind == "register_resource":
        reg = cfg.registers.get(chk["register"])
        if reg is None:
            return False, f"нет регистра {chk['register']}"
        ok = any(r.name == chk["name"] for r in reg.resources)
        return ok, f"ресурс {chk['name']}"
    if kind == "document_moves":
        doc = cfg.documents.get(chk["document"])
        if doc is None:
            return False, f"нет документа {chk['document']}"
        ok = any(r == chk["register"] and m == chk["movement"] for r, m in doc.register_records)
        return ok, f"{chk['document']} → {chk['register']} {chk['movement']}"
    if kind == "module_contains":
        doc = cfg.documents.get(chk.get("document", ""))
        text = ""
        if doc is not None:
            text = doc.object_module + "\n" + doc.form_module
        cat = cfg.catalogs.get(chk.get("catalog", ""))
        if cat is not None:
            text += "\n".join(f.module for f in cat.forms)
        ok = chk["needle"] in text
        return ok, f"модуль содержит {chk['needle']!r}"
    if kind == "has_report":
        ok = chk["name"] in cfg.reports
        return ok, f"отчёт {chk['name']}"
    if kind == "report_chart":
        rep = cfg.reports.get(chk["report"])
        if rep is None:
            return False, f"нет отчёта {chk['report']}"
        return rep.chart, f"диаграмма у {chk['report']}"
    if kind == "report_variant":
        rep = cfg.reports.get(chk["report"])
        if rep is None:
            return False, f"нет отчёта {chk['report']}"
        ok = chk["name"] in rep.variants
        return ok, f"вариант {chk['name']}"
    if kind == "has_form":
        owner = _owner(cfg, chk["object"])
        if owner is None:
            return False, f"нет {chk['object']}"
        ok = any(f.name == chk["name"] for f in owner.forms)
        return ok, f"форма {chk['name']}"
    if kind == "quick_choice":
        cat = cfg.catalogs.get(chk["catalog"])
        return bool(cat and cat.quick_choice), f"быстрый выбор {chk['catalog']}"
    if kind == "object_presentation":
        cat = cfg.catalogs.get(chk["catalog"])
        ok = bool(cat and cat.object_presentation == chk["equals"])
        return ok, f"представление {chk['catalog']}"
    if kind == "synonym":
        path = chk["object"]
        cat = cfg.catalogs.get(path.split(".")[1] if "." in path else "")
        if cat and path.endswith("Description"):
            ok = cat.description_synonym == chk["equals"]
            return ok, f"синоним {chk['equals']}"
        return False, "синоним не найден"
    if kind == "catalog_count":
        n = sum(1 for x in ib.items if x.catalog == chk["catalog"] and not x.is_folder)
        ok = n >= chk.get("min", 1)
        return ok, f"{chk['catalog']} записей {n}"
    if kind == "folder_exists":
        ok = any(
            x.catalog == chk["catalog"] and x.is_folder and x.description == chk["name"]
            for x in ib.items
        )
        return ok, f"папка {chk['name']}"
    if kind == "document_count":
        n = sum(1 for x in ib.documents if x.document == chk["document"])
        ok = n >= chk.get("min", 1)
        return ok, f"{chk['document']} документов {n}"
    if kind == "posted_count":
        n = sum(1 for x in ib.documents if x.document == chk["document"] and x.posted)
        ok = n >= chk.get("min", 1)
        return ok, f"{chk['document']} проведено {n}"
    if kind == "register_movements":
        n = 0
        receipts = expenses = 0
        for rec in ib.documents:
            for mv in rec.movements:
                if mv["register"] != chk["register"]:
                    continue
                n += 1
                if mv["movement"] == "Receipt":
                    receipts += 1
                else:
                    expenses += 1
        if "min" in chk and n < chk["min"]:
            return False, f"движений {n}"
        if "min_receipt" in chk and receipts < chk["min_receipt"]:
            return False, f"приходов {receipts}"
        if "min_expense" in chk and expenses < chk["min_expense"]:
            return False, f"расходов {expenses}"
        return True, f"движений {n} (приход {receipts}, расход {expenses})"
    if kind == "report_run":
        ok = any(r["report"] == chk["report"] for r in ib.report_runs)
        if chk.get("variant"):
            ok = any(
                r["report"] == chk["report"] and r.get("variant") == chk["variant"]
                for r in ib.report_runs
            )
        return ok, f"сформирован {chk['report']}"
    if kind == "desktop_set":
        ok = bool(cfg.desktop)
        return ok, "рабочий стол настроен"
    return False, f"неизвестная проверка {kind}"


def _owner(cfg, path: str):
    parts = path.split(".")
    kind, name = parts[0], parts[1]
    obj = None
    if kind == "Catalog":
        obj = cfg.catalogs.get(name)
    elif kind == "Document":
        obj = cfg.documents.get(name)
    elif kind == "AccumulationRegister":
        obj = cfg.registers.get(name)
    elif kind == "Report":
        obj = cfg.reports.get(name)
    if obj is None:
        return None
    if len(parts) >= 4 and parts[2] == "TabularSection":
        for ts in obj.tabular_sections:
            if ts.name == parts[3]:
                return ts
        return None
    return obj
