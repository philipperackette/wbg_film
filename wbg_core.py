#!/usr/bin/env python3
"""
wbg_core.py — Cœur géométrique HONNÊTE du découpage de Wallace–Bolyai–Gerwien
(construction de Boyer, ch. III §8.2). Reconstruit pour satisfaire exactement
le contrat de wbg_animate.py.

Principes non négociables :
  * AUCUN redimensionnement : uniquement des ISOMÉTRIES DIRECTES
    (translations, rotations). Aucune réflexion, aucun cisaillement affine.
  * Conservation EXACTE de l'aire, vérifiée par assertion à chaque étape.
  * Chaque pièce transporte la transformation rigide inverse (`back`)
    qui la ramène à sa position d'origine dans le polygone de départ.
  * Un ENREGISTREUR (rec_start/rec_stop) journalise coupes et isométries
    pour que la scène « méthode » rejoue la chaîne pas à pas.

Chaîne (par triangle, base = plus longue arête, hauteur du parallélogramme h):
  triangle → (ligne des milieux + demi-tour) → parallélogramme base L, côté v
  → rationalisation : le côté oblique prend la longueur EXACTE p/q ≥ h
    (une coupe + une translation de ±L)
  → q bandes empilées : côté oblique = p (entier)
  → si p > 1 : p tranches empilées : côté = 1
  → redressement : coupes ⊥ au côté unité + translations → rectangle 1 × aire.
"""
from __future__ import annotations
import math

EPS = 1e-9


# ───────────────────────── points & vecteurs ─────────────────────────
class P:
    __slots__ = ("x", "y")

    def __init__(self, x, y):
        self.x = float(x); self.y = float(y)

    def __add__(self, o):  return P(self.x + o.x, self.y + o.y)
    def __sub__(self, o):  return P(self.x - o.x, self.y - o.y)
    def __mul__(self, k):  return P(self.x * k, self.y * k)
    __rmul__ = __mul__
    def __neg__(self):     return P(-self.x, -self.y)
    def norm(self):        return math.hypot(self.x, self.y)
    def dot(self, o):      return self.x * o.x + self.y * o.y
    def cross(self, o):    return self.x * o.y - self.y * o.x
    def tup(self):         return (self.x, self.y)
    def __iter__(self):    return iter((self.x, self.y))
    def __repr__(self):    return f"P({self.x:.6f},{self.y:.6f})"


def poly_area(verts):
    """Aire (positive) d'un polygone simple (liste de P)."""
    n = len(verts); s = 0.0
    for i in range(n):
        a = verts[i]; b = verts[(i + 1) % n]
        s += a.x * b.y - b.x * a.y
    return abs(s) / 2.0


def _signed_area(verts):
    n = len(verts); s = 0.0
    for i in range(n):
        a = verts[i]; b = verts[(i + 1) % n]
        s += a.x * b.y - b.x * a.y
    return s / 2.0


# ───────────────────────── triangulation (ear clipping) ─────────────────────────
def _pt_in_tri(p, a, b, c):
    d1 = (p - a).cross(b - a); d2 = (p - b).cross(c - b); d3 = (p - c).cross(a - c)
    neg = (d1 < -EPS) or (d2 < -EPS) or (d3 < -EPS)
    pos = (d1 > EPS) or (d2 > EPS) or (d3 > EPS)
    return not (neg and pos)


def ear_clip(poly):
    """Triangulation déterministe par coupage d'oreilles (polygone simple).
    Renvoie une liste de triangles (a, b, c) en orientation CCW."""
    verts = [P(p.x, p.y) for p in poly]
    if _signed_area(verts) < 0:
        verts.reverse()
    idx = list(range(len(verts)))
    tris = []
    guard = 0
    while len(idx) > 3:
        guard += 1
        assert guard < 10000, "ear_clip : boucle infinie (polygone non simple ?)"
        n = len(idx); clipped = False
        for k in range(n):
            i0, i1, i2 = idx[(k - 1) % n], idx[k], idx[(k + 1) % n]
            a, b, c = verts[i0], verts[i1], verts[i2]
            if (b - a).cross(c - a) <= EPS:        # réflexe ou plat
                continue
            ok = True
            for j in idx:
                if j in (i0, i1, i2):
                    continue
                if _pt_in_tri(verts[j], a, b, c):
                    ok = False; break
            if ok:
                tris.append((a, b, c))
                idx.pop(k); clipped = True; break
        assert clipped, "ear_clip : aucune oreille trouvée"
    a, b, c = (verts[idx[0]], verts[idx[1]], verts[idx[2]])
    tris.append((a, b, c))
    A0 = poly_area(verts); A1 = sum(poly_area(list(t)) for t in tris)
    assert abs(A0 - A1) < 1e-7 * max(1.0, A0), "ear_clip : aire non conservée"
    return tris


