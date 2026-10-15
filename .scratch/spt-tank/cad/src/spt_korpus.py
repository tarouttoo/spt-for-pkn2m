# -*- coding: utf-8 -*-
"""Корпус СПТ (базовый размер ~70 л) — компоновочный прототип.

Артефакт тикета #21 (карта усилия — issue #1 с лейблом wayfinder:map).
ВСЕ размеры — заглушки (тикет 05 «геометрия и толщина стенки» открыт):
принято D420, стенка 4 мм, обечайка 310 мм, днища эллиптические 2:1 ГОСТ 6533
с отбортовкой 40 мм, уклон 40 мм (торец B выше), изоляция+кожух 40+1 мм.

Слои (переключаются в просмотрщике):
  korpus             — обечайка+днища+патрубки 1-10 (сталь, единое тело) + опоры
  izolyaciya_kozhuh  — изоляция 40 мм + кожух 1 мм (заглушка, тикет 03 открыт)
  nachinka           — условные объёмы (ТЭН-трубки, фильтр, коробка, термометр, ДТС)
"""
from __future__ import annotations

from cadgen import build123d as bd
from cadgen import glb, srgb, step

# --- Основные заглушки размеров (⚠️ тикет 05 открыт) -----------------------
D_OUT = 420.0          # наружный диаметр обечайки
S_WALL = 4.0           # толщина стенки (s_min по тикету 11, без расчёта)
L_SHELL = 310.0        # длина обечайки (под внутренний объём ~70 л)
HEAD_DEPTH = D_OUT / 4 # эллиптическая часть 2:1
HEAD_FLANGE = 40.0     # отбортовка днища
R_OUT = D_OUT / 2
R_IN = R_OUT - S_WALL
L_HALF = L_SHELL / 2
TIP_X = L_HALF + HEAD_FLANGE + HEAD_DEPTH        # торец купола: 300
SLOPE = 40.0                                  # уклон: B выше A, мм (30..50)
LEG_X = 220.0                                 # привязка лап по оси
LEG_Y = 145.0
LEG_A_HEIGHT = 180.0                          # высота лапы у торца A (заглушка)
INS_T = 40.0                                  # изоляция (тикет 03 открыт)
SKIN_T = 1.0                                  # кожух

# Производные
ALPHA = SLOPE / (2 * TIP_X)                   # tan ≈ sin (малый угол)
ALPHA_DEG = ALPHA * 180.0 / 3.141592653589793


# --- Фабрики ----------------------------------------------------------------
def _ell_head(radius: float, depth: float, flange: float, apex_x: float,
              flip: bool, offset: float = 0.0) -> bd.Shape:
    """Днище (купол + отбортовка) вращением профиля вокруг оси X.

    apex_x — координата вершины купола; flip=True — купол смотрит в −X.
    offset > 0 — эквидистантное сжатие профиля внутрь на offset (стенка днища);
    линия закрытия по оси после offset даёт осевое отверстие ~2*offset, оно
    заваривается цилиндром-заплаткой радиусом 10 (внутри полости, на прочность
    и вид не влияет).
    """
    # фикс #22: заплатка раньше заканчивалась ровно в плоскости полюса купола
    # (выступала сквозь купол на ~12 мкм, лишние вершины ломали чек уклона);
    # теперь — на 0.2 мм за естественной вершиной offset-профиля, сталь на
    # полюсе ≈3.8 мм (запас до наружной поверхности ≈ S_WALL − 0.2)
    plug_end = (depth - offset) + 0.2 if offset else 0.0
    with bd.BuildSketch(bd.Plane.XZ) as sk:
        with bd.BuildLine():
            bd.EllipticalCenterArc((0, 0), depth, radius, 0, arc_size=90)
            bd.Line((0, radius), (-flange, radius))
            bd.Line((-flange, radius), (-flange, 0))
            bd.Line((-flange, 0), (depth, 0))
        bd.make_face()
        if offset:
            bd.offset(amount=-offset, kind=bd.Kind.ARC)  # эквидистанта профиля
    with bd.BuildPart() as part:
        bd.add(sk.face())
        bd.revolve(axis=bd.Axis.X)
        if offset:  # заплатка осевого отверстия от offset'а линии закрытия
            bd.add(bd.Cylinder(10.0, plug_end + flange).moved(
                bd.Location(((plug_end - flange) / 2.0, 0, 0), (0, 90, 0))))
    head = part.part
    if flip:  # купол в −X: вершина в apex_x, отбортовка к x=apex_x+depth+flange
        head = bd.Rot(0, 0, 180) * head
        head = head.moved(bd.Location((apex_x + depth, 0, 0)))
    else:     # купол в +X: вершина в apex_x, отбортовка к x=apex_x-depth-flange
        head = head.moved(bd.Location((apex_x - depth, 0, 0)))
    return head


