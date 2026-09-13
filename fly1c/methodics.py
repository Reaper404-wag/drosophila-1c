"""Разбор методички: PDF -> задание для мухи.

Из текста вытаскиваются требования — какие подсистемы, справочники, документы,
регистры и отчёты должны появиться, с какими реквизитами и какого типа. Это те же
проверки, по которым потом оценивается работа, только не написанные руками,
а прочитанные из PDF.

    python -m fly1c.methodics "Методичка ИСРПО.pdf"
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

BULLET = re.compile(r"^\s*(?:[-−–—•]|\d+\))\s*(.+)$")
LAB_HEAD = re.compile(r"Лабораторн\w*\s*работа\s*№?\s*(\d+)")

# «Строка , длина -20 символов» -> String(20)
LEN_PAT = re.compile(r"длин\w*\s*[-–—:]?\s*(\d+)")
PREC_PAT = re.compile(r"точност\w*\s*[-–—:]?\s*(\d+)")
UNLIMITED = re.compile(r"неограниченн")


def read_pdf(path: str | Path) -> str:
    import pypdf

    reader = pypdf.PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def normalize(text: str) -> str:
    """PDF рассыпает пробелы внутри слов и перед знаками — собираем обратно."""
    text = text.replace(" ", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s+([,.;:)])", r"\1", text)
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"([А-Яа-яЁё])\s+\.\s*([А-ЯЁ])", r"\1.\2", text)  # СправочникСсылка .X
    return text


def parse_type(chunk: str) -> str | None:
    """Кусок вроде «тип Строка, длина -20 символов» -> String(20)."""
    low = chunk.lower()
    ref = re.search(r"справочникссылка\.?\s*([А-ЯЁ][А-Яа-яЁё]+)", chunk, re.I)
    if ref:
        return f"CatalogRef.{ref.group(1)}"
    enum = re.search(r"перечислениессылка\.?\s*([А-ЯЁ][А-Яа-яЁё]+)", chunk, re.I)
    if enum:
        return f"EnumRef.{enum.group(1)}"
    if "булево" in low:
        return "Boolean"
    if "дата" in low:
        return "DateTime" if "время" in low else "Date"
    if "число" in low:
        digits = LEN_PAT.search(low)
        frac = PREC_PAT.search(low)
        return f"Number({digits.group(1) if digits else 10},{frac.group(1) if frac else 0})"
    if "строка" in low:
        if UNLIMITED.search(low):
            return "String(0)"
        digits = LEN_PAT.search(low)
        return f"String({digits.group(1)})" if digits else "String(0)"
    return None


LEAD_VERB = re.compile(
    r"^\s*(?:добавить|создать|создайте|задать|указать|ввести|реквизит\w*|поле)\s*[:\-–—]?\s*",
    re.I)


def _name_of(chunk: str) -> str | None:
    """Имя реквизита: в методичке строка бывает «Добавить реквизит: ДатаНачала – тип Дата»."""
    chunk = LEAD_VERB.sub("", chunk)
    chunk = LEAD_VERB.sub("", chunk)
    m = re.match(r"\s*«?([А-ЯЁ][А-Яа-яЁё0-9]*)»?", chunk)
    if not m:
        return None
    name = m.group(1)
    if name.lower() in {"тип", "длина", "точность", "состав", "дата", "число",
                        "строка", "булево", "закладка", "рис", "измерение",
                        "измерения", "ресурс", "ресурсы", "реквизит", "реквизиты"}:
        return None
    return name


def parse_lab(title: str, body: str) -> dict[str, Any]:
    """Требования одной лабораторной."""
    checks: list[dict] = []
    seen: set[str] = set()

    def add(ch: dict) -> None:
        key = json.dumps(ch, ensure_ascii=False, sort_keys=True)
        if key not in seen:
            seen.add(key)
            checks.append(ch)

    context = ""        # к какому объекту относятся следующие реквизиты
    owner_catalog = ""  # справочник/документ, внутри которого может быть ТЧ
    reg_mode = None     # для регистра: сейчас перечисляют измерения или ресурсы

    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            continue
        low = line.lower()

        for m in re.finditer(r"подсистем\w*\s+([А-ЯЁ][А-Яа-яЁё]+)", line):
            add({"check": "has_subsystem", "name": m.group(1)})

        m = re.search(r"справочник\w*\s+«?([А-ЯЁ][А-Яа-яЁё]+)»?", line)
        if m and re.search(r"созда|добав", low):
            name = m.group(1)
            add({"check": "has_catalog", "name": name})
            context = f"Catalog.{name}"
            owner_catalog = context
            sub = re.search(r"подсистем\w*\s+([А-ЯЁ][А-Яа-яЁё]+)", line)
            if sub:
                add({"check": "catalog_in_subsystem", "catalog": name,
                     "subsystem": sub.group(1)})

        m = re.search(r"документ\w*\s+«?([А-ЯЁ][А-Яа-яЁё]+)»?", line)
        if m and re.search(r"созда|добав", low):
            name = m.group(1)
            add({"check": "has_document", "name": name})
            context = f"Document.{name}"
            owner_catalog = context

        m = re.search(r"регистр\w*\s+накоплени\w*\s+«?([А-ЯЁ][А-Яа-яЁё]+)»?", line)
        if m:
            name = m.group(1)
            add({"check": "has_register", "name": name})
            context = f"AccumulationRegister.{name}"
            owner_catalog = context

        m = re.search(r"отч[её]т\w*\s+«?([А-ЯЁ][А-Яа-яЁё]+)»?", line)
        if m and re.search(r"созда|сформир|постро", low):
            add({"check": "has_report", "name": m.group(1)})

        m = re.search(r"табличн\w*\s+част\w*\s+«?([А-ЯЁ][А-Яа-яЁё]+)»?", line)
        if m and owner_catalog and not owner_catalog.startswith("AccumulationRegister."):
            add({"check": "has_tabular_section", "object": owner_catalog, "name": m.group(1)})
            context = f"{owner_catalog}.TabularSection.{m.group(1)}"

        m = re.search(r"длин\w*\s+наименовани\w*\D*(\d+)", low)
        if m and owner_catalog.startswith("Catalog."):
            add({"check": "has_catalog", "name": owner_catalog.split(".", 1)[1],
                 "description_length": int(m.group(1))})

        if re.search(r"иерархическ", low) and owner_catalog.startswith("Catalog."):
            add({"check": "has_catalog", "name": owner_catalog.split(".", 1)[1],
                 "hierarchical": True})

        # у регистра не реквизиты, а измерения и ресурсы — методичка так и пишет
        if re.search(r"\bизмерени", low):
            reg_mode = "dimension"
        elif re.search(r"\bресурс", low):
            reg_mode = "resource"

        # реквизиты идут списком под текущим объектом
        bullet = BULLET.match(line)
        if bullet and context:
            chunk = bullet.group(1)
            name = _name_of(chunk)
            if name and re.search(r"тип|строка|число|дата|булево|ссылка", chunk, re.I):
                kind = parse_type(chunk)
                if kind and context.startswith("AccumulationRegister."):
                    register = context.split(".", 1)[1]
                    is_resource = (reg_mode == "resource"
                                   or (reg_mode is None and kind.startswith("Number")))
                    add({"check": "register_resource" if is_resource else "register_dimension",
                         "register": register, "name": name})
                elif kind:
                    add({"check": "has_attribute", "object": context,
                         "name": name, "type": kind})

    return {"title": title.strip()[:80], "checks": checks}


def parse(text: str) -> list[dict[str, Any]]:
    text = normalize(text)
    marks = list(LAB_HEAD.finditer(text))
    labs = []
    for i, m in enumerate(marks):
        start = m.start()
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        body = text[start:end]
        head = body.splitlines()[0] if body else m.group(0)
        lab = parse_lab(head, body)
        lab["id"] = f"pdf_{i + 1:02d}"
        if lab["checks"]:
            labs.append(lab)
    return labs


def from_pdf(path: str | Path) -> list[dict[str, Any]]:
    return parse(read_pdf(path))


def main() -> int:
    if len(sys.argv) < 2:
        print("укажи путь к PDF методички")
        return 2
    labs = from_pdf(sys.argv[1])
    total = 0
    for lab in labs:
        print(f"\n{lab['id']}: {lab['title']}")
        kinds: dict[str, int] = {}
        for ch in lab["checks"]:
            kinds[ch["check"]] = kinds.get(ch["check"], 0) + 1
        print("   ", ", ".join(f"{k}×{v}" for k, v in sorted(kinds.items())))
        total += len(lab["checks"])
    print(f"\nвсего требований разобрано: {total} в {len(labs)} лабораторных")
    out = ROOT / "assets" / "methodics.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(labs, ensure_ascii=False, indent=1), encoding="utf-8")
    print("сохранено:", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
