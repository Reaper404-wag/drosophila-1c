from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from fly1c.agent import MushroomBodyAgent, OracleAgent
from fly1c.checker import run_checks
from fly1c.curriculum import BY_ID, LABS, TRACKS
from fly1c.ir import World
from fly1c.ones_bridge import write_vm_loader
from fly1c import ones_real
from fly1c.xml_dump import dump_world


def _print_checks(world: World, lab: dict) -> None:
    for ok, msg in run_checks(world, lab["checks"]):
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {msg}")


def cmd_list(_: argparse.Namespace) -> int:
    print(f"{'id':<22} {'трек':<14} ходов  проверок  название")
    for lab in LABS:
        print(
            f"{lab['id']:<22} {lab['track']:<14} {len(lab['ops']):>3}  "
            f"{len(lab['checks']):>6}  {lab['title']}"
        )
    return 0


def _run_one(lab_id: str, world: World, agent_name: str, episodes: int, dump: bool) -> dict:
    lab = BY_ID[lab_id]
    print(f"\n=== {lab['id']}: {lab['title']} ===")
    if agent_name == "oracle":
        result = OracleAgent().run(world, lab)
    elif agent_name == "flywire":
        from fly1c.fly_agent import ConnectomeAgent

        result = ConnectomeAgent().run(world, lab, episodes=episodes)
        if not result["ok"]:
            print("  муха не добила; доигрывает оракул, чтобы выгрузка была полной")
            result.update(OracleAgent().run(world, lab))
            result["agent"] = "flywire+oracle"
    else:
        result = MushroomBodyAgent().run(world, lab, episodes=episodes)
        if not result["ok"]:
            print("  муха не добила; доигрывает оракул, чтобы выгрузка была полной")
            result["fly"] = dict(result)
            result.update(OracleAgent().run(world, lab))
            result["agent"] = "fly+oracle"
    print(
        f"  решал={result['agent']} готово={result['ok']} "
        f"проверок={result.get('passed', result.get('best'))}/{result.get('checks')}"
    )
    if result.get("solved_at"):
        print(f"  муха справилась на эпизоде {result['solved_at']}")
    _print_checks(world, lab)
    if dump:
        out = ROOT / "dumps" / lab["track"] / lab["id"]
        dump_world(world, out)
        write_vm_loader(out, ib_name=world.config.name)
        print(f"  выгрузка -> {out}")
    return result


def cmd_run(args: argparse.Namespace) -> int:
    if args.id not in BY_ID:
        print("не знаю такой лабораторной:", args.id)
        return 2
    world = World()
    result = _run_one(args.id, world, args.agent, args.episodes, dump=not args.no_dump)
    return 0 if result["ok"] else 1


def cmd_track(args: argparse.Namespace) -> int:
    if args.name not in TRACKS:
        print("треки:", ", ".join(TRACKS))
        return 2
    world = World()
    failed = False
    for lab_id in TRACKS[args.name]:
        result = _run_one(lab_id, world, args.agent, args.episodes, dump=not args.no_dump)
        if not result["ok"]:
            failed = True
            if args.agent == "oracle":
                break
    out = ROOT / "dumps" / args.name / "final"
    dump_world(world, out)
    write_vm_loader(out, ib_name=world.config.name)
    ones_real.write_status(ROOT / "dumps" / "platform_status.json")
    print(f"\nитоговая выгрузка -> {out}")
    plat = ones_real.find_platform()
    if plat:
        print("платформа 1С:", plat)
    else:
        print("1С на хосте не найдена.")
    return 1 if failed else 0


def cmd_all(args: argparse.Namespace) -> int:
    rc = 0
    for name in TRACKS:
        print(f"\n######## ТРЕК {name} ########")
        ns = argparse.Namespace(
            name=name, agent=args.agent, episodes=args.episodes, no_dump=args.no_dump
        )
        rc |= cmd_track(ns)
    return rc


def cmd_report(args: argparse.Namespace) -> int:
    """Прогнать все треки мухой, записать телеметрию и собрать HTML-отчёт."""
    from fly1c import telemetry, viz

    tel = ROOT / "report" / "telemetry.json"
    data = telemetry.write(tel, episodes=args.episodes, agent=args.agent)
    out = viz.build(tel, ROOT / "report" / "index.html")
    print(f"лабораторных: {len(data['labs'])}")
    print(f"проверок:     {data['passed_checks']}/{data['total_checks']}")
    print(f"муха сама:    {data['solved_by_fly']}/{len(data['labs'])}")
    print(f"отчёт:        {out}")
    return 0


