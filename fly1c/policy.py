"""Муха, которая учится работать с 1С вообще, а не помнит ответы конкретной лабы.

Отличие от прежнего агента: раньше у каждой операции был свой вектор весов, то есть
муха запоминала «эту кнопку жать здесь». Такое не переносится на новую методичку.

Здесь ход описывается признаками («создание справочника», «объект уже есть»,
«предпосылки на месте», «целится в несошедшуюся проверку», …). Набор признаков —
это запах: каждый признак включает свой пучок обонятельных рецепторов. Запах идёт
через настоящий коннектом, грибовидное тело выдаёт разреженный код, а поверх него
один общий вектор весов KC → выход. Поэтому выученное на одних лабах работает
на других: признаки те же, меняются только имена объектов.
"""
from __future__ import annotations

import hashlib
import random
from copy import deepcopy
from typing import Any

import numpy as np

from .actions import candidates
from .brain import get_brain
from .checker import run_checks
from .ir import OpError, World
from .ops import apply_op
from .score import junk

SECTION = {
    "create_catalog": "Справочники", "fill_catalog": "Справочники",
    "add_predefined": "Справочники", "set_quick_choice": "Справочники",
    "set_object_presentation": "Справочники",
    "create_document": "Документы", "copy_document": "Документы",
    "fill_document": "Документы", "post_all": "Документы",
    "bind_register": "Документы", "write_object_module": "Документы",
    "create_register": "Регистры", "add_dimension": "Регистры", "add_resource": "Регистры",
    "create_report": "Отчёты", "run_report": "Отчёты", "add_report_variant": "Отчёты",
    "create_subsystem": "Подсистемы", "set_subsystem_order": "Подсистемы",
    "create_enum": "Перечисления",
}


def op_target(op: dict[str, Any]) -> tuple[str, str]:
    """(вид объекта, имя) — к чему относится ход."""
    for key, kind in (("catalog", "Catalog"), ("document", "Document"),
                      ("register", "AccumulationRegister"), ("report", "Report")):
        if op.get(key):
            return kind, op[key]
    obj = op.get("object")
    if obj:
        kind, _, rest = obj.partition(".")
        return kind, rest.split(".", 1)[0]
    if op["op"].startswith("create_") or op["op"] in {"set_config_name"}:
        kind = {"create_catalog": "Catalog", "create_document": "Document",
                "create_register": "AccumulationRegister", "create_report": "Report",
                "create_subsystem": "Subsystem", "create_enum": "Enum"}.get(op["op"], "Config")
        return kind, op.get("name", "")
    return "Config", op.get("name", "")


def exists(world: World, kind: str, name: str) -> bool:
    cfg = world.config
    table = {"Catalog": cfg.catalogs, "Document": cfg.documents,
             "AccumulationRegister": cfg.registers, "Report": cfg.reports,
             "Enum": cfg.enums, "Subsystem": cfg.subsystems}.get(kind)
    return bool(table and name in table)


def prereq_ok(world: World, op: dict[str, Any]) -> bool:
    """Грубая проверка предпосылок — без применения операции."""
    kind, name = op_target(op)
    needs_object = op["op"] in {
        "add_attribute", "create_tabular_section", "fill_catalog", "fill_document",
        "post_all", "bind_register", "add_dimension", "add_resource", "add_predefined",
        "run_report", "add_report_variant", "create_form", "set_quick_choice",
        "set_object_presentation", "set_synonym", "write_object_module", "write_form_module",
    }
    if needs_object and not exists(world, kind, name):
        return False
    if op["op"] == "bind_register" and op.get("register") not in world.config.registers:
        return False
    if op["op"] == "post_all":
        doc = world.config.documents.get(name)
        if doc is None or not doc.register_records:
            return False
        if not any(d.document == name for d in world.ib.documents):
            return False
    if op["op"] == "run_report" and not any(
            d.document for d in world.ib.documents):
        return False
    return True


CHECK_FOR_OP = {
    "create_catalog": ("has_catalog",), "create_document": ("has_document",),
    "create_register": ("has_register",), "create_report": ("has_report", "report_chart"),
    "create_subsystem": ("has_subsystem",), "create_enum": ("has_enum",),
    "add_attribute": ("has_attribute",), "create_tabular_section": ("has_tabular_section",),
    "add_dimension": ("register_dimension",), "add_resource": ("register_resource",),
    "bind_register": ("document_moves",), "create_form": ("has_form",),
    "fill_catalog": ("catalog_count", "folder_exists"),
    "fill_document": ("document_count",),
    "post_all": ("posted_count", "register_movements"),
    "run_report": ("report_run",), "add_predefined": ("has_predefined",),
    "set_quick_choice": ("quick_choice",), "set_object_presentation": ("object_presentation",),
    "set_synonym": ("synonym",), "set_config_name": ("config_name",),
    "set_subsystem_order": ("subsystem_order",), "set_desktop": ("desktop_set",),
    "add_report_variant": ("report_variant",),
    "write_object_module": ("module_contains",), "write_form_module": ("module_contains",),
    "copy_document": ("has_document",),
}


