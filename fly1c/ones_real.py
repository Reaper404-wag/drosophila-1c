"""Настоящая платформа 1С на хосте: создать ИБ, залить конфигурацию из XML, проверить.

Батч-режим 1cv8.exe: CREATEINFOBASE / DESIGNER. Всё пишется в .log рядом с ИБ.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# учебная платформа ставит 1cv8t.exe, коммерческая — 1cv8.exe
EXE_NAMES = ("1cv8t.exe", "1cv8.exe")

PLATFORM_ROOTS = [
    ROOT / "1Cexe",
    ROOT / "1С",
    Path(r"C:\Program Files\1cv8"),
    Path(r"C:\Program Files (x86)\1cv8"),
    Path(r"C:\Program Files\1cv82"),
]

IB_DIR = ROOT / "ib"
LOG_DIR = ROOT / "logs"


class OneSError(RuntimeError):
    pass


LICENSE_MARKERS = ("не найдена лицензия", "ключ защиты", "license not found")


@dataclass
class RunResult:
    rc: int
    log: str
    cmd: list[str]

    @property
    def ok(self) -> bool:
        return self.rc == 0 and not self.license_missing

    @property
    def license_missing(self) -> bool:
        low = self.log.lower()
        return any(m in low for m in LICENSE_MARKERS)


def find_platform(explicit: str | Path | None = None) -> Path | None:
    """Путь к 1cv8.exe. Сначала копия платформы в проекте, потом стандартные места."""
    if explicit:
        p = Path(explicit)
        if p.is_file():
            return p
        if p.is_dir():
            hits = [h for name in EXE_NAMES for h in sorted(p.glob(f"**/bin/{name}"))]
            if hits:
                return hits[-1]
        raise OneSError(f"1cv8.exe не найден по пути {explicit}")
    found: list[Path] = []
    for root in PLATFORM_ROOTS:
        if not root.exists():
            continue
        for name in EXE_NAMES:
            found.extend(root.glob(f"*/bin/{name}"))
            found.extend(root.glob(f"bin/{name}"))
    if not found:
        return None
    # учебная идёт первой: ей не нужна лицензия, а значит батч-режим реально стартует
    found.sort(key=lambda p: (p.name.lower() != "1cv8t.exe", p.parent.parent.name))
    return found[0]


def platform_version(exe: Path | None = None) -> str | None:
    exe = exe or find_platform()
    if exe is None:
        return None
    return exe.parent.parent.name


def _cmdline(args: list[str]) -> str:
    parts = []
    for a in args:
        if a.startswith("File=") or a.startswith('"'):
            parts.append(a)  # уже в том виде, в каком ждёт 1С
        elif " " in a:
            parts.append(f'"{a}"')
        else:
            parts.append(a)
    return " ".join(parts)


def _watch_windows(pid: int) -> list[str]:
    """Заголовки окон процесса — чтобы поймать модалку вместо зависания на полчаса."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    titles: list[str] = []
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(hwnd, _):
        out = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(out))
        if out.value == pid:
            buf = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(hwnd, buf, 512)
            if buf.value:
                titles.append(buf.value)
        return True

    try:
        user32.EnumWindows(WNDENUMPROC(cb), 0)
    except OSError:
        pass
    return titles


BLOCKING_WINDOWS = ("лиценз", "licen", "регистрац")


