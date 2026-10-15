# -*- coding: utf-8 -*-
"""Углублённые детерминированные проверки модели корпуса СПТ (тикет 20).

Отличие от check_korpus.py: тут проверяется РЕАЛЬНАЯ геометрия тел, а не
аналитические формулы — коллизии (overlap_volume), зазоры (closest_points),
топологическая целостность, фактический объём полости.

Запуск из .scratch/spt-tank/cad:
  uvx --no-config --managed-python --python 3.13 --from cadgen==0.7.21 \
      python tmp/check_korpus_geom.py
"""
from __future__ import annotations

import math
import sys
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cadgen import build123d as bd  # noqa: E402
from cadgen.geometry import (  # noqa: E402
    closest_points,
    is_sound,
    overlap_volume,
    self_intersections,
    topology_errors,
)

import spt_korpus as m  # noqa: E402

STEEL_DENSITY = 7.85e-3  # г/мм³ (ВСт3сп)
OVERLAP_LIMIT_MM3 = 10.0  # порог шума булевых операций


def solids_of(shape):
    """solids может быть свойством или методом — унифицируем."""
    s = shape.solids
    if callable(s):
        s = s()
    return list(s) if isinstance(s, (list, tuple)) else [s]


def main() -> int:
    ok = True

    def check(name: str, cond: bool, detail: str) -> None:
        nonlocal ok
        print(f"{'PASS' if cond else 'FAIL'}  {name}: {detail}")
        ok = ok and cond

    def report(name: str, detail: str) -> None:
        print(f"INFO  {name}: {detail}")

    tree = m.spt_korpus()

    # --- Разбор слоёв на тела --------------------------------------------
    layers: dict[str, list] = {}

    def collect(shape, label=None):
        lab = shape.label or label
        solids = solids_of(shape)
        if solids and lab not in ("spt_korpus_70l", "izolyaciya_kozhuh",
                                  "nachinka"):
            layers.setdefault(lab, []).extend(solids)
        for ch in shape.children:
            collect(ch, lab)

    collect(tree)

    # Патрубки отдельно (в корпусе они сплавлены) — в мировой системе
    tilt = bd.Rot(0, -m.ALPHA_DEG, 0)
    drop = -220.0 * m.ALPHA - (m.R_OUT ** 2 - m.LEG_Y ** 2) ** 0.5
    lift = bd.Location((0, 0, m.LEG_A_HEIGHT - drop))

    def to_world(shape):
        return lift * (tilt * shape)

    nozzles: dict[str, list] = {}
    for n in m.NOZZLES:
        body, _, _ = m._nozzle(n)
        nozzles[n["label"].split("_")[0]] = solids_of(to_world(body))

    # --- 1. Топологическая целостность -----------------------------------
    for lab in ("korpus", "izolyaciya", "kozhuh"):
        for i, sol in enumerate(layers[lab]):
            snd = is_sound(sol)
            errs = topology_errors(sol)
            selfx = self_intersections(sol)
            check(f"topologiya_{lab}[{i}]", snd and not errs and not selfx,
                  f"sound={snd}, errors={len(errs)}, self_int={len(selfx)}")

    # --- 2. Реальный объём полости и масса стали -------------------------
    cavity = to_world(m._vessel_cavity())
    liters = sum(s.volume for s in solids_of(cavity)) / 1e6
    check("polost_realnaya_70l", 66.0 < liters < 74.0,
          f"{liters:.1f} л (геометрия; цель ~70)")

    steel_mm3 = sum(s.volume for sol in layers["korpus"] for s in solids_of(sol))
    mass = steel_mm3 * STEEL_DENSITY / 1e3
    report("massa_stali", f"{mass:.0f} кг (без фланцевых болтов/арматуры)")

    # --- 3. Коллизии: пары, которые НЕ должны пересекаться ---------------
    pair_expect_zero = [
        ("ten_trubki", "filtr"),
        ("ten_trubki", "korpus"),
        ("filtr", "korpus"),
        ("ten_trubki", "izolyaciya"),
        ("filtr", "izolyaciya"),
        ("korobka_soedinitelnaya", "izolyaciya"),
        ("korobka_soedinitelnaya", "kozhuh"),
        ("izolyaciya", "korpus"),
        ("kozhuh", "izolyaciya"),
        ("kozhuh", "korpus"),
    ]
    for a, b in pair_expect_zero:
        vol = sum(overlap_volume(sa, sb)
                  for sa in layers[a] for sb in layers[b])
        check(f"net_kolliziy_{a}__{b}", vol <= OVERLAP_LIMIT_MM3,
              f"пересечение {vol:.2f} мм³ (порог {OVERLAP_LIMIT_MM3:.0f})")

    # Коробка — условный объём, но сталь протыкать не должна даже заглушка
    vol = sum(overlap_volume(sa, sb)
              for sa in layers["korobka_soedinitelnaya"]
              for sb in layers["korpus"])
    check("korobka_ne_skvoz_stenku", vol <= OVERLAP_LIMIT_MM3,
          f"проникновение в сталь {vol:.2f} мм³ "
          f"(утопление должно быть в изоляцию, не в металл)")

    # Термометр/ДТС — над кожухом, касаться не должны
    for lab in ("termometr", "termometr_shkala", "dts_datchik"):
        vol = sum(overlap_volume(sa, sb)
                  for sa in layers[lab] for sb in layers["kozhuh"])
        check(f"net_kolliziy_{lab}__kozhuh", vol <= OVERLAP_LIMIT_MM3,
              f"пересечение {vol:.2f} мм³")

    # --- 4. Зазоры (мм) ----------------------------------------------------
    def dist(layer_a: str, layer_b: str) -> float:
        best = math.inf
        for sa in layers[layer_a]:
            for sb in layers[layer_b]:
                best = min(best, closest_points(sa, sb).distance)
        return best

    d = dist("filtr", "ten_trubki")
    check("zazor_filtr__ten", d >= 10.0, f"{d:.1f} мм (мин. 10)")
    d = dist("filtr", "korpus")
    check("zazor_filtr__stenka", d >= 5.0, f"{d:.1f} мм (мин. 5)")
    d = dist("ten_trubki", "korpus")
    check("zazor_ten__stenka", d >= 5.0, f"{d:.1f} мм (мин. 5)")

    # Верхняя образующая: патрубки 5/6, гильзы 7/8, коробка, шкала БТ
    top_parts = {"05": nozzles["05"], "06": nozzles["06"],
                 "07": nozzles["07"], "08": nozzles["08"],
                 "korobka": layers["korobka_soedinitelnaya"],
                 "shkala": layers["termometr_shkala"]}
    names = {"05": "перелив DN20", "06": "воздухоотвод DN15",
             "07": "гильза БТ", "08": "гильза ДТС",
             "korobka": "коробка", "shkala": "шкала БТ"}
    worst = math.inf
    worst_pair = ""
    for ka, kb in combinations(top_parts, 2):
        best = math.inf
        for sa in top_parts[ka]:
            for sb in top_parts[kb]:
                best = min(best, closest_points(sa, sb).distance)
        report("verh_obrazuyushchaya", f"{names[ka]} — {names[kb]}: "
               f"{best:.1f} мм")
        if best < worst:
            worst, worst_pair = best, f"{names[ka]} — {names[kb]}"
    check("verh_obrazuyushchaya_min_zazor", worst >= 10.0,
          f"минимум {worst:.1f} мм у пары «{worst_pair}» (мин. 10 для "
          f"ключа/монтажа)")

    # Кожух против фланцев: вырез cut_d = D+20 → ожидаем зазор ~10 мм
    for pos, lab in (("01", "корпус"), ("03", "корпус"), ("04", "ТЭН-блок"),
                     ("05", "перелив"), ("06", "воздухоотвод")):
        best = math.inf
        for sa in nozzles[pos]:
            for sb in layers["kozhuh"]:
                best = min(best, closest_points(sa, sb).distance)
        check(f"virez_kozhuh__{pos}", best >= 5.0,
              f"зазор {best:.1f} мм (расчётный ~10, мин. 5)")

    # --- 5. Единство корпуса и открытые каналы ------------------------------
    # фикс дефекта 3: корпус — одно тело, а не рассыпанные патрубки
    check("korpus_edinoe_telo", len(layers["korpus"]) == 1,
          f"тел в слое korpus: {len(layers['korpus'])} (цель 1)")

    # фикс дефекта 4: канал каждого патрубка открыт по всей длине —
    # точки на оси не лежат в стали
    for n in m.NOZZLES:
        if not n["bore"] > 0:
            continue
        t0, t1 = n["span"]
        blocked = []
        for i in range(1, 20):
            t = t0 + (t1 - t0) * i / 20.0
            pt = to_world(bd.Vertex(*m._along(n["axis"], n["at"], t)))
            d = min(closest_points(pt, s).distance for s in layers["korpus"])
            if d < 1.0:
                blocked.append(round(t, 1))
        check(f"kanal_otkryt_{n['pos']:02d}", not blocked,
              ("перекрыт на t=" + ", ".join(map(str, blocked))) if blocked
              else "ось свободна по всей длине")

    print("OK" if ok else "PROVERKI NE PROSHLI")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
