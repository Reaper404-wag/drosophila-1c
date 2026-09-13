from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TypeSpec:
    kind: str
    length: int | None = None
    digits: int | None = None
    fraction: int | None = None
    date_fractions: str | None = None
    ref: str | None = None
    unlimited: bool = False
    nonnegative: bool = False

    def key(self) -> str:
        if self.kind in {"CatalogRef", "EnumRef"}:
            return f"{self.kind}.{self.ref}"
        if self.kind == "String":
            return f"String({0 if self.unlimited else self.length or 0})"
        if self.kind == "Number":
            return f"Number({self.digits},{self.fraction or 0})"
        if self.kind == "Date":
            return f"Date({self.date_fractions or 'Date'})"
        return self.kind


@dataclass
class Attribute:
    name: str
    type: TypeSpec
    multiline: bool = False
    extended_edit: bool = False
    synonym: str | None = None


@dataclass
class TabularSection:
    name: str
    attributes: list[Attribute] = field(default_factory=list)
    synonym: str | None = None


@dataclass
class FormDef:
    name: str
    kind: str = "object"
    module: str = ""
    deleted_fields: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Catalog:
    name: str
    synonym: str | None = None
    description_length: int = 25
    hierarchical: bool = False
    hierarchy_type: str = "HierarchyFoldersAndItems"
    subsystems: list[str] = field(default_factory=list)
    attributes: list[Attribute] = field(default_factory=list)
    tabular_sections: list[TabularSection] = field(default_factory=list)
    predefined: list[dict[str, str]] = field(default_factory=list)
    quick_choice: bool = False
    object_presentation: str | None = None
    forms: list[FormDef] = field(default_factory=list)
    description_synonym: str | None = None
    comment_multiline: bool = False


@dataclass
class Document:
    name: str
    synonym: str | None = None
    subsystems: list[str] = field(default_factory=list)
    attributes: list[Attribute] = field(default_factory=list)
    tabular_sections: list[TabularSection] = field(default_factory=list)
    register_records: list[tuple[str, str]] = field(default_factory=list)
    object_module: str = ""
    form_module: str = ""
    forms: list[FormDef] = field(default_factory=list)
    auto_delete_movements: bool = False


@dataclass
class EnumDef:
    name: str
    values: list[str] = field(default_factory=list)
    subsystems: list[str] = field(default_factory=list)


@dataclass
class Register:
    name: str
    register_type: str = "Balances"
    subsystems: list[str] = field(default_factory=list)
    dimensions: list[Attribute] = field(default_factory=list)
    resources: list[Attribute] = field(default_factory=list)
    forms: list[FormDef] = field(default_factory=list)
    registrars: list[str] = field(default_factory=list)


@dataclass
class Report:
    name: str
    subsystems: list[str] = field(default_factory=list)
    query_table: str | None = None
    fields: list[str] = field(default_factory=list)
    resources: list[str] = field(default_factory=list)
    group_by: list[str] = field(default_factory=list)
    chart: bool = False
    chart_type: str | None = None
    variants: list[str] = field(default_factory=list)
    forms: list[FormDef] = field(default_factory=list)
    user_params: list[str] = field(default_factory=list)


@dataclass
class Subsystem:
    name: str
    synonym: str | None = None
    parent: str | None = None
    picture: bool = False
    content: list[str] = field(default_factory=list)
    important: list[str] = field(default_factory=list)


@dataclass
class IBItem:
    catalog: str
    description: str
    is_folder: bool = False
    parent: str | None = None
    attrs: dict[str, Any] = field(default_factory=dict)
    tabular: dict[str, list[dict[str, Any]]] = field(default_factory=dict)


@dataclass
class IBDocument:
    document: str
    number: str
    posted: bool = False
    attrs: dict[str, Any] = field(default_factory=dict)
    tabular: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    movements: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ConfigIR:
    name: str = "Конфигурация"
    synonym: str | None = None
    subsystems: dict[str, Subsystem] = field(default_factory=dict)
    subsystem_order: list[str] = field(default_factory=list)
    catalogs: dict[str, Catalog] = field(default_factory=dict)
    documents: dict[str, Document] = field(default_factory=dict)
    enums: dict[str, EnumDef] = field(default_factory=dict)
    registers: dict[str, Register] = field(default_factory=dict)
    reports: dict[str, Report] = field(default_factory=dict)
    desktop: dict[str, Any] = field(default_factory=dict)
    roles: list[str] = field(default_factory=lambda: ["ПолныеПрава"])


@dataclass
class InfobaseIR:
    items: list[IBItem] = field(default_factory=list)
    documents: list[IBDocument] = field(default_factory=list)
    report_runs: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class World:
    config: ConfigIR = field(default_factory=ConfigIR)
    ib: InfobaseIR = field(default_factory=InfobaseIR)
    log: list[str] = field(default_factory=list)


class OpError(Exception):
    pass


def parse_type(spec: str | dict[str, Any]) -> TypeSpec:
    if isinstance(spec, dict):
        return TypeSpec(**spec)
    if spec.startswith("CatalogRef."):
        return TypeSpec("CatalogRef", ref=spec.split(".", 1)[1])
    if spec.startswith("EnumRef."):
        return TypeSpec("EnumRef", ref=spec.split(".", 1)[1])
    if spec in {"String", "Строка"}:
        return TypeSpec("String", unlimited=True)
    if spec in {"Boolean", "Булево"}:
        return TypeSpec("Boolean")
    if spec in {"Date", "Дата"}:
        return TypeSpec("Date", date_fractions="Date")
    if spec in {"DateTime", "ДатаВремя"}:
        return TypeSpec("Date", date_fractions="DateTime")
    if spec.startswith("String:"):
        n = spec.split(":", 1)[1]
        if n in {"0", "unlim", "неогр"}:
            return TypeSpec("String", unlimited=True)
        return TypeSpec("String", length=int(n))
    if spec.startswith("Number:"):
        body = spec.split(":", 1)[1]
        parts = body.split(",")
        digits = int(parts[0])
        frac = int(parts[1]) if len(parts) > 1 else 0
        nn = "nn" in parts[2] if len(parts) > 2 else False
        return TypeSpec("Number", digits=digits, fraction=frac, nonnegative=nn)
    raise OpError(f"unknown type {spec!r}")