def _vessel_outer() -> bd.Shape:
    shell = bd.Cylinder(R_OUT, L_SHELL).moved(bd.Location((0, 0, 0), (0, 90, 0)))
    head_a = _ell_head(R_OUT, HEAD_DEPTH, HEAD_FLANGE, -TIP_X, flip=True)
    # фикс: было R_IN — торец B получал ⌀412 вместо ⌀420 (дефект 1 из чека)
    head_b = _ell_head(R_OUT, HEAD_DEPTH, HEAD_FLANGE, TIP_X, flip=False)
    return shell.fuse(head_a, head_b)


def _vessel_cavity() -> bd.Shape:
    # фикс #22: цилиндр полости длиной обечайка + две отбортовки — торец в
    # плоскости привалки купола (x=±195). Раньше вылет до x=±225 прожигал
    # «плечо» днища там, где наружный радиус купола опускается ниже R_IN
    # (кольцевые зазоры со стенкой от x≈±215.4, полость сообщалась снаружи,
    # а стенки днищ отваливались отдельными телами).
    cyl = bd.Cylinder(R_IN, L_SHELL + 2 * HEAD_FLANGE).moved(
        bd.Location((0, 0, 0), (0, 90, 0)))
    # фикс: было масштабирование эллипса (стенка вырождалась к 0 на вершине);
    # теперь эквидистанта профиля наружного днища на S_WALL (дефект 2).
    # Стык цилиндра с отбортовкой полости — касательный, общий радиус R_IN.
    head_a = _ell_head(R_OUT, HEAD_DEPTH, HEAD_FLANGE, -TIP_X, flip=True,
                       offset=S_WALL)
    head_b = _ell_head(R_OUT, HEAD_DEPTH, HEAD_FLANGE, TIP_X, flip=False,
                       offset=S_WALL)
    return cyl.fuse(head_a, head_b)


