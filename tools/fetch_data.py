"""Скачивание всего, что не лежит в репозитории: коннектом, меши мухи, three.js.

    python tools/fetch_data.py            # всё сразу (~370 МБ)
    python tools/fetch_data.py --light    # без 302 МБ координат синапсов

Коннектом FlyWire (CC BY 4.0) и модель NeuroMechFly (Apache-2.0) лежат в открытом
доступе, регистрация не нужна. Подробности об источниках — в ATTRIBUTION.md.
"""
from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FLYWIRE = "https://storage.googleapis.com/flywire-data/codex/data/fafb/783/"
NMF = "https://raw.githubusercontent.com/NeLy-EPFL/NeuroMechFly/master/data/design/"
THREE = "https://cdn.jsdelivr.net/npm/three@0.128.0/"

CONNECTOME = [
    "connections.csv.gz", "classification.csv.gz", "neurons.csv.gz",
    "coordinates.csv.gz", "cell_stats.csv.gz", "labels.csv.gz",
    "consolidated_cell_types.csv.gz",
]
HEAVY = ["synapse_coordinates.csv.gz"]        # 302 МБ, нужен для облака и анатомии цепи

MESHES = """A1A2 A3 A4 A5 A6 Haustellum Head LAntenna LEye LFCoxa LFFemur LFTarsus1 LFTarsus2
LFTarsus3 LFTarsus4 LFTarsus5 LFTibia LHCoxa LHFemur LHTarsus1 LHTarsus2 LHTarsus3 LHTarsus4
LHTarsus5 LHTibia LHaltere LMCoxa LMFemur LMTarsus1 LMTarsus2 LMTarsus3 LMTarsus4 LMTarsus5
LMTibia LWing RAntenna REye RFCoxa RFFemur RFTarsus1 RFTarsus2 RFTarsus3 RFTarsus4 RFTarsus5
RFTibia RHCoxa RHFemur RHTarsus1 RHTarsus2 RHTarsus3 RHTarsus4 RHTarsus5 RHTibia RHaltere
RMCoxa RMFemur RMTarsus1 RMTarsus2 RMTarsus3 RMTarsus4 RMTarsus5 RMTibia RWing Rostrum
Thorax""".split()

THREE_FILES = [
    ("build/three.min.js", ROOT / "assets" / "three.min.js"),
    ("examples/js/shaders/CopyShader.js", ROOT / "assets" / "three" / "CopyShader.js"),
    ("examples/js/shaders/LuminosityHighPassShader.js",
     ROOT / "assets" / "three" / "LuminosityHighPassShader.js"),
    ("examples/js/postprocessing/EffectComposer.js",
     ROOT / "assets" / "three" / "EffectComposer.js"),
    ("examples/js/postprocessing/RenderPass.js", ROOT / "assets" / "three" / "RenderPass.js"),
    ("examples/js/postprocessing/ShaderPass.js", ROOT / "assets" / "three" / "ShaderPass.js"),
    ("examples/js/postprocessing/MaskPass.js", ROOT / "assets" / "three" / "MaskPass.js"),
    ("examples/js/postprocessing/UnrealBloomPass.js",
     ROOT / "assets" / "three" / "UnrealBloomPass.js"),
]


def grab(url: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  уже есть: {dest.name}")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  качаю {dest.name} …", end="", flush=True)
    urllib.request.urlretrieve(url, dest)
    print(f" {dest.stat().st_size // 1024} КБ")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--light", action="store_true",
                    help="без координат синапсов (302 МБ)")
    args = ap.parse_args()

    print("коннектом FlyWire v783:")
    for name in CONNECTOME + ([] if args.light else HEAVY):
        grab(FLYWIRE + name, ROOT / "connectome" / name)

    print("модель NeuroMechFly:")
    grab(NMF + "sdf/neuromechfly_noLimits.sdf", ROOT / "assets" / "nmf" / "neuromechfly.sdf")
    for name in MESHES:
        grab(f"{NMF}meshes/stl/{name}.stl", ROOT / "assets" / "nmf" / "stl" / f"{name}.stl")

    print("three.js:")
    for rel, dest in THREE_FILES:
        grab(THREE + rel, dest)

    print("\nготово. дальше:")
    print("  python tools/build_fly3d.py        меши -> assets/fly3d.json")
    print("  python tools/build_fly3d.py --lite облегчённая модель")
    print("  python tools/build_circuit.py      цепь для лаборатории")
    print("  python tools/build_cloud.py        облако синапсов для студии")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
