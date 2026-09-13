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
    const keyMat = new THREE.MeshStandardMaterial({color: 0x4e5a53, roughness: 0.7});
    for (let r = 0; r < 5; r++) {
      for (let c = 0; c < 11; c++) {
        const k = new THREE.Mesh(new THREE.BoxGeometry(0.15, 0.15, 0.05), keyMat.clone());
        k.position.set(0.94 - r * 0.19, -1.0 + c * 0.2, keyTop + 0.02);
        g.add(k); keys.push(k);
      }
    }
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
      const slip = p * 0.34;
      glasses.position.set(-slip * 0.35, 0, -slip);
      glasses.rotation.y = slip * 0.5;
      rot('Head', -0.10 - 0.12 * p + Math.sin(t * 2.2) * 0.02);
      frontLeg('L', 0.15 + 0.05 * Math.sin(t * 1.7), 0);
      frontLeg('R', 0.12, 0);
      spot.intensity = 0.4 + 1.6 * p;
      keys.forEach(k => k.material.color.setHex(0x4e5a53));
    },
    /* лапка поднимается к очкам и возвращает их на место */
    adjust(p) {
      const back = 1 - p;
      const k = Math.sin(p * Math.PI);
      glasses.position.set(-back * 0.12, 0, -back * 0.34);
      glasses.rotation.y = back * 0.5;
      frontLeg('R', 0.1, k);
      frontLeg('L', 0.12, 0);
      rot('Head', -0.10 + k * 0.05);
      spot.intensity = 0.5;
    },
    /* печать: лапки стучат, подсвечивается клавиша */
    type(t, keyIndex) {
      const a = Math.sin(t * 16), b = Math.sin(t * 16 + Math.PI);
      frontLeg('L', 0.30 + a * 0.28, 0);
      frontLeg('R', 0.30 + b * 0.28, 0);
      rot('Head', -0.16 + Math.sin(t * 8) * 0.015);
      glasses.position.set(0, 0, 0);
      glasses.rotation.y = 0;
      rot('LWing', Math.sin(t * 30) * 0.12);
      rot('RWing', -Math.sin(t * 30) * 0.12);
      spot.intensity = 0.25;
      if (keys.length) {
        keys.forEach(k => k.material.color.setHex(0x4e5a53));
        const k = keys[Math.abs(keyIndex | 0) % keys.length];
        k.material.color.setHex(0xffd200);
      }
    },
    idle(t) {
      frontLeg('L', 0.12 + Math.sin(t) * 0.03, 0);
      frontLeg('R', 0.12 + Math.cos(t) * 0.03, 0);
      rot('Head', -0.1);
      spot.intensity = 0.2;
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
  else if (mode === 'type') FlyRig.type(t, Math.floor(t * 8));
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
