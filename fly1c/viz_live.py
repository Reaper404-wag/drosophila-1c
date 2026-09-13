"""Живая визуализация: мозг мухи горит, в 1С по шагам появляются объекты."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PAGE = """<!doctype html><html lang="ru"><meta charset="utf-8">
<title>Муха делает лабораторную</title>
<style>
:root{--bg:#0e1116;--card:#161b22;--line:#232b36;--ink:#e6edf3;--dim:#8b949e;
--ok:#3fb950;--bad:#f85149;--fly:#d29922;--acc:#58a6ff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);padding:24px;
font:14px/1.5 "Segoe UI",system-ui,sans-serif}
h1{font-size:20px;margin:0 0 2px}
.sub{color:var(--dim);margin-bottom:18px;font-size:13px}
.wrap{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(280px,1fr);gap:16px}
.panel{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px}
canvas{width:100%;height:auto;background:#0d1117;border-radius:8px;display:block}
.ctl{display:flex;gap:10px;align-items:center;margin-top:12px;flex-wrap:wrap}
button{background:#21262d;color:var(--ink);border:1px solid var(--line);
border-radius:7px;padding:6px 14px;cursor:pointer;font:inherit}
button:hover{border-color:var(--acc)}
input[type=range]{flex:1;min-width:120px;accent-color:var(--fly)}
.stat{display:flex;gap:18px;color:var(--dim);font-size:12px;margin-top:10px;flex-wrap:wrap}
.stat b{color:var(--ink)}
.ops{max-height:300px;overflow:auto;margin:0;padding:0;list-style:none;font-size:13px}
.ops li{padding:4px 8px;border-radius:6px;color:var(--dim);
white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ops li.done{color:var(--ink)}
.ops li.now{background:#1f2937;color:#fff}
.ops li.fail{color:var(--bad)}
.dots{display:flex;flex-wrap:wrap;gap:4px;margin-top:8px}
.dot{width:13px;height:13px;border-radius:4px;background:#2b3440;transition:background .2s}
.dot.on{background:var(--ok)}
.lg{display:flex;gap:14px;color:var(--dim);font-size:12px;margin-top:10px;flex-wrap:wrap}
.lg i{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:5px}
h2{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--dim);
margin:0 0 8px;font-weight:600}
</style>
<h1>__TITLE__</h1>
<div class="sub">__SUB__</div>
<div class="wrap">
  <div class="panel">
    <canvas id="c" width="1440" height="840"></canvas>
    <div class="ctl">
      <button id="play">пауза</button>
      <button id="again">сначала</button>
      <input type="range" id="seek" min="0" value="0">
      <span id="pos" style="color:var(--dim);font-size:12px"></span>
    </div>
    <div class="lg">
      <span><i style="background:#58a6ff"></i>нейрон мозга</span>
      <span><i style="background:#d29922"></i>клетка Кеньона</span>
      <span><i style="background:#3fb950"></i>MBON</span>
      <span><i style="background:#f85149"></i>дофаминовый</span>
      <span><i style="background:#a371f7"></i>обонятельный</span>
    </div>
    <div class="stat">
      <span>спайков в этом такте: <b id="spk">—</b></span>
      <span>горит нейронов: <b id="fire">—</b></span>
      <span>нейронов в мозге: <b id="ntot">—</b></span>
    </div>
  </div>
  <div class="panel">
    <h2>что муха делает в 1С</h2>
    <ol class="ops" id="ops"></ol>
    <h2 style="margin-top:16px">проверки методички</h2>
    <div class="dots" id="checks"></div>
    <div class="stat"><span>пройдено: <b id="passed">0</b> из <b id="total">0</b></span></div>
  </div>
</div>
<script>
const DATA = __DATA__;
const cv = document.getElementById('c'), ctx = cv.getContext('2d');
const N = DATA.neurons.x.length, W = cv.width, H = cv.height;
const PAL = ['#58a6ff','#d29922','#3fb950','#f85149','#a371f7'];
const px = new Float32Array(N), py = new Float32Array(N);
for (let i = 0; i < N; i++) {
  px[i] = 30 + DATA.neurons.x[i] * (W - 60);
  py[i] = 30 + DATA.neurons.y[i] * (H - 60);
}
const heat = new Float32Array(N);
const ops = document.getElementById('ops'), checks = document.getElementById('checks');
DATA.frames.forEach((f, i) => {
  const li = document.createElement('li');
  li.textContent = (i + 1) + '. ' + f.op + (f.failed ? '  — не вышло' : '');
  if (f.failed) li.className = 'fail';
  ops.appendChild(li);
});
DATA.checks.forEach(m => {
  const d = document.createElement('div');
  d.className = 'dot'; d.title = m; checks.appendChild(d);
});
document.getElementById('total').textContent = DATA.checks.length;
document.getElementById('ntot').textContent = DATA.brain['нейронов'].toLocaleString('ru');
const seek = document.getElementById('seek');
seek.max = DATA.frames.length - 1;

let frame = 0, tick = 0, playing = true;
const HOLD = 26;

function paintFrame(i) {
  const f = DATA.frames[i];
  heat.fill(0);
  for (const n of f.fire) heat[n] = 1;
  document.getElementById('spk').textContent = f.spikes.toLocaleString('ru');
  document.getElementById('fire').textContent = f.fire.length.toLocaleString('ru');
  [...ops.children].forEach((li, k) => {
    li.classList.toggle('now', k === i);
    li.classList.toggle('done', k < i);
  });
  ops.children[i] && ops.children[i].scrollIntoView({block: 'nearest'});
  [...checks.children].forEach((d, k) => d.classList.toggle('on', !!f.mask[k]));
  document.getElementById('passed').textContent = f.mask.reduce((a, b) => a + b, 0);
  document.getElementById('pos').textContent = 'шаг ' + (i + 1) + ' из ' + DATA.frames.length;
  seek.value = i;
}

function draw() {
  ctx.fillStyle = '#0d1117';
  ctx.fillRect(0, 0, W, H);
  for (let i = 0; i < N; i++) {
    const k = DATA.neurons.k[i], h = heat[i];
    if (h < 0.02) {
      ctx.fillStyle = 'rgba(43,52,64,0.85)';
      ctx.fillRect(px[i] - 0.9, py[i] - 0.9, 1.8, 1.8);
      continue;
    }
    ctx.globalAlpha = 0.25 + 0.75 * h;
    ctx.fillStyle = PAL[k];
    ctx.beginPath();
    ctx.arc(px[i], py[i], (k ? 2.6 : 1.8) + 2.2 * h, 0, 6.2832);
    ctx.fill();
    ctx.globalAlpha = 1;
    heat[i] = h * 0.9;
  }
}

function loop() {
  if (playing) {
    if (tick % HOLD === 0) {
      paintFrame(frame);
      frame = (frame + 1) % DATA.frames.length;
    }
    tick++;
  }
  draw();
  requestAnimationFrame(loop);
}
document.getElementById('play').onclick = e => {
  playing = !playing;
  e.target.textContent = playing ? 'пауза' : 'играть';
};
document.getElementById('again').onclick = () => { frame = 0; tick = 0; };
seek.oninput = () => { frame = +seek.value; tick = 0; paintFrame(frame); frame++; playing = false;
  document.getElementById('play').textContent = 'играть'; };
paintFrame(0);
loop();
</script>
</html>"""


def build(trace_data: dict[str, Any], out: Path) -> Path:
    brain = trace_data["brain"]
    sub = (
        f'коннектом FlyWire v783 · {brain["нейронов"]} нейронов, '
        f'{brain["синаптических связей"]} синаптических связей · '
        f'{brain["клеток Кеньона"]} клеток Кеньона выбирают следующую операцию · '
        "каждый такт — LIF-симуляция реального мозга мухи"
    ).replace(str(brain["нейронов"]), f'{brain["нейронов"]:,}'.replace(",", " ")).replace(
        str(brain["синаптических связей"]),
        f'{brain["синаптических связей"]:,}'.replace(",", " "),
    )
    html = (
        PAGE.replace("__TITLE__", f'{trace_data["lab"]} — {trace_data["title"]}')
        .replace("__SUB__", sub)
        .replace("__DATA__", json.dumps(trace_data, ensure_ascii=False, separators=(",", ":")))
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out