# ───────────────────────── isométries directes ─────────────────────────
class Iso:
    """Isométrie directe  X ↦ R(θ)·X + t,  avec descripteur pour le journal."""
    __slots__ = ("c", "s", "tx", "ty", "desc")

    def __init__(self, c, s, tx, ty, desc):
        self.c = c; self.s = s; self.tx = tx; self.ty = ty; self.desc = desc

    def __call__(self, p: P) -> P:
        return P(self.c * p.x - self.s * p.y + self.tx,
                 self.s * p.x + self.c * p.y + self.ty)

    def compose(self, other: "Iso") -> "Iso":
        """self ∘ other (applique other puis self)."""
        c = self.c * other.c - self.s * other.s
        s = self.s * other.c + self.c * other.s
        tx = self.c * other.tx - self.s * other.ty + self.tx
        ty = self.s * other.tx + self.c * other.ty + self.ty
        return Iso(c, s, tx, ty, ("comp",))

    def inverse(self) -> "Iso":
        c, s = self.c, -self.s
        tx = -(c * self.tx - s * self.ty)
        ty = -(s * self.tx + c * self.ty)
        return Iso(c, s, tx, ty, ("inv",))


def identity_iso():
    return Iso(1.0, 0.0, 0.0, 0.0, ("trans", 0.0, 0.0))


def make_trans(dx, dy):
    return Iso(1.0, 0.0, dx, dy, ("trans", dx, dy))


def make_rot(theta, cx, cy):
    c = math.cos(theta); s = math.sin(theta)
    return Iso(c, s, cx - c * cx + s * cy, cy - s * cx - c * cy,
               ("rot", theta, cx, cy))


def make_rot180(center: P):
    """Demi-tour autour de `center` (triangle → parallélogramme)."""
    return make_rot(math.pi, center.x, center.y)


# ───────────────────────── enregistreur d'événements ─────────────────────────
_REC = None


def rec_start():
    global _REC
    _REC = []


def rec_stop():
    global _REC
    ev = _REC if _REC is not None else []
    _REC = None
    return ev


def _rec(event):
    if _REC is not None:
        _REC.append(event)


# ───────────────────────── pièces ─────────────────────────
_PID = [0]


class Piece:
    """Polygone convexe rigide. `back` ramène la pose courante à la pose
    d'origine dans le polygone de départ (composée des inverses)."""
    __slots__ = ("verts", "color", "step", "name", "pid", "origin", "back")

    def __init__(self, verts, color, step=0, name="", origin=0, back=None):
        self.verts = [P(v.x, v.y) for v in verts]
        self.color = color; self.step = step; self.name = name
        self.origin = origin
        self.back = back if back is not None else identity_iso()
        _PID[0] += 1; self.pid = _PID[0]

    def area(self):
        return poly_area(self.verts)

    def tups(self):
        return [v.tup() for v in self.verts]

    def centroid(self):
        n = len(self.verts)
        return P(sum(v.x for v in self.verts) / n, sum(v.y for v in self.verts) / n)

    def apply(self, iso: Iso) -> "Piece":
        """Applique une isométrie (journalisée si l'enregistreur est actif).
        Le pid est conservé : c'est la même pièce qui bouge."""
        before = self.tups()
        self.back = self.back.compose(iso.inverse())
        self.verts = [iso(v) for v in self.verts]
        _rec({"t": "move", "id": self.pid, "before": before,
              "after": self.tups(), "iso": iso.desc, "color": self.color})
        return self

    def translated(self, dx, dy):
        return self.apply(make_trans(dx, dy))


def _clip_halfplane(verts, p0: P, d: P, side):
    """Garde la partie du polygone où side*cross(d, X−p0) ≥ 0 (Sutherland–Hodgman)."""
    out = []
    n = len(verts)
    for i in range(n):
        a = verts[i]; b = verts[(i + 1) % n]
        fa = side * d.cross(a - p0); fb = side * d.cross(b - p0)
        if fa >= -EPS:
            out.append(a)
        if (fa > EPS and fb < -EPS) or (fa < -EPS and fb > EPS):
            t = fa / (fa - fb)
            out.append(P(a.x + t * (b.x - a.x), a.y + t * (b.y - a.y)))
    # nettoie les doublons consécutifs
    res = []
    for v in out:
        if not res or (v - res[-1]).norm() > 1e-10:
            res.append(v)
    if len(res) >= 2 and (res[0] - res[-1]).norm() <= 1e-10:
        res.pop()
    return res


