from __future__ import annotations

from copy import deepcopy
from typing import Any

from .ir import (
    Attribute,
    Catalog,
    ConfigIR,
    Document,
    EnumDef,
    FormDef,
    IBDocument,
    IBItem,
    InfobaseIR,
    OpError,
    Register,
    Report,
    Subsystem,
    TabularSection,
    World,
    parse_type,
)


def _need_catalog(cfg: ConfigIR, name: str) -> Catalog:
    if name not in cfg.catalogs:
        raise OpError(f"нет справочника {name}")
    return cfg.catalogs[name]


def _need_document(cfg: ConfigIR, name: str) -> Document:
    if name not in cfg.documents:
        raise OpError(f"нет документа {name}")
    return cfg.documents[name]


def _need_register(cfg: ConfigIR, name: str) -> Register:
    if name not in cfg.registers:
        raise OpError(f"нет регистра {name}")
    return cfg.registers[name]


def _resolve_owner(cfg: ConfigIR, path: str):
    parts = path.split(".")
    kind, name = parts[0], parts[1]
    if kind == "Catalog":
        obj = _need_catalog(cfg, name)
    elif kind == "Document":
        obj = _need_document(cfg, name)
    elif kind == "AccumulationRegister":
        obj = _need_register(cfg, name)
    elif kind == "Report":
        if name not in cfg.reports:
            raise OpError(f"нет отчёта {name}")
        obj = cfg.reports[name]
    else:
        raise OpError(f"неизвестный владелец {path}")
    if len(parts) >= 4 and parts[2] == "TabularSection":
        ts_name = parts[3]
        for ts in obj.tabular_sections:
            if ts.name == ts_name:
                return ts
        raise OpError(f"нет ТЧ {ts_name} у {path}")
    return obj