def _run(args: list[str], log_path: Path, timeout: int = 1800) -> RunResult:
    """Запуск 1С в батч-режиме под присмотром: если вылезла модалка про лицензию —
    гасим процесс и говорим об этом, а не висим до таймаута."""
    import time

    log_path.parent.mkdir(parents=True, exist_ok=True)
    if log_path.exists():
        log_path.unlink()
    cmd = args + ["/Out", str(log_path), "/DisableStartupMessages", "/DisableStartupDialogs"]
    # 1С разбирает командную строку сама: строку соединения вида File="...";
    # нельзя отдавать списком — Windows экранирует внутренние кавычки и 1С их не понимает
    proc = subprocess.Popen(_cmdline(cmd), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    deadline = time.time() + timeout
    blocked = None
    while proc.poll() is None:
        if time.time() > deadline:
            proc.kill()
            raise OneSError(f"1С не ответила за {timeout} с: {' '.join(cmd)}")
        time.sleep(1.0)
        for title in _watch_windows(proc.pid):
            low = title.lower()
            if any(w in low for w in BLOCKING_WINDOWS):
                blocked = title
                break
        if blocked:
            proc.kill()
            raise OneSError(
                f"1С открыла окно {blocked!r} — платформе нужна лицензия, "
                "батч-режим невозможен. См. `python run_lab.py platform`."
            )
    rc = proc.returncode
    text = ""
    if log_path.exists():
        for enc in ("utf-8-sig", "utf-8", "cp1251"):
            try:
                text = log_path.read_text(encoding=enc).strip()
                break
            except UnicodeDecodeError:
                continue
    return RunResult(rc, text, cmd)


def is_training(exe: Path | None = None) -> bool:
    """Учебная версия: защиты у неё нет, лицензия не нужна вообще."""
    exe = exe or find_platform()
    if exe is None:
        return False
    marker = str(exe).lower()
    if exe.name.lower() == "1cv8t.exe" or "training" in marker or "учебн" in marker:
        return True
    return (exe.parent / "1cv8t.exe").exists()


def preflight() -> None:
    """Проверка перед батч-запуском: платформа на месте."""
    if find_platform() is None:
        raise OneSError("платформа 1С не найдена (ждём её в govno/1С/<версия>/bin/1cv8.exe)")


def license_warning() -> str | None:
    """Текст предупреждения, если коммерческой платформе явно нечем лицензироваться.

    Учебную версию не трогаем — ей защита не нужна. Окончательный вердикт всё равно
    даёт сама 1С: её лог ловится через RunResult.license_missing.
    """
    if is_training() or licenses() or hasp_present():
        return None
    return (
        "лицензии не видно: ни программной в C:/ProgramData/1C/licenses, ни ключа защиты. "
        "Если это коммерческая платформа, батч-режим встанет на окне «Получение лицензии»."
    )


def hasp_present() -> bool:
    """Грубая проверка драйвера/ключа HASP."""
    import shutil

    return Path(r"C:\Windows\System32\hasplms.exe").exists() or bool(shutil.which("haspdinst"))


def ib_path(name: str) -> Path:
    return IB_DIR / name


def ib_exists(name: str) -> bool:
    return (ib_path(name) / "1Cv8.1CD").exists()


def create_ib(name: str, exe: Path | None = None, force: bool = False) -> RunResult:
    """Пустая файловая ИБ в ib/<name>. Если уже есть — ничего не делаем (force пересоздаёт)."""
    exe = exe or find_platform()
    if exe is None:
        raise OneSError("платформа 1С не найдена")
    target = ib_path(name)
    if ib_exists(name) and not force:
        return RunResult(0, f"ИБ уже есть: {target}", [])
    if force and target.exists():
        import shutil

        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    return _run(
        [str(exe), "CREATEINFOBASE", f'File="{target}";'],
        LOG_DIR / f"{name}.create.log",
        timeout=300,
    )


def load_config(name: str, src: Path, exe: Path | None = None, timeout: int = 1800) -> RunResult:
    """DESIGNER /LoadConfigFromFiles + /UpdateDBCfg — конфигурация реально компилируется."""
    exe = exe or find_platform()
    if exe is None:
        raise OneSError("платформа 1С не найдена")
    if not (src / "Configuration.xml").exists():
        raise OneSError(f"в {src} нет Configuration.xml")
    return _run(
        [
            str(exe),
            "DESIGNER",
            "/F",
            str(ib_path(name)),
            "/LoadConfigFromFiles",
            str(src),
            "/UpdateDBCfg",
        ],
        LOG_DIR / f"{name}.load.log",
        timeout=timeout,
    )


def check_config(name: str, exe: Path | None = None, timeout: int = 900) -> RunResult:
    """Синтаксический контроль модулей и проверка метаданных уже загруженной конфигурации."""
    exe = exe or find_platform()
    if exe is None:
        raise OneSError("платформа 1С не найдена")
    return _run(
        [
            str(exe),
            "DESIGNER",
            "/F",
            str(ib_path(name)),
            "/CheckConfig",
            "-ConfigLogIntegrity",
            "-IncorrectReferences",
            "-ThinClient",
            "-Server",
        ],
        LOG_DIR / f"{name}.check.log",
        timeout=timeout,
    )


def dump_config(name: str, out: Path, exe: Path | None = None, timeout: int = 900) -> RunResult:
    """Обратная выгрузка из ИБ в XML — чем 1С реально считает то, что мы залили."""
    exe = exe or find_platform()
    if exe is None:
        raise OneSError("платформа 1С не найдена")
    out.mkdir(parents=True, exist_ok=True)
    return _run(
        [str(exe), "DESIGNER", "/F", str(ib_path(name)), "/DumpConfigToFiles", str(out)],
        LOG_DIR / f"{name}.dump.log",
        timeout=timeout,
    )


def enterprise(name: str, start_param: str = "", exe: Path | None = None, timeout: int = 900) -> RunResult:
    """Запуск в режиме Предприятия с параметром запуска (для заполнения данных)."""
    exe = exe or find_platform()
    if exe is None:
        raise OneSError("платформа 1С не найдена")
    args = [str(exe), "ENTERPRISE", "/F", str(ib_path(name))]
    if start_param:
        args += ["/C", start_param]
    return _run(args, LOG_DIR / f"{name}.enterprise.log", timeout=timeout)


LICENSE_DIRS = [
    Path(r"C:\ProgramData\1C\licenses"),
    Path.home() / "AppData/Roaming/1C/licenses",
]


def licenses() -> list[str]:
    out = []
    for d in LICENSE_DIRS:
        if d.exists():
            out += [str(p) for p in d.glob("*.lic")]
    return out


def launch(name: str, designer: bool = False, exe: Path | None = None):
    """Открыть готовую ИБ окном — посмотреть глазами, что муха наделала."""
    exe = exe or find_platform()
    if exe is None:
        raise OneSError("платформа 1С не найдена")
    if not ib_exists(name):
        raise OneSError(f"нет ИБ {name} в {IB_DIR}")
    mode = "DESIGNER" if designer else "ENTERPRISE"
    return subprocess.Popen(_cmdline([str(exe), mode, "/F", str(ib_path(name))]))


def status() -> dict:
    exe = find_platform()
    lic = licenses()
    return {
        "licensed": bool(lic) or is_training(exe),
        "training": is_training(exe),
        "license_files": lic,
        "platform_found": exe is not None,
        "platform_path": str(exe) if exe else None,
        "version": platform_version(exe),
        "ib_dir": str(IB_DIR),
        "infobases": sorted(p.name for p in IB_DIR.glob("*") if (p / "1Cv8.1CD").exists())
        if IB_DIR.exists()
        else [],
    }


def write_status(path: Path) -> dict:
    info = status()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    return info
