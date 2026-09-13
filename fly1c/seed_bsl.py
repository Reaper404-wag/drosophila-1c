"""Генерация кода 1С, который заливает в ИБ данные из лабораторных.

В конфигурацию добавляется общий модуль «ЗагрузкаДанных» и модуль управляемого
приложения: при запуске с параметром SEED он создаёт справочники и документы,
проводит их и закрывает систему. Всё в батч-режиме, без кликов.
"""
from __future__ import annotations

from typing import Any

from .ir import ConfigIR, TypeSpec, World

MODULE_NAME = "ЗагрузкаДанных"
START_PARAM = "SEED"


def _lit(value: Any) -> str:
    if isinstance(value, bool):
        return "Истина" if value else "Ложь"
    if isinstance(value, (int, float)):
        return str(value)
    return '"' + str(value).replace('"', '""') + '"'


def _value_expr(spec: TypeSpec | None, value: Any) -> str:
    """Значение реквизита: ссылки ищем по наименованию, перечисления — по имени."""
    if spec is not None and isinstance(value, str):
        if spec.kind == "CatalogRef":
            return f'Справочники.{spec.ref}.НайтиПоНаименованию({_lit(value)}, Истина)'
        if spec.kind == "EnumRef":
            return f"Перечисления.{spec.ref}.{value}"
    return _lit(value)


def _attr_types(cfg: ConfigIR, kind: str, name: str) -> dict[str, TypeSpec]:
    owner = cfg.catalogs.get(name) if kind == "catalog" else cfg.documents.get(name)
    if owner is None:
        return {}
    return {a.name: a.type for a in owner.attributes}


def _ts_types(cfg: ConfigIR, kind: str, name: str, ts_name: str) -> dict[str, TypeSpec]:
    owner = cfg.catalogs.get(name) if kind == "catalog" else cfg.documents.get(name)
    if owner is None:
        return {}
    for ts in owner.tabular_sections:
        if ts.name == ts_name:
            return {a.name: a.type for a in ts.attributes}
    return {}


def _item_code(cfg: ConfigIR, item) -> list[str]:
    cat = item.catalog
    types = _attr_types(cfg, "catalog", cat)
    maker = "СоздатьГруппу()" if item.is_folder else "СоздатьЭлемент()"
    lines = [
        f"    // {cat}: {item.description}",
        f"    Если Справочники.{cat}.НайтиПоНаименованию({_lit(item.description)}, Истина).Пустая() Тогда",
        f"        Об = Справочники.{cat}.{maker};",
        f"        Об.Наименование = {_lit(item.description)};",
    ]
    if item.parent:
        lines.append(
            f"        Об.Родитель = Справочники.{cat}."
            f"НайтиПоНаименованию({_lit(item.parent)}, Истина);"
        )
    for key, value in item.attrs.items():
        lines.append(f"        Об.{key} = {_value_expr(types.get(key), value)};")
    for ts_name, rows in item.tabular.items():
        ts_types = _ts_types(cfg, "catalog", cat, ts_name)
        for row in rows:
            lines.append(f"        Стр = Об.{ts_name}.Добавить();")
            for key, value in row.items():
                lines.append(f"        Стр.{key} = {_value_expr(ts_types.get(key), value)};")
    lines += ["        Об.Записать();", "    КонецЕсли;", ""]
    return lines