def _fields(ch: dict) -> set[str]:
    out = set()
    for key, value in ch.items():
        if key == "check":
            continue
        if isinstance(value, str):
            out.add(value)
        elif isinstance(value, list):
            out.update(str(v) for v in value)
    return out


def check_match(op: dict[str, Any], checks: list[dict], unmet_ids: set[int]) -> tuple[int, int]:
    """Совпадает ли ход с пунктом задания — и сошёлся ли уже этот пункт.

    Это не заглядывание вперёд, а чтение условия: «нужен реквизит Телефон
    у справочника Друзья» и ход «добавить Друзьям реквизит Телефон» — одно и то же.
    """
    kinds = CHECK_FOR_OP.get(op["op"], ())
    if not kinds:
        return 0, 0
    _, name = op_target(op)
    op_words = {name, str(op.get("name", "")), str(op.get("register", "")),
                str(op.get("object", ""))} - {""}
    hit_unmet = hit_met = 0
    for ch in checks:
        if ch["check"] not in kinds:
            continue
        fields = _fields(ch)
        if not (op_words & fields):
            continue
        if op["op"] in {"add_attribute", "add_dimension", "add_resource",
                        "create_tabular_section", "create_form", "add_report_variant"}:
            if str(op.get("name", "")) not in fields:
                continue
        if id(ch) in unmet_ids:
            hit_unmet = 1
        else:
            hit_met = 1
    return hit_unmet, hit_met


def tokens(world: World, op: dict[str, Any], checks: list[dict], unmet_ids: set[int],
           progress: float, done: set[str], failed_here: set[str],
           last_failed: bool) -> list[str]:
    kind, name = op_target(op)
    key = _op_key(op)
    hit_unmet, hit_met = check_match(op, checks, unmet_ids)
    t = [
        f"op:{op['op']}",
        f"sec:{SECTION.get(op['op'], 'Прочее')}",
        f"kind:{kind}",
        f"exists:{int(exists(world, kind, name))}",
        f"prereq:{int(prereq_ok(world, op))}",
        f"unmet:{hit_unmet}",
        f"met:{hit_met}",
        f"done:{int(key in done)}",
        f"failedbefore:{int(key in failed_here)}",
        f"progress:{int(progress * 4)}",
        f"lastfail:{int(last_failed)}",
        f"empty:{int(not world.config.catalogs and not world.config.documents)}",
    ]
    if op.get("type"):
        t.append(f"type:{str(op['type']).split(':')[0]}")
    if op.get("items"):
        t.append(f"items:{min(3, len(op['items']))}")
    return t


