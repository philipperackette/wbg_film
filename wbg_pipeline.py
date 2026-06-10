#!/usr/bin/env python3
"""
wbg_pipeline.py — Chaîne complète du découpage de Wallace–Bolyai–Gerwien.

dissect_polygon(poly, palette, tag, max_den=2)
    Triangule le polygone, transforme chaque triangle en rectangle de largeur 1
    (chaîne wbg_core), puis empile les rectangles en une colonne 1 × aire.
    → dict(column=[Piece], rect_rows=[(y, h, i)], colH=aire, tris=[...])

    Chaque Piece de `column` transporte `back` : l'isométrie directe qui la
    ramène EXACTEMENT à sa position d'origine dans le polygone.

common_refinement(colA, colB, area)
    Intersections (shapely) des deux découpages du même rectangle 1 × aire.
    → liste de dict(verts=[P], ia=idx dans colA, ib=idx dans colB)

common_located(com, colA, colB)
    Les trois poses CONGRUENTES (mêmes sommets, même ordre) de chaque pièce
    commune : dans A, dans le rectangle, dans B.
    → liste de dict(inA=[P], rect=[P], inB=[P], color=…, ai=…)
"""
from __future__ import annotations
import math

from wbg_core import (P, Piece, poly_area, ear_clip, make_rot180, make_rot,
                      make_trans, par_basis, par_height,
                      choose_simple_rational_side, rationalize,
                      q_cut_and_stack, p_cut_and_stack, par_to_rectangle)

from shapely.geometry import Polygon as SPoly
from shapely.geometry import GeometryCollection, MultiPolygon


def dissect_triangle(tri, color, origin, step0=1, max_den=2):
    """Triangle (3 P, pose quelconque) → pièces pavant un rectangle de largeur 1.
    Renvoie dict(pieces=[Piece], rect=[4 P], p=..., q=..., h=...)."""
    pts = list(tri)
    A0 = poly_area(pts)
    # base = plus longue arête (B→C), A = sommet opposé
    edges = []
    for i in range(3):
        b = pts[i]; c = pts[(i + 1) % 3]; a = pts[(i + 2) % 3]
        edges.append((a, b, c, (c - b).norm()))
    edges.sort(key=lambda e: -e[3])
    A, B, C, _ = edges[0]
    M = (A + B) * 0.5; N = (A + C) * 0.5
    trap = Piece([M, B, C, N], color, step0, "trapèze", origin=origin)
    amn = Piece([A, M, N], color, step0, "demi-triangle", origin=origin)
    ndc = amn.apply(make_rot180(N))
    corners = (B, C, 2 * N - M, M)   # (B, C, D, M) avec D = 2N − M
    pieces = [trap, ndc]
    _b, u, v = par_basis(corners)
    h, L = par_height(u, v)
    strict = abs(h - round(h)) < 1e-9
    p, q, val, _txt = choose_simple_rational_side(h, max_den=max_den, strict=strict)
    step = step0 + 1
    pieces, corners, _ = rationalize(pieces, corners, val, step)
    if q > 1:
        step += 1; cq = step; step += 1; sq = step
        pieces, corners, _ = q_cut_and_stack(pieces, corners, q, cq, sq)
    if p > 1:
        step += 1; cp = step; step += 1; sp = step
        pieces, corners, _ = p_cut_and_stack(pieces, corners, p, cp, sp)
    step += 1
    pieces, rect, info = par_to_rectangle(pieces, corners, step)
    A1 = sum(pc.area() for pc in pieces)
    assert abs(A1 - A0) < 1e-7 * max(1.0, A0), "dissect_triangle : aire non conservée"
    assert abs(info["area"] - A0) < 1e-7 * max(1.0, A0)
    return dict(pieces=pieces, rect=rect, p=p, q=q, h=h, area=A0)