# Патрубки: («ось», привязка centerline, границы вдоль оси, труба, канал, фланец)
NOZZLES = [
    # поз.1 — выход к горелке DN25 (торец A, верх днища; фильтр внутри на нём)
    dict(pos=1, axis="x", at=(-90.0, 90.0), span=(-200.0, -380.0),
         od=34.0, bore=27.0, fl=115.0, ft=14.0, label="01_vyhod_gorrelka_DN25"),
    # поз.2 — дренаж DN15 (торец A, низ днища)
    dict(pos=2, axis="x", at=(50.0, -130.0), span=(-210.0, -370.0),
         od=22.0, bore=16.0, fl=95.0, ft=12.0, label="02_drenazh_DN15"),
    # поз.3 — заполнение из РЕ DN20 (торец B, ~уровень оси)
    dict(pos=3, axis="x", at=(140.0, 25.0), span=(210.0, 386.0),
         od=27.0, bore=21.0, fl=105.0, ft=12.0, label="03_zapolnenie_RE_DN20"),
    # поз.4 — ответный фланец ТЭН-блока (торец B, низ; Ø150 — заглушка)
    dict(pos=4, axis="x", at=(0.0, -130.0), span=(195.0, 346.0),
         od=133.0, bore=121.0, fl=150.0, ft=16.0, label="04_flanec_ten_bloka"),
    # поз.5 — перелив DN20 (верхняя образующая, у торца B)
    dict(pos=5, axis="z", at=(60.0, -105.0), span=(176.0, 290.0),
         od=27.0, bore=21.0, fl=105.0, ft=12.0, label="05_perepolnenie_DN20"),
    # поз.6 — воздухоотвод DN15 (верхняя образующая, высшая точка у торца B)
    dict(pos=6, axis="z", at=(150.0, 0.0), span=(176.0, 280.0),
         od=22.0, bore=16.0, fl=95.0, ft=12.0, label="06_vozduhootvod_DN15"),
    # поз.7 — гильза термометра G1/2
    dict(pos=7, axis="z", at=(-115.0, 0.0), span=(176.0, 250.0),
         od=26.0, bore=20.0, fl=0.0, ft=0.0, label="07_gilza_termometr_G12"),
    # поз.8 — гильза ДТС G1/2
    dict(pos=8, axis="z", at=(-65.0, 0.0), span=(176.0, 250.0),
         od=26.0, bore=20.0, fl=0.0, ft=0.0, label="08_gilza_dts_G12"),
    # поз.9 — вход обратки DN20 (нижняя образующая, ближе к торцу A)
    dict(pos=9, axis="z", at=(-95.0, 0.0), span=(-176.0, -290.0),
         od=27.0, bore=21.0, fl=105.0, ft=12.0, label="09_obratka_DN20"),
    # поз.10 — шпилька заземления М12 (обечайка, у лапы A)
    dict(pos=10, axis="y", at=(-120.0, 0.0), span=(180.0, 250.0),
         od=12.0, bore=0.0, fl=0.0, ft=0.0, label="10_zazemlenie_M12"),
]


def _along(axis: str, at, t: float, rot_to_world=False):
    """Точка на оси патрубка: axis 'x' → at=(y,z); 'z' → at=(x,y); 'y' → at=(x,z)."""
    if axis == "x":
        return (t, at[0], at[1])
    if axis == "z":
        return (at[0], at[1], t)
    return (at[0], t, at[1])


def _cyl_along(axis: str, at, t0: float, t1: float, diameter: float) -> bd.Shape:
    c = (t0 + t1) / 2.0
    h = abs(t1 - t0)
    rot = {"x": (0, 90, 0), "z": (0, 0, 0), "y": (90, 0, 0)}[axis]
    return bd.Cylinder(diameter / 2.0, h).moved(
        bd.Location(_along(axis, at, c), rot))


def _nozzle(n) -> tuple[bd.Shape, bd.Shape, bd.Shape]:
    """Возвращает (тело патрубка, вырез канала в корпусе, вырез в изоляции)."""
    t0, t1 = n["span"]                      # t0 — внутри, t1 — внешний торец
    d = 1.0 if t1 >= t0 else -1.0
    tube = _cyl_along(n["axis"], n["at"], t0, t1, n["od"])
    body = tube
    if n["fl"] > 0:
        flange = _cyl_along(n["axis"], n["at"], t1 - d * n["ft"], t1, n["fl"])
        body = tube.fuse(flange)
    bore = None
    if n["bore"] > 0:
        bore = _cyl_along(n["axis"], n["at"], t0 - 30.0 * d, t1 + 10.0 * d,
                          n["bore"])
    cut_d = (n["fl"] if n["fl"] > 0 else n["od"]) + 20.0
    ins = _cyl_along(n["axis"], n["at"], t0 - 10.0 * d, t1 + 25.0 * d, cut_d)
    return body, bore, ins


