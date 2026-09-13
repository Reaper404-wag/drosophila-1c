"""Запись таймлапса: муха проходит лабораторную, кадр пишется в docs/timelapse.mp4.

    python tools/record.py                 лаба 10_ms_lab1, скорость ×4, 20 секунд
    python tools/record.py 20_ds_lab1 26      другая лаба и длительность

Страница открывается в отдельном окне Edge с заданной скоростью, окно выводится
вперёд, и ffmpeg снимает именно его. Во время записи не трогай мышь и не переключай
окна: захват идёт с экрана, всё лишнее попадёт в кадр.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

REPORT = ROOT / "report"
DOCS = ROOT / "docs"
PAGE = REPORT / "cap_timelapse.html"
TITLE = "Муха и 1С"
WIDTH, HEIGHT = 1440, 780

FOREGROUND = r"""
Add-Type -AssemblyName System.Drawing
$src = @'
using System;
using System.Runtime.InteropServices;
public class Fg {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [StructLayout(LayoutKind.Sequential)]
  public struct RECT { public int Left, Top, Right, Bottom; }
}
'@
Add-Type -TypeDefinition $src -Language CSharp
$p = $null
foreach ($i in 1..10) {
  $p = Get-Process | Where-Object { $_.MainWindowTitle -like '*__TITLE__*' } | Select-Object -First 1
  if ($p) { break }
  Start-Sleep -Milliseconds 800
}
if (-not $p) { Write-Output "NOWINDOW"; exit }
$h = $p.MainWindowHandle
# SW_RESTORE + AppActivate: обычный SetForegroundWindow из фонового процесса
# Windows часто отклоняет
[Fg]::ShowWindow($h, 9) | Out-Null
Add-Type -AssemblyName Microsoft.VisualBasic
try { [Microsoft.VisualBasic.Interaction]::AppActivate($p.Id) } catch {}
[Fg]::SetForegroundWindow($h) | Out-Null
Start-Sleep -Milliseconds 1200
if ([Fg]::GetForegroundWindow() -ne $h) { Write-Output "NOTFRONT"; exit }
$r = New-Object Fg+RECT
[Fg]::GetWindowRect($h, [ref]$r) | Out-Null
Write-Output ("RECT {0} {1} {2} {3}" -f $r.Left, $r.Top, ($r.Right - $r.Left), ($r.Bottom - $r.Top))
"""


def build_page(lab_id: str, speed: int = 2, delay_ms: int = 16000) -> int:
    """Копия сцены: лаба выбрана, но прогон стартует через delay_ms.

    Пауза обязательна: страница грузится секунд десять, и без неё муха успевает
    закрыть лабораторную ещё до того, как ffmpeg снимет первый кадр.
    """
    from fly1c import ones_real, viz_fly3d, viz_stage

    data = json.loads((REPORT / "stage.json").read_text(encoding="utf-8"))
    index = next((i for i, lab in enumerate(data["labs"]) if lab["id"] == lab_id), 0)
    html = (viz_stage.PAGE
            .replace("__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
            .replace("__IBDIR__", json.dumps(str(ones_real.IB_DIR), ensure_ascii=False))
            .replace("<script>__THREE__</script>", "<script>" + viz_fly3d.three_js() + "</script>")
            .replace("__FLYDATA__", viz_fly3d.fly_data_js(lite=True))
            .replace("__RIG__", viz_fly3d.RIG_JS))
    html = html.replace(
        "pick(0);\nrequestAnimationFrame(loop);",
        f"sel.value = '{index}';\npick({index});\nplaying = false;\n"
        f"speed = {speed};\ndocument.getElementById('speed').value = '{speed}';\n"
        f"setTimeout(() => {{ pick({index}); playing = true; }}, {delay_ms});\n"
        "requestAnimationFrame(loop);")
    PAGE.write_text(html, encoding="utf-8")
    return index


def window_rect() -> tuple[int, int, int, int] | None:
    res = subprocess.run(["powershell", "-NoProfile", "-Command",
                          FOREGROUND.replace("__TITLE__", TITLE)],
                         capture_output=True, text=True)
    out = (res.stdout or "").strip()
    if out.startswith("RECT"):
        _, x, y, w, h = out.split()
        return int(x), int(y), int(w), int(h)
    if "NOTFRONT" in out:
        print("  окно не вышло вперёд — запись отменена, чтобы не снять чужой экран")
    else:
        print("  окно браузера не найдено")
    return None


WAIT = 14          # сколько ждём загрузки страницы перед записью
LEAD = 2           # запас: прогон стартует уже под запись


def record(lab_id: str, seconds: int) -> int:
    DOCS.mkdir(exist_ok=True)
    out = DOCS / "timelapse.mp4"
    build_page(lab_id, speed=4, delay_ms=(WAIT + LEAD) * 1000)
    profile = Path(tempfile.gettempdir()) / "fly1c-shots"
    edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    if not edge.exists():
        edge = Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe")
    proc = subprocess.Popen([
        str(edge), f"--app=file:///{PAGE.as_posix()}",
        f"--window-size={WIDTH},{HEIGHT}", "--window-position=0,0", "--new-window",
        f"--user-data-dir={profile}", "--no-first-run", "--no-default-browser-check",
    ])
    try:
        print("  жду загрузки страницы…", flush=True)
        time.sleep(WAIT)
        rect = window_rect()
        if rect is None:
            return 2
        x, y, w, h = rect
        # снимаем область экрана строго по окну; чётные размеры нужны кодеку
        w -= w % 2
        h -= h % 2
        print(f"  пишу {seconds} с с области {w}x{h} в {x},{y} - не трогай экран", flush=True)
        cmd = [
            "ffmpeg", "-y", "-f", "gdigrab", "-framerate", "20",
            "-offset_x", str(x), "-offset_y", str(y), "-video_size", f"{w}x{h}",
            "-i", "desktop", "-t", str(seconds),
            "-vf", "crop=iw-16:ih-48:8:40,scale=1280:-2",
            "-c:v", "libx264", "-preset", "medium", "-crf", "23",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(res.stderr[-1200:])
            return 3
        print(f"  готово: {out} ({out.stat().st_size // 1024} КБ)")
        return 0
    finally:
        proc.terminate()
        time.sleep(1)
        PAGE.unlink(missing_ok=True)


if __name__ == "__main__":
    lab = sys.argv[1] if len(sys.argv) > 1 else "10_ms_lab1"
    secs = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    raise SystemExit(record(lab, secs))