class GeneralFly:
    """Один общий вектор весов KC → выход. Обучается на одних лабах, работает на других."""

    name = "flywire-general"

    def __init__(self, seed: int = 11, epsilon: float = 0.25, lr: float = 0.02,
                 sparsity: float = 0.05, n_orn: int = 90, mode: str = "features"):
        """mode: 'features' — признаки и их пары напрямую (работает),
        'connectome' — код грибовидного тела (замерено: хуже случайного выбора)."""
        self.brain = get_brain()
        self.rng = random.Random(seed)
        self.epsilon = epsilon
        self.lr = lr
        self.n_kc = int(self.brain.pop.kenyon.size)
        self.mode = mode
        self.n_feat = 8192
        self.index: dict[str, int] = {}
        self.w = np.zeros(self.n_kc if mode == "connectome" else self.n_feat,
                          dtype=np.float32)
        self.sparsity = sparsity   # доля клеток Кеньона, которым позволено гореть
        self.n_orn = n_orn         # сколько рецепторов включает один признак
        self.orn = self.brain.pop.olfactory
        self._odor_cache: dict[str, np.ndarray] = {}

    # --- запах из признаков -------------------------------------------
    def _slot(self, name: str) -> np.ndarray:
        """Свой участок рецепторов под каждый вид признака — как отдельный канал запаха.

        Раньше все признаки тянули рецепторы из общей кучи по 14 штук, и смена одного
        признака меняла стимул на проценты: коды грибовидного тела получались почти
        одинаковыми (совпадение 0.63 против 0.54 у совсем разных ходов). Теперь каждый
        вид признака владеет своим участком целиком, и его смена перекрашивает канал.
        """
        slots = getattr(self, "_slots", None)
        if slots is None:
            slots = self._slots = {}
        hit = slots.get(name)
        if hit is None:
            h = hashlib.blake2b(name.encode("utf-8"), digest_size=8).digest()
            rng = np.random.default_rng(int.from_bytes(h, "little"))
            hit = slots[name] = rng.choice(self.orn, size=self.n_orn, replace=False)
        return hit

    def _odor(self, toks: list[str]) -> np.ndarray:
        """Значение признака зажигает половину своего канала — смена значения видна."""
        key = "|".join(sorted(toks))
        hit = self._odor_cache.get(key)
        if hit is not None:
            return hit
        chosen: set[int] = set()
        for tok in toks:
            name, _, value = tok.partition(":")
            block = self._slot(name)
            h = hashlib.blake2b(tok.encode("utf-8"), digest_size=8).digest()
            rng = np.random.default_rng(int.from_bytes(h, "little"))
            take = max(4, block.size // 2)
            chosen.update(int(x) for x in rng.choice(block, size=take, replace=False))
        arr = np.fromiter(chosen, dtype=np.int32)
        self._odor_cache[key] = arr
        return arr

    def _slot_index(self, token: str) -> int:
        i = self.index.get(token)
        if i is None:
            i = self.index[token] = len(self.index) % self.n_feat
        return i

    def _feature_code(self, toks: list[str]) -> np.ndarray:
        """Признаки и их пары. Пары нужны: решает не «добавить реквизит» само по себе,
        а сочетание «добавить реквизит» + «пункт задания ещё не сошёлся»."""
        v = np.zeros(self.n_feat, dtype=np.float32)
        for tok in toks:
            v[self._slot_index(tok)] = 1.0
        for a in range(len(toks)):
            for b in range(a + 1, len(toks)):
                v[self._slot_index(toks[a] + "&" + toks[b])] = 1.0
        return v

    def code(self, toks: list[str]) -> np.ndarray:
        if self.mode != "connectome":
            return self._feature_code(toks)
        return self._kc_code(toks)

    def _kc_code(self, toks: list[str]) -> np.ndarray:
        """Ответ грибовидного тела на этот стимул (через настоящий коннектом)."""
        key = f"ф{self.sparsity}.{self.n_orn}|" + "|".join(sorted(toks))
        cached = self.brain._cache.get(key)
        if cached is not None:
            return cached
        counts = self.brain.simulate(self._odor(toks))
        kc = counts[self.brain.pop.kenyon] / self.brain._baseline()
        k = max(1, int(kc.size * self.sparsity))
        top = np.argpartition(kc, -k)[-k:]
        sparse = np.zeros_like(kc)
        sparse[top] = kc[top]
        peak = sparse.max()
        out = (sparse / peak) if peak > 0 else sparse
        self.brain._cache[key] = out
        return out

    # --- один проход по лабораторной ----------------------------------
    def solve(self, lab: dict[str, Any], base: World, greedy: bool = False,
              max_steps: int | None = None, learn: bool = True,
              on_step=None) -> dict[str, Any]:
        """on_step(op, failed, world, mask) вызывается после каждого хода.

        Нужен, чтобы визуализация показывала этот самый прогон, а не отдельную
        постановку рядом: рисуется ровно то, что решатель сделал, промахи включительно.
        """
        world = deepcopy(base)
        checks = lab["checks"]
        limit = max_steps or 60
        done: set[str] = set()
        failed_here: set[str] = set()
        failed_sig: dict[str, tuple] = {}   # ход -> состояние, в котором он не вышел
        last_failed = False
        fails = 0
        steps = 0
        stall = 0
        base_junk = set(junk(base, checks))   # чужой мусор из прошлых лаб не считаем
        trash_before = len(junk(world, checks, base_junk))
        while steps < limit and stall < 14:
            steps += 1
            results = run_checks(world, checks)
            passed = sum(1 for ok, _ in results if ok)
            if passed == len(checks):
                break
            unmet_ids = {id(ch) for (ok, _), ch in zip(results, checks) if not ok}
            progress = passed / max(1, len(checks))
            # Удавшийся ход повторять незачем — он уже сделан. Провалившийся тоже
            # незачем, пока мир не изменился: раньше муха могла пять раз подряд
            # ломиться в один и тот же ход и просто жечь бюджет шагов.
            sig = tuple(1 if ok else 0 for ok, _ in results)
            acts = [op for op in candidates(world, checks)
                    if _op_key(op) not in done
                    and failed_sig.get(_op_key(op)) != sig]
            if not acts:
                break
            codes = [self.code(tokens(world, op, checks, unmet_ids, progress,
                                      done, failed_here, last_failed)) for op in acts]
            scores = [float(self.w @ c) for c in codes]
            if not greedy and self.rng.random() < self.epsilon:
                idx = self.rng.randrange(len(acts))
            else:
                best = max(scores)
                idx = self.rng.choice([i for i, s in enumerate(scores) if s == best])
            op = acts[idx]
            key = _op_key(op)
            before = passed
            try:
                apply_op(world, op)
                failed = False
                done.add(key)
            except OpError:
                failed = True
                fails += 1
                failed_here.add(key)
                failed_sig[key] = sig
            after = sum(1 for ok, _ in run_checks(world, checks) if ok)
            trash_after = len(junk(world, checks, base_junk))
            # цена ошибки: лишний объект в конфигурации бьёт по награде так же,
            # как непройденная проверка
            reward = (-0.5 if failed
                      else (after - before) - 0.5 * (trash_after - trash_before) - 0.01)
            trash_before = trash_after
            if learn:
                active = codes[idx] > 0
                self.w[active] += self.lr * reward * codes[idx][active]
            stall = 0 if after > before else stall + 1
            last_failed = failed
            if on_step is not None:
                on_step(op, failed, world,
                        [1 if ok else 0 for ok, _ in run_checks(world, checks)])
        from .score import score as final_score

        marks = final_score(world, checks, base_junk)
        results = run_checks(world, checks)
        return {
            "score": marks["score"],
            "junk": marks["junk"],
            "passed": sum(1 for ok, _ in results if ok),
            "checks": len(checks),
            "steps": steps,
            "fails": fails,
            "world": world,
        }


def _op_key(op: dict[str, Any]) -> str:
    import json

    return json.dumps(op, ensure_ascii=False, sort_keys=True)


# --- общее обучение --------------------------------------------------------
# Раньше процедура обучения была скопирована в трёх местах (инструмент обучения,
# аудит, запись сцены), и они разошлись: сцена грузила сохранённый файл весов и
# показывала 5 проверок из 16 там, где замер давал 13. Теперь точка одна.

TRAIN_IDS = ["00_uchebnaya", "10_ms_lab1", "11_ms_lab2", "12_ms_lab3",
             "20_ds_lab1", "21_ds_lab2", "22_ds_lab3"]
TEST_IDS = ["13_ms_lab4", "14_ms_lab5", "23_ds_lab4", "24_ds_lab5", "25_ds_lab6"]


def start_world(lab_id: str) -> World:
    """Мир на начало лабы: предыдущие лабы той же линейки уже сделаны."""
    from .agent import OracleAgent
    from .curriculum import BY_ID, TRACKS

    lab = BY_ID[lab_id]
    base = World()
    for prev in TRACKS[lab["track"]]:
        if prev == lab_id:
            break
        OracleAgent().run(base, BY_ID[prev])
    return base


def train_policy(mode: str = "features", seed: int = 11, epochs: int = 6,
                 lab_ids: list[str] | None = None, on_epoch=None) -> GeneralFly:
    """Учим и оставляем лучшие веса: политика гуляет, последняя эпоха не лучшая.

    Веса co-адаптированы с разбором ничьих: у многих ходов оценки равны, и выбор
    между ними делает тот же генератор. Поэтому обучение и прогон должны жить в
    одном объекте — сохранённый файл весов под чужим генератором заметно слабее.
    """
    from .curriculum import BY_ID

    ids = lab_ids or TRAIN_IDS
    fly = GeneralFly(seed=seed, mode=mode)
    best_w, best = fly.w.copy(), -1
    for epoch in range(1, epochs + 1):
        for lab_id in ids:
            fly.solve(BY_ID[lab_id], start_world(lab_id))
        fly.epsilon = max(0.05, fly.epsilon * 0.88)
        got = sum(fly.solve(BY_ID[i], start_world(i), greedy=True, learn=False)["passed"]
                  for i in ids)
        if got > best:
            best, best_w = got, fly.w.copy()
        if on_epoch is not None:
            on_epoch(epoch, got)
    fly.w = best_w
    return fly