# --- Сборка -----------------------------------------------------------------
@step(out="../STEP/spt_korpus.step")
@glb(out="../GLB/spt_korpus.glb")
def spt_korpus() -> bd.Shape:
    tilt = bd.Rot(0, -ALPHA_DEG, 0)                 # +X (торец B) — вверх
    drop = -220.0 * ALPHA - (R_OUT ** 2 - LEG_Y ** 2) ** 0.5   # низ сосуда у лапы A
    lift = bd.Location((0, 0, LEG_A_HEIGHT - drop))

    def to_world(shape: bd.Shape) -> bd.Shape:
        return lift * (tilt * shape)

    # Корпус: стенка + днища, каналы, патрубки
    shell = _vessel_outer() - _vessel_cavity()
    nozzles, bores, ins_cutters = [], [], []
    for n in NOZZLES:
        body, bore, ins = _nozzle(n)
        nozzles.append(body)
        if bore is not None:
            bores.append(bore)
        ins_cutters.append(ins)
    # фикс: приварить патрубки ДО вырезания каналов — иначе цельная труба
    # глушила собственный канал (дефект 4)
    korpus_local = shell.fuse(*nozzles).cut(*bores)

    # Изоляция + кожух (заглушка тикета 03)
    env_r, env_d = R_OUT + INS_T, HEAD_DEPTH + INS_T
    with bd.BuildPart() as p_env:
        bd.add(bd.Cylinder(env_r, L_SHELL).moved(bd.Location((0, 0, 0), (0, 90, 0))))
        bd.add(_ell_head(env_r, env_d, HEAD_FLANGE + 5, -TIP_X - INS_T, flip=True))
        bd.add(_ell_head(env_r, env_d, HEAD_FLANGE + 5, TIP_X + INS_T, flip=False))
    envelope = p_env.part
    with bd.BuildPart() as p_env2:
        bd.add(bd.Cylinder(env_r + SKIN_T, L_SHELL).moved(bd.Location((0, 0, 0), (0, 90, 0))))
        bd.add(_ell_head(env_r + SKIN_T, env_d + SKIN_T, HEAD_FLANGE + 5,
                         -TIP_X - INS_T - SKIN_T, flip=True))
        bd.add(_ell_head(env_r + SKIN_T, env_d + SKIN_T, HEAD_FLANGE + 5,
                         TIP_X + INS_T + SKIN_T, flip=False))
    envelope2 = p_env2.part
    # вырез под коробку соединительную — следует за коробкой (ниже)
    box_cut = bd.Box(170.0, 120.0, 120.0).moved(bd.Location((25.0, 0.0, 265.0)))
    izol_local = (envelope - _vessel_outer() - box_cut).cut(*ins_cutters)
    kozhuh_local = (envelope2 - envelope).cut(*ins_cutters, box_cut)

    # Начинка — условные объёмы
    tena = [
        _cyl_along("x", (y, z), 180.0, -180.0, 16.0)
        for y, z in ((-50.0, -120.0), (0.0, -145.0), (50.0, -120.0))
    ]
    # фикс: было 190..200 — траверса входила на 5 мм в трубу патрубка 4 (от x=195);
    # теперь 178..188, зазор до трубы 7 мм (дефект 6)
    ten_hub = _cyl_along("x", (0.0, -130.0), 188.0, 178.0, 100.0)
    # фикс: фильтр надет coaxially на трубу патрубка 1 (⌀34) — нужен канал 45
    # (зазор 5.5 мм), иначе труба глухо входит в сплошной цилиндр (дефект 5,
    # 36317 мм³ пересечения)
    with bd.BuildPart() as p_filtr:
        bd.add(bd.Cylinder(45.0, 150.0).moved(
            bd.Location((-165.0, -90.0, 90.0), (0, 90, 0))))
        # канал стакана фильтра: mode — аргумент add, не moved (иначе падение
        # регенерации)
        bd.add(bd.Cylinder(22.5, 160.0).moved(
            bd.Location((-160.0, -90.0, 90.0), (0, 90, 0))),
            mode=bd.Mode.SUBTRACT)
    filtr = p_filtr.part
    # фикс компоновки (рация 2026-10-15): дно коробки на образующей z=210 (было
    # 195 — утоплена в сталь) и сдвиг от гильзы ДТС (поз. 8): центр x=25, ширина
    # 130 (было 150 при +10 мм — упиралась во фланец воздухоотвода 6, остался бы
    # нахлёст 2.5 мм; 130 даёт 12 мм к гильзе 8 и 12.5 мм к фланцу 6) (дефект 7)
    # фикс #22: глубина 80 (было 100) — фланец перелива 5 (⌀105 при y=−105)
    # доставал до y=−52.5, зазор к стенке коробки был 2.5 мм (<10 для монтажа);
    # при y∈[−40;40] зазор 12.5 мм, остальные записанные зазоры не меняются
    korobka = bd.Box(130.0, 80.0, 70.0).moved(bd.Location((25.0, 0.0, 245.0)))
    term_stem = _cyl_along("z", (-115.0, 0.0), 250.0, 330.0, 8.0)
    term_dial = _cyl_along("z", (-115.0, 0.0), 330.0, 338.0, 60.0)
    dts = _cyl_along("z", (-65.0, 0.0), 250.0, 300.0, 6.0)
    tena_solid = tena[0].fuse(*tena[1:], ten_hub)
    tena_solid.color = srgb("#B87333")
    filtr.color = srgb("#4A6FA5")
    korobka.color = srgb("#6B7280")
    term_stem.color = term_dial.color = srgb("#E5E7EB")
    dts.color = srgb("#9CA3AF")
    for part, name in ((tena_solid, "ten_trubki"), (filtr, "filtr"),
                       (korobka, "korobka_soedinitelnaya"),
                       (term_stem, "termometr"), (term_dial, "termometr_shkala"),
                       (dts, "dts_datchik")):
        part.label = name
    nachinka_local = bd.Compound(
        children=[tena_solid, filtr, korobka, term_stem, term_dial, dts],
        label="nachinka")

    # Мир: наклон + подъём на лапы
    korpus_w = to_world(korpus_local)
    izol_w = to_world(izol_local)
    kozhuh_w = to_world(kozhuh_local)
    nachinka_w = to_world(nachinka_local)

    # Опоры — вертикальные листовые лапы (мир): пригнать по корпусу и вырезать в изоляции/кожухе
    plates = []
    for x_l in (-LEG_X, LEG_X):
        for y in (-LEG_Y, LEG_Y):
            z_attach = x_l * ALPHA - (R_OUT ** 2 - y ** 2) ** 0.5
            z_top = z_attach - drop + LEG_A_HEIGHT + 8.0
            plates.append(bd.Box(110.0, 8.0, z_top).moved(
                bd.Location((x_l, y, z_top / 2.0))))
    legs = [plate - korpus_w for plate in plates]
    legs_solid = legs[0].fuse(*legs[1:])
    legs_solid.color = srgb("#8D98A5")
    izol_w = izol_w.cut(*plates)
    kozhuh_w = kozhuh_w.cut(*plates)

    korpus_solid = korpus_w.fuse(legs_solid)
    korpus_solid.label = "korpus"
    korpus_solid.color = srgb("#8D98A5")
    izol_w.label = "izolyaciya"
    izol_w.color = srgb("#3A4750")
    kozhuh_w.label = "kozhuh"
    kozhuh_w.color = srgb("#64748B")
    izol_group = bd.Compound(children=[izol_w, kozhuh_w], label="izolyaciya_kozhuh")

    return bd.Compound(children=[korpus_solid, izol_group, nachinka_w],
                       label="spt_korpus_70l")


if __name__ == "__main__":
    spt_korpus()
