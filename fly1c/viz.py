"""Визуализация: один самодостаточный HTML про то, как муха закрыла лабораторные."""
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

TRACK_TITLES = {
    "uchebnaya": "Учебная конфигурация",
    "moi_sobytiya": "Мои события",
    "uchet_ds": "Учёт денежных средств",
}

CSS = """
:root{--bg:#0e1116;--card:#161b22;--line:#232b36;--ink:#e6edf3;--dim:#8b949e;
--ok:#3fb950;--bad:#f85149;--fly:#d29922;--acc:#58a6ff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:14px/1.5 "Segoe UI",system-ui,sans-serif;padding:28px}
h1{font-size:22px;margin:0 0 4px}
h2{font-size:15px;margin:30px 0 12px;color:var(--dim);font-weight:600;
letter-spacing:.08em;text-transform:uppercase}
.sub{color:var(--dim);margin-bottom:22px}
.kpis{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:8px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:14px 18px;min-width:150px}
.kpi b{display:block;font-size:26px;line-height:1.2}
.kpi span{color:var(--dim);font-size:12px}
.warn{background:#2d1e0a;border:1px solid #6a4a12;color:#e3b341;
border-radius:10px;padding:12px 16px;margin:16px 0}
.lab{background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:14px 16px;margin-bottom:10px;display:grid;
grid-template-columns:1fr 210px;gap:16px;align-items:center}
.lab h3{margin:0 0 6px;font-size:15px}
.meta{color:var(--dim);font-size:12px;margin-bottom:8px}
.badge{display:inline-block;padding:1px 8px;border-radius:99px;font-size:11px;
border:1px solid;margin-left:8px}
.b-fly{color:var(--fly);border-color:var(--fly)}
.b-oracle{color:var(--dim);border-color:var(--line)}
.dots{display:flex;flex-wrap:wrap;gap:3px}
.dot{width:11px;height:11px;border-radius:3px;background:var(--ok)}
.dot.f{background:var(--bad)}
.obj{display:flex;gap:12px;flex-wrap:wrap;color:var(--dim);font-size:12px;margin-top:8px}
.obj b{color:var(--ink)}
table{border-collapse:collapse;width:100%;background:var(--card);
border:1px solid var(--line);border-radius:10px;overflow:hidden}
td,th{padding:7px 12px;text-align:left;border-bottom:1px solid var(--line);font-size:13px}
th{color:var(--dim);font-weight:600}
tr:last-child td{border-bottom:none}
.bar{height:9px;background:var(--acc);border-radius:3px}
.brain{background:#0d1117;border:1px solid var(--line);border-radius:10px;
padding:10px;margin-bottom:14px}
footer{color:var(--dim);margin-top:34px;font-size:12px}
"""


def _curve_svg(curve: list[int], total: int, solved_at: int | None,
               w: int = 200, h: int = 54) -> str:
    """Кривая обучения: по оси X эпизоды, по Y — сколько проверок прошло."""
    if not curve:
        return ""
    n = len(curve)
    top = max(total, 1)

    def x(i: int) -> float:
        return 1 + i * (w - 2) / max(n - 1, 1)

    def y(v: int) -> float:
        return h - 3 - (v / top) * (h - 8)

    pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(curve))
    area = f"M1,{h - 3} L" + pts.replace(" ", " L") + f" L{w - 1},{h - 3} Z"
    mark = ""
    if solved_at:
        mx = x(solved_at - 1)
        mark = (f'<line x1="{mx:.1f}" y1="2" x2="{mx:.1f}" y2="{h - 3}" '
                'stroke="#3fb950" stroke-width="1" stroke-dasharray="2 2"/>')
    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
        f'<rect width="{w}" height="{h}" rx="6" fill="#0d1117"/>'
        f'<path d="{area}" fill="#d2992222"/>'
        f'<polyline points="{pts}" fill="none" stroke="#d29922" stroke-width="1.6"/>'
        f"{mark}</svg>"
    )


