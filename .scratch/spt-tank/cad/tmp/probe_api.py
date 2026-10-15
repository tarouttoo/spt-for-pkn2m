# -*- coding: utf-8 -*-
"""Одноразовый зонд API: offset в BuildSketch + Vertex в closest_points."""
from cadgen import build123d as bd
from cadgen.geometry import closest_points

with bd.BuildSketch(bd.Plane.XZ) as sk:
    with bd.BuildLine():
        bd.EllipticalCenterArc((0, 0), 105, 210, 0, arc_size=90)
        bd.Line((0, 210), (-40, 210))
        bd.Line((-40, 210), (-40, 0))
        bd.Line((-40, 0), (105, 0))
    bd.make_face()
    bd.offset(amount=-4.0, kind=bd.Kind.ARC)
f = sk.face()
print("offset face ok, area =", f.area)
bb = f.bounding_box()
print("bbox x:", bb.min.X, bb.max.X, " z:", bb.min.Z, bb.max.Z)

v = bd.Vertex(0, 0, 0)
box = bd.Solid.make_box(10, 10, 10)
print("vertex-box dist:", closest_points(v, box).distance)
v2 = bd.Vertex(20, 0, 0)
print("vertex-box dist (вне):", closest_points(v2, box).distance)
