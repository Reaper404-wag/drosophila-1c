"""Кинематографичная страница: муха в студийном свете и объёмный мозг из синапсов.

Слева — модель NeuroMechFly с постобработкой (свечение, тёмная студия, медленный облёт).
Справа — 250 тысяч настоящих координат синапсов FlyWire, нарисованных аддитивно
с раскраской по глубине: так объём читается без воксельного рендера.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"

PAGE = r"""<!doctype html><html lang="ru"><meta charset="utf-8">
<title>Муха · студия</title>
<style>
:root{--ink:#dfe8f2;--dim:#7d90a6;--line:#16202c}
*{box-sizing:border-box}
body{margin:0;background:#05080c;color:var(--ink);
font:12.5px/1.5 "Cascadia Mono",Consolas,ui-monospace,monospace;overflow:hidden}
.wrap{display:grid;grid-template-columns:1fr 1fr;height:100vh;gap:2px;background:#0b1118}
.pane{position:relative;overflow:hidden}
.cap{position:absolute;left:14px;top:12px;letter-spacing:.12em;font-size:11px;
color:var(--dim);text-transform:uppercase;z-index:2;text-shadow:0 0 12px #000}
.cap b{color:#ffd200}
.sub{position:absolute;left:14px;bottom:12px;color:var(--dim);font-size:11px;z-index:2;
text-shadow:0 0 12px #000}
.legend{position:absolute;left:14px;bottom:34px;z-index:2;display:flex;gap:12px;flex-wrap:wrap;
max-width:calc(100% - 28px);color:var(--dim);font-size:10.5px;text-shadow:0 0 12px #000}
.legend i{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:4px}
.mode{position:absolute;left:14px;bottom:34px;z-index:2;color:var(--dim);font-size:11px;
letter-spacing:.06em;text-shadow:0 0 12px #000}
.mode b{color:#ffd200}
canvas{display:block}
.ctl{position:absolute;right:12px;top:10px;z-index:3;display:flex;gap:6px}
.ctl button{background:#0e1720cc;color:var(--ink);border:1px solid var(--line);
border-radius:3px;padding:4px 9px;font:inherit;font-size:11px;cursor:pointer}
.ctl button:hover{border-color:#ffd200}
</style>
<div class="wrap">
  <div class="pane" id="left">
    <div class="cap"><b>МУХА</b> / NeuroMechFly · студийный свет</div>
    <div class="sub" id="lsub"></div>
    <div class="ctl"><button id="spin">вращение: вкл</button>
      <button id="lshot">кадр в PNG</button></div>
    <div class="mode">муха: <b id="lmode">думает</b></div>
  </div>
  <div class="pane" id="right">
    <div class="cap"><b>МОЗГ</b> / FlyWire · синапсы объёмом</div>
    <div class="sub" id="rsub"></div>
    <div class="legend" id="rlegend"></div>
    <div class="ctl"><button id="dense">точки: ярче</button>
      <button id="shot">кадр в PNG</button></div>
  </div>
</div>
<script>__THREE__</script>
<script>__PP__</script>
<script>__FLY__</script>
<script>__CLOUD__</script>
<script>
/* ============ левая панель: муха в студии ============ */
const L = document.getElementById('left');
const lScene = new THREE.Scene();
lScene.background = new THREE.Color(0x05080c);
lScene.fog = new THREE.FogExp2(0x03060a, 0.055);
const lCam = new THREE.PerspectiveCamera(32, 1, 0.1, 200);
lCam.up.set(0, 0, 1);

const lRen = new THREE.WebGLRenderer({antialias: true, preserveDrawingBuffer: true});
lRen.setPixelRatio(Math.min(2, devicePixelRatio || 1));
lRen.outputEncoding = THREE.sRGBEncoding;
lRen.toneMapping = THREE.ACESFilmicToneMapping;
lRen.toneMappingExposure = 0.9;
lRen.shadowMap.enabled = true;
lRen.shadowMap.type = THREE.PCFSoftShadowMap;
L.appendChild(lRen.domElement);

/* свет студии: холодный контровой + тёплый ключевой + мягкая заливка */
lScene.add(new THREE.HemisphereLight(0x22344a, 0x05080c, 0.25));
const key = new THREE.SpotLight(0xffe6c0, 2.6, 40, 0.55, 0.5, 1.2);
key.position.set(5, -7, 9);
key.castShadow = true;
key.shadow.mapSize.set(1024, 1024);
lScene.add(key);
const rim = new THREE.SpotLight(0x63d6ff, 1.5, 40, 0.7, 0.7, 1.1);
rim.position.set(-7, 5, 4);
lScene.add(rim);
const fill = new THREE.PointLight(0xff9a4d, 0.7, 18);
fill.position.set(2.5, 3, 1);
lScene.add(fill);

/* пол: тёмная сетка со свечением, как на референсе */
const grid = new THREE.GridHelper(60, 60, 0x0d3346, 0x08202c);
grid.rotation.x = Math.PI / 2;
grid.position.z = -1.93;
lScene.add(grid);
const floor = new THREE.Mesh(
  new THREE.PlaneGeometry(80, 80),
  new THREE.MeshStandardMaterial({color: 0x070b11, roughness: 0.75, metalness: 0.3})
);
floor.position.z = -1.94;
floor.receiveShadow = true;
lScene.add(floor);

/* муха: те же детали NeuroMechFly, что и в сцене */
function decode(b64) {
  const raw = atob(b64), bytes = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
  return new Int16Array(bytes.buffer);
}
const FLY = window.FLY3D;
const fbuf = decode(FLY.buffer);
const nodes = {};
const flyRoot = new THREE.Group();
const COLORS = {eye: 0x7d0f08, wing: 0xcfe4f5, leg: 0x5b3714, body: 0xa8621d, head: 0x9c5c1b};
function colorFor(name) {
  if (/Eye/.test(name)) return COLORS.eye;
  if (/Wing|Haltere/.test(name)) return COLORS.wing;
  if (/Coxa|Femur|Tibia|Tarsus|Antenna/.test(name)) return COLORS.leg;
  if (/Head|Rostrum|Haustellum/.test(name)) return COLORS.head;
  return COLORS.body;
}
for (const link of FLY.links) {
  const node = new THREE.Group();
  node.position.set(link.t[0], link.t[1], link.t[2]);
  node.userData.axis = new THREE.Vector3(...link.axis);
  nodes[link.name] = node;
  (link.parent ? nodes[link.parent] : flyRoot).add(node);
  if (link.mesh === null || link.mesh === undefined) continue;
  const m = FLY.meshes[link.mesh];
  const q = fbuf.subarray(m.off / 2, m.off / 2 + m.len);
  const pos = new Float32Array(m.len);
  for (let i = 0; i < m.len; i += 3) {
    pos[i] = (q[i] + 32768) / 65535 * m.span[0] + m.lo[0];
    pos[i + 1] = (q[i + 1] + 32768) / 65535 * m.span[1] + m.lo[1];
    pos[i + 2] = (q[i + 2] + 32768) / 65535 * m.span[2] + m.lo[2];
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  geo.computeVertexNormals();
  const wing = /Wing/.test(link.name);
  const mat = wing
    ? new THREE.MeshPhysicalMaterial({color: COLORS.wing, transparent: true, opacity: 0.18,
        roughness: 0.08, metalness: 0, transmission: 0.85, thickness: 0.2,
        side: THREE.DoubleSide})
    // в three r128 sheen — это Color, а не число: передашь число — ломается загрузка юниформа
    : new THREE.MeshPhysicalMaterial({color: colorFor(link.name), roughness: 0.52,
        metalness: 0.06, clearcoat: 0.45, clearcoatRoughness: 0.35,
        side: THREE.DoubleSide});
  const mesh = new THREE.Mesh(geo, mat);
  mesh.castShadow = mesh.receiveShadow = !wing;
  node.add(mesh);
}
/* очки: линзы смотрят наружу, потому что глаза у мухи по бокам головы */
function buildGlasses() {
  const g = new THREE.Group();
  const frame = new THREE.MeshPhysicalMaterial({
    color: 0x2b2b2b, roughness: 0.28, metalness: 0.75, clearcoat: 0.6});
  const glass = new THREE.MeshPhysicalMaterial({
    color: 0xbfe4ff, transparent: true, opacity: 0.24, roughness: 0.04,
    metalness: 0, transmission: 0.8, side: THREE.DoubleSide});
  for (const side of [1, -1]) {
    const y = side * 0.455;
    const ring = new THREE.Mesh(new THREE.TorusGeometry(0.28, 0.028, 12, 30), frame);
    ring.position.set(0.21, y, 0.06);
    ring.rotation.x = Math.PI / 2;
    g.add(ring);
    const lens = new THREE.Mesh(new THREE.CircleGeometry(0.28, 26), glass);
    lens.position.set(0.21, y * 0.985, 0.06);
    lens.rotation.x = Math.PI / 2;
    g.add(lens);
    const temple = new THREE.Mesh(new THREE.CylinderGeometry(0.018, 0.018, 0.5, 8), frame);
    temple.position.set(-0.06, y * 0.95, 0.12);
    temple.rotation.z = Math.PI / 2;
    g.add(temple);
  }
  const bridge = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.02, 0.92, 10), frame);
  bridge.position.set(0.40, 0, 0.15);
  g.add(bridge);
  return g;
}

lScene.add(flyRoot);
function rot(name, a) {
  const n = nodes[name];
  if (n) n.quaternion.setFromAxisAngle(n.userData.axis, a);
}
rot('LWing_roll', 1.45); rot('LWing_yaw', -0.22);
rot('RWing_roll', -1.45); rot('RWing_yaw', 0.22);
const glasses = buildGlasses();
(nodes['Head'] || flyRoot).add(glasses);

flyRoot.updateMatrixWorld(true);
const box = new THREE.Box3().setFromObject(flyRoot);
flyRoot.position.z += -1.93 - box.min.z;

/* поза передней лапки: подъём и «дотянуться до очков» */
function frontLeg(side, lift, reach) {
  const p = side + 'F';
  rot(p + 'Coxa_roll', reach * 0.55);
  rot(p + 'Femur', -0.35 + lift * 0.55 + reach * 0.8);
  rot(p + 'Tibia', 0.75 - lift * 0.7 - reach * 0.6);
  rot(p + 'Tarsus1', 0.3 - lift * 0.35);
}

/* цикл: думает — очки сползают; решила — лапка возвращает их на место; печатает */
const CYCLE = [
  {name: 'думает', dur: 3.4},
  {name: 'поправляет очки', dur: 1.1},
  {name: 'печатает', dur: 2.6},
];
let phase = 0, phaseT = 0;
function animateFly(dt, now) {
  phaseT += dt;
  const cur = CYCLE[phase];
  const p = Math.min(1, phaseT / cur.dur);
  if (cur.name === 'думает') {
    const slip = p * 0.34;
    glasses.position.set(-slip * 0.35, 0, -slip);
    glasses.rotation.y = slip * 0.5;
    rot('Head', -0.10 - 0.12 * p + Math.sin(now * 1.7) * 0.02);
    frontLeg('L', 0.14 + 0.04 * Math.sin(now * 1.4), 0);
    frontLeg('R', 0.12, 0);
  } else if (cur.name === 'поправляет очки') {
    const back = 1 - p, k = Math.sin(p * Math.PI);
    glasses.position.set(-back * 0.12, 0, -back * 0.34);
    glasses.rotation.y = back * 0.5;
    frontLeg('R', 0.1, k);
    frontLeg('L', 0.12, 0);
    rot('Head', -0.10 + k * 0.06);
  } else {
    glasses.position.set(0, 0, 0);
    glasses.rotation.y = 0;
    const a = Math.sin(now * 15), b = -a;
    frontLeg('L', 0.30 + a * 0.26, 0);
    frontLeg('R', 0.30 + b * 0.26, 0);
    rot('Head', -0.16 + Math.sin(now * 7) * 0.015);
  }
  if (p >= 1) { phase = (phase + 1) % CYCLE.length; phaseT = 0; }
  document.getElementById('lmode').textContent = cur.name;
}
document.getElementById('lsub').textContent =
  FLY.triangles.toLocaleString('ru') + ' треугольников · ' + FLY.links.length + ' звеньев скелета';

/* постобработка: свечение делает кадр «киношным» */
const lComposer = new THREE.EffectComposer(lRen);
lComposer.addPass(new THREE.RenderPass(lScene, lCam));
const bloom = new THREE.UnrealBloomPass(new THREE.Vector2(1, 1), 0.32, 0.7, 0.82);
lComposer.addPass(bloom);

/* ============ правая панель: объём мозга ============ */
const R = document.getElementById('right');
const rScene = new THREE.Scene();
rScene.background = new THREE.Color(0x02070c);
const rCam = new THREE.PerspectiveCamera(32, 1, 0.1, 100);

const rRen = new THREE.WebGLRenderer({antialias: true, preserveDrawingBuffer: true});
rRen.setPixelRatio(Math.min(2, devicePixelRatio || 1));
rRen.outputEncoding = THREE.sRGBEncoding;
R.appendChild(rRen.domElement);

const CL = window.CLOUD;
function bytesOf(b64) {
  const raw = atob(b64), out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}
const cq = new Uint16Array(bytesOf(CL.p).buffer);
const cg = bytesOf(CL.g);
const N = CL.n;

/* анатомическая плоскость: x — вправо, y — вверх, глубина — z.
   Раньше камера стояла вдоль y и смотрела на мозг «сверху», отчего он читался мазком. */
const cpos = new Float32Array(N * 3);
const cgrp = new Float32Array(N);
const fit = 9.4 / Math.max(CL.span[0], CL.span[1], CL.span[2]);
for (let i = 0; i < N; i++) {
  cpos[i * 3] = (cq[i * 3] / 65535 - 0.5) * CL.span[0] * fit;
  cpos[i * 3 + 1] = -(cq[i * 3 + 1] / 65535 - 0.5) * CL.span[1] * fit;
  cpos[i * 3 + 2] = (cq[i * 3 + 2] / 65535 - 0.5) * CL.span[2] * fit;
  cgrp[i] = cg[i];
}
const cgeo = new THREE.BufferGeometry();
cgeo.setAttribute('position', new THREE.BufferAttribute(cpos, 3));
cgeo.setAttribute('grp', new THREE.BufferAttribute(cgrp, 1));

/* цвета отделов мозга — как в научных схемах */
const PALETTE = [
  [0.21, 0.78, 1.00],  // зрительные доли
  [1.00, 0.82, 0.12],  // антеннальные доли
  [1.00, 0.48, 0.24],  // грибовидные тела
  [0.71, 0.49, 1.00],  // центральный комплекс
  [0.24, 0.86, 0.59],  // латеральный рог
  [1.00, 0.36, 0.56],  // подглоточная зона
  [0.54, 0.63, 0.73],  // остальной мозг
];
const palFlat = [];
PALETTE.forEach(c => palFlat.push(...c));

const cloudMat = new THREE.ShaderMaterial({
  uniforms: {
    uSize: {value: 2.0},
    uAlpha: {value: Math.min(0.22, Math.max(0.02, 26.0 / Math.sqrt(N)))},
    uPal: {value: palFlat},
    uNear: {value: 5.2},
    uFar: {value: 11.5},
  },
  transparent: true,
  depthWrite: false,
  blending: THREE.AdditiveBlending,
  vertexShader: `
    attribute float grp;
    varying float vDepth;
    varying float vGrp;
    uniform float uSize;
    void main() {
      vec4 mv = modelViewMatrix * vec4(position, 1.0);
      vDepth = -mv.z;
      vGrp = grp;
      // точка фиксированного размера: мелкие жёсткие точки дают структуру,
      // крупные мягкие спрайты превращают мозг в дым
      gl_PointSize = uSize;
      gl_Position = projectionMatrix * mv;
    }`,
  fragmentShader: `
    varying float vDepth;
    varying float vGrp;
    uniform float uAlpha, uNear, uFar;
    uniform vec3 uPal[7];
    void main() {
      vec2 c = gl_PointCoord - 0.5;
      if (dot(c, c) > 0.25) discard;
      int g = int(vGrp + 0.5);
      vec3 col = uPal[6];
      for (int i = 0; i < 7; i++) if (i == g) col = uPal[i];
      // дальние точки тускнеют — так читается объём
      float t = clamp((vDepth - uNear) / (uFar - uNear), 0.0, 1.0);
      float dim = mix(1.0, 0.28, t);
      gl_FragColor = vec4(col * dim, uAlpha);
    }`,
});
const cloud = new THREE.Points(cgeo, cloudMat);
rScene.add(cloud);
document.getElementById('rsub').textContent =
  N.toLocaleString('ru') + ' синапсов из 34 миллионов · FlyWire v783';

const legend = document.getElementById('rlegend');
legend.innerHTML = (CL.titles || []).map((title, i) =>
  '<span><i style="background:rgb(' +
  PALETTE[i].map(v => Math.round(v * 255)).join(',') + ')"></i>' + title + '</span>').join('');

const rComposer = new THREE.EffectComposer(rRen);
rComposer.addPass(new THREE.RenderPass(rScene, rCam));
rComposer.addPass(new THREE.UnrealBloomPass(new THREE.Vector2(1, 1), 0.12, 0.9, 0.85));

/* ============ размеры и цикл ============ */
function resize() {
  for (const [el, ren, cam, comp] of [[L, lRen, lCam, lComposer], [R, rRen, rCam, rComposer]]) {
    const w = el.clientWidth, h = el.clientHeight;
    ren.setSize(w, h, false);
    comp.setSize(w, h);
    cam.aspect = w / h;
    cam.updateProjectionMatrix();
  }
}
addEventListener('resize', resize);
resize();

let spin = true, t = 0, prev = performance.now();
document.getElementById('spin').onclick = e => {
  spin = !spin;
  e.target.textContent = 'вращение: ' + (spin ? 'вкл' : 'выкл');
};
let bright = false;
document.getElementById('dense').onclick = e => {
  bright = !bright;
  const a0 = Math.min(0.22, Math.max(0.02, 26.0 / Math.sqrt(N)));
  cloudMat.uniforms.uAlpha.value = bright ? a0 * 2.2 : a0;
  cloudMat.uniforms.uSize.value = bright ? 2.8 : 2.0;
  e.target.textContent = 'точки: ' + (bright ? 'мягче' : 'ярче');
};

document.getElementById('lshot').onclick = () => {
  lComposer.render();
  const a = document.createElement('a');
  a.download = 'fly.png';
  a.href = lRen.domElement.toDataURL('image/png');
  a.click();
};
document.getElementById('shot').onclick = () => {
  rComposer.render();                       // кадр надо сохранять сразу после отрисовки
  const a = document.createElement('a');
  a.download = 'brain.png';
  a.href = rRen.domElement.toDataURL('image/png');
  a.click();
};

function loop(now) {
  now = now || performance.now();
  const dt = Math.min(0.05, (now - prev) / 1000);
  prev = now;
  animateFly(dt, now / 1000);
  if (spin) t += 0.0035;
  const r = 10.5;
  lCam.position.set(Math.cos(t) * r, Math.sin(t) * r, 3.4);
  lCam.lookAt(0, 0, -1.15);
  cloud.rotation.y = Math.sin(t * 0.7) * 0.45;   // лёгкий поворот, а не карусель
  rCam.position.set(0, 0, 8.4);
  rCam.up.set(0, 1, 0);
  rCam.lookAt(0, 0, 0);
  lComposer.render();
  rComposer.render();
  requestAnimationFrame(loop);
}
loop();
</script>
</html>"""


def build(out: Path, lite: bool = False) -> Path:
    three = (ASSETS / "three.min.js").read_text(encoding="utf-8")
    pp = "\n".join((ASSETS / "three" / name).read_text(encoding="utf-8") for name in (
        "CopyShader.js", "LuminosityHighPassShader.js", "EffectComposer.js",
        "RenderPass.js", "ShaderPass.js", "MaskPass.js", "UnrealBloomPass.js"))
    fly = (ASSETS / ("fly3d_lite.json" if lite else "fly3d.json")).read_text(encoding="utf-8")
    cloud = (ASSETS / "cloud.json").read_text(encoding="utf-8")
    html = (PAGE.replace("__THREE__", three)
            .replace("__PP__", pp)
            .replace("__FLY__", "window.FLY3D=" + fly + ";")
            .replace("__CLOUD__", "window.CLOUD=" + cloud + ";"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out


if __name__ == "__main__":
    p = build(ROOT / "report" / "cinema.html")
    print(p, p.stat().st_size // 1024, "КБ")