def _lab_block(lab: dict[str, Any]) -> str:
    ok_n = sum(1 for c in lab["checks"] if c["ok"])
    dots = "".join(
        '<i class="dot{}" title="{}"></i>'.format(
            "" if c["ok"] else " f", html.escape(c["msg"], quote=True)
        )
        for c in lab["checks"]
    )
    if lab["fell_back_to_oracle"]:
        badge = '<span class="badge b-oracle">добил оракул</span>'
    else:
        badge = f'<span class="badge b-fly">муха, эпизод {lab["solved_at"]}</span>'
    objs = " ".join(f"<span>{k}: <b>{v}</b></span>" for k, v in lab["objects"].items() if v)
    return (
        '<div class="lab"><div>'
        f'<h3>{html.escape(lab["id"])} — {html.escape(lab["title"])}{badge}</h3>'
        f'<div class="meta">операций: {lab["n_ops"]} · проверок: {ok_n}/{lab["n_checks"]} · '
        f'эпизодов: {lab["episodes"]} · {lab["seconds"]} с</div>'
        f'<div class="dots">{dots}</div>'
        f'<div class="obj">{objs}</div>'
        "</div><div>"
        + _curve_svg(lab["curve"], lab["n_checks"], lab["solved_at"])
        + "</div></div>"
    )


def _kc_table(labs: list[dict[str, Any]], limit: int = 12) -> str:
    """Какие операции муха «выучила» крепче всего — по числу усиленных KC-синапсов."""
    agg: dict[str, int] = {}
    for lab in labs:
        for key, n in lab.get("kc_weights", {}).items():
            agg[key] = max(agg.get(key, 0), n)
    top = sorted(agg.items(), key=lambda kv: -kv[1])[:limit]
    if not top:
        return ""
    mx = top[0][1] or 1
    rows = "".join(
        "<tr><td>{}</td><td style='color:#8b949e'>{}</td>"
        "<td style='width:200px'><div class='bar' style='width:{}%'></div></td>"
        "<td style='width:60px'>{}</td></tr>".format(
            html.escape(k.split("|")[0]),
            html.escape("|".join(k.split("|")[1:])[:60]),
            max(2, n * 100 // mx),
            n,
        )
        for k, n in top
    )
    return (
        "<table><tr><th>операция</th><th>аргументы</th>"
        "<th>усиленные синапсы KC→действие</th><th></th></tr>" + rows + "</table>"
    )


def _brain_svg(bm: dict[str, list], w: int = 1000, h: int = 500) -> str:
    """Карта мозга: нейроны на своих местах, яркость — сколько раз нейрон разрядился."""
    if not bm:
        return ""
    palette = {0: "#58a6ff", 1: "#d29922", 2: "#3fb950", 3: "#f85149"}
    dots = []
    silent = []
    pts = list(zip(bm["x"], bm["y"], bm["a"], bm["k"]))
    # молчащий фон прореживаем — на картинке это не видно, а вес страницы режет вдвое
    pts = [p for i, p in enumerate(pts) if p[2] or p[3] or i % 3 == 0]
    for x, y, a, k in pts:
        if a == 0 and k == 0:
            # молчащие нейроны — одним path, иначе страница пухнет на сотни килобайт
            silent.append(f"M{x:.0f} {y:.0f}h1")
            continue
        op = 0.25 + 0.75 * min(a, 6) / 6 if a else 0.22
        r = 1.2 + 0.35 * min(a, 6) + (1.0 if k else 0)
        dots.append(
            f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r:.1f}" fill="{palette[k]}" '
            f'opacity="{op:.2f}"/>'
        )
    legend = (
        '<g font-size="13" fill="#8b949e">'
        '<circle cx="14" cy="14" r="4" fill="#58a6ff"/><text x="26" y="19">нейрон мозга</text>'
        '<circle cx="154" cy="14" r="4" fill="#d29922"/><text x="166" y="19">клетка Кеньона</text>'
        '<circle cx="316" cy="14" r="4" fill="#3fb950"/><text x="328" y="19">MBON</text>'
        '<circle cx="396" cy="14" r="4" fill="#f85149"/><text x="408" y="19">дофаминовый</text>'
        "</g>"
    )
    return (
        f'<div class="brain"><svg viewBox="0 -20 {w} {h + 30}" width="100%">'
        f'<rect x="-10" y="-30" width="{w + 20}" height="{h + 50}" fill="#0d1117"/>'
        + f'<path d="{"".join(silent)}" stroke="#2b3440" stroke-width="1.6" fill="none"/>'
        + "".join(dots)
        + legend
        + "</svg></div>"
    )