def _chord(verts, p0: P, d: P):
    """Intersection (segment) de la droite (p0, d) avec le polygone convexe."""
    ts = []
    n = len(verts)
    for i in range(n):
        a = verts[i]; b = verts[(i + 1) % n]
        e = b - a
        den = d.cross(e)
        if abs(den) < 1e-14:
            continue
        t = (a - p0).cross(e) / den
        u = (a - p0).cross(d) / den
        if -1e-9 <= u <= 1 + 1e-9:
            ts.append(t)
    if not ts:
        return None
    t0, t1 = min(ts), max(ts)
    if t1 - t0 < 1e-9:
        return None
    A = P(p0.x + t0 * d.x, p0.y + t0 * d.y)
    B = P(p0.x + t1 * d.x, p0.y + t1 * d.y)
    return (A.tup(), B.tup())


def cut_piece(piece: Piece, p0: P, d: P, kind: str, step: int):
    """Coupe une pièce par la droite (p0, d). Renvoie 1 ou 2 pièces.
    Les enfants héritent couleur/origine/back. Journalise la coupe."""
    A0 = piece.area()
    left = _clip_halfplane(piece.verts, p0, d, +1)
    right = _clip_halfplane(piece.verts, p0, d, -1)
    la = poly_area(left) if len(left) >= 3 else 0.0
    ra = poly_area(right) if len(right) >= 3 else 0.0
    if la < 1e-10 or ra < 1e-10:
        return [piece]
    assert abs(la + ra - A0) < 1e-7 * max(1.0, A0), "cut_piece : aire non conservée"
    ch = []
    for vv in (left, right):
        ch.append(Piece(vv, piece.color, step, piece.name,
                        origin=piece.origin, back=piece.back))
    _rec({"t": "cut", "kind": kind, "parent": piece.pid,
          "children": [(c.pid, c.tups(), c.color) for c in ch],
          "segment": _chord(piece.verts, p0, d)})
    return ch


# ───────────────────────── repère local du parallélogramme ─────────────────────────
def par_basis(corners):
    """corners = (B, C, D, M). Renvoie (B, u, v) avec u = C−B (base), v = M−B."""
    B, C, D, M = corners
    return B, C - B, M - B


def par_height(u: P, v: P):
    """(h, L) : hauteur du parallélogramme relative à la base u, et L = |u|."""
    L = u.norm()
    h = abs(u.cross(v)) / L
    return h, L


def _frame(corners):
    """Repère local : origine B, axe ξ = û, axe ζ = n̂ (v·n̂ > 0).
    Renvoie (B, û, n̂, L, s, h) avec v = s·û + h·n̂, h > 0."""
    B, u, v = par_basis(corners)
    L = u.norm()
    uh = P(u.x / L, u.y / L)
    nh = P(-uh.y, uh.x)
    if v.dot(nh) < 0:
        nh = P(uh.y, -uh.x)
    s = v.dot(uh); h = v.dot(nh)
    assert h > EPS, "_frame : parallélogramme dégénéré"
    return B, uh, nh, L, s, h


def _w(Bo, uh, nh, xi, zeta):
    """local (ξ,ζ) → monde."""
    return P(Bo.x + xi * uh.x + zeta * nh.x, Bo.y + xi * uh.y + zeta * nh.y)


