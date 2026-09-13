"""Установка платформы 1С из дистрибутива и подключение её к проекту.

Умеет: zip с учебной версией (training_8_3_x_Windows.zip), распакованную папку,
setup.exe или сразу «1CEnterprise 8.msi».

    python install_1c.py "C:\\Users\\Reaper\\Downloads\\training_8_3_27_1508_Windows.zip"
    python install_1c.py --check

После установки сам проверяет, видит ли проект платформу и нужна ли ей лицензия.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from fly1c import ones_real  # noqa: E402

UNPACK = ROOT / "1С" / "distrib"


def _find_installer(folder: Path) -> Path | None:
    for pattern in ("**/1CEnterprise 8.msi", "**/setup.exe", "**/*.msi"):
        hits = sorted(folder.glob(pattern))
        if hits:
            return hits[0]
    return None


def unpack(archive: Path) -> Path:
    UNPACK.mkdir(parents=True, exist_ok=True)
    target = UNPACK / archive.stem
    if target.exists() and any(target.iterdir()):
        print(f"уже распаковано: {target}")
        return target
    print(f"распаковываю {archive.name} -> {target}")
    with zipfile.ZipFile(archive) as z:
        z.extractall(target)
    return target


def install(installer: Path, silent: bool = True) -> int:
    """msi ставим тихо, setup.exe — как есть (он сам дальше зовёт msi)."""
    if installer.suffix.lower() == ".msi":
        cmd = ["msiexec", "/i", str(installer), "/passive", "/norestart"]
        if silent:
            cmd[-2:-1] = ["/qb"]
    else:
        cmd = [str(installer)]
    print("запускаю:", " ".join(cmd))
    print("установщику нужны права администратора — подтверди запрос UAC.")
    proc = subprocess.run(cmd)
    return proc.returncode


def report() -> int:
    info = ones_real.status()
    print()
    print("платформа:", info["platform_path"] or "не найдена")
    print("версия:   ", info["version"] or "-")
    print("лицензия: ", "есть" if info["licensed"] else "нет")
    if not info["platform_found"]:
        print("\nПроект ищет 1С в govno/1С/<версия>/bin и в Program Files/1cv8.")
        return 2
    if not info["licensed"]:
        print(
            "\nУ учебной версии защиты нет — если лицензия всё ещё «нет», значит "
            "найдена коммерческая платформа. Проверь, какая версия подхватилась."
        )
    print("\nдальше:  python run_lab.py build uchebnaya")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Поставить 1С и подключить к проекту")
    p.add_argument("source", nargs="?", help="zip, папка дистрибутива, setup.exe или .msi")
    p.add_argument("--check", action="store_true", help="только показать, что видит проект")
    args = p.parse_args()

    if args.check or not args.source:
        return report()

    src = Path(args.source)
    if not src.exists():
        print("нет такого файла:", src)
        return 2
    if src.is_file() and src.suffix.lower() == ".zip":
        src = unpack(src)
    if src.is_dir():
        installer = _find_installer(src)
        if installer is None:
            print("в папке нет ни setup.exe, ни msi:", src)
            return 2
    else:
        installer = src

    rc = install(installer)
    print("установщик вернул", rc)
    return report()


if __name__ == "__main__":
    raise SystemExit(main())
