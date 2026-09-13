"""Лаборатория коннектома: реальная анатомия цепи мухи и живая LIF-симуляция в браузере.

Точки — настоящие координаты синапсов FlyWire v783, связи — измеренные контакты между
этими нейронами. Симуляция считается прямо на странице, поэтому напряжения и спайки
в инспекторе живые.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
CONNECTOME = ROOT / "connectome"

PAGE = r"""<!doctype html><html lang="ru"><meta charset="utf-8">
<title>Лаборатория коннектома</title>
<style>
:root{--bg:#0b0f14;--panel:#111823;--line:#1e2a38;--ink:#dfe8f2;--dim:#7d90a6;
--ok:#31d67f;--warn:#ffd200;--kc:#ffd200;--mbon:#5cc8ff;--dan:#ff6b5e;--orn:#c084fc;--pn:#31d67f}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:12.5px/1.5 "Cascadia Mono",Consolas,ui-monospace,monospace}
.top{display:flex;align-items:baseline;gap:14px;padding:10px 14px;border-bottom:1px solid var(--line)}
.brand{font-size:19px;font-weight:700;letter-spacing:.04em}
.brand b{color:var(--warn)}
.path{color:var(--dim);letter-spacing:.06em}
.live{margin-left:auto;color:var(--ok);letter-spacing:.1em}
.ctl{display:flex;gap:16px;align-items:center;padding:6px 14px;border-bottom:1px solid var(--line);
color:var(--dim)}
.ctl label{display:flex;gap:6px;align-items:center;cursor:pointer}
.ctl button{margin-left:auto;background:#16202c;color:var(--ink);border:1px solid var(--line);
border-radius:3px;padding:4px 10px;font:inherit;cursor:pointer}
.wrap{display:grid;grid-template-columns:minmax(0,1.45fr) minmax(330px,1fr);gap:12px;padding:12px}
.stage{position:relative;border:1px solid var(--line);border-radius:3px;background:#080c11}
.stage .cap{position:absolute;left:10px;top:8px;color:var(--dim);letter-spacing:.08em;font-size:11px}
canvas{display:block;width:100%;height:auto}
.legend{position:absolute;left:10px;bottom:8px;display:flex;gap:14px;flex-wrap:wrap;font-size:11px;
color:var(--dim)}
.legend i{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:5px}
.card{border:1px solid var(--line);border-radius:3px;background:var(--panel);margin-bottom:10px}
.card h3{margin:0;padding:6px 10px;font-size:11px;letter-spacing:.1em;color:var(--dim);
font-weight:600;border-bottom:1px solid var(--line)}
.card .b{padding:9px 10px}
.kv{display:grid;grid-template-columns:1fr auto;gap:2px 10px}
.kv span{color:var(--dim)}
.kv b{font-weight:600;font-variant-numeric:tabular-nums}
.state{padding:7px 10px;color:var(--warn);border-bottom:1px solid var(--line);letter-spacing:.05em}
table{border-collapse:collapse;width:100%;font-size:11.5px}
th{text-align:left;color:var(--dim);font-weight:600;border-bottom:1px solid var(--line);padding:4px 8px}
td{padding:3px 8px;border-bottom:1px solid #16202c;font-variant-numeric:tabular-nums}
tr.hot td{color:var(--warn)}
.foot{color:var(--dim);padding:4px 14px 14px;font-size:11px;display:flex;gap:16px;flex-wrap:wrap}
</style>
<div class="top">
  <span class="brand">МУХА<b>·</b>КОННЕКТОМ</span>
  <span class="path">ЛАБОРАТОРИЯ &nbsp;/&nbsp; FlyWire v783 &nbsp;/&nbsp; FAFB</span>
  <span class="live" id="live">ЖИВОЕ ПОДКЛЮЧЕНИЕ</span>
</div>
<div class="ctl">
  <label><input type="checkbox" id="out" checked> выход мозга включён</label>
  <label><input type="checkbox" id="mute"> заглушить клетки Кеньона (эксперимент)</label>
  <label><input type="checkbox" id="rot"> вращать анатомию</label>
  <button id="shot">Сохранить кадр</button>
</div>
<div class="wrap">
  <div class="stage">
    <div class="cap">МОЗГ МУХИ / РЕАЛЬНАЯ АНАТОМИЯ ПО СИНАПСАМ</div>
    <canvas id="c" width="1180" height="900"></canvas>
    <div class="legend" id="legend"></div>
  </div>
  <div>
    <div class="card">
      <div class="b kv" id="tele"></div>
    </div>
    <div class="state" id="state">ЗАПАХ ПОДАН / ГРИБОВИДНОЕ ТЕЛО ОТВЕЧАЕТ</div>
    <div class="card">
      <h3>ВХОД (ЗАПАХ) / ОТВЕТ ГРИБОВИДНОГО ТЕЛА</h3>
      <canvas id="trace" width="640" height="150"></canvas>
    </div>
    <div class="card">
      <h3>ИНСПЕКТОР НЕЙРОНОВ — самые активные клетки</h3>
      <table><thead><tr><th>Body ID</th><th>Тип клетки</th><th>Напряжение*</th><th>Спайки</th></tr></thead>
      <tbody id="insp"></tbody></table>
    </div>
  </div>
</div>
<div class="foot" id="foot"></div>
<script>
const C = __CIRCUIT__;
const BG = __BG__;

/* ---------- анатомия ---------- */
const cv = document.getElementById('c'), ctx = cv.getContext('2d');
const W = cv.width, H = cv.height;
const COL = ['#c084fc', '#31d67f', '#ffd200', '#5cc8ff', '#ff6b5e'];
const raw = atob(C.points);
const pts = new Uint16Array(new Uint8Array([...raw].map(c => c.charCodeAt(0))).buffer);
const NP = pts.length / 3;
const bgRaw = atob(BG.p);
const bgPts = new Uint16Array(new Uint8Array([...bgRaw].map(c => c.charCodeAt(0))).buffer);

/* индексы точек по нейронам */
const start = new Int32Array(C.neurons.length + 1);
for (let i = 0; i < C.neurons.length; i++) start[i + 1] = start[i] + C.neurons[i].n;

/* обе выборки приводим к одной мировой системе: у цепи и у фона разные габариты */
const LO = C.lo, SP = C.span, BLO = BG.lo, BSP = BG.span;
function toWorld(arr, n, lo, sp) {
  const out = new Float32Array(n * 3);
  for (let i = 0; i < n; i++)
    for (let a = 0; a < 3; a++) out[i * 3 + a] = lo[a] + arr[i * 3 + a] / 65535 * sp[a];
  return out;
}
const NB = bgPts.length / 3;
const WC = toWorld(pts, NP, LO, SP);
const WB = toWorld(bgPts, NB, BLO, BSP);
const gmin = [Infinity, Infinity, Infinity], gmax = [-Infinity, -Infinity, -Infinity];
for (const arr of [WC, WB])
  for (let i = 0; i < arr.length; i += 3)
    for (let a = 0; a < 3; a++) {
      if (arr[i + a] < gmin[a]) gmin[a] = arr[i + a];
      if (arr[i + a] > gmax[a]) gmax[a] = arr[i + a];
    }
const gspan = gmax.map((v, a) => Math.max(1, v - gmin[a]));
/* кадр строим по самой цепи — фон мозга пусть уходит за края */
const cmin = [Infinity, Infinity, Infinity], cmax = [-Infinity, -Infinity, -Infinity];
for (let i = 0; i < WC.length; i += 3)
  for (let a = 0; a < 3; a++) {
    if (WC[i + a] < cmin[a]) cmin[a] = WC[i + a];
    if (WC[i + a] > cmax[a]) cmax[a] = WC[i + a];
  }
const cmid = cmin.map((v, a) => (v + cmax[a]) / 2);
const scaleAll = Math.max(cmax[0] - cmin[0], cmax[1] - cmin[1]) * 1.5;

let angle = 0;
const SX = new Float32Array(NP), SY = new Float32Array(NP);
const BX = new Float32Array(bgPts.length / 3), BY = new Float32Array(bgPts.length / 3);
function project() {
  const ca = Math.cos(angle), sa = Math.sin(angle);
  const put = (arr, n, X, Y) => {
    for (let i = 0; i < n; i++) {
      const x = (arr[i * 3] - cmid[0]) / scaleAll;
      const y = (arr[i * 3 + 1] - cmid[1]) / scaleAll;
      const z = (arr[i * 3 + 2] - cmid[2]) / scaleAll;
      const rx = x * ca - z * sa;
      X[i] = W * 0.5 + rx * W * 0.92;
      Y[i] = H * 0.5 + y * W * 0.92;
    }
  };
  put(WC, NP, SX, SY);
  put(WB, NB, BX, BY);
}
project();

/* ---------- сеть: LIF прямо здесь ---------- */
const N = C.neurons.length;
const V = new Float32Array(N), S = new Float32Array(N), prevS = new Float32Array(N);
const Vshow = new Float32Array(N);
const spikes = new Int32Array(N);
const refr = new Int32Array(N);   // рефрактерный период, как у живого нейрона
const cls = C.neurons.map(n => n.cls);
const colOf = C.neurons.map(n => n.c);
const heads = [], tails = [], wts = [];
for (const [a, b, syn, sign] of C.edges) { heads.push(a); tails.push(b); wts.push(syn * sign); }
const E = heads.length;
const EH = new Int32Array(heads), ET = new Int32Array(tails), EW = new Float32Array(wts);
const isKC = cls.map(c => c === 'Kenyon_Cell');
const isORN = cls.map(c => c === 'olfactory');
const isMBON = cls.map(c => c === 'MBON');

const LEAK = 0.82, THETA = 1.0;
/* у каждого нейрона свой суммарный вход: нормируем, иначе одни молчат, другие взрываются */
(function normalize() {
  const pos = new Float32Array(N);
  for (let e = 0; e < E; e++) if (EW[e] > 0) pos[ET[e]] += EW[e];
  for (let e = 0; e < E; e++) {
    const p = pos[ET[e]];
    if (p > 0) EW[e] *= 2.1 / p;
  }
})();
const SCALE = 1.0;
let odor = new Float32Array(N);
let odorId = 0, tickCount = 0, packets = 0, releases = 0;

function newOdor() {
  odorId++;
  odor = new Float32Array(N);
  const orns = [];
  for (let i = 0; i < N; i++) if (isORN[i]) orns.push(i);
  const k = Math.max(6, Math.floor(orns.length * 0.35));
  for (let j = 0; j < k; j++) odor[orns[(Math.random() * orns.length) | 0]] = 1.8 + Math.random();
}
newOdor();

let burst = 0;
function step(drive) {
  const inj = new Float32Array(N);
  for (let i = 0; i < N; i++) if (odor[i]) inj[i] = odor[i] * drive;
  const cur = new Float32Array(N);
  for (let e = 0; e < E; e++) {
    const s = prevS[EH[e]];
    if (s) cur[ET[e]] += EW[e] * s * SCALE;
  }
  const mute = document.getElementById('mute').checked;
  const out = document.getElementById('out').checked;
  let active = 0;
  for (let i = 0; i < N; i++) {
    if (mute && isKC[i]) { V[i] = 0; S[i] = 0; continue; }
    if (!out && isMBON[i]) { V[i] = 0; S[i] = 0; continue; }
    if (refr[i] > 0) { refr[i]--; S[i] = 0; V[i] *= 0.4; Vshow[i] *= 0.85; continue; }
    V[i] = V[i] * LEAK + cur[i] + inj[i];
    Vshow[i] = Vshow[i] * 0.85 + V[i] * 0.15;
    if (V[i] > THETA) { S[i] = 1; V[i] = 0; refr[i] = 3; spikes[i]++; active++; }
    else S[i] = 0;
  }
  prevS.set(S);
  packets += active;
  return active;
}

/* ---------- отрисовка ---------- */
const base = document.createElement('canvas');
base.width = W; base.height = H;
const bctx = base.getContext('2d');
function drawBase() {
  bctx.fillStyle = '#080c11';
  bctx.fillRect(0, 0, W, H);
  bctx.fillStyle = 'rgba(105,128,150,0.42)';       // фон: клетки, которые не симулируются
  for (let i = 0; i < BX.length; i++) bctx.fillRect(BX[i], BY[i], 1, 1);
  for (let n = 0; n < N; n++) {                    // сама цепь — тускло, но цветом типа
    bctx.fillStyle = COL[colOf[n]] + '38';
    for (let i = start[n]; i < start[n + 1]; i++) bctx.fillRect(SX[i] - 0.5, SY[i] - 0.5, 1.6, 1.6);
  }
}
drawBase();

const glow = new Float32Array(N);
function draw() {
  ctx.drawImage(base, 0, 0);
  for (let n = 0; n < N; n++) {
    const g = glow[n];
    if (g < 0.05) continue;
    ctx.globalAlpha = Math.min(1, 0.25 + 0.75 * g);
    ctx.fillStyle = COL[colOf[n]];
    const r = 1.2 + 1.8 * g;
    for (let i = start[n]; i < start[n + 1]; i++) {
      ctx.beginPath(); ctx.arc(SX[i], SY[i], r, 0, 6.2832); ctx.fill();
    }
    glow[n] = g * 0.9;
  }
  ctx.globalAlpha = 1;
}

/* ---------- график ---------- */
const tc = document.getElementById('trace'), tctx = tc.getContext('2d');
const hist = {in: [], out: []};
function drawTrace() {
  const w = tc.width, h = tc.height;
  tctx.fillStyle = '#0c1219'; tctx.fillRect(0, 0, w, h);
  tctx.strokeStyle = '#1e2a38';
  tctx.beginPath(); tctx.moveTo(0, h - 12); tctx.lineTo(w, h - 12); tctx.stroke();
  const line = (arr, color, scale) => {
    tctx.strokeStyle = color; tctx.lineWidth = 1.6; tctx.beginPath();
    arr.forEach((v, i) => {
      const x = i / Math.max(1, arr.length - 1) * w;
      const y = h - 12 - Math.min(1, v / scale) * (h - 24);
      i ? tctx.lineTo(x, y) : tctx.moveTo(x, y);
    });
    tctx.stroke();
  };
  line(hist.in, '#5cc8ff', 1.05);
  line(hist.out, '#ffd200', Math.max(12, ...hist.out) * 1.1);
}

/* ---------- телеметрия ---------- */
const groupTotals = {};
C.groups.forEach(g => groupTotals[g.cls] = g);
document.getElementById('legend').innerHTML = C.groups.map(g =>
  `<span><i style="background:${COL[g.color]}"></i>${g.title}</span>`).join('') +
  '<span><i style="background:#5a6e82"></i>не симулируются</span>';
document.getElementById('foot').innerHTML =
  `<span>${N} реальных клеток</span><span>${C.edges.length} измеренных связей</span>` +
  `<span>${C.synapses.toLocaleString('ru')} синапсов</span>` +
  `<span>точек анатомии: ${NP.toLocaleString('ru')}</span>` +
  '<span>Активность симулируется. Серые клетки фона в расчёт не входят.</span>';

function telemetry(active, drive) {
  const kc = [], mb = [];
  for (let i = 0; i < N; i++) { if (isKC[i] && S[i]) kc.push(i); if (isMBON[i] && S[i]) mb.push(i); }
  document.getElementById('tele').innerHTML = `
    <span>СТИМУЛ</span><b>запах #${odorId}</b>
    <span>НЕЙРОНОВ / АКТИВНО</span><b>${N} / ${active}</b>
    <span>СИЛА ВХОДА</span><b>${drive.toFixed(2)}</b>
    <span>КЛЕТКИ КЕНЬОНА</span><b>${kc.length} разрядов</b>
    <span>ВЫХОД MBON</span><b>${mb.length} разрядов</b>
    <span>ПАКЕТОВ СПАЙКОВ</span><b>${packets.toLocaleString('ru')}</b>
    <span>ТАКТОВ</span><b>${tickCount}</b>`;
  const top = [...Array(N).keys()].sort((a, b) => spikes[b] - spikes[a]).slice(0, 9);
  document.getElementById('insp').innerHTML = top.map(i =>
    `<tr class="${S[i] ? 'hot' : ''}"><td>${C.neurons[i].id.slice(-6)}</td>` +
    `<td>${cls[i]}</td><td>${Vshow[i].toFixed(3)}</td><td>${spikes[i]}</td></tr>`).join('');
}

/* ---------- цикл ---------- */
let phase = 0;
function loop() {
  tickCount++;
  phase += 0.02;
  // запах приходит волнами, как в опытах: вдох — пауза — вдох
  const drive = Math.max(0, Math.sin(phase)) ** 2;
  if (drive < 0.02 && Math.random() < 0.02) newOdor();
  const active = step(drive);
  for (let i = 0; i < N; i++) if (S[i]) glow[i] = 1;
  hist.in.push(drive); hist.out.push(active);
  if (hist.in.length > 220) { hist.in.shift(); hist.out.shift(); }
  document.getElementById('state').textContent = drive > 0.05
    ? 'ЗАПАХ ПОДАН / ГРИБОВИДНОЕ ТЕЛО ОТВЕЧАЕТ'
    : 'ПАУЗА / ФОНОВАЯ АКТИВНОСТЬ';
  if (document.getElementById('rot').checked) { angle += 0.004; project(); drawBase(); }
  draw(); drawTrace(); telemetry(active, drive);
  requestAnimationFrame(loop);
}
document.getElementById('shot').onclick = () => {
  const a = document.createElement('a');
  a.download = 'connectome.png'; a.href = cv.toDataURL('image/png'); a.click();
};
loop();
</script>
</html>"""


def background_points(n: int = 9000, seed: int = 11) -> dict:
    """Серый фон: сомы остальных нейронов мозга, они в симуляции не участвуют."""
    xyz = np.load(CONNECTOME / "flywire783_xyz.npy").astype(np.float64)
    ok = np.isfinite(xyz[:, 0])
    xyz = xyz[ok]
    rng = np.random.default_rng(seed)
    xyz = xyz[rng.choice(xyz.shape[0], size=min(n, xyz.shape[0]), replace=False)]
    lo = xyz.min(0)
    span = np.maximum(xyz.max(0) - lo, 1.0)
    q = (xyz - lo) / span * 65535.0
    return {
        "lo": [round(float(x), 1) for x in lo],
        "span": [round(float(x), 1) for x in span],
        "p": base64.b64encode(q.astype(np.uint16).tobytes()).decode("ascii"),
    }


def build(out: Path) -> Path:
    circuit = (ASSETS / "circuit.json").read_text(encoding="utf-8")
    html = (PAGE.replace("__CIRCUIT__", circuit)
            .replace("__BG__", json.dumps(background_points(), separators=(",", ":"))))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out


if __name__ == "__main__":
    p = build(ROOT / "report" / "lab.html")
    print(p, p.stat().st_size // 1024, "КБ")