def apply_op(world: World, op: dict[str, Any]) -> None:
    cfg, ib = world.config, world.ib
    kind = op["op"]
    if kind == "set_config_name":
        cfg.name = op["name"]
        cfg.synonym = op.get("synonym", op["name"])
    elif kind == "create_subsystem":
        name = op["name"]
        if name in cfg.subsystems:
            raise OpError(f"подсистема {name} уже есть")
        cfg.subsystems[name] = Subsystem(
            name=name,
            synonym=op.get("synonym", name),
            parent=op.get("parent"),
            picture=bool(op.get("picture")),
        )
        if name not in cfg.subsystem_order:
            cfg.subsystem_order.append(name)
    elif kind == "set_subsystem_order":
        cfg.subsystem_order = list(op["names"])
    elif kind == "create_catalog":
        name = op["name"]
        if name in cfg.catalogs:
            raise OpError(f"справочник {name} уже есть")
        cat = Catalog(
            name=name,
            synonym=op.get("synonym", name),
            description_length=int(op.get("description_length", 25)),
            hierarchical=bool(op.get("hierarchical")),
            hierarchy_type=op.get("hierarchy_type", "HierarchyFoldersAndItems"),
            subsystems=list(op.get("subsystems", [])),
            quick_choice=bool(op.get("quick_choice")),
            object_presentation=op.get("object_presentation"),
        )
        for sub in cat.subsystems:
            if sub not in cfg.subsystems:
                raise OpError(f"нет подсистемы {sub}")
            cfg.subsystems[sub].content.append(f"Catalog.{name}")
        cfg.catalogs[name] = cat
    elif kind == "create_tabular_section":
        owner = _resolve_owner(cfg, op["object"])
        name = op["name"]
        if any(ts.name == name for ts in owner.tabular_sections):
            raise OpError(f"ТЧ {name} уже есть")
        owner.tabular_sections.append(
            TabularSection(name=name, synonym=op.get("synonym", name))
        )
    elif kind == "add_attribute":
        owner = _resolve_owner(cfg, op["object"])
        name = op["name"]
        bag = owner.attributes if hasattr(owner, "attributes") else None
        if bag is None:
            raise OpError("сюда нельзя добавить реквизит")
        if any(a.name == name for a in bag):
            raise OpError(f"реквизит {name} уже есть")
        bag.append(
            Attribute(
                name=name,
                type=parse_type(op["type"]),
                multiline=bool(op.get("multiline")),
                extended_edit=bool(op.get("extended_edit")),
                synonym=op.get("synonym"),
            )
        )
    elif kind == "add_predefined":
        cat = _need_catalog(cfg, op["catalog"])
        cat.predefined.append(
            {"name": op["name"], "description": op.get("description", op["name"])}
        )
    elif kind == "create_enum":
        name = op["name"]
        if name in cfg.enums:
            raise OpError(f"перечисление {name} уже есть")
        en = EnumDef(name=name, values=list(op.get("values", [])), subsystems=list(op.get("subsystems", [])))
        for sub in en.subsystems:
            if sub not in cfg.subsystems:
                raise OpError(f"нет подсистемы {sub}")
            cfg.subsystems[sub].content.append(f"Enum.{name}")
        cfg.enums[name] = en
    elif kind == "create_document":
        name = op["name"]
        if name in cfg.documents:
            raise OpError(f"документ {name} уже есть")
        doc = Document(
            name=name,
            synonym=op.get("synonym", name),
            subsystems=list(op.get("subsystems", [])),
            auto_delete_movements=bool(op.get("auto_delete_movements")),
        )
        for sub in doc.subsystems:
            if sub not in cfg.subsystems:
                raise OpError(f"нет подсистемы {sub}")
            cfg.subsystems[sub].content.append(f"Document.{name}")
        cfg.documents[name] = doc
    elif kind == "copy_document":
        src = _need_document(cfg, op["from"])
        name = op["to"]
        if name in cfg.documents:
            raise OpError(f"документ {name} уже есть")
        clone = deepcopy(src)
        clone.name = name
        clone.synonym = op.get("synonym", name)
        clone.register_records = []
        clone.object_module = ""
        clone.form_module = ""
        if op.get("tabular_rename"):
            old, new = op["tabular_rename"]
            for ts in clone.tabular_sections:
                if ts.name == old:
                    ts.name = new
        clone.subsystems = list(op.get("subsystems", src.subsystems))
        for sub in clone.subsystems:
            cfg.subsystems[sub].content.append(f"Document.{name}")
        cfg.documents[name] = clone
    elif kind == "create_register":
        name = op["name"]
        if name in cfg.registers:
            raise OpError(f"регистр {name} уже есть")
        reg = Register(
            name=name,
            register_type=op.get("register_type", "Balances"),
            subsystems=list(op.get("subsystems", [])),
        )
        for sub in reg.subsystems:
            if sub not in cfg.subsystems:
                raise OpError(f"нет подсистемы {sub}")
            cfg.subsystems[sub].content.append(f"AccumulationRegister.{name}")
        cfg.registers[name] = reg
    elif kind == "add_dimension":
        reg = _need_register(cfg, op["register"])
        name = op["name"]
        if any(d.name == name for d in reg.dimensions):
            raise OpError(f"измерение {name} уже есть")
        reg.dimensions.append(Attribute(name=name, type=parse_type(op["type"])))
    elif kind == "add_resource":
        reg = _need_register(cfg, op["register"])
        name = op["name"]
        if any(r.name == name for r in reg.resources):
            raise OpError(f"ресурс {name} уже есть")
        reg.resources.append(Attribute(name=name, type=parse_type(op["type"])))
    elif kind == "bind_register":
        doc = _need_document(cfg, op["document"])
        reg = _need_register(cfg, op["register"])
        movement = op.get("movement", "Receipt")
        doc.register_records.append((reg.name, movement))
        if doc.name not in reg.registrars:
            reg.registrars.append(doc.name)
        if op.get("module"):
            doc.object_module = op["module"]
        else:
            doc.object_module = _default_movement_module(doc, reg.name, movement)
    elif kind == "write_object_module":
        doc = _need_document(cfg, op["document"])
        doc.object_module = op["code"]
    elif kind == "write_form_module":
        path = op["object"]
        owner = _resolve_owner(cfg, path)
        if isinstance(owner, Document):
            owner.form_module = op["code"]
        elif isinstance(owner, Catalog):
            fname = op.get("form", "ФормаЭлемента")
            found = next((f for f in owner.forms if f.name == fname), None)
            if found is None:
                found = FormDef(name=fname, kind="object")
                owner.forms.append(found)
            found.module = op["code"]
        else:
            raise OpError("модуль формы не туда")
    elif kind == "create_form":
        owner = _resolve_owner(cfg, op["object"])
        form = FormDef(
            name=op["name"],
            kind=op.get("kind", "object"),
            module=op.get("module", ""),
            deleted_fields=list(op.get("deleted_fields", [])),
            extra=dict(op.get("extra", {})),
        )
        owner.forms.append(form)
    elif kind == "create_report":
        name = op["name"]
        if name in cfg.reports:
            raise OpError(f"отчёт {name} уже есть")
        rep = Report(
            name=name,
            subsystems=list(op.get("subsystems", [])),
            query_table=op.get("query_table"),
            fields=list(op.get("fields", [])),
            resources=list(op.get("resources", [])),
            group_by=list(op.get("group_by", [])),
            chart=bool(op.get("chart")),
            chart_type=op.get("chart_type"),
            user_params=list(op.get("user_params", [])),
        )
        for sub in rep.subsystems:
            if sub not in cfg.subsystems:
                raise OpError(f"нет подсистемы {sub}")
            cfg.subsystems[sub].content.append(f"Report.{name}")
        cfg.reports[name] = rep
    elif kind == "add_report_variant":
        if op["report"] not in cfg.reports:
            raise OpError(f"нет отчёта {op['report']}")
        cfg.reports[op["report"]].variants.append(op["name"])
    elif kind == "set_quick_choice":
        _need_catalog(cfg, op["catalog"]).quick_choice = True
    elif kind == "set_object_presentation":
        _need_catalog(cfg, op["catalog"]).object_presentation = op["presentation"]
    elif kind == "set_synonym":
        path = op["object"]
        if path.endswith(".StandardAttribute.Description"):
            cat = _need_catalog(cfg, path.split(".")[1])
            cat.description_synonym = op["synonym"]
        elif ".TabularSection." in path and path.count(".") >= 4:
            ts = _resolve_owner(cfg, ".".join(path.split(".")[:4]))
            attr_name = path.split(".")[-1]
            for a in ts.attributes:
                if a.name == attr_name:
                    a.synonym = op["synonym"]
                    break
            else:
                raise OpError(f"нет реквизита {attr_name}")
        else:
            raise OpError(f"не умею синоним для {path}")
    elif kind == "set_desktop":
        cfg.desktop = dict(op.get("layout", {}))
    elif kind == "fill_catalog":
        cat = _need_catalog(cfg, op["catalog"])
        for row in op["items"]:
            ib.items.append(
                IBItem(
                    catalog=cat.name,
                    description=row["description"],
                    is_folder=bool(row.get("is_folder")),
                    parent=row.get("parent"),
                    attrs=dict(row.get("attrs", {})),
                    tabular=dict(row.get("tabular", {})),
                )
            )
    elif kind == "fill_document":
        doc = _need_document(cfg, op["document"])
        n = op.get("count")
        rows = list(op.get("items", []))
        if n and not rows:
            rows = [{"number": str(i + 1)} for i in range(int(n))]
        for i, row in enumerate(rows, 1):
            posted = bool(row.get("posted", False))
            rec = IBDocument(
                document=doc.name,
                number=str(row.get("number", i)),
                posted=posted,
                attrs=dict(row.get("attrs", {})),
                tabular=dict(row.get("tabular", {})),
            )
            if posted and doc.register_records:
                rec.movements = _movements_from(doc, rec)
            ib.documents.append(rec)
    elif kind == "post_all":
        doc = _need_document(cfg, op["document"])
        n = 0
        for rec in ib.documents:
            if rec.document != doc.name:
                continue
            rec.posted = True
            rec.movements = _movements_from(doc, rec)
            n += 1
        if n == 0:
            raise OpError(f"нечего проводить в {doc.name}")
    elif kind == "run_report":
        if op["report"] not in cfg.reports:
            raise OpError(f"нет отчёта {op['report']}")
        ib.report_runs.append(
            {"report": op["report"], "filter": op.get("filter"), "variant": op.get("variant")}
        )
    else:
        raise OpError(f"неизвестная операция {kind}")
    world.log.append(kind)


