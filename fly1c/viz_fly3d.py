"""3D-муха для сцены: настоящая модель NeuroMechFly, скелет из суставов SDF, очки сверху.

RIG_JS — код, который собирает муху из данных `assets/fly3d.json` и умеет её анимировать:
думает (очки сползают), поправляет очки лапкой, печатает по клавиатуре.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"

RIG_JS = r"""
window.FlyRig = (function () {
  let renderer, scene, camera, root, nodes = {}, glasses, keys = [], clock = 0;
  // какая передняя лапка с какой стороны по y — считаем по модели, а не гадаем
  let sideByY = {plus: 'L', minus: 'R'}, bodyHome = null, body = null;
  let host, spot;
  const S = 1.0;

  function decodeBuffer(b64) {
    const raw = atob(b64), n = raw.length, bytes = new Uint8Array(n);
    for (let i = 0; i < n; i++) bytes[i] = raw.charCodeAt(i);
    return new Int16Array(bytes.buffer);
  }

  const COLORS = {
    eye: 0x8e1810, wing: 0xcfe2da, leg: 0x5f3c18, body: 0xb06a22,
    head: 0xa8641f, dark: 0x6d411a
  };
  function colorFor(name) {
    if (/Eye/.test(name)) return COLORS.eye;
    if (/Wing|Haltere/.test(name)) return COLORS.wing;
    if (/Coxa|Femur|Tibia|Tarsus|Antenna/.test(name)) return COLORS.leg;
    if (/Head|Rostrum|Haustellum/.test(name)) return COLORS.head;
    if (/^A[0-9]/.test(name)) return COLORS.dark;
    return COLORS.body;
  }

  function buildFly(D) {
    const buf = decodeBuffer(D.buffer);
    root = new THREE.Group();
    for (const link of D.links) {
      const node = new THREE.Group();
      node.position.set(link.t[0] * S, link.t[1] * S, link.t[2] * S);
      node.userData.axis = new THREE.Vector3(link.axis[0], link.axis[1], link.axis[2]);
      if (node.userData.axis.lengthSq() < 1e-6) node.userData.axis.set(0, 0, 1);
      nodes[link.name] = node;
      (link.parent ? nodes[link.parent] : root).add(node);
      if (link.mesh === null || link.mesh === undefined) continue;
      const m = D.meshes[link.mesh];
      const q = buf.subarray(m.off / 2, m.off / 2 + m.len);
      const pos = new Float32Array(m.len);
      for (let i = 0; i < m.len; i += 3) {
        pos[i] = ((q[i] + 32768) / 65535 * m.span[0] + m.lo[0]) * S;
        pos[i + 1] = ((q[i + 1] + 32768) / 65535 * m.span[1] + m.lo[1]) * S;
        pos[i + 2] = ((q[i + 2] + 32768) / 65535 * m.span[2] + m.lo[2]) * S;
      }
      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
      geo.computeVertexNormals();
      const wing = /Wing/.test(link.name);
      const mat = new THREE.MeshStandardMaterial({
        color: colorFor(link.name),
        roughness: wing ? 0.25 : 0.62,
        metalness: wing ? 0.0 : 0.12,
        transparent: wing, opacity: wing ? 0.22 : 1,
        side: THREE.DoubleSide, flatShading: false
      });
      node.add(new THREE.Mesh(geo, mat));
    }
    return root;
  }

  function buildGlasses() {
    /* у мухи глаза по бокам головы, поэтому линзы смотрят наружу (вдоль ±Y),
       а не вперёд, как у человека: центр глаза в системе головы ≈ (0.21, ±0.30, 0.06) */
    const g = new THREE.Group();
    const frame = new THREE.MeshStandardMaterial({
      color: 0x3a3a3a, roughness: 0.35, metalness: 0.55
    });
    const glass = new THREE.MeshPhysicalMaterial({
      color: 0xbfe4ff, transparent: true, opacity: 0.26,
      roughness: 0.05, metalness: 0, side: THREE.DoubleSide
    });
    for (const side of [1, -1]) {
      const y = side * 0.455;
      const ring = new THREE.Mesh(new THREE.TorusGeometry(0.28, 0.028, 10, 28), frame);
      ring.position.set(0.21, y, 0.06);
      ring.rotation.x = Math.PI / 2;
      g.add(ring);
      const lens = new THREE.Mesh(new THREE.CircleGeometry(0.28, 24), glass);
      lens.position.set(0.21, y * 0.985, 0.06);
      lens.rotation.x = Math.PI / 2;
      g.add(lens);
      // дужка назад вдоль головы
      const temple = new THREE.Mesh(new THREE.CylinderGeometry(0.018, 0.018, 0.5, 6), frame);
      temple.position.set(-0.06, y * 0.95, 0.12);
      temple.rotation.z = Math.PI / 2;
      g.add(temple);
    }
    // перемычка по передней кромке головы
    const bridge = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.02, 0.92, 8), frame);
    bridge.position.set(0.40, 0, 0.15);
    g.add(bridge);
    return g;
  }

  /* Раскладка настоящая: русские буквы и латиница делят одну клавишу ровно так же,
     как на физической клавиатуре ЙЦУКЕН/QWERTY. Поэтому «С» из «Справочники» и «C»
     из «CatalogRef» жмутся одной и той же кнопкой — это не совпадение, это раскладка. */
  const LAYOUT = [
    {rus: 'ё1234567890-=', lat: '`1234567890-='},
    {rus: 'йцукенгшщзхъ',  lat: 'qwertyuiop[]'},
    {rus: 'фывапролджэ',   lat: "asdfghjkl;'"},
    {rus: 'ячсмитьбю.',    lat: 'zxcvbnm,./'},
  ];
  // верхний регистр цифрового ряда: двоеточие, скобки и прочее из логов 1С
  const SHIFT = {'!': '1', '"': '2', '№': '3', ';': '4', '%': '5', ':': '6',
                 '?': '7', '*': '8', '(': '9', ')': '0', '_': '-', '+': '='};
  const keyByChar = new Map();

  function keyLabel(rus, lat) {
    const cv = document.createElement('canvas');
    cv.width = cv.height = 64;
    const c = cv.getContext('2d');
    c.fillStyle = '#e9ede9'; c.fillRect(0, 0, 64, 64);
    c.fillStyle = '#2c332e'; c.font = 'bold 30px system-ui,sans-serif';
    c.textAlign = 'center'; c.fillText(rus.toUpperCase(), 32, 44);
    if (lat && lat !== rus) {
      c.fillStyle = '#8d968f'; c.font = '18px system-ui,sans-serif';
      c.textAlign = 'left'; c.fillText(lat.toUpperCase(), 5, 20);
    }
    const tex = new THREE.CanvasTexture(cv);
    tex.anisotropy = 4;
    return tex;
  }

  /* Клавиша знает свой символ: это и есть та карта, по которой лапка ищет,
     куда бить. Индекс в массиве keys ничего не решает. */
  function addKey(g, row, col, cols, rus, lat, keyTop, wide) {
    const pitch = 0.16, w = wide ? pitch * 6.2 : pitch * 0.88;
    const y = -(cols - 1) * pitch / 2 + col * pitch;
    const k = new THREE.Mesh(
      new THREE.BoxGeometry(pitch * 0.88, w, 0.05),
      [0, 1, 2, 3, 4, 5].map(i => new THREE.MeshStandardMaterial({
        color: 0xdfe4df, roughness: 0.6,
        map: i === 4 ? keyLabel(rus, lat) : null,
      }))
    );
    k.position.set(0.92 - row * 0.175, y, keyTop + 0.025);
    k.castShadow = true;
    k.userData = {home: k.position.z, rus, lat};
    g.add(k); keys.push(k);
    if (rus) keyByChar.set(rus, k);
    if (lat && lat !== rus) keyByChar.set(lat, k);
    return k;
  }

  function buildKeyboard(keyTop) {
    const g = new THREE.Group();
    LAYOUT.forEach((row, r) => {
      const n = Math.max(row.rus.length, row.lat.length);
      for (let c = 0; c < n; c++) {
        addKey(g, r, c, n, row.rus[c] || '', row.lat[c] || '', keyTop, false);
      }
    });
    const space = addKey(g, 4, 0, 1, '', '', keyTop, true);
    space.geometry = new THREE.BoxGeometry(0.14, 1.0, 0.05);
    keyByChar.set(' ', space);
    // верхний регистр и буквы-исключения ведут на ту же физическую клавишу
    for (const [ch, base] of Object.entries(SHIFT)) {
      const k = keyByChar.get(base);
      if (k) keyByChar.set(ch, k);
    }
    for (const ch of [...keyByChar.keys()]) {
      const up = ch.toUpperCase();
      if (up !== ch && !keyByChar.has(up)) keyByChar.set(up, keyByChar.get(ch));
    }
    // длинное тире в логах 1С набирается той же клавишей, что и дефис
    for (const [ch, base] of Object.entries({'—': '-', '–': '-'})) {
      const k = keyByChar.get(base);
      if (k) keyByChar.set(ch, k);
    }
    return g;
  }

  function buildDesk(keyTop) {
    const g = new THREE.Group();
    // высоты подобраны по самой модели: задние лапки стоят на столе (z=-1.92),
    // передние — на клавиатуре (z=-1.23)
    const desk = new THREE.Mesh(
      new THREE.BoxGeometry(11, 8, 0.3),
      new THREE.MeshStandardMaterial({color: 0xb7c0ba, roughness: 1.0})
    );
    desk.position.set(-0.6, 0, -2.07);
    desk.receiveShadow = true;
    g.add(desk);
    const base = new THREE.Mesh(
      new THREE.BoxGeometry(2.2, 2.6, 0.2),
      new THREE.MeshStandardMaterial({color: 0x2f3833, roughness: 0.8})
    );
    base.position.set(0.62, 0, keyTop - 0.1);
    base.receiveShadow = true;
    g.add(base);
    g.add(buildKeyboard(keyTop));
    return g;
  }

  function init(el, D) {
    host = el;
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0xdfe6e3);
    camera = new THREE.PerspectiveCamera(30, 16 / 10, 0.1, 100);
    camera.position.set(4.4, -9.6, 2.6);
    camera.up.set(0, 0, 1);
    camera.lookAt(-0.15, 0, -0.35);

    scene.add(new THREE.HemisphereLight(0xffffff, 0x9aa49e, 0.25));
    scene.add(new THREE.AmbientLight(0xffffff, 0.06));
    const key = new THREE.DirectionalLight(0xfff4e2, 0.9);
    key.position.set(5, -4, 7);
    key.castShadow = true;
    scene.add(key);
    const rim = new THREE.DirectionalLight(0xfff0c0, 0.28);
    rim.position.set(-6, 3, 2);
    scene.add(rim);
    spot = new THREE.PointLight(0xffd200, 0.0, 8);
    spot.position.set(1.6, 0, 1.4);
    scene.add(spot);

    const fly = buildFly(D);
    scene.add(fly);
    settle();
    fly.updateMatrixWorld(true);
    // сажаем муху ровно на стол: задние лапки касаются столешницы,
    // клавиатура подставляется под фактическую высоту передних
    const DESK_TOP = -1.92;
    // высоту тела задают средние лапки: они самые короткие, тянуться им некуда
    const mid = new THREE.Box3().setFromObject(nodes['LMTarsus5'] || fly);
    body = fly;
    fly.position.z += DESK_TOP - mid.min.z;
    fly.updateMatrixWorld(true);
    // задние поджимаются до столешницы — у них запас хода есть
    for (const s of ['L', 'R']) groundLeg(s + 'H', DESK_TOP, fly);
    // передние ставим в рабочую позу и подводим клавиатуру ровно под них
    frontLeg('L', 0.18, 0);
    frontLeg('R', 0.18, 0);
    fly.updateMatrixWorld(true);
    const front = new THREE.Box3().setFromObject(nodes['LFTarsus5'] || fly);
    scene.add(buildDesk(front.min.z - 0.03));
    const ly = new THREE.Vector3(), ry = new THREE.Vector3();
    nodes['LFTarsus5'].getWorldPosition(ly);
    nodes['RFTarsus5'].getWorldPosition(ry);
    sideByY = ly.y > ry.y ? {plus: 'L', minus: 'R'} : {plus: 'R', minus: 'L'};
    bodyHome = fly.position.clone();

    glasses = buildGlasses();
    (nodes['Head'] || fly).add(glasses);

    // preserveDrawingBuffer нужен, чтобы кадр можно было сохранить или снять со страницы
    renderer = new THREE.WebGLRenderer({antialias: true, alpha: false,
                                        preserveDrawingBuffer: true});
    renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
    // без sRGB и тонмаппинга картинка выглядит выцветшей
    renderer.outputEncoding = THREE.sRGBEncoding;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 0.85;
    renderer.shadowMap.enabled = true;
    el.appendChild(renderer.domElement);
    resize();
    window.addEventListener('resize', resize);
    return api;
  }

  function resize() {
    if (!renderer || !host) return;
    const w = host.clientWidth || 420;
    const h = Math.round(w * 10 / 16);
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }

  /* посадочная поза: у модели лапки в «полётном» положении, сажаем муху на стол */
  function settle() {
    for (const s of ['L', 'R']) {
      rot(s + 'MFemur', 0.30);
      rot(s + 'MTibia', -0.22);
      rot(s + 'HFemur', 0.06);
    }
    // крылья сложены вдоль брюшка: сустав _roll разворачивает их назад
    rot('LWing_roll', 1.45); rot('LWing_yaw', -0.22);
    rot('RWing_roll', -1.45); rot('RWing_yaw', 0.22);
  }

  /* подгибаем ногу (бедро + голень) так, чтобы кончик лапки встал на столешницу */
  function groundLeg(prefix, targetZ, root3) {
    const tip = nodes[prefix + 'Tarsus5'];
    if (!tip) return;
    const femur = prefix + 'Femur', tibia = prefix + 'Tibia';
    const box = new THREE.Box3();
    const coxaYaw = prefix + 'Coxa_yaw';
    const measure = (a, b, c) => {
      rot(femur, a); rot(tibia, b); rot(coxaYaw, c);
      root3.updateMatrixWorld(true);
      return box.setFromObject(tip).min.z;
    };
    let best = null;
    for (let c = -0.7; c <= 0.7001; c += 0.175) {
      for (let a = -1.0; a <= 1.2001; a += 0.15) {
        for (let b = -1.0; b <= 1.0001; b += 0.2) {
          const z = measure(a, b, c);
          // тянемся к столешнице, но суставы без надобности не выкручиваем
          const err = Math.abs(z - targetZ) + 0.03 * Math.abs(b) + 0.05 * Math.abs(c);
          if (!best || err < best.err) best = {a, b, c, err, z};
        }
      }
    }
    measure(best.a, best.b, best.c);
  }

  /* Куда бить: подбираем углы суставов так, чтобы кончик лапки (Tarsus5) попал
     в центр конкретной клавиши. Перебор грубый, но считается один раз на клавишу
     и кладётся в кэш — дальше поза просто берётся готовой. */
  const ikCache = new Map();
  const TARSUS = -0.05;   // положение последнего сустава при ударе по клавише
  const _v = new THREE.Vector3(), _t = new THREE.Vector3();

  function legIK(prefix, key) {
    const tag = prefix + '|' + key.userData.rus + key.position.y.toFixed(3);
    if (ikCache.has(tag)) return ikCache.get(tag);
    const tip = nodes[prefix + 'Tarsus5'];
    const base = nodes[prefix + 'Coxa_yaw'] || nodes[prefix + 'Coxa'];
    if (!tip || !base) return null;
    // считаем от домашнего положения корпуса: иначе поза предыдущей клавиши
    // уезжает в кэш следующей и ошибка накапливается
    homeBody();
    if (body) body.updateMatrixWorld(true);
    key.getWorldPosition(_t);
    _t.z += 0.06;                      // целимся в верхнюю грань, а не в центр кубика
    const measure = (a) => {
      rot(prefix + 'Coxa_yaw', a[0]);
      rot(prefix + 'Femur', a[1]);
      rot(prefix + 'Tibia', a[2]);
      rot(prefix + 'Coxa_roll', a[3]);
      rot(prefix + 'Coxa', a[4]);
      // тот же угол лапки, что и при печати: иначе решение верное, а удар мимо
      rot(prefix + 'Tarsus1', TARSUS);
      base.updateMatrixWorld(true);
      return tip.getWorldPosition(_v).distanceTo(_t);
    };
    // грубый проход по трём главным суставам
    let a = [0, -0.24, 0.62, 0, 0], err = measure(a);
    for (let yaw = -1.0; yaw <= 1.0001; yaw += 0.1) {
      for (let f = -1.2; f <= 1.0001; f += 0.11) {
        for (let b = -0.6; b <= 1.5001; b += 0.11) {
          const cand = [yaw, f, b, 0, 0], e = measure(cand);
          if (e < err) { err = e; a = cand; }
        }
      }
    }
    // покоординатное уточнение с уменьшающимся шагом: грубой сетки мало,
    // шаг клавиш 0.16, а промах в 0.3 — это две клавиши мимо
    for (let stepSize = 0.12; stepSize > 0.004; stepSize *= 0.55) {
      let moved = true;
      while (moved) {
        moved = false;
        for (let i = 0; i < 5; i++) {
          for (const d of [stepSize, -stepSize]) {
            const cand = a.slice();
            cand[i] += d;
            const e = measure(cand);
            if (e < err - 1e-5) { err = e; a = cand; moved = true; }
          }
        }
      }
    }
    // до крайних клавиш лапке не дотянуться — остаток добираем корпусом,
    // как это делает живой человек за клавиатурой: не тянет палец, а подаётся телом
    measure(a);
    tip.getWorldPosition(_v);
    const dx = _t.x - _v.x, dy = _t.y - _v.y;
    const len = Math.hypot(dx, dy), cap = Math.min(len, 0.35);
    const best = {
      yaw: a[0], femur: a[1], tibia: a[2], roll: a[3], coxa: a[4], err,
      shift: len > 1e-4 ? {x: dx / len * cap, y: dy / len * cap} : {x: 0, y: 0},
    };
    ikCache.set(tag, best);
    return best;
  }

  /* какой лапке эта клавиша ближе — решает измеренная ошибка, а не сторона по y */
  const sideCache = new Map();
  function bestSide(key) {
    const tag = key.userData.rus + key.position.y.toFixed(3);
    if (sideCache.has(tag)) return sideCache.get(tag);
    const l = legIK('LF', key), r = legIK('RF', key);
    const pick = (!r || (l && l.err <= r.err)) ? 'L' : 'R';
    sideCache.set(tag, pick);
    return pick;
  }

  function homeBody() {
    if (body && bodyHome) { body.position.x = bodyHome.x; body.position.y = bodyHome.y; }
  }

  function rot(name, angle) {
    const n = nodes[name];
    if (!n) return;
    n.quaternion.setFromAxisAngle(n.userData.axis, angle);
  }

  /* поза лапки: три сустава одной передней ноги */
  function frontLeg(side, lift, reach) {
    const p = side + 'F';
    rot(p + 'Coxa_roll', reach * 0.55);
    rot(p + 'Femur', -0.35 + lift * 0.55 + reach * 0.75);
    rot(p + 'Tibia', 0.75 - lift * 0.7 - reach * 0.55);
    rot(p + 'Tarsus1', 0.3 - lift * 0.35);
  }

  const api = {
    init,
    resize,
    /* p: 0..1 — насколько глубоко муха задумалась */
    think(p, t) {
      homeBody();
      const slip = p * 0.34;
      glasses.position.set(-slip * 0.35, 0, -slip);
      glasses.rotation.y = slip * 0.5;
      rot('Head', -0.10 - 0.12 * p + Math.sin(t * 2.2) * 0.02);
      frontLeg('L', 0.15 + 0.05 * Math.sin(t * 1.7), 0);
      frontLeg('R', 0.12, 0);
      spot.intensity = 0.4 + 1.6 * p;
      for (const k of keys) {
        k.position.z = k.userData.home;
        k.material[4].color.setHex(0xffffff);
      }
    },
    /* лапка поднимается к очкам и возвращает их на место */
    adjust(p) {
      homeBody();
      const back = 1 - p;
      const k = Math.sin(p * Math.PI);
      glasses.position.set(-back * 0.12, 0, -back * 0.34);
      glasses.rotation.y = back * 0.5;
      frontLeg('R', 0.1, k);
      frontLeg('L', 0.12, 0);
      rot('Head', -0.10 + k * 0.05);
      spot.intensity = 0.5;
    },
    /* Печать: ch — символ, который набирается прямо сейчас, u — 0..1 внутри удара.
       Лапка идёт к той клавише, на которой этот символ написан, и вдавливает её. */
    type(t, ch, u) {
      rot('Head', -0.16 + Math.sin(t * 8) * 0.015);
      glasses.position.set(0, 0, 0);
      glasses.rotation.y = 0;
      rot('LWing', Math.sin(t * 30) * 0.12);
      rot('RWing', -Math.sin(t * 30) * 0.12);
      spot.intensity = 0.25;
      for (const k of keys) {
        k.position.z = k.userData.home;
        k.material[4].color.setHex(0xffffff);
      }
      const key = keyByChar.get(ch);
      if (!key) {                       // символа нет на раскладке — не врём, лапки ждут
        frontLeg('L', 0.20, 0); frontLeg('R', 0.20, 0);
        homeBody();
        return;
      }
      // рукой ближе к клавише: у передних лапок разный знак по y
      // клавишу берёт та лапка, которая до неё реально дотягивается: знак координаты
      // угадывает неверно для среднего ряда, а промах там был в целую клавишу
      const side = bestSide(key);
      const other = side === 'L' ? 'R' : 'L';
      const leg = side + 'F';          // узлы скелета зовутся LFCoxa_yaw, LFFemur и т.д.
      const pose = legIK(leg, key);
      frontLeg(other, 0.20, 0);
      if (!pose) return;
      const uu = Math.max(0, Math.min(1, u));
      // замах в первой половине удара, попадание во второй
      const swing = uu < 0.5 ? uu * 2 : 1;
      const hit = uu < 0.5 ? 0 : (uu - 0.5) * 2;
      const rest = {yaw: 0, femur: -0.24, tibia: 0.62};
      const mix = (a, b) => a + (b - a) * swing;
      rot(leg + 'Coxa_yaw', mix(rest.yaw, pose.yaw));
      // подъём только на замахе: к моменту касания он обязан быть нулём,
      // иначе лапка систематически висит мимо клавиши
      const lift = uu < 0.5 ? 0.18 * Math.sin(uu * Math.PI * 2) : 0;
      rot(leg + 'Femur', mix(rest.femur, pose.femur) - lift);
      rot(leg + 'Tibia', mix(rest.tibia, pose.tibia));
      rot(leg + 'Coxa_roll', mix(0, pose.roll));
      rot(leg + 'Coxa', mix(0, pose.coxa));
      rot(leg + 'Tarsus1', TARSUS);
      if (body && bodyHome) {
        body.position.x = bodyHome.x + pose.shift.x * swing;
        body.position.y = bodyHome.y + pose.shift.y * swing;
      }
      if (hit > 0) {
        key.position.z = key.userData.home - 0.03 * Math.sin(hit * Math.PI);
        key.material[4].color.setHex(0xffd200);
      }
    },
    idle(t) {
      homeBody();
      frontLeg('L', 0.12 + Math.sin(t) * 0.03, 0);
      frontLeg('R', 0.12 + Math.cos(t) * 0.03, 0);
      rot('Head', -0.1);
      spot.intensity = 0.2;
    },
    /* какая клавиша отвечает за символ — для подписи на странице */
    keyFor(ch) {
      const k = keyByChar.get(ch);
      return k ? {rus: k.userData.rus, lat: k.userData.lat} : null;
    },
    /* Проверка попадания: бьём по символу и меряем, где оказался кончик лапки
       относительно центра клавиши. Нужно, чтобы «муха жмёт кнопку» было
       утверждением с числом, а не обещанием. */
    probe(ch) {
      const key = keyByChar.get(ch);
      if (!key) return {ch, found: false};
      api.type(0, ch, 0.9);
      scene.updateMatrixWorld(true);
      const side = bestSide(key);
      const tip = new THREE.Vector3(), kp = new THREE.Vector3();
      nodes[side + 'FTarsus5'].getWorldPosition(tip);
      key.getWorldPosition(kp);
      return {
        ch, found: true, label: key.userData.rus, lat: key.userData.lat, side,
        dist: +tip.distanceTo(kp).toFixed(3),
        ikErr: +((legIK(side + 'F', key) || {err: -1}).err).toFixed(3),
        shift: (legIK(side + 'F', key) || {shift: null}).shift,
        bodyOff: body && bodyHome
          ? +Math.hypot(body.position.x - bodyHome.x, body.position.y - bodyHome.y).toFixed(3)
          : null,
        dxy: +Math.hypot(tip.x - kp.x, tip.y - kp.y).toFixed(3),
        pressed: +(key.userData.home - key.position.z).toFixed(4),
        keys: keys.length,
      };
    },
    /* координаты опорных точек — чтобы проверять посадку, не гадая по картинке */
    debug() {
      const box = n => {
        const b = new THREE.Box3().setFromObject(nodes[n]);
        return [+b.min.z.toFixed(3), +b.max.z.toFixed(3)];
      };
      return {
        hindTarsus: box('LHTarsus5'), midTarsus: box('LMTarsus5'),
        frontTarsus: box('LFTarsus5'), deskTop: -1.92,
        keyTop: keys.length ? +(keys[0].position.z + 0.025).toFixed(3) : null,
        glasses: [+glasses.position.x.toFixed(3), +glasses.position.z.toFixed(3)]
      };
    },
    render(dt) {
      clock += dt;
      if (renderer) renderer.render(scene, camera);
    }
  };
  return api;
})();
"""


def rig_js() -> str:
    return RIG_JS


def three_js() -> str:
    return (ASSETS / "three.min.js").read_text(encoding="utf-8")


def fly_data_js(lite: bool = False) -> str:
    name = "fly3d_lite.json" if lite else "fly3d.json"
    data = (ASSETS / name).read_text(encoding="utf-8")
    return "window.FLY3D=" + data + ";"


TEST_PAGE = r"""<!doctype html><html lang="ru"><meta charset="utf-8">
<title>3D муха — проверка</title>
<style>body{background:#0b1410;color:#d7e6dc;font:13px ui-monospace,monospace;margin:0;padding:12px}
#box{width:560px;border:1px solid #1e3428;border-radius:6px;overflow:hidden}
button{background:#132018;color:#d7e6dc;border:1px solid #1e3428;border-radius:4px;
padding:5px 10px;font:inherit;margin-right:6px;cursor:pointer}</style>
<div id="box"></div>
<p><button data-m="think">думает</button><button data-m="adjust">поправляет</button>
<button data-m="type">печатает</button><button data-m="idle">покой</button>
<span id="info"></span></p>
<script>__THREE__</script>
<script>__DATA__</script>
<script>__RIG__</script>
<script>
FlyRig.init(document.getElementById('box'), FLY3D);
document.getElementById('info').textContent =
  FLY3D.triangles + ' треугольников · ' + FLY3D.links.length + ' звеньев скелета';
let mode = 'think', t = 0, p = 0, last = performance.now();
document.querySelectorAll('button').forEach(b => b.onclick = () => { mode = b.dataset.m; p = 0; });
(function loop(now) {
  const dt = Math.min(0.05, (now - last) / 1000); last = now; t += dt;
  p = Math.min(1, p + dt * 0.8);
  if (mode === 'think') FlyRig.think(p, t);
  else if (mode === 'adjust') FlyRig.adjust(p);
  else if (mode === 'type') FlyRig.type(t, 'йцукен'[Math.floor(t * 4) % 6], (t * 4) % 1);
  else FlyRig.idle(t);
  FlyRig.render(dt);
  requestAnimationFrame(loop);
})(performance.now());
</script>
</html>"""


def build_test(out: Path) -> Path:
    html = (TEST_PAGE.replace("__THREE__", three_js())
            .replace("__DATA__", fly_data_js())
            .replace("__RIG__", RIG_JS))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out


if __name__ == "__main__":
    p = build_test(ROOT / "report" / "fly3d.html")
    print(p, p.stat().st_size // 1024, "КБ")
