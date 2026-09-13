from __future__ import annotations

import json
from pathlib import Path

V8_CANDIDATES = [
    Path(r"C:\Program Files\1cv8"),
    Path(r"C:\Program Files (x86)\1cv8"),
    Path(r"C:\Program Files\1cv82"),
]


def find_1cv8() -> Path | None:
    found: list[Path] = []
    for root in V8_CANDIDATES:
        if not root.exists():
            continue
        found.extend(root.glob("*/bin/1cv8.exe"))
        found.extend(root.glob("*/bin/1cv8c.exe"))
    if not found:
        return None
    found.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return found[0]


def designer_load_cmd(ib_path: Path, dump_dir: Path, v8: Path | None = None) -> str:
    exe = v8 or find_1cv8()
    if exe is None:
        exe = Path(r"C:\Program Files\1cv8\8.3.xx.xxxx\bin\1cv8.exe")
    return (
        f'"{exe}" DESIGNER /F "{ib_path}" '
        f'/LoadConfigFromFiles "{dump_dir}" /UpdateDBCfg /Out "{dump_dir / "load.log"}"'
    )


def write_vm_loader(dump_dir: Path, ib_name: str = "Учебная") -> Path:
    v8 = find_1cv8()
    ib = Path(r"C:\1C") / ib_name
    cmd = designer_load_cmd(ib, dump_dir, v8)
    script = dump_dir / "load_into_1c.cmd"
    script.write_text(
        "@echo off\r\n"
        "REM Запускать ВНУТРИ ВМ, когда платформа 8.3 уже стоит.\r\n"
        "REM Сначала создай пустую файловую ИБ в C:\\1C\\%IB% через стартер 1С.\r\n"
        f"set IB={ib_name}\r\n"
        f"{cmd}\r\n"
        "echo Load finished. See load.log\r\n"
        "pause\r\n",
        encoding="utf-8",
    )
    return script


def write_status(path: Path) -> dict:
    exe = find_1cv8()
    info = {
        "platform_found": exe is not None,
        "platform_path": str(exe) if exe else None,
    }
    path.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    return info