def _default_movement_module(doc: Document, register: str, movement: str) -> str:
    ts = doc.tabular_sections[0].name if doc.tabular_sections else None
    kind = "Приход" if movement == "Receipt" else "Расход"
    if ts:
        loop = (
            f"Для Каждого ТекСтрока Из {ts} Цикл\n"
            f"\tДвижение = Движения.{register}.Добавить();\n"
            f"\tДвижение.ВидДвижения = ВидДвиженияНакопления.{kind};\n"
            f"\tДвижение.Период = Дата;\n"
            f"\tДвижение.Сумма = ТекСтрока.Сумма;\n"
            f"КонецЦикла;"
        )
    else:
        loop = (
            f"Движение = Движения.{register}.Добавить();\n"
            f"Движение.ВидДвижения = ВидДвиженияНакопления.{kind};\n"
            f"Движение.Период = Дата;\n"
            f"Движение.Сумма = Сумма;"
        )
    return (
        "Процедура ОбработкаПроведения(Отказ, Режим)\n"
        f"\tДвижения.{register}.Записывать = Истина;\n"
        f"\t{loop}\n"
        "КонецПроцедуры\n"
    )


def _movements_from(doc: Document, rec: IBDocument) -> list[dict[str, Any]]:
    out = []
    for register, movement in doc.register_records:
        ts_name = doc.tabular_sections[0].name if doc.tabular_sections else None
        rows = rec.tabular.get(ts_name, [{}]) if ts_name else [rec.attrs]
        for row in rows:
            amount = row.get("Сумма", rec.attrs.get("Сумма", 0))
            out.append(
                {
                    "register": register,
                    "movement": movement,
                    "sum": amount,
                    "row": row,
                }
            )
    return out
