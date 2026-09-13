"""Скриншоты страниц для README: открываем в браузере и снимаем окно.

    python tools/screenshot.py                     все страницы
    python tools/screenshot.py stage lab           только выбранные

Страница открывается в Edge в режиме приложения (без вкладок и панелей) с заданным
размером окна, ждём отрисовки и снимаем прямоугольник этого окна. Иначе WebGL-панели
снять нечем: html2canvas не видит содержимое трёхмерных сцен без лишних плясок.

Важно: во время съёмки рабочий стол должен быть свободен. Если поверх висит
полноэкранное приложение, окно браузера не выйдет на передний план — инструмент
это заметит и ничего не сохранит, чтобы не снять чужой экран.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "report"
DOCS = ROOT / "docs"

EDGE = [
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
]

# страница -> (файл, ширина, высота, ожидание, кусок заголовка окна)
PAGES = {
    "stage": ("stage.png", 1440, 900, 16, "Муха и 1С"),
    "lab": ("lab.png", 1440, 900, 11, "Лаборатория"),
    "cinema": ("fly.png", 1440, 820, 13, "студия"),
    "home": ("home.png", 1200, 900, 6, "старт"),
}

# снимаем строго окно браузера по его дескриптору: полноэкранный захват утащил бы
# всё, что у человека открыто на рабочем столе
CAPTURE = r"""
Add-Type -AssemblyName System.Drawing
$src = @'
using System;
using System.Runtime.InteropServices;
public class Win {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [StructLayout(LayoutKind.Sequential)]
  public struct RECT { public int Left, Top, Right, Bottom; }
}
'@
Add-Type -TypeDefinition $src -Language CSharp
$proc = Get-Process -Id __PID__ -ErrorAction SilentlyContinue
if (-not $proc) { Write-Output "NOWINDOW"; exit }
$h = $proc.MainWindowHandle
if ($h -eq 0) {
  $h = (Get-Process msedge, chrome -ErrorAction SilentlyContinue |
        Where-Object { $_.MainWindowTitle -like '*__TITLE__*' } |
        Select-Object -First 1).MainWindowHandle
}
if (-not $h -or $h -eq 0) { Write-Output "NOWINDOW"; exit }
[Win]::ShowWindow($h, 5) | Out-Null
[Win]::SetForegroundWindow($h) | Out-Null
Start-Sleep -Milliseconds 900
# если окно так и не вышло вперёд (например, поверх полноэкранная игра),
# снимать нельзя: в кадр попадёт чужой экран
if ([Win]::GetForegroundWindow() -ne $h) { Write-Output "NOTFRONT"; exit }
$r = New-Object Win+RECT
[Win]::GetWindowRect($h, [ref]$r) | Out-Null
$w = $r.Right - $r.Left; $hh = $r.Bottom - $r.Top
if ($w -lt 200 -or $hh -lt 200) { Write-Output "NOWINDOW"; exit }
$bmp = New-Object System.Drawing.Bitmap($w, $hh)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($r.Left, $r.Top, 0, 0, $bmp.Size)
$bmp.Save('__OUT__', [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $bmp.Dispose()
Write-Output "OK"
"""


def browser() -> Path:
    for path in EDGE:
        if path.exists():
            return path
    raise SystemExit("не нашёл Edge или Chrome — поправь список EDGE в этом файле")


def shoot(name: str) -> None:
    out_name, width, height, wait, title = PAGES[name]
    page = REPORT / f"{name}.html"
    if not page.exists():
        print(f"  нет страницы {page.name} — собери её через run_lab.py")
        return
    DOCS.mkdir(exist_ok=True)
    out = DOCS / out_name
    proc = subprocess.Popen([
        str(browser()),
        f"--app=file:///{page.as_posix()}",
        f"--window-size={width},{height}",
        "--window-position=0,0",
        "--new-window",
        "--disable-features=Translate",
    ])
    try:
        print(f"  {name}: жду отрисовки {wait} с …", flush=True)
        time.sleep(wait)
        script = (CAPTURE.replace("__PID__", str(proc.pid))
                  .replace("__TITLE__", title)
                  .replace("__OUT__", str(out).replace("\\", "\\\\")))
        res = subprocess.run(["powershell", "-NoProfile", "-Command", script],
                             capture_output=True, text=True)
        answer = res.stdout or ""
        if "NOTFRONT" in answer:
            print(f"  {name}: окно не вышло на передний план (полноэкранное приложение?) — "
                  "снимок не сделан, чтобы не снять чужой экран")
            return
        if "NOWINDOW" in answer or not out.exists():
            print(f"  {name}: окно браузера не найдено, снимок не сделан")
            return
        print(f"  {name}: {out} ({out.stat().st_size // 1024} КБ)")
    finally:
        proc.terminate()
        time.sleep(1)


def main() -> int:
    names = sys.argv[1:] or list(PAGES)
    for name in names:
        if name not in PAGES:
            print(f"не знаю страницу {name}; есть: {', '.join(PAGES)}")
            continue
        shoot(name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