def _activity_bars(act: dict[str, float]) -> str:
    if not act:
        return ""
    mx = max(act.values()) or 1
    rows = "".join(
        "<tr><td>{}</td><td style='width:260px'>"
        "<div class='bar' style='width:{}%'></div></td>"
        "<td style='width:90px'>{:.2f}</td></tr>".format(
            html.escape(k), max(2, int(v / mx * 100)), v
        )
        for k, v in act.items()
    )
    return ("<table><tr><th>популяция</th><th>средняя активность на стимул</th>"
            "<th>спайков/нейрон</th></tr>" + rows + "</table>")


def render(data: dict[str, Any]) -> str:
    plat = data["platform"]
    brain = data.get("brain") or {}
    warn = ""
    if not plat.get("licensed"):
        warn = (
            '<div class="warn">Платформа 1С '
            f'{html.escape(str(plat.get("version") or "—"))} на месте, но лицензии нет — '
            "батч-сборка ИБ (<code>run_lab.py build</code>) не стартует. "
            "Нужна учебная версия 8.3 или программная лицензия.</div>"
        )
    head = ""
    if brain:
        n_neu = f'{brain["нейронов"]:,}'.replace(",", " ")
        n_syn = f'{brain["синаптических связей"]:,}'.replace(",", " ")
        head = (
            "<h2>Мозг, который это решает</h2>"
            '<div class="sub">коннектом FlyWire v783 (публичный релиз, CC-BY-4.0): '
            f"{n_neu} нейронов, {n_syn} связей. "
            "Состояние лабораторной подаётся как запах — ток в обонятельные рецепторы; "
            "дальше считает реальная проводка мухи, а решение снимается со спайков "
            "грибовидного тела.</div>"
            + _brain_svg(data.get("brain_map", {}))
            + _activity_bars(data.get("brain_activity", {}))
        )
    body = []
    for track, title in TRACK_TITLES.items():
        labs = [l for l in data["labs"] if l["track"] == track]
        if not labs:
            continue
        body.append(f"<h2>{html.escape(title)}</h2>")
        body += [_lab_block(l) for l in labs]
    kpis = [
        (len(data["labs"]), "лабораторных из методички"),
        (f'{data["passed_checks"]}/{data["total_checks"]}', "проверок пройдено"),
        (f'{data["solved_by_fly"]}/{len(data["labs"])}', "муха решила сама"),
        (html.escape(str(plat.get("version") or "—")), "платформа 1С"),
    ]
    if brain:
        kpis += [
            (f'{brain["нейронов"] // 1000}k', "нейронов коннектома"),
            (f'{brain["синаптических связей"] / 1e6:.1f}M', "синаптических связей"),
        ]
    kpi_html = "".join(
        f'<div class="kpi"><b>{v}</b><span>{s}</span></div>' for v, s in kpis
    )
    if brain:
        lead = (f'настоящий коннектом дрозофилы FlyWire вместо кликов в конфигураторе '
                f'· {brain["клеток Кеньона"]} клеток Кеньона решают, что делать дальше')
    else:
        lead = "грибовидное тело (хэш-модель) вместо кликов в конфигураторе"
    return (
        '<!doctype html><html lang="ru"><meta charset="utf-8">'
        "<title>Муха и лабораторные 1С</title>"
        f"<style>{CSS}</style>"
        "<h1>Муха закрывает лабораторные по 1С</h1>"
        f'<div class="sub">{lead} · собрано {html.escape(data["generated"])}</div>'
        f'<div class="kpis">{kpi_html}</div>'
        f"{warn}{head}{''.join(body)}"
        "<h2>Чему научилась муха</h2>"
        f"{_kc_table(data['labs'])}"
        "<footer>Пунктир на кривой — эпизод, в котором сошлись все проверки лабораторной. "
        "Наведи курсор на квадратик, чтобы увидеть текст проверки.</footer>"
        "</html>"
    )


def build(telemetry_path: Path, out: Path) -> Path:
    data = json.loads(telemetry_path.read_text(encoding="utf-8"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(data), encoding="utf-8")
    return out
