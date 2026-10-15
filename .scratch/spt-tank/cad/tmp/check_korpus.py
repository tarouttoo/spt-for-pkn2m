# -*- coding: utf-8 -*-
"""Детерминированные проверки модели корпуса СПТ (тикет 20).

Запуск из .scratch/spt-tank/cad:
  uvx --no-config --managed-python --python 3.13 --from cadgen==0.7.21 \
      python tmp/check_korpus.py
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import spt_korpus as m  # noqa: E402


def main() -> int:
    tree = m.spt_korpus()
    ok = True

    def check(name: str, cond: bool, detail: str) -> None:
        nonlocal ok
        print(f"{'PASS' if cond else 'FAIL'}  {name}: {detail}")
        ok = ok and cond

    bbox = tree.bounding_box()
    size = (bbox.size.X, bbox.size.Y, bbox.size.Z)
    print(f"bbox size (Д x Ш x В) = {size[0]:.1f} x {size[1]:.1f} x {size[2]:.1f} mm")
    print(f"bbox min = {bbox.min}, max = {bbox.max}")

    # Габарит: длина корпуса с фланцами ~< 800 (референс 850 — с кранами),
    # ширина = кожух 500 (референс 500), высота < 800
    check("shirina_kozhuka_500", abs(size[1] - 502.0) < 3.0,
          f"{size[1]:.1f} мм (D420+40 изоляция+1 кожух ≈ 502; референс 500)")
    check("dlina_do_850", size[0] < 850.0, f"{size[0]:.1f} < 850 (краны не смоделированы)")
    check("vysota_do_800", size[2] < 800.0, f"{size[2]:.1f} < 800")

    # Пол: лапы стоят на z = 0
    check("pol_z0", abs(bbox.min.Z) < 1.0, f"min Z = {bbox.min.Z:.2f}")

    # Уклон: торцы сосуда (без лап) differ by SLOPE
    tips = [v for v in tree.vertices()
            if abs(abs(v.X) - m.TIP_X * math.cos(m.ALPHA)) < 2.0]
    z_a = min(v.Z for v in tips if v.X < 0)
    z_b = max(v.Z for v in tips if v.X > 0)
    check("uklon_40mm", abs((z_b - z_a) - m.SLOPE) < 1.0,
          f"B - A = {z_b - z_a:.1f} мм (цель {m.SLOPE})")

    # Внутренний объём ~70 л (аналитически, заготовка тикета 05)
    r_in, l = m.R_IN, m.L_SHELL
    d_in = m.HEAD_DEPTH - m.S_WALL
    v_cyl = math.pi * r_in ** 2 * l
    v_fl = 2 * math.pi * r_in ** 2 * m.HEAD_FLANGE
    v_ell = 2 * (2.0 / 3.0) * math.pi * r_in ** 2 * d_in
    liters = (v_cyl + v_fl + v_ell) / 1e6
    check("vnutr_obem_70l", 66.0 < liters < 74.0, f"{liters:.1f} л (цель ~70)")

    # Слои: корпус/изоляция/кожух/начинка — положительные объёмы
    parts = {}
    def walk(shape, depth=0):
        for child in shape.children:
            vol = child.volume / 1e6
            parts[child.label] = vol
            walk(child, depth + 1)
    walk(tree)
    for label, vol in sorted(parts.items()):
        check(f"obyem_{label}", vol > 0.0005, f"{vol * 1000:.1f} см³")

    # Начинка внутри полости: максимальный радиус ТЭНов/фильтра < R_IN
    r_filter = math.hypot(90.0, 90.0) + 45.0
    r_ten = 145.0 + 8.0
    check("nachinka_v_polosti", max(r_filter, r_ten) < m.R_IN,
          f"фильтр {r_filter:.0f}, ТЭН {r_ten:.0f} < R_IN {m.R_IN:.0f}")

    print("OK" if ok else "PROVERKI NE PROSHLI")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
