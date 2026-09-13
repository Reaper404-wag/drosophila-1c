"""Стартовая страница: всё, что есть в проекте, одним экраном."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "report"

PAGE = """<!doctype html><html lang="ru"><meta charset="utf-8">
<title>Муха и 1С — старт</title>
<style>
:root{--y:#ffd200;--y2:#f7b500;--ink:#2b2b2b;--dim:#6d6d6d;--line:#c9c9c9;
--bg:#eceff1;--panel:#fff;--head:#f5f6f7;--ok:#3a9d3a;--bad:#c62828;--blue:#1f6fb2}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:13.5px/1.5 "Segoe UI",Tahoma,Arial,sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:14px}
.appbar{display:flex;align-items:center;gap:12px;background:linear-gradient(180deg,var(--y),var(--y2));
border:1px solid #d9a800;border-radius:4px;padding:9px 13px;margin-bottom:12px}
.logo{background:#fff;border:1px solid #d9a800;border-radius:3px;padding:1px 7px;
font-weight:700;color:#c62828}
.title{font-weight:600;font-size:16px}
.when{margin-left:auto;color:#3b2d00;font-size:12px}
h2{font-size:12px;letter-spacing:.09em;text-transform:uppercase;color:var(--dim);margin:18px 0 8px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:10px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:4px;
padding:13px 15px;display:flex;flex-direction:column}
.card h3{margin:0 0 4px;font-size:15px}
.card p{margin:0 0 10px;color:var(--dim);font-size:12.5px;flex:1}
.card a{display:inline-block;align-self:flex-start;background:linear-gradient(180deg,#ffe27a,var(--y));
border:1px solid #d9a800;border-radius:3px;padding:5px 13px;color:#3b2d00;
text-decoration:none;font-weight:600;font-size:12.5px}
.card a.sec{background:#fff;border-color:var(--line);color:var(--blue);font-weight:400}
.status{background:var(--panel);border:1px solid var(--line);border-radius:4px;padding:0}
.status table{border-collapse:collapse;width:100%;font-size:12.5px}
.status td{border-bottom:1px solid #eee;padding:6px 12px}
.status td:first-child{color:var(--dim);width:38%}
.status tr:last-child td{border-bottom:none}
.ok{color:var(--ok);font-weight:600}
.no{color:var(--bad);font-weight:600}
pre{background:#fbfbfb;border:1px solid var(--line);border-radius:4px;padding:10px 12px;
overflow:auto;font:12px/1.65 "Cascadia Mono",Consolas,monospace;margin:0}
.note{color:var(--dim);font-size:12px;margin-top:8px}
</style>
<div class="wrap">
<div class="appbar"><span class="logo">1С</span>
  <span class="title">Муха закрывает лабораторные — что где смотреть</span>
  <span class="when">собрано __WHEN__</span></div>

<h2>Посмотреть</h2>
<div class="cards">__CARDS__</div>

<h2>Состояние стенда</h2>
<div class="status"><table>__STATUS__</table></div>

<h2>Запустить руками</h2>
<pre>__CMDS__</pre>
<div class="note">Каждая страница — обычный html-файл в папке <b>report</b>, открывается двойным
кликом и работает без интернета.</div>
</div>
</html>"""

CARDS = [
    ("stage.html", "Сцена: муха делает лабораторную",
     "Главное. Слева живое окно 1С:Предприятия — подсистемы, справочники, журналы документов, "
     "проверки методички; справа активность коннектома и 3D-муха в очках за клавиатурой. "
     "Лабораторная выбирается в списке."),
    ("lab.html", "Лаборатория коннектома",
     "Мозг крупным планом: анатомия обонятельной цепи по реальным координатам синапсов FlyWire "
     "и живая LIF-симуляция прямо в браузере — телеметрия, лента ответа, инспектор нейронов."),
    ("index.html", "Отчёт по всем 12 лабораторным",
     "Итог прогона: сколько проверок сошлось, на каком эпизоде муха решила каждую лабу, "
     "кривые обучения и что она выучила крепче всего."),
    ("cinema.html", "Студия: муха и объём мозга",
     "Картинка для показа: модель в студийном свете с мягкими тенями и свечением, рядом "
     "объёмный мозг из 262 тысяч настоящих координат синапсов — раскраска по глубине, "
     "медленное вращение."),
    ("fly3d.html", "3D-муха отдельно",
     "Модель NeuroMechFly с костями и кнопками режимов: думает, поправляет очки, печатает, покой. "
     "Удобно, если нужен крупный план."),
]

COMMANDS = """cd <папка проекта>

python run_lab.py list                 список лабораторных
python run_lab.py stage                пересобрать сцену (муха проходит все 12 лаб)
python run_lab.py report               пересобрать отчёт
python run_lab.py lab                  пересобрать лабораторию коннектома
python run_lab.py platform             что с платформой 1С и лицензией

python run_lab.py build 10_ms_lab1     собрать настоящую ИБ 1С для одной лабы
python run_lab.py seed  10_ms_lab1     залить в неё справочники и провести документы
python run_lab.py open  10_ms_lab1     открыть её окном 1С (--designer — конфигуратор)"""


def _num(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def status_rows() -> str:
    from . import ones_real

    info = ones_real.status()
    rows = []

    def row(name: str, value: str) -> None:
        rows.append(f"<tr><td>{name}</td><td>{value}</td></tr>")

    row("платформа 1С", (info["version"] or "не найдена")
        + (' <span class="ok">учебная, лицензия не нужна</span>' if info.get("training")
           else ' <span class="no">нужна лицензия</span>' if not info["licensed"] else ""))
    ibs = info["infobases"]
    row("собранные ИБ", ", ".join(ibs) if ibs else '<span class="no">пока ни одной</span>')

    stage = REPORT / "stage.json"
    if stage.exists():
        data = json.loads(stage.read_text(encoding="utf-8"))
        row("лабораторных в сцене", f"{len(data['labs'])}")
        row("мозг", f"{_num(data['brain']['нейронов'])} нейронов, "
                    f"{_num(data['brain']['синаптических связей'])} синаптических связей")
        # берём итог того самого прогона, который показан на сцене: телеметрия
        # старого агента показывала здесь 113/113 и противоречила замеру
        got = sum(sum(lab["frames"][-1]["mask"]) for lab in data["labs"] if lab["frames"])
        total = sum(len(lab["checks"]) for lab in data["labs"])
        misses = sum(1 for lab in data["labs"] for f in lab["frames"] if f["failed"])
        row("проверок сошлось", f'<span class="ok">{got}</span>/{total} '
                                f'<span class="dim">(промахов {misses})</span>')
        full = sum(1 for lab in data["labs"]
                   if lab["frames"] and sum(lab["frames"][-1]["mask"]) == len(lab["checks"]))
        row("закрыто целиком", f"{full} из {len(data['labs'])} лабораторных")
    circuit = ROOT / "assets" / "circuit.json"
    if circuit.exists():
        data = json.loads(circuit.read_text(encoding="utf-8"))
        row("цепь в лаборатории", f"{len(data['neurons'])} клеток, "
                                  f"{len(data['edges'])} связей, "
                                  f"{_num(data['synapses'])} синапсов")
    return "".join(rows)


def build(out: Path | None = None) -> Path:
    out = out or REPORT / "home.html"
    cards = []
    for href, title, text in CARDS:
        exists = (REPORT / href).exists()
        link = (f'<a href="{href}">Открыть</a>' if exists
                else '<a class="sec">ещё не собрано</a>')
        cards.append(f'<div class="card"><h3>{title}</h3><p>{text}</p>{link}</div>')
    html = (PAGE.replace("__CARDS__", "".join(cards))
            .replace("__STATUS__", status_rows())
            .replace("__CMDS__", COMMANDS)
            .replace("__WHEN__", datetime.now().strftime("%d.%m.%Y %H:%M")))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out


if __name__ == "__main__":
    print(build())
