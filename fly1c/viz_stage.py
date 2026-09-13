"""Сцена: муха печатает лабораторную, рядом живое окно 1С и активность коннектома.

Оформление — «Такси», как в 1С:Предприятии 8: жёлтая шапка, серые панели, белые формы.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PAGE = r"""<!doctype html><html lang="ru"><meta charset="utf-8">
<title>Муха и 1С</title>
<style>
:root{
  --y:#ffd200; --y2:#f7b500; --ink:#2b2b2b; --dim:#6d6d6d; --line:#c9c9c9;
  --bg:#eceff1; --panel:#ffffff; --head:#f5f6f7; --sel:#fff3c4; --blue:#1f6fb2;
  --ok:#3a9d3a; --bad:#c62828; --dark:#0d1b14;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:13px/1.45 "Segoe UI",Tahoma,Arial,sans-serif}
.wrap{padding:12px;max-width:1560px;margin:0 auto}
.appbar{display:flex;align-items:center;gap:12px;background:linear-gradient(180deg,var(--y),var(--y2));
border:1px solid #d9a800;border-radius:4px;padding:7px 12px;margin-bottom:10px}
.logo{background:#fff;border:1px solid #d9a800;border-radius:3px;padding:1px 7px;
font-weight:700;color:#c62828;letter-spacing:-.5px}
.title{font-weight:600;font-size:15px}
.crumbs{color:#6b5200;font-size:12px}
.crumbs b{color:#3b2d00}
.clock{margin-left:auto;font-variant-numeric:tabular-nums;color:#3b2d00;font-weight:600}
.grid{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(320px,1fr);gap:10px}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:4px}
.ph{display:flex;align-items:center;gap:8px;background:var(--head);
border-bottom:1px solid var(--line);padding:5px 10px;font-weight:600;font-size:12px}
.ph .r{margin-left:auto;font-weight:400;color:var(--dim)}
.pb{padding:10px}
.bar{display:flex;gap:7px;align-items:center;flex-wrap:wrap;margin-bottom:9px}
select,button{font:inherit;font-size:12px;border:1px solid var(--line);border-radius:3px;
background:#fff;color:var(--ink);padding:4px 9px;cursor:pointer}
button.primary{background:linear-gradient(180deg,#ffe27a,var(--y));border-color:#d9a800;font-weight:600}
button:hover,select:hover{border-color:var(--y2)}
.tabs{display:flex;gap:2px;margin-bottom:-1px}
.tab{padding:5px 14px;border:1px solid var(--line);border-bottom:none;border-radius:4px 4px 0 0;
background:#e7e9ea;cursor:pointer;font-size:12px}
.tab.on{background:#fff;font-weight:600}
.win{border:1px solid var(--line);background:#fff}
.wintitle{background:linear-gradient(180deg,#fdfdfd,#eef0f1);border-bottom:1px solid var(--line);
padding:4px 9px;font-size:12px;display:flex;gap:8px;align-items:center}
.dot3{margin-left:auto;color:#9a9a9a;letter-spacing:2px}
.sections{display:flex;gap:1px;background:#e3e5e6;border-bottom:1px solid var(--line);
padding:0 4px;overflow:auto}
.sec{padding:6px 13px;font-size:12px;white-space:nowrap;border-bottom:3px solid transparent;color:#444}
.sec.on{background:#fff;border-bottom-color:var(--y2);font-weight:600}
.cols{display:grid;grid-template-columns:190px minmax(0,1fr);min-height:262px}
.nav{border-right:1px solid var(--line);background:#fafbfb;padding:6px 0;overflow:auto;max-height:262px}
.nav .grp{padding:4px 10px;color:var(--dim);font-size:11px;text-transform:uppercase}
.nav a{display:block;padding:3px 10px 3px 18px;color:var(--blue);cursor:default;font-size:12px}
.nav a.on{background:var(--sel);color:#3b2d00;font-weight:600}
.work{padding:8px 10px;overflow:auto;max-height:262px}
.formtitle{font-size:14px;font-weight:600;margin-bottom:6px}
table{border-collapse:collapse;width:100%;font-size:12px}
th{background:#f2f3f4;border:1px solid var(--line);padding:3px 7px;text-align:left;font-weight:600}
td{border:1px solid #e3e5e6;padding:3px 7px}
tr.new td{background:var(--sel)}
.badge{display:inline-block;border-radius:2px;padding:0 5px;font-size:11px;border:1px solid}
.b-ok{color:var(--ok);border-color:#a5d6a7;background:#edf7ed}
.b-no{color:var(--dim);border-color:#ddd;background:#f5f5f5}
.props td:first-child{width:45%;color:var(--dim)}
.msgs{border-top:1px solid var(--line);background:#fbfbfb;padding:6px 9px;height:92px;overflow:auto;
font:12px/1.5 "Cascadia Mono",Consolas,monospace}
.msgs .t{color:#8a8a8a}
.msgs .err{color:var(--bad)}
.caret{display:inline-block;width:6px;background:#3b2d00;animation:bl .9s steps(1) infinite}
@keyframes bl{50%{opacity:0}}
.tree{font:12px/1.6 "Cascadia Mono",Consolas,monospace;max-height:300px;overflow:auto;padding:6px 10px}
.tree .s{color:var(--dim)}
.tree .o{padding-left:14px}
.tree .o:before{content:"├ ";color:#bbb}
.tree .d{padding-left:30px;color:var(--dim)}
.tree .d:before{content:"· "}
.tree .fresh{background:var(--sel)}
.checks{display:flex;flex-wrap:wrap;gap:3px;margin:9px 0 6px}
.ck{width:12px;height:12px;border:1px solid #cfcfcf;border-radius:2px;background:#efefef}
.ck.on{background:#5cb85c;border-color:#3a9d3a}
.stat{display:flex;gap:15px;flex-wrap:wrap;color:var(--dim);font-size:12px}
.stat b{color:var(--ink)}
canvas{display:block;width:100%;height:auto;background:var(--dark)}
.legend{display:flex;gap:11px;flex-wrap:wrap;font-size:11px;color:var(--dim);padding:5px 9px;
border-top:1px solid var(--line)}
.legend i{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:4px}
.mode{padding:5px 9px;border-top:1px solid var(--line);font-size:12px;color:var(--dim)}
.mode b{color:#3b2d00}
.hint{margin-top:8px;color:var(--dim);font-size:11.5px;line-height:1.75}
code{background:#f4f5f6;border:1px solid var(--line);border-radius:2px;padding:1px 5px;
font:11.5px "Cascadia Mono",Consolas,monospace;color:#2b2b2b}
</style>
<div class="wrap">
<div class="appbar">
  <span class="logo">1С</span>
  <span class="title">Муха закрывает лабораторные</span>
  <span class="crumbs">коннектом &rsaquo; муха &rsaquo; клавиатура &rsaquo; <b id="crumb">1С</b></span>
  <span class="clock">t = <span id="clock">00.00</span> c</span>
</div>

<div class="grid">
  <div>
    <div class="panel">
      <div class="ph">Рабочее место мухи <span class="r" id="labid"></span></div>
      <div class="pb">
        <div class="bar">
          <select id="lab"></select>
          <button id="play" class="primary">Пауза</button>
          <button id="again">Сначала</button>
          <select id="speed">
            <option value="0.5">×0,5</option><option value="1" selected>×1</option>
            <option value="2">×2</option><option value="4">×4</option>
          </select>
          <span style="color:var(--dim);font-size:12px" id="pos"></span>
        </div>

        <div class="tabs">
          <div class="tab on" data-v="ent">1С:Предприятие</div>
          <div class="tab" data-v="cfg">Конфигуратор</div>
        </div>

        <div class="win" id="view-ent">
          <div class="wintitle"><span class="logo" style="font-size:11px">1С</span>
            <span id="ibname">Конфигурация</span> — 1С:Предприятие
            <span class="dot3">— □ ×</span></div>
          <div class="sections" id="sections"></div>
          <div class="cols">
            <div class="nav" id="nav"></div>
            <div class="work" id="work"></div>
          </div>
          <div class="msgs" id="msgs"></div>
        </div>

        <div class="win" id="view-cfg" hidden>
          <div class="wintitle"><span class="logo" style="font-size:11px">1С</span>
            Конфигуратор — дерево метаданных <span class="dot3">— □ ×</span></div>
          <div class="tree" id="tree"></div>
          <div class="msgs" id="msgs2"></div>
        </div>

        <div class="checks" id="checks"></div>
        <div class="stat">
          <span>проверок: <b id="passed">0</b>/<b id="total">0</b></span>
          <span>операций: <b id="opsdone">0</b>/<b id="opstotal">0</b></span>
          <span>промахов: <b id="fails">0</b></span>
          <span>обучилась за: <b id="solved">—</b> эпизодов</span>
        </div>
        <div class="hint" id="hint"></div>
      </div>
    </div>
  </div>

  <div>
    <div class="panel" style="margin-bottom:10px">
      <div class="ph">Нейронная активность
        <span class="r">коннектом FlyWire v783</span></div>
      <canvas id="brain" width="900" height="430"></canvas>
      <div class="legend">
        <span><i style="background:#5ce08a"></i>мозг</span>
        <span><i style="background:#ffd200"></i>клетки Кеньона</span>
        <span><i style="background:#6ad1ff"></i>MBON</span>
        <span><i style="background:#ff6b5e"></i>дофаминовые</span>
        <span style="margin-left:auto">спайков: <b id="spk">—</b> · KC: <b id="kcn">—</b></span>
      </div>
    </div>
    <div class="panel">
      <div class="ph">Муха за клавиатурой <span class="r">NeuroMechFly</span></div>
      <div id="flybox"></div>
      <div class="mode">режим: <b id="mode">думает</b><span id="modehint"></span></div>
    </div>
  </div>
</div>
</div>
<script>__THREE__</script>
<script>__FLYDATA__</script>
<script>__RIG__</script>
<script>
const D = __DATA__;
const IB_DIR = __IBDIR__;

FlyRig.init(document.getElementById('flybox'), FLY3D);

/* ---------- список лабораторных ---------- */
const sel = document.getElementById('lab');
const byTrack = {};
D.labs.forEach((l, i) => { (byTrack[l.trackTitle] ||= []).push([i, l]); });
for (const [track, items] of Object.entries(byTrack)) {
  const g = document.createElement('optgroup'); g.label = track;
  for (const [i, l] of items) {
    const o = document.createElement('option');
    o.value = i; o.textContent = l.id + ' — ' + l.title;
    g.appendChild(o);
  }
  sel.appendChild(g);
}

/* ---------- мозг ---------- */
const cv = document.getElementById('brain'), ctx = cv.getContext('2d');
const N = D.neurons.n, W = cv.width, H = cv.height;
const PX = new Float32Array(N), PY = new Float32Array(N);
for (let i = 0; i < N; i++) {
  PX[i] = 22 + D.neurons.x[i] * (W - 44);
  PY[i] = 18 + D.neurons.y[i] * (H - 36);
}
const PAL = ['#5ce08a', '#ffd200', '#6ad1ff', '#ff6b5e'];
const heat = new Float32Array(N);

function unpack(b64) {
  const raw = atob(b64), out = [];
  for (let i = 0; i < raw.length; i++) {
    const byte = raw.charCodeAt(i);
    if (!byte) continue;
    for (let b = 0; b < 8; b++) if (byte & (128 >> b)) out.push(i * 8 + b);
  }
  return out;
}

function drawBrain() {
  ctx.fillStyle = '#0d1b14';
  ctx.fillRect(0, 0, W, H);
  // фоновая жизнь: мозг никогда не выглядит выключенным
  for (let k = 0; k < N * 0.012; k++) {
    const i = (Math.random() * N) | 0;
    if (heat[i] < 0.3) heat[i] = 0.3 + Math.random() * 0.25;
  }
  for (let i = 0; i < N; i++) {
    const h = heat[i], k = D.neurons.k[i];
    if (h < 0.04) {
      ctx.fillStyle = 'rgba(110,170,140,0.45)';
      ctx.fillRect(PX[i] - 0.8, PY[i] - 0.8, 1.6, 1.6);
      continue;
    }
    ctx.globalAlpha = Math.min(1, 0.45 + 0.55 * h);
    ctx.fillStyle = PAL[k];
    ctx.beginPath();
    ctx.arc(PX[i], PY[i], (k ? 2.1 : 1.5) + 2.1 * h, 0, 6.2832);
    ctx.fill();
    ctx.globalAlpha = 1;
    heat[i] = h * 0.965;
  }
}

/* ---------- состояние окна 1С ---------- */
let lab, step, phase, phaseT, typed, fails, playing = true, speed = 1, t0 = 0;
let view = 'ent', curSection = null;
const PHASES = {think: 900, adjust: 280, type: 900, settle: 260};
const SECTION_NAV = {
  'Справочники': 'Справочники', 'Документы': 'Документы',
  'Отчёты': 'Отчёты', 'РегистрыНакопления': 'Регистры', 'Перечисления': 'Перечисления'
};

function model() {
  /* состояние конфигурации, собранное по кадрам с начала до текущего шага */
  const m = {subsystems: [], objects: {}, ib: '', last: null, lastData: null};
  for (let i = 0; i < step; i++) {
    const f = lab.frames[i];
    if (f.failed) continue;
    if (f.ui.kind === 'config') m.ib = f.obj;
    if (f.section === 'Подсистемы' && f.obj && !m.subsystems.includes(f.obj)) m.subsystems.push(f.obj);
    if (SECTION_NAV[f.section] && f.obj) {
      const sec = (m.objects[f.section] ||= {});
      const o = (sec[f.obj] ||= {details: [], rows: null, kind: f.ui.kind});
      if (f.detail && !o.details.includes(f.detail)) o.details.push(f.detail);
      if (f.ui.rows && f.ui.rows.length) { o.rows = f.ui.rows; o.kind = f.ui.kind; }
    }
    m.last = f;
    if (f.ui.rows && f.ui.rows.length) m.lastData = f;
  }
  return m;
}

function renderEnterprise() {
  const m = model();
  document.getElementById('ibname').textContent = m.ib || lab.trackTitle;
  const secs = document.getElementById('sections');
  const names = m.subsystems.length ? m.subsystems : ['Начальная страница'];
  if (!curSection || !names.includes(curSection)) curSection = names[names.length - 1];
  const focus = m.last;
  secs.innerHTML = names.map(n =>
    `<div class="sec${n === curSection ? ' on' : ''}">${n}</div>`).join('');

  const nav = document.getElementById('nav');
  let navHtml = '';
  for (const [section, objs] of Object.entries(m.objects)) {
    const keys = Object.keys(objs);
    if (!keys.length) continue;
    navHtml += `<div class="grp">${SECTION_NAV[section]}</div>`;
    navHtml += keys.map(k =>
      `<a class="${focus && focus.obj === k ? 'on' : ''}">${k}</a>`).join('');
  }
  nav.innerHTML = navHtml || '<div class="grp">нет объектов</div>';

  const work = document.getElementById('work');
  const data = m.lastData;
  if (!focus) {
    work.innerHTML = '<div class="formtitle">Начальная страница</div>' +
      '<div style="color:var(--dim)">Конфигурация пустая — муха только села за клавиатуру.</div>';
  } else if (data && data === focus && data.ui.kind === 'fill_catalog') {
    work.innerHTML = `<div class="formtitle">${data.ui.owner} (список)</div>` +
      '<table><tr><th style="width:32px"></th><th>Наименование</th><th>Родитель</th></tr>' +
      data.ui.rows.map((r, i) =>
        `<tr class="${i === data.ui.rows.length - 1 ? 'new' : ''}"><td>${r.f ? '▣' : '▢'}</td>` +
        `<td>${r.n}</td><td>${r.p || ''}</td></tr>`).join('') + '</table>';
  } else if (data && data === focus && (data.ui.kind === 'fill_document' || data.ui.kind === 'post')) {
    work.innerHTML = `<div class="formtitle">${data.ui.owner} (журнал документов)</div>` +
      '<table><tr><th>Номер</th><th>Сумма</th><th>Проведён</th></tr>' +
      data.ui.rows.map(r => `<tr><td>${r.n}</td><td>${r.s ? r.s.toLocaleString('ru') : ''}</td>` +
        `<td>${r.p ? '<span class="badge b-ok">проведён</span>'
                   : '<span class="badge b-no">не проведён</span>'}</td></tr>`).join('') + '</table>';
  } else if (focus.ui.kind === 'run_report') {
    work.innerHTML = `<div class="formtitle">Отчёт «${focus.ui.owner}»</div>` +
      '<table><tr><th>Показатель</th><th>Значение</th></tr>' +
      (focus.ui.rows && focus.ui.rows.length
        ? focus.ui.rows.map(r => `<tr><td>${r.n}</td><td>${r.s}</td></tr>`).join('')
        : '<tr><td colspan="2" style="color:var(--dim)">отчёт сформирован</td></tr>') + '</table>';
  } else {
    const obj = (m.objects[focus.section] || {})[focus.obj];
    const props = (obj ? obj.details : []).slice(-9);
    work.innerHTML = `<div class="formtitle">${focus.obj || focus.section}` +
      `<span style="font-weight:400;color:var(--dim)"> — ${focus.section}</span></div>` +
      '<table class="props"><tr><th>Свойство</th><th>Значение</th></tr>' +
      `<tr class="new"><td>последнее действие</td><td>${focus.detail || 'объект создан'}</td></tr>` +
      props.map(d => `<tr><td>состав</td><td>${d}</td></tr>`).join('') + '</table>';
  }
}

function renderTree() {
  const m = model();
  const last = m.last;
  let html = '<div class="s">Конфигурация' + (m.ib ? ' ' + m.ib : '') + '</div>';
  const sections = D.sections.filter(s => s === 'Подсистемы' || m.objects[s]);
  for (const s of sections) {
    if (s === 'Подсистемы') {
      if (!m.subsystems.length) continue;
      html += '<div class="s">Подсистемы</div>' +
        m.subsystems.map(n => `<div class="o">${n}</div>`).join('');
      continue;
    }
    html += `<div class="s">${s}</div>`;
    for (const [name, o] of Object.entries(m.objects[s])) {
      const fresh = last && last.section === s && last.obj === name;
      html += `<div class="o${fresh ? ' fresh' : ''}">${name}</div>`;
      html += o.details.map(d => `<div class="d">${d}</div>`).join('');
    }
  }
  document.getElementById('tree').innerHTML = html;
}

function renderChecks() {
  const f = step > 0 ? lab.frames[step - 1] : null;
  const dots = document.getElementById('checks').children;
  let n = 0;
  for (let i = 0; i < dots.length; i++) {
    const on = f ? !!f.mask[i] : false;
    dots[i].classList.toggle('on', on);
    if (on) n++;
  }
  document.getElementById('passed').textContent = n;
  document.getElementById('opsdone').textContent = step;
  document.getElementById('fails').textContent = fails;
  document.getElementById('pos').textContent =
    'шаг ' + Math.min(step + 1, lab.frames.length) + ' из ' + lab.frames.length;
}

function msgBoxes() {
  return [document.getElementById('msgs'), document.getElementById('msgs2')];
}

function logLine(f, partial) {
  for (const box of msgBoxes()) {
    let cur = box.querySelector('.cur');
    if (!cur) { cur = document.createElement('div'); cur.className = 'cur'; box.appendChild(cur); }
    cur.innerHTML = '<span class="t">&gt; </span>' + f.op.slice(0, partial) +
      '<span class="caret">&nbsp;</span>';
    box.scrollTop = box.scrollHeight;
  }
}

function finishLine(f) {
  for (const box of msgBoxes()) {
    const cur = box.querySelector('.cur');
    if (!cur) continue;
    cur.className = f.failed ? 'err' : '';
    cur.innerHTML = '<span class="t">&gt; </span>' + f.op +
      (f.failed ? '  — не вышло, муха пробует иначе' : '');
  }
}

function pick(i) {
  lab = D.labs[i];
  step = 0; phase = 'think'; phaseT = 0; typed = 0; fails = 0; t0 = 0; curSection = null;
  document.getElementById('labid').textContent = lab.id + ' · ' + lab.trackTitle;
  document.getElementById('crumb').textContent = lab.trackTitle;
  document.getElementById('opstotal').textContent = lab.frames.length;
  document.getElementById('total').textContent = lab.checks.length;
  document.getElementById('solved').textContent = lab.solved_at ?? '—';
  const checks = document.getElementById('checks');
  checks.innerHTML = '';
  lab.checks.forEach(m => {
    const d = document.createElement('div'); d.className = 'ck'; d.title = m; checks.appendChild(d);
  });
  msgBoxes().forEach(b => b.innerHTML = '');
  document.getElementById('hint').innerHTML =
    'Посмотреть эту лабу в живой 1С — собрать её ИБ и открыть окном:<br>'
    + `<code>python run_lab.py build ${lab.id}</code> `
    + `<code>python run_lab.py seed ${lab.id}</code> `
    + `<code>python run_lab.py open ${lab.id}</code><br>`
    + `файлы базы: <code>${IB_DIR}\\${lab.id}</code>, конфигуратор — <code>--designer</code>`;
  heat.fill(0);
  renderEnterprise(); renderTree(); renderChecks();
}

/* ---------- проигрыватель ---------- */
let prev = performance.now();
function loop(now) {
  const dt = Math.min(80, now - prev); prev = now;
  if (playing && lab) {
    t0 += dt / 1000;
    phaseT += dt * speed;
    const f = lab.frames[Math.min(step, lab.frames.length - 1)];
    const dur = PHASES[phase] * (phase === 'type' ? Math.max(.5, f.op.length / 34) : 1);
    const p = Math.min(1, phaseT / dur);

    if (phase === 'think') {
      document.getElementById('spk').textContent = f.spikes.toLocaleString('ru');
      document.getElementById('kcn').textContent = f.kc;
      FlyRig.think(p, t0);
      const on = unpack(f.fire);
      for (const i of on) if (Math.random() < .3) heat[i] = 1;
      if (p >= 1) { phase = 'adjust'; phaseT = 0; }
    } else if (phase === 'adjust') {
      FlyRig.adjust(p);
      if (p >= 1) { phase = 'type'; phaseT = 0; typed = 0; }
    } else if (phase === 'type') {
      const want = Math.floor(p * f.op.length);
      if (want !== typed) { typed = want; logLine(f, typed); }
      // муха бьёт по клавише того символа, который сейчас появляется в логе
      FlyRig.type(t0, f.op.charAt(Math.min(typed, f.op.length - 1)), p * f.op.length % 1);
      if (p >= 1) {
        phase = 'settle'; phaseT = 0;
        finishLine(f);
        if (f.failed) fails++;
        step++;
        renderEnterprise(); renderTree(); renderChecks();
      }
    } else if (phase === 'settle') {
      FlyRig.idle(t0);
      if (p >= 1) {
        phaseT = 0;
        if (step >= lab.frames.length) {
          playing = false;
          document.getElementById('play').textContent = 'Играть';
          document.getElementById('mode').textContent = 'готово';
          document.getElementById('modehint').textContent =
            ' — лабораторная закрыта, базу можно открывать';
        } else phase = 'think';
      }
    }
    if (playing) {
      const modes = {think: 'думает', adjust: 'поправляет очки',
                     type: 'печатает', settle: 'проверяет'};
      document.getElementById('mode').textContent = modes[phase];
      let hint = '';
      if (phase === 'think') hint = ' — грибовидное тело выбирает операцию';
      else if (phase === 'type') {
        // показываем символ и клавишу под ним: видно, что лапка бьёт именно туда
        const ch = f.op.charAt(Math.min(typed, f.op.length - 1));
        const key = FlyRig.keyFor(ch);
        hint = key ? ' — клавиша «' + (key.rus || 'пробел').toUpperCase() + '»'
                   : ' — символа «' + ch + '» на раскладке нет';
      }
      document.getElementById('modehint').textContent = hint;
    }
    document.getElementById('clock').textContent = t0.toFixed(2).padStart(5, '0');
  }
  drawBrain();
  FlyRig.render(dt / 1000);
  requestAnimationFrame(loop);
}

document.querySelectorAll('.tab').forEach(tab => tab.onclick = () => {
  view = tab.dataset.v;
  document.querySelectorAll('.tab').forEach(x => x.classList.toggle('on', x === tab));
  document.getElementById('view-ent').hidden = view !== 'ent';
  document.getElementById('view-cfg').hidden = view !== 'cfg';
});
sel.onchange = () => { pick(+sel.value); playing = true;
  document.getElementById('play').textContent = 'Пауза'; };
document.getElementById('play').onclick = e => {
  playing = !playing; e.target.textContent = playing ? 'Пауза' : 'Играть';
};
document.getElementById('again').onclick = () => {
  pick(+sel.value); playing = true; document.getElementById('play').textContent = 'Пауза';
};
document.getElementById('speed').onchange = e => { speed = +e.target.value; };

pick(0);
requestAnimationFrame(loop);
</script>
</html>"""


def build(data: dict[str, Any], out: Path, ib_dir: str, lite: bool = False,
          cdn: bool = False) -> Path:
    """lite/cdn — облегчённый вариант для быстрой проверки в панели предпросмотра."""
    from . import viz_fly3d

    three = ('<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js">'
             "</script>" if cdn else "<script>" + viz_fly3d.three_js() + "</script>")
    html = PAGE.replace(
        "__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    ).replace("__IBDIR__", json.dumps(ib_dir, ensure_ascii=False))
    html = (html.replace("<script>__THREE__</script>", three)
            .replace("__FLYDATA__", viz_fly3d.fly_data_js(lite=lite))
            .replace("__RIG__", viz_fly3d.RIG_JS))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out
