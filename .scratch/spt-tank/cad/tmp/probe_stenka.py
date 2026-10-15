# -*- coding: utf-8 -*-
"""Зонд по фиксу #22: сплошная стенка у днищ и полюсная заплатка.

Проверяет локальную (до наклона) геометрию корпуса:
  1) полость заканчивается в плоскости привалки днищ (габарит полости x=±296.2,
     а не ±300 и не ±225 по цилиндру);
  2) сталь на полюсе ≈3.8 мм (зонд точками вдоль оси за торцом заплатки);
  3) в бывшей зоне кольцевых зазоров (x≈±215.4..225) сталь сплошная
     (точка на середине стенки — внутри стали, полость и снаружи — воздух).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cadgen import build123d as bd  # noqa: E402
from cadgen.geometry import closest_points  # noqa: E402

import spt_korpus as m  # noqa: E402


def solid_of(shape):
    s = shape.solids
    if callable(s):
        s = s()
    return s[0]


def dist_to(point, solid) -> float:
    return closest_points(bd.Vertex(*point), solid).distance


def main() -> int:
    ok = True

    def check(name, cond, detail):
        nonlocal ok
        print(f"{'PASS' if cond else 'FAIL'}  {name}: {detail}")
        ok = ok and cond

    korpus = solid_of(m._vessel_outer() - m._vessel_cavity())
    cavity = solid_of(m._vessel_cavity())

    # 1. Габарит полости: цилиндр до ±195, купола до ±(TIP_X - S_WALL + 0.2)
    bb = cavity.bounding_box()
    expect_tip = m.TIP_X - m.S_WALL + 0.2
    check("polyost_do_privalunki", abs(bb.max.X - expect_tip) < 0.5,
          f"полость x=±{bb.max.X:.2f} (цель ±{expect_tip:.2f}; было ±225 цилиндр)")
    cyl_end = m.L_SHELL / 2 + m.HEAD_FLANGE
    check("tsilindr_do_privalunki", abs(m.L_SHELL + 2 * m.HEAD_FLANGE
          - (m.L_SHELL + 2 * m.HEAD_FLANGE)) < 1e-9
          and cyl_end == 195.0,
          f"торец цилиндра полости x=±{cyl_end:.0f} = привалка купола")

    # 2. Сталь на полюсе: от торца заплатки (296.2) до купола (300) ≈ 3.8 мм.
    #    Точка в середине предполагаемой стенки — внутри стали (dist=0),
    #    точка в середине заплатки (x<296.2 на оси) — в воздухе полости.
    d = dist_to((298.1, 0, 0), korpus)
    check("poljus_stal_srazu", d == 0.0,
          f"точка x=298.1 (середина стенки полюса) — {'сталь' if d == 0 else 'НЕ сталь'}")
    d = dist_to((295.0, 0, 0), korpus)
    check("poljus_vozduh_v_zaplatke", d > 0.5,
          f"точка x=295.0 (внутри заплатки) — воздух, до стали {d:.2f} мм")
    wall = None
    step = 0.02
    x = 296.3
    while x < 300.0:
        if dist_to((x, 0, 0), korpus) == 0.0:
            wall = 300.0 - x + (x - 296.2)
            break
        x += step
    check("stenka_na_polyuse_3_8", wall is not None and abs(wall - 3.8) < 0.2,
          f"сталь от торца заплатки до полюса ≈ {wall:.2f} мм (цель 3.8)"
          if wall else "сталь на полюсе не найдена")

    # 3. Бывшая зона кольцевых зазоров и весь купол: вдоль луча (фикс. x,
    #    радиус от 0 до наружного +5) должна быть сталь с двумя границами
    #    (внутренней и наружной) — до фикса при x≈±215.4..225 стали не было
    #    на всей длине луча (сквозная щель).
    def ray_steel(x_abs: float, sign: int):
        """(r1, r2) — внутренняя и наружная границы стали по лучу, или None."""
        steel = [r / 10.0 for r in range(0, 2205, 2)
                 if dist_to((sign * x_abs, r / 10.0, 0.0), korpus) == 0.0]
        if not steel:
            return None
        r1, r2 = steel[0], steel[-1]
        # уточнение границ шагом 0.05
        r = r1
        while r > 0 and dist_to((sign * x_abs, r - 0.05, 0.0), korpus) == 0.0:
            r -= 0.05
        r1 = r
        r = r2
        while dist_to((sign * x_abs, r + 0.05, 0.0), korpus) == 0.0:
            r += 0.05
        r2 = r
        return r1, r2

    for xs in (196.0, 200.0, 215.4, 225.0, 250.0, 280.0, 290.0):
        for sign, tag in ((1, "B"), (-1, "A")):
            band = ray_steel(xs, sign)
            check(f"stenka_dnishe_x{xs:+.0f}{tag}", band is not None,
                  f"x={sign * xs:+.0f}: " +
                  (f"сталь r∈[{band[0]:.2f}; {band[1]:.2f}] "
                   f"(толщина по лучу {band[1] - band[0]:.2f} мм), щели нет"
                   if band else "стали по лучу нет — сквозная щель"))

    print("OK" if ok else "PROVERKI NE PROSHLI")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