def _doc_code(cfg: ConfigIR, doc, index: int) -> list[str]:
    name = doc.document
    types = _attr_types(cfg, "document", name)
    lines = [
        f"    // {name} №{doc.number}",
        f"    Если НЕ Документы.{name}.НайтиПоНомеру({_lit(doc.number)}, ДатаЗагрузки).Пустая() Тогда",
        "    Иначе",
        f"        Док = Документы.{name}.СоздатьДокумент();",
        "        Док.Дата = ДатаЗагрузки;",
        f"        Док.Номер = {_lit(doc.number)};",
    ]
    for key, value in doc.attrs.items():
        lines.append(f"        Док.{key} = {_value_expr(types.get(key), value)};")
    for ts_name, rows in doc.tabular.items():
        ts_types = _ts_types(cfg, "document", name, ts_name)
        for row in rows:
            lines.append(f"        Стр = Док.{ts_name}.Добавить();")
            for key, value in row.items():
                lines.append(f"        Стр.{key} = {_value_expr(ts_types.get(key), value)};")
    mode = "РежимЗаписиДокумента.Проведение" if doc.posted else "РежимЗаписиДокумента.Запись"
    lines += [f"        Док.Записать({mode});", "    КонецЕсли;", ""]
    return lines


COUNT_HELPER = [
    "Функция Количество(ИмяТаблицы, ТолькоПроведённые = Ложь)",
    "",
    '    Условие = ?(ТолькоПроведённые, " ГДЕ Т.Проведен", "");',
    '    Текст = "ВЫБРАТЬ КОЛИЧЕСТВО(*) КАК К ИЗ " + ИмяТаблицы + " КАК Т" + Условие;',
    "    Запрос = Новый Запрос(Текст);",
    "    Выборка = Запрос.Выполнить().Выбрать();",
    "    Выборка.Следующий();",
    "    Возврат Выборка.К;",
    "",
    "КонецФункции",
    "",
]


def common_module(world: World) -> str:
    """Серверный модуль: создаёт объекты и возвращает отчёт о том, что легло в базу."""
    cfg = world.config
    body: list[str] = [
        "// Сгенерировано fly1c: данные лабораторных из методички.",
        "",
    ]
    body += COUNT_HELPER
    body += [
        "Функция Заполнить() Экспорт",
        "",
        "    ДатаЗагрузки = НачалоДня(ТекущаяДата());",
        "",
    ]
    for item in world.ib.items:
        body += _item_code(cfg, item)
    for i, doc in enumerate(world.ib.documents):
        body += _doc_code(cfg, doc, i)
    body += ['    Отчёт = "";', ""]
    for name in sorted({i.catalog for i in world.ib.items}):
        body.append(
            f'    Отчёт = Отчёт + "Справочник.{name}=" + Количество("Справочник.{name}")'
            " + Символы.ПС;"
        )
    for name in sorted({d.document for d in world.ib.documents}):
        body.append(
            f'    Отчёт = Отчёт + "Документ.{name}=" + Количество("Документ.{name}")'
            f' + " проведено=" + Количество("Документ.{name}", Истина) + Символы.ПС;'
        )
    for name in sorted(cfg.registers):
        body.append(
            f'    Отчёт = Отчёт + "РегистрНакопления.{name}="'
            f' + Количество("РегистрНакопления.{name}") + Символы.ПС;'
        )
    body += ["", "    Возврат Отчёт;", "", "КонецФункции", ""]
    return "\n".join(body)


def application_module() -> str:
    return "\n".join(
        [
            "// Сгенерировано fly1c: запуск с параметром SEED заливает данные и выходит.",
            "",
            "Процедура ПередНачаломРаботыСистемы(Отказ)",
            "",
            f'    Если Лев(ПараметрЗапуска, {len(START_PARAM)}) = "{START_PARAM}" Тогда',
            "        Отказ = Истина;",
            f"        Путь = Сред(ПараметрЗапуска, {len(START_PARAM) + 2});",
            f"        Отчёт = {MODULE_NAME}.Заполнить();",
            "        Если ЗначениеЗаполнено(Путь) Тогда",
            "            Файл = Новый ЗаписьТекста(Путь, КодировкаТекста.UTF8);",
            "            Файл.ЗаписатьСтроку(Отчёт);",
            "            Файл.Закрыть();",
            "        КонецЕсли;",
            "        ЗавершитьРаботуСистемы(Ложь, Ложь);",
            "    КонецЕсли;",
            "",
            "КонецПроцедуры",
            "",
        ]
    )
