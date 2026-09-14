"""Проверки на то, что проект действительно делает заявленное.

    python -m pytest tests -q        (или python tests/test_project.py)

Тесты намеренно короткие и про утверждения из README, а не про внутренности:
воспроизводимость коннектома, разбор методички, цена ошибки, обучение сильнее
случайного выбора. Тяжёлые вещи (настоящая 1С, сборка страниц) сюда не входят —
им нужна платформа и браузер.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CONNECTOME = ROOT / "connectome" / "connections.csv.gz"
needs_data = pytest.mark.skipif(
    not CONNECTOME.exists(),
    reason="нет коннектома: python tools/fetch_data.py --light")


@needs_data
def test_brain_reproducible():
    """Одно состояние задачи — один и тот же ответ мозга, до спайка.

    На этом держится панель активности: числа на странице должны пересчитываться,
    иначе это картинка, а не симуляция.
    """
    from fly1c.brain import get_brain

    b = get_brain()
    key = "0" * 16 + "|"
    first = int(b.simulate(b.odor(key)).sum())
    second = int(b.simulate(b.odor(key)).sum())
    assert first == second
    assert first > 0
    assert int((b.kc_response(key) > 0).sum()) > 0


@needs_data
def test_brain_is_the_real_connectome():
    """Размер матрицы — тот самый релиз FlyWire, а не игрушка на сто нейронов."""
    from fly1c.brain import get_brain

    b = get_brain()
    assert b.n > 100_000
    assert b.W.nnz > 1_000_000


@needs_data
def test_escape_circuit_fires():
    """Канонический тест коннектома: looming слева -> гигантское волокно слева.

    Стимулируем детекторы приближающегося объекта (LC4, LPLC2) с одной стороны
    головы — разрядиться должно DNp01 той же стороны, это команда прыжка. Цепь
    заранее не закладывалась: веса берутся из карты синапсов, знак — из медиатора
    нейрона. Если тест упал, сломана калибровка усиления, и всё остальное в
    проекте считает шум.
    """
    import sys as _sys

    _sys.path.insert(0, str(ROOT / "tools"))
    from calibrate import passes, probe

    from fly1c.brain import get_brain

    result = probe(get_brain())
    assert result["weight_ipsi"] > 0, "связь LC4/LPLC2 -> DNp01 вышла тормозной"
    assert passes(result), result


@needs_data
def test_named_cells_resolve():
    """Именованные типы клеток должны находиться: без них нет ни входа, ни выхода."""
    from fly1c import cells
    from fly1c.brain import get_brain

    brain = get_brain()
    census = cells.census(brain)
    assert census["DNp01"] == 2, census          # гигантское волокно, по одному на сторону
    assert census["LC4"] > 50, census
    assert census["PAM"] > 100, census
    assert cells.find(brain, "DNp01", "left").size == 1


def test_methodics_parses_types():
    """«Строка, длина -20» должно превращаться в String(20), а ссылка — в CatalogRef."""
    from fly1c.methodics import parse_type

    assert parse_type("Строка, длина -20 символов") == "String(20)"
    assert parse_type("СправочникСсылка.СтатусыДрузей") == "CatalogRef.СтатусыДрузей"


def test_action_space_has_traps():
    """В пространстве ходов обязаны быть заведомо неверные — иначе ошибиться негде."""
    from fly1c.actions import candidates
    from fly1c.curriculum import BY_ID
    from fly1c.ir import World

    lab = BY_ID["10_ms_lab1"]
    world = World()
    with_traps = candidates(world, lab["checks"], with_traps=True)
    clean = candidates(world, lab["checks"], with_traps=False)
    assert len(with_traps) > len(clean)


def test_junk_is_punished():
    """Лишний объект в конфигурации обязан считаться мусором, иначе цены ошибки нет."""
    from fly1c.curriculum import BY_ID
    from fly1c.ir import World
    from fly1c.ops import apply_op
    from fly1c.score import junk

    lab = BY_ID["10_ms_lab1"]
    world = World()
    before = len(junk(world, lab["checks"]))
    apply_op(world, {"op": "create_catalog", "name": "СовершенноЛишнийСправочник"})
    assert len(junk(world, lab["checks"])) > before


@needs_data
def test_policy_is_not_worse_than_chance():
    """Честное сравнение политики с выбором наугад — в ОДНОМ И ТОМ ЖЕ цикле.

    Раньше здесь стояло «обучение обгоняет случайный выбор», и случайный выбор
    брался из другого, более слабого цикла: без отсева сделанных и провалившихся
    ходов, без предела топтания. Так сравнивалась обвязка среды, а не политики.
    Замер на равных показывает, что обучение не даёт выигрыша (103,2 против
    103,4 на пяти зёрнах), поэтому и проверяется теперь только то, что оно не
    делает хуже. Подробности в README, раздел «Раздел, где мы сами себя
    разоблачаем».
    """
    from fly1c.curriculum import BY_ID
    from fly1c.policy import GeneralFly, start_world, train_policy

    lab_id = "10_ms_lab1"
    lab = BY_ID[lab_id]

    chance = GeneralFly(seed=11)          # нулевые веса: все ходы равны, выбор наугад
    blind = chance.solve(lab, start_world(lab_id), greedy=True, learn=False)["passed"]
    taught = train_policy(epochs=3).solve(
        lab, start_world(lab_id), greedy=True, learn=False)["passed"]
    assert taught >= blind - 2, f"обучение {taught}, наугад {blind}"


def test_xml_dump_is_valid_xml():
    """Выгрузка должна быть разбираемым XML: иначе конфигуратор её просто не возьмёт."""
    import xml.etree.ElementTree as ET

    from fly1c.agent import OracleAgent
    from fly1c.curriculum import BY_ID
    from fly1c.ir import World
    from fly1c import xml_dump

    world = World()
    OracleAgent().run(world, BY_ID["00_uchebnaya"])
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        xml_dump.dump_world(world, Path(tmp))
        files = list(Path(tmp).rglob("*.xml"))
        assert files, "выгрузка пустая"
        for path in files:
            ET.parse(path)          # падает, если XML битый


if __name__ == "__main__":
    raise SystemExit(pytest.main([str(Path(__file__)), "-q"]))