def cmd_live(args: argparse.Namespace) -> int:
    """Записать прогон лабораторной и собрать анимацию мозга."""
    from fly1c import trace, viz_live

    if args.id not in BY_ID:
        print("не знаю такой лабораторной:", args.id)
        return 2
    data = trace.record(args.id, episodes=args.episodes)
    out = viz_live.build(data, ROOT / "report" / f"live_{args.id}.html")
    fails = sum(1 for f in data["frames"] if f["failed"])
    passed = sum(data["frames"][-1]["mask"])
    print(f"шагов: {len(data['frames'])} (промахов {fails})")
    print(f"проверок: {passed}/{len(data['checks'])}")
    print(f"анимация: {out}")
    return 0


def cmd_seed(args: argparse.Namespace) -> int:
    """Залить данные лабораторных в уже собранную ИБ (режим Предприятия, батчем)."""
    name = args.ib or args.target
    if not ones_real.ib_exists(name):
        print("нет ИБ", name, "— сначала python run_lab.py build", args.target)
        return 2
    out = ROOT / "logs" / f"{name}.seed.txt"
    if out.exists():
        out.unlink()
    try:
        r = ones_real.enterprise(name, f"SEED|{out}", timeout=args.timeout)
    except ones_real.OneSError as exc:
        print("1С:", exc)
        return 3
    if out.exists():
        print(out.read_text(encoding="utf-8-sig").strip())
        return 0
    print("данные не записались, rc=", r.rc)
    if r.log:
        print(r.log[:1500])
    return 1


def cmd_stage(args: argparse.Namespace) -> int:
    """Собрать сцену: муха печатает лабораторную, слева видно 1С."""
    from fly1c import stage, viz_stage

    ids = args.labs.split(",") if args.labs else None
    data = stage.write(ROOT / "report" / "stage.json", episodes=args.episodes, lab_ids=ids)
    out = viz_stage.build(data, ROOT / "report" / "stage.html",
                          lite=args.lite, cdn=args.cdn)
    print(f"лабораторных в сцене: {len(data['labs'])}")
    print(f"сцена: {out}")
    return 0


def cmd_open(args: argparse.Namespace) -> int:
    """Открыть собранную ИБ: посмотреть, что муха сделала."""
    name = args.ib or args.target
    try:
        ones_real.launch(name, designer=args.designer)
    except ones_real.OneSError as exc:
        print("1С:", exc)
        return 2
    where = "конфигуратор" if args.designer else "предприятие"
    print(f"открываю {name} ({where}) — окно 1С появится через пару секунд")
    return 0


def cmd_home(args: argparse.Namespace) -> int:
    """Стартовая страница со ссылками на всё и состоянием стенда."""
    from fly1c import viz_home

    print("старт:", viz_home.build())
    return 0


def cmd_cinema(args: argparse.Namespace) -> int:
    """Студийная страница: муха в свете и объём мозга из синапсов."""
    from fly1c import viz_cinema

    print("студия:", viz_cinema.build(ROOT / "report" / "cinema.html"))
    return 0


def cmd_lab(args: argparse.Namespace) -> int:
    """Лаборатория коннектома: реальная анатомия цепи + живая симуляция в браузере."""
    from fly1c import viz_lab

    out = viz_lab.build(ROOT / "report" / "lab.html")
    print(f"лаборатория: {out}")
    return 0


def cmd_platform(_: argparse.Namespace) -> int:
    info = ones_real.status()
    print("платформа:", info["platform_path"] or "не найдена")
    print("версия:   ", info["version"] or "-")
    if info.get("training"):
        print("лицензия:  не нужна (учебная версия)")
    else:
        print("лицензия: ", "есть" if info["licensed"] else "НЕТ")
    print("ИБ:       ", ", ".join(info["infobases"]) or "-")
    if not info["licensed"] and not info.get("training"):
        print()
        print("Без лицензии батч-режим 1С не стартует (окно «Получение лицензии»).")
        print("Варианты: поставить учебную версию 8.3 (лицензия не нужна)")
        print("или один раз получить программную лицензию по своим рег. номерам.")
    return 0 if info["licensed"] else 1


def _dump_dir(target: str) -> Path | None:
    """Цель — либо трек целиком (dumps/<track>/final), либо одна лаба (dumps/<track>/<id>)."""
    if target in TRACKS:
        return ROOT / "dumps" / target / "final"
    lab = BY_ID.get(target)
    if lab is None:
        return None
    return ROOT / "dumps" / lab["track"] / target


