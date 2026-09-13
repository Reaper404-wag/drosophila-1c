"""Сборка 3D-мухи для сцены: меши NeuroMechFly + скелет из SDF -> компактный JSON.

Модель NeuroMechFly (NeLy-EPFL, Apache-2.0): 65 отдельных деталей тела и SDF с суставами.
Здесь меши прореживаются, квантуются в int16 и складываются вместе с деревом костей,
чтобы страница могла собрать анимируемую муху без внешних файлов.

    python tools/build_fly3d.py
"""
from __future__ import annotations

import base64
import json
import struct
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SDF = ROOT / "assets" / "nmf" / "neuromechfly.sdf"
STL_DIR = ROOT / "assets" / "nmf" / "stl"
OUT = ROOT / "assets" / "fly3d.json"

MESH_SCALE = 1000.0  # в SDF у всех визуалов scale 1000

# сколько треугольников оставляем: крупное — детальнее, лапки — грубее
BUDGET = {
    "Head": 4200, "LEye": 1400, "REye": 1400, "Thorax": 3200,
    "A1A2": 700, "A3": 600, "A4": 600, "A5": 600, "A6": 700,
    "LWing": 500, "RWing": 500, "Rostrum": 400, "Haustellum": 300,
    "LAntenna": 300, "RAntenna": 300, "LHaltere": 150, "RHaltere": 150,
}
DEFAULT_BUDGET = 260


def read_stl(path: Path) -> np.ndarray:
    """Бинарный STL -> (n, 3, 3) вершины треугольников."""
    data = path.read_bytes()
    n = struct.unpack_from("<I", data, 80)[0]
    if 84 + n * 50 != len(data):  # текстовый STL
        nums = np.array([float(x) for x in data.decode("ascii", "ignore").split()
                         if _isnum(x)], dtype=np.float32)
        return nums.reshape(-1, 3, 3)
    arr = np.frombuffer(data, dtype=np.uint8, count=n * 50, offset=84).reshape(n, 50)
    verts = arr[:, 12:48].copy().view(np.float32).reshape(n, 3, 3)
    return verts


def _isnum(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False


def decimate(tris: np.ndarray, target: int) -> np.ndarray:
    """Прореживание кластеризацией вершин: вершины стягиваются в узлы сетки."""
    if tris.shape[0] <= target:
        return tris
    v = tris.reshape(-1, 3)
    lo, hi = v.min(0), v.max(0)
    span = np.maximum(hi - lo, 1e-9)
    # подбираем шаг сетки так, чтобы треугольников осталось примерно target
    grid = max(4, int(round((target * 2) ** (1 / 2.2))))
    for _ in range(9):
        cell = np.floor((v - lo) / span * grid).clip(0, grid - 1).astype(np.int64)
        key = (cell[:, 0] * grid + cell[:, 1]) * grid + cell[:, 2]
        uniq, inv = np.unique(key, return_inverse=True)
        # центр каждой ячейки — среднее попавших вершин
        centers = np.zeros((uniq.size, 3), dtype=np.float64)
        counts = np.bincount(inv, minlength=uniq.size).astype(np.float64)
        for a in range(3):
            centers[:, a] = np.bincount(inv, weights=v[:, a], minlength=uniq.size)
        centers /= counts[:, None]
        faces = inv.reshape(-1, 3)
        ok = (faces[:, 0] != faces[:, 1]) & (faces[:, 1] != faces[:, 2]) & (faces[:, 0] != faces[:, 2])
        faces = faces[ok]
        if faces.shape[0] <= target * 1.25 or grid <= 4:
            return centers[faces].astype(np.float32)
        grid = max(4, int(grid * 0.82))
    return centers[faces].astype(np.float32)


def parse_sdf() -> tuple[dict[str, np.ndarray], list[tuple[str, str, list[float]]]]:
    """Позы звеньев и список суставов (родитель, потомок, ось)."""
    root = ET.parse(SDF).getroot()
    model = root.find("model")
    poses: dict[str, np.ndarray] = {}
    for link in model.findall("link"):
        pose = [float(x) for x in (link.findtext("pose") or "0 0 0 0 0 0").split()]
        poses[link.get("name")] = np.array(pose[:3], dtype=np.float64)
    joints = []
    for joint in model.findall("joint"):
        parent = joint.findtext("parent")
        child = joint.findtext("child")
        axis = joint.find("axis")
        xyz = [float(x) for x in (axis.findtext("xyz") if axis is not None else "0 0 1").split()]
        joints.append((parent, child, xyz))
    return poses, joints


def build() -> dict:
    global BUDGET, DEFAULT_BUDGET
    poses, joints = parse_sdf()
    parent_of = {child: parent for parent, child, _ in joints}
    axis_of = {child: axis for _, child, axis in joints}
    roots = [name for name in poses if name not in parent_of]
    root_name = "Thorax" if "Thorax" in poses else roots[0]

    order: list[str] = []
    seen: set[str] = set()

    def walk(name: str) -> None:
        if name in seen:
            return
        seen.add(name)
        order.append(name)
        for other, parent in parent_of.items():
            if parent == name:
                walk(other)

    walk(root_name)
    # всё, что не свисает с груди (опоры симуляции prismatic_support и т.п.), не берём

    links = []
    meshes = []
    blobs: list[bytes] = []
    total_tris = 0
    for name in order:
        # у корня родителя нет: опора симуляции в дерево не идёт
        parent = None if name == root_name else parent_of.get(name)
        offset = poses[name] - (poses[parent] if parent else np.zeros(3))
        mesh_id = None
        stl = STL_DIR / f"{name}.stl"
        if stl.exists():
            tris = read_stl(stl) * MESH_SCALE
            tris = decimate(tris, BUDGET.get(name, DEFAULT_BUDGET))
            total_tris += tris.shape[0]
            v = tris.reshape(-1, 3)
            lo, hi = v.min(0), v.max(0)
            span = np.maximum(hi - lo, 1e-6)
            q = np.round((v - lo) / span * 65535.0 - 32768.0).astype(np.int16)
            mesh_id = len(meshes)
            meshes.append(
                {
                    "name": name,
                    "tris": int(tris.shape[0]),
                    "lo": [round(float(x), 5) for x in lo],
                    "span": [round(float(x), 5) for x in span],
                    "off": sum(len(b) for b in blobs),
                    "len": int(q.size),
                }
            )
            blobs.append(q.tobytes())
        links.append(
            {
                "name": name,
                "parent": parent,
                "t": [round(float(x), 5) for x in offset],
                "axis": [round(float(x), 4) for x in axis_of.get(name, [0, 0, 1])],
                "mesh": mesh_id,
            }
        )

    buf = b"".join(blobs)
    data = {
        "source": "NeuroMechFly (NeLy-EPFL), Apache-2.0",
        "root": root_name,
        "triangles": total_tris,
        "links": links,
        "meshes": meshes,
        "buffer": base64.b64encode(buf).decode("ascii"),
    }
    return data


if __name__ == "__main__":
    lite = "--lite" in sys.argv
    if lite:  # облегчённая версия для быстрой визуальной проверки в панели
        BUDGET = {k: max(60, v // 6) for k, v in BUDGET.items()}
        DEFAULT_BUDGET = 60
        OUT = ROOT / "assets" / "fly3d_lite.json"
    data = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    print(f"деталей: {len(data['meshes'])}  треугольников: {data['triangles']}")
    print(f"звеньев в скелете: {len(data['links'])}")
    print(f"{OUT}  {OUT.stat().st_size // 1024} КБ")
    sys.exit(0)