# ───────────────────────── rationalisation ─────────────────────────
def choose_simple_rational_side(h, max_den=2, strict=False):
    """Plus simple fraction p/q ≥ h avec q ≤ max_den (valeur minimale,
    puis dénominateur minimal). strict : h est (numériquement) entier."""
    if strict:
        p = max(1, int(round(h))); q = 1
        return p, q, float(p), f"{p}"
    best = None
    for q in range(1, max_den + 1):
        p = max(1, int(math.ceil(q * h - 1e-12)))
        val = p / q
        g = math.gcd(p, q)
        cand = (val, q // g, p // g)
        if best is None or cand < best:
            best = cand
    val, q, p = best
    txt = f"{p}/{q}" if q > 1 else f"{p}"
    return p, q, val, txt


def rationalize(pieces, corners, val, step):
    """Cisaillement HONNÊTE : une coupe + une translation de ±L.
    Le côté oblique prend la longueur EXACTE val (= p/q ≥ h)."""
    A0 = sum(pc.area() for pc in pieces)
    Bo, uh, nh, L, s, h = _frame(corners)
    assert val >= h - 1e-9, "rationalize : val < h impossible"
    st = math.sqrt(max(0.0, val * val - h * h))      # pente cible (≥ 0)
    if abs(st - s) < 1e-12:
        newc = (Bo, _w(Bo, uh, nh, L, 0), _w(Bo, uh, nh, L + st, h), _w(Bo, uh, nh, st, h))
        return pieces, newc, {"s": st, "h": h}
    if st < s:
        # coupe de C=(L,0) vers (L+st, h) ; le coin de droite recule de −L
        p0 = _w(Bo, uh, nh, L, 0); d = P(st * uh.x + h * nh.x, st * uh.y + h * nh.y)
        keep_side = lambda pc: (pc.centroid() - p0).cross(d) * uh.cross(nh)  # signe
        dxy = (-L * uh.x, -L * uh.y)
    else:
        assert st <= L + s + 1e-9, "rationalize : cible trop inclinée pour une seule coupe"
        # coupe de B=(0,0) vers (st, h) ; le coin de gauche avance de +L
        p0 = Bo; d = P(st * uh.x + h * nh.x, st * uh.y + h * nh.y)
        dxy = (L * uh.x, L * uh.y)
    out = []
    for pc in pieces:
        out += cut_piece(pc, p0, d, "shear", step)
    # qui bouge ? le morceau situé du côté « hors du nouveau parallélogramme »
    moved = []
    for pc in out:
        c = pc.centroid()
        alpha = (c - Bo).dot(uh) - (st / h) * (c - Bo).dot(nh)   # abscisse de base oblique-cible
        if st < s:
            if alpha > L + 1e-9:
                pc.translated(*dxy); moved.append(pc)
        else:
            if alpha < -1e-9:
                pc.translated(*dxy); moved.append(pc)
    assert moved, "rationalize : aucun morceau déplacé (géométrie inattendue)"
    A1 = sum(pc.area() for pc in out)
    assert abs(A1 - A0) < 1e-7 * max(1.0, A0), "rationalize : aire non conservée"
    newc = (Bo, _w(Bo, uh, nh, L, 0), _w(Bo, uh, nh, L + st, h), _w(Bo, uh, nh, st, h))
    # contrôle : tous les morceaux dans le nouveau parallélogramme (par aire)
    return out, newc, {"s": st, "h": h}


# ───────────────────────── empilements q puis p ─────────────────────────
def q_cut_and_stack(pieces, corners, q, cut_step, stack_step):
    """Coupe la base en q bandes parallèles au côté oblique et les empile
    le long du côté : côté oblique → q × (p/q) = p (entier)."""
    A0 = sum(pc.area() for pc in pieces)
    Bo, uh, nh, L, s, h = _frame(corners)
    d = P(s * uh.x + h * nh.x, s * uh.y + h * nh.y)       # direction du côté
    out = list(pieces)
    for k in range(1, q):
        nxt = []
        p0 = _w(Bo, uh, nh, k * L / q, 0)
        for pc in out:
            nxt += cut_piece(pc, p0, d, "q-cut", cut_step)
        out = nxt
    # bande k : abscisse oblique α ∈ (kL/q, (k+1)L/q) ; translation k·(v − u·L/q)
    for pc in out:
        c = pc.centroid()
        alpha = (c - Bo).dot(uh) - (s / h) * (c - Bo).dot(nh)
        k = min(q - 1, max(0, int(alpha // (L / q))))
        if k > 0:
            dx = k * (s - L / q); dz = k * h
            pc.translated(dx * uh.x + dz * nh.x, dx * uh.y + dz * nh.y)
    A1 = sum(pc.area() for pc in out)
    assert abs(A1 - A0) < 1e-7 * max(1.0, A0), "q_cut_and_stack : aire non conservée"
    newc = (Bo, _w(Bo, uh, nh, L / q, 0),
            _w(Bo, uh, nh, L / q + q * s, q * h), _w(Bo, uh, nh, q * s, q * h))
    return out, newc, {}


def p_cut_and_stack(pieces, corners, p, cut_step, stack_step):
    """Coupe le grand côté (longueur p, entier) en p tranches parallèles à la
    base et les empile : le côté devient exactement 1."""
    A0 = sum(pc.area() for pc in pieces)
    Bo, uh, nh, L, s, h = _frame(corners)        # ici |v| = p (entier)
    out = list(pieces)
    for k in range(1, p):
        nxt = []
        p0 = _w(Bo, uh, nh, k * s / p, k * h / p)
        for pc in out:
            nxt += cut_piece(pc, p0, uh, "p-cut", cut_step)
        out = nxt
    for pc in out:
        c = pc.centroid()
        beta = (c - Bo).dot(nh) / (h / p)        # niveau de tranche
        k = min(p - 1, max(0, int(beta)))
        if k > 0:
            dx = k * (L - s / p); dz = -k * h / p
            pc.translated(dx * uh.x + dz * nh.x, dx * uh.y + dz * nh.y)
    A1 = sum(pc.area() for pc in out)
    assert abs(A1 - A0) < 1e-7 * max(1.0, A0), "p_cut_and_stack : aire non conservée"
    newc = (Bo, _w(Bo, uh, nh, p * L, 0),
            _w(Bo, uh, nh, p * L + s / p, h / p), _w(Bo, uh, nh, s / p, h / p))
    return out, newc, {}


# ───────────────────────── redressement final ─────────────────────────
def par_to_rectangle(pieces, corners, step):
    """Parallélogramme (base b, côté de longueur EXACTE 1) → rectangle 1 × aire.
    Coupes ⊥ au côté unité + translations le long de ce côté (toutes solidaires).
    Renvoie (pieces, rect_corners, info) avec rect_corners[0]→[1] = côté de
    largeur 1 (orienté pour que la rotation finale pose le rectangle au-dessus)."""
    A0 = sum(pc.area() for pc in pieces)
    Bo, uh, nh, L, s, h = _frame(corners)        # v = côté unité : s²+h² = 1
    assert abs(math.hypot(s, h) - 1.0) < 1e-7, "par_to_rectangle : côté ≠ 1"
    wv = P(s * uh.x + h * nh.x, s * uh.y + h * nh.y)     # ŵ (unitaire)
    # n̂σ : ⊥ à ŵ, pointant vers l'intérieur de la bande (ξ(B+u·L) > 0)
    n1 = P(-wv.y, wv.x)
    bvec = P(L * uh.x, L * uh.y)
    sigma = 1.0 if bvec.dot(n1) > 0 else -1.0
    no = P(sigma * n1.x, sigma * n1.y)
    area = bvec.dot(no)                                   # = aire (>0)
    eta0 = bvec.dot(wv)                                   # décalage le long de ŵ
    assert eta0 >= -1e-9
    K = int(math.ceil(eta0 - 1e-9))
    out = list(pieces)
    for m in range(1, K + 1):
        nxt = []
        p0 = P(Bo.x + m * wv.x, Bo.y + m * wv.y)
        for pc in out:
            nxt += cut_piece(pc, p0, no, "par-rect", step)
        out = nxt
    for pc in out:
        c = pc.centroid()
        eta = (c - Bo).dot(wv)
        m = min(K, max(0, int(math.floor(eta + 1e-12))))
        if m > 0:
            pc.translated(-m * wv.x, -m * wv.y)
    A1 = sum(pc.area() for pc in out)
    assert abs(A1 - A0) < 1e-7 * max(1.0, A0), "par_to_rectangle : aire non conservée"
    # rectangle final : côté r0→r1 = largeur 1, orienté pour que la rotation
    # qui aligne r0→r1 sur +x pose le rectangle AU-DESSUS (cross(r1−r0,r3−r0)>0)
    if sigma > 0:
        r0 = Bo; r1 = P(Bo.x + wv.x, Bo.y + wv.y)
    else:
        r0 = P(Bo.x + wv.x, Bo.y + wv.y); r1 = Bo
    r2 = P(r1.x + area * no.x, r1.y + area * no.y)
    r3 = P(r0.x + area * no.x, r0.y + area * no.y)
    rect = [r0, r1, r2, r3]
    assert (r1 - r0).cross(r3 - r0) > 0
    # contrôle géométrique : toutes les pièces dans le rectangle (à ε près)
    for pc in out:
        for v in pc.verts:
            xi = (v - Bo).dot(no); et = (v - Bo).dot(wv)
            assert -1e-6 <= xi <= area + 1e-6 and -1e-6 <= et <= 1 + 1e-6, \
                "par_to_rectangle : pièce hors du rectangle"
    return out, rect, {"area": area}
