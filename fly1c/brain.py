"""Настоящий мозг дрозофилы: коннектом FlyWire v783, 139 255 нейронов, 3.87 млн связей.

Данные — публичный релиз FlyWire (CC-BY-4.0), лежат в connectome/*.csv.gz.
Здесь из них собирается разреженная матрица синапсов и гоняется LIF-симуляция:
ток подаётся в обонятельные рецепторы, дальше всё считает реальная проводка мухи,
а наружу снимаются спайки клеток Кеньона (грибовидное тело) — то место,
где у настоящей мухи и живёт ассоциативное обучение.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy import sparse

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "connectome"
CACHE = DATA / "flywire783.npz"

# Знак синапса по нейромедиатору: ацетилхолин возбуждает, ГАМК и глутамат тормозят
# (у мухи глутамат в основном на GluCl-каналах), моноамины — слабая модуляция.
NT_SIGN = {
    "ACH": 1.0,
    "GABA": -1.0,
    "GLUT": -1.0,
    "DA": 0.15,
    "SER": 0.15,
    "OCT": 0.15,
    "UNK": 0.3,
    "": 0.3,
}


def _read_classification() -> tuple[dict[int, int], list[str], list[str]]:
    """root_id -> индекс, плюс колонки class и super_class в том же порядке."""
    index: dict[int, int] = {}
    classes: list[str] = []
    supers: list[str] = []
    with gzip.open(DATA / "classification.csv.gz", "rt", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            index[int(row["root_id"])] = len(classes)
            classes.append(row["class"])
            supers.append(row["super_class"])
    return index, classes, supers


def build_cache(force: bool = False) -> Path:
    """Разобрать csv.gz в npz: индексы рёбер, веса со знаком, популяции нейронов."""
    if CACHE.exists() and not force:
        return CACHE
    index, classes, supers = _read_classification()
    pre_l: list[int] = []
    post_l: list[int] = []
    w_l: list[float] = []
    with gzip.open(DATA / "connections.csv.gz", "rt", encoding="utf-8") as fh:
        for row in csv.reader(fh):
            if row[0] == "pre_root_id":
                continue
            a = index.get(int(row[0]))
            b = index.get(int(row[1]))
            if a is None or b is None:
                continue
            pre_l.append(a)
            post_l.append(b)
            w_l.append(int(row[3]) * NT_SIGN.get(row[4], 0.3))
    cls = np.array(classes)
    sup = np.array(supers)
    np.savez_compressed(
        CACHE,
        pre=np.asarray(pre_l, dtype=np.int32),
        post=np.asarray(post_l, dtype=np.int32),
        weight=np.asarray(w_l, dtype=np.float32),
        n=np.int64(len(classes)),
        cls=cls,
        sup=sup,
    )
    return CACHE


@dataclass
class Populations:
    olfactory: np.ndarray
    kenyon: np.ndarray
    mbon: np.ndarray
    dan: np.ndarray
    descending: np.ndarray


class FlyBrain:
    """LIF-симуляция полного коннектома. Один шаг ≈ один миллисекундный такт."""

    def __init__(self, leak: float = 0.82, theta: float = 1.0, scale: float = 0.01):
        build_cache()
        z = np.load(CACHE, allow_pickle=False)
        self.n = int(z["n"])
        w = z["weight"].astype(np.float32) * scale
        # W[j, i] — вклад пресинаптического i в постсинаптический j
        self.W = sparse.csr_matrix(
            (w, (z["post"], z["pre"])), shape=(self.n, self.n), dtype=np.float32
        )
        cls, sup = z["cls"], z["sup"]
        self.pop = Populations(
            olfactory=np.flatnonzero(cls == "olfactory").astype(np.int32),
            kenyon=np.flatnonzero(cls == "Kenyon_Cell").astype(np.int32),
            mbon=np.flatnonzero(cls == "MBON").astype(np.int32),
            dan=np.flatnonzero(cls == "DAN").astype(np.int32),
            descending=np.flatnonzero(sup == "descending").astype(np.int32),
        )
        self.leak = leak
        self.theta = theta
        self._cache: dict[str, np.ndarray] = {}

    # --- стимул ---------------------------------------------------------
    def odor(self, key: str, n_active: int = 120) -> np.ndarray:
        """Состояние лабораторной -> запах: детерминированный набор рецепторов."""
        orn = self.pop.olfactory
        h = hashlib.blake2b(key.encode("utf-8"), digest_size=16).digest()
        rng = np.random.default_rng(int.from_bytes(h, "little"))
        return rng.choice(orn, size=min(n_active, orn.size), replace=False)

    # --- динамика -------------------------------------------------------
    def simulate(self, stim: np.ndarray, steps: int = 20, drive: float = 2.0) -> np.ndarray:
        """Спайки за время симуляции: счётчик разрядов каждого нейрона."""
        v = np.zeros(self.n, dtype=np.float32)
        counts = np.zeros(self.n, dtype=np.float32)
        spikes = np.zeros(self.n, dtype=np.float32)
        inj = np.zeros(self.n, dtype=np.float32)
        inj[stim] = drive
        for _ in range(steps):
            v *= self.leak
            v += self.W.dot(spikes)
            v += inj
            spikes = (v > self.theta).astype(np.float32)
            counts += spikes
            v[spikes > 0] = 0.0
        return counts

    def kc_response(self, key: str, steps: int = 20, sparsity: float = 0.05) -> np.ndarray:
        """Ответ клеток Кеньона на состояние — вектор признаков для обучения.

        Живое грибовидное тело держит разреженный код: гигантский тормозный нейрон APL
        глушит всё, кроме самых активных клеток. Здесь то же самое сделано отбором топ-k,
        иначе коды разных состояний слипаются и обучать нечего.
        """
        hit = self._cache.get(key)
        if hit is None:
            counts = self.simulate(self.odor(key), steps=steps)
            kc = counts[self.pop.kenyon] / self._baseline(steps)
            k = max(1, int(kc.size * sparsity))
            top = np.argpartition(kc, -k)[-k:]
            sparse_kc = np.zeros_like(kc)
            sparse_kc[top] = kc[top]
            peak = sparse_kc.max()
            hit = (sparse_kc / peak) if peak > 0 else sparse_kc
            self._cache[key] = hit
        return hit

    def _baseline(self, steps: int = 20, n: int = 48) -> np.ndarray:
        """Средний отклик каждой клетки Кеньона на случайные запахи.

        Гомеостатическая нормировка: без неё топ всегда занимают одни и те же
        жирно связанные клетки, и коды разных состояний почти неразличимы.
        """
        if getattr(self, "_base", None) is None:
            acc = np.zeros(self.pop.kenyon.size, dtype=np.float32)
            for i in range(n):
                acc += self.simulate(self.odor(f"__baseline__{i}"), steps=steps)[self.pop.kenyon]
            self._base = acc / n + 0.05
        return self._base

    def activity(self, key: str, steps: int = 20) -> dict[str, float]:
        """Средняя активность по популяциям — для картинки."""
        counts = self.simulate(self.odor(key), steps=steps)
        return {
            name: float(counts[idx].mean()) if idx.size else 0.0
            for name, idx in (
                ("обонятельные", self.pop.olfactory),
                ("клетки Кеньона", self.pop.kenyon),
                ("MBON", self.pop.mbon),
                ("дофаминовые", self.pop.dan),
                ("нисходящие", self.pop.descending),
            )
        }

    def positions(self) -> np.ndarray:
        if getattr(self, "_pos", None) is None:
            self._pos = build_positions()
        return self._pos

    def summary(self) -> dict[str, int]:
        return {
            "нейронов": self.n,
            "синаптических связей": int(self.W.nnz),
            "обонятельных рецепторов": int(self.pop.olfactory.size),
            "клеток Кеньона": int(self.pop.kenyon.size),
            "MBON": int(self.pop.mbon.size),
            "дофаминовых": int(self.pop.dan.size),
            "нисходящих": int(self.pop.descending.size),
        }


XYZ = DATA / "flywire783_xyz.npy"


def build_positions(force: bool = False) -> np.ndarray:
    """Координаты нейронов в мозге (FAFB) в порядке индексов — для карты активности."""
    if XYZ.exists() and not force:
        return np.load(XYZ)
    index, _, _ = _read_classification()
    pos = np.full((len(index), 3), np.nan, dtype=np.float32)
    with gzip.open(DATA / "coordinates.csv.gz", "rt", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            i = index.get(int(row["root_id"]))
            if i is None or not np.isnan(pos[i, 0]):
                continue
            pos[i] = [float(v) for v in row["position"].strip("[]").split()]
    np.save(XYZ, pos)
    return pos


_BRAIN: FlyBrain | None = None


def get_brain() -> FlyBrain:
    global _BRAIN
    if _BRAIN is None:
        _BRAIN = FlyBrain()
    return _BRAIN