def cmd_build(args: argparse.Namespace) -> int:
    """Собрать реальную ИБ 1С из выгрузки: создать базу, залить конфигурацию, проверить."""
    src = _dump_dir(args.target)
    if src is None:
        print("не знаю такой лабы или трека:", args.target)
        return 2
    if not (src / "Configuration.xml").exists():
        print("нет выгрузки", src, "— сначала python run_lab.py track <трек>")
        return 2
    try:
        ones_real.preflight()
    except ones_real.OneSError as exc:
        print("1С:", exc)
        return 3
    warn = ones_real.license_warning()
    if warn:
        print("  предупреждение:", warn)
    name = args.ib or args.target
    print(f"ИБ {name} <- {src}")
    r = ones_real.create_ib(name, force=args.force)
    print("  create:", "ok" if r.ok else f"rc={r.rc} {r.log}")
    try:
        r = ones_real.load_config(name, src, timeout=args.timeout)
    except ones_real.OneSError as exc:
        print("  load:", exc)
        return 3
    print("  load:  ", "ok" if r.ok else f"rc={r.rc} {r.log}")
    if not r.ok:
        return 3
    r = ones_real.check_config(name)
    print("  check: ", "ok" if r.ok else f"rc={r.rc}")
    if r.log:
        print("   ", r.log[:2000])
    print(f"  готово: {ones_real.ib_path(name)}")
    return 0 if r.ok else 1


def main() -> int:
    p = argparse.ArgumentParser(description="Муха закрывает лабораторные по 1С")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="список лабораторных и треков")
    r = sub.add_parser("run", help="прогон одной лабораторной")
    r.add_argument("id")
    r.add_argument("--agent", choices=["oracle", "fly", "flywire"], default="oracle")
    r.add_argument("--episodes", type=int, default=40)
    r.add_argument("--no-dump", action="store_true")
    t = sub.add_parser("track", help="прогон всего трека конфигурации")
    t.add_argument("name", choices=list(TRACKS))
    t.add_argument("--agent", choices=["oracle", "fly", "flywire"], default="oracle")
    t.add_argument("--episodes", type=int, default=30)
    t.add_argument("--no-dump", action="store_true")
    b = sub.add_parser("build", help="собрать реальную ИБ 1С (трек целиком или одна лаба)")
    b.add_argument("target", help="трек (uchebnaya/moi_sobytiya/uchet_ds) или id лабы")
    b.add_argument("--ib", default=None, help="имя ИБ в папке ib/")
    b.add_argument("--force", action="store_true", help="пересоздать ИБ с нуля")
    b.add_argument("--timeout", type=int, default=1800)
    sd = sub.add_parser("seed", help="залить данные лабораторных в собранную ИБ")
    sd.add_argument("target", help="трек или id лабы")
    sd.add_argument("--ib", default=None)
    sd.add_argument("--timeout", type=int, default=900)
    st = sub.add_parser("stage", help="сцена: муха печатает лабу, слева 1С")
    st.add_argument("--episodes", type=int, default=25)
    st.add_argument("--labs", default=None, help="список id через запятую")
    st.add_argument("--lite", action="store_true", help="облегчённая модель мухи")
    st.add_argument("--cdn", action="store_true", help="three.js с CDN, а не внутри файла")
    op = sub.add_parser("open", help="открыть собранную ИБ в 1С")
    op.add_argument("target", help="трек или id лабы")
    op.add_argument("--ib", default=None)
    op.add_argument("--designer", action="store_true", help="открыть конфигуратор")
    sub.add_parser("home", help="стартовая страница: всё сразу")
    sub.add_parser("cinema", help="студийная картинка: муха и объём мозга")
    sub.add_parser("lab", help="лаборатория коннектома: анатомия цепи + живой LIF")
    sub.add_parser("platform", help="что с платформой 1С и лицензией")
    lv = sub.add_parser("live", help="анимация: мозг мухи + шаги в 1С")
    lv.add_argument("id")
    lv.add_argument("--episodes", type=int, default=25)
    rp = sub.add_parser("report", help="прогон + HTML-визуализация в report/")
    rp.add_argument("--episodes", type=int, default=30)
    rp.add_argument("--agent", choices=["flywire", "fly"], default="flywire")
    a = sub.add_parser("all", help="прогнать все треки подряд")
    a.add_argument("--agent", choices=["oracle", "fly", "flywire"], default="oracle")
    a.add_argument("--episodes", type=int, default=30)
    a.add_argument("--no-dump", action="store_true")
    args = p.parse_args()
    if args.cmd == "list":
        return cmd_list(args)
    if args.cmd == "run":
        return cmd_run(args)
    if args.cmd == "track":
        return cmd_track(args)
    if args.cmd == "all":
        return cmd_all(args)
    if args.cmd == "build":
        return cmd_build(args)
    if args.cmd == "platform":
        return cmd_platform(args)
    if args.cmd == "lab":
        return cmd_lab(args)
    if args.cmd == "cinema":
        return cmd_cinema(args)
    if args.cmd == "home":
        return cmd_home(args)
    if args.cmd == "stage":
        return cmd_stage(args)
    if args.cmd == "open":
        return cmd_open(args)
    if args.cmd == "seed":
        return cmd_seed(args)
    if args.cmd == "report":
        return cmd_report(args)
    if args.cmd == "live":
        return cmd_live(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