def dissect_polygon(poly, palette, tag, max_den=2):
    """Polygone → colonne 1 × aire. Voir docstring du module."""
    verts = [P(v.x, v.y) for v in poly]
    A0 = poly_area(verts)
    tris = ear_clip(verts)
    column = []; rect_rows = []; y = 0.0; details = []
    for i, t in enumerate(tris):
        color = palette[i % len(palette)]
        res = dissect_triangle(list(t), color, i, step0=1, max_den=max_den)
        r0, r1 = res["rect"][0], res["rect"][1]
        ang = -math.atan2(r1.y - r0.y, r1.x - r0.x)
        g = make_trans(0.0, y).compose(
            make_trans(-r0.x, -r0.y).compose(make_rot(ang, r0.x, r0.y)))
        for pc in res["pieces"]:
            pc.apply(g)
            column.append(pc)
        # contrôle : pièces dans [0,1] × [y, y+aire]
        hi = res["area"]
        for pc in res["pieces"]:
            for v in pc.verts:
                assert -1e-6 <= v.x <= 1 + 1e-6, f"{tag} T{i} : x hors [0,1]"
                assert y - 1e-6 <= v.y <= y + hi + 1e-6, f"{tag} T{i} : y hors bande"
        rect_rows.append((y, hi, i))
        details.append(dict(i=i, p=res["p"], q=res["q"], h=res["h"], area=hi,
                            n=len(res["pieces"])))
        y += hi
    assert abs(y - A0) < 1e-7 * max(1.0, A0), "dissect_polygon : hauteur ≠ aire"
    Acol = sum(pc.area() for pc in column)
    assert abs(Acol - A0) < 1e-7 * max(1.0, A0), "dissect_polygon : aire colonne"
    # contrôle ultime : chaque pièce, ramenée par `back`, est dans le polygone
    SP = SPoly([(v.x, v.y) for v in verts])
    for pc in column:
        orig = [pc.back(v) for v in pc.verts]
        out_area = SPoly([(v.x, v.y) for v in orig]).difference(SP.buffer(1e-7)).area
        assert out_area < 1e-9, \
            f"{tag} : pièce {pc.pid} hors du polygone après retour (déborde {out_area})"
    return dict(column=column, rect_rows=rect_rows, colH=y, tris=tris,
                details=details)


def _spoly(verts):
    return SPoly([(v.x, v.y) for v in verts])


def _rings(geom):
    if geom.is_empty:
        return []
    if isinstance(geom, SPoly):
        return [geom]
    if isinstance(geom, (MultiPolygon, GeometryCollection)):
        out = []
        for g in geom.geoms:
            out += _rings(g)
        return out
    return []


def common_refinement(colA, colB, area, min_area=1e-9):
    """Raffinement commun des deux découpages du rectangle 1 × aire."""
    SA = [_spoly(pc.verts) for pc in colA]
    SB = [_spoly(pc.verts) for pc in colB]
    com = []; tot = 0.0
    for ia, pa in enumerate(SA):
        for ib, pb in enumerate(SB):
            if not pa.intersects(pb):
                continue
            inter = pa.intersection(pb)
            for g in _rings(inter):
                if g.area < min_area:
                    continue
                g = g.simplify(1e-10)
                xy = list(g.exterior.coords)[:-1]
                if SPoly(xy).exterior.is_ccw is False:
                    xy = xy[::-1]
                com.append(dict(verts=[P(x, yy) for (x, yy) in xy], ia=ia, ib=ib))
                tot += g.area
    # tolérance : les sommets de POLY_A/POLY_B sont arrondis à 4 décimales,
    # leurs aires diffèrent donc de ~2e-4 (invisible à l'écran)
    assert abs(tot - area) < 1e-3 * max(1.0, area), \
        f"common_refinement : aire {tot} ≠ {area}"
    return com


def common_located(com, colA, colB):
    """Les trois poses congruentes (A, rectangle, B) de chaque pièce commune."""
    out = []
    for c in com:
        pa = colA[c["ia"]]; pb = colB[c["ib"]]
        inA = [pa.back(v) for v in c["verts"]]
        inB = [pb.back(v) for v in c["verts"]]
        # congruence : mêmes longueurs d'arêtes (isométrie directe)
        n = len(c["verts"])
        for k in range(n):
            d0 = (c["verts"][(k + 1) % n] - c["verts"][k]).norm()
            dA = (inA[(k + 1) % n] - inA[k]).norm()
            dB = (inB[(k + 1) % n] - inB[k]).norm()
            assert abs(d0 - dA) < 1e-7 and abs(d0 - dB) < 1e-7, \
                "common_located : poses non congruentes"
        out.append(dict(inA=inA, rect=list(c["verts"]), inB=inB,
                        color=pa.color, ai=pa.origin, bi=pb.origin))
    return out
