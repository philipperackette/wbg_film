#!/usr/bin/env bash
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV="${WBG_ENV:-wbgvideo}"
if ! command -v conda >/dev/null 2>&1; then echo "conda introuvable"; exit 1; fi
source "$(conda info --base)/etc/profile.d/conda.sh"
if conda env list | awk '{print $1}' | grep -qx "$ENV"; then
  conda install -y -n "$ENV" -c conda-forge shapely matplotlib numpy ffmpeg
else
  conda create -y -n "$ENV" -c conda-forge python=3.12 shapely matplotlib numpy ffmpeg
fi
conda activate "$ENV"
echo ">> wbg_core.py"
cat > wbg_core.py <<'WBG_CORE_EOF'
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
WBG_CORE_EOF

echo ">> wbg_pipeline.py"
cat > wbg_pipeline.py <<'WBG_PIPE_EOF'
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
WBG_PIPE_EOF

echo ">> wbg_animate.py"
cat > wbg_animate.py <<'WBG_ANIMATE_EOF'
#!/usr/bin/env python3
"""
wbg_animate.py — mise en MOUVEMENT du découpage de Wallace–Bolyai–Gerwien.

Idée : la géométrie (pièces communes situées dans A, dans le rectangle 1×6 et
dans B) est déjà calculée de façon exacte par wbg_pipeline. Chaque pièce y
apparaît sous trois poses CONGRUENTES (mêmes sommets, même ordre). Le passage
d'une pose à l'autre est donc une isométrie rigide (rotation + translation) que
l'on interpole continûment dans le temps :
    - translations « glissées »,
    - rotations degré par degré (vitesse angulaire contrôlée),
    - les pièces se séparent de A puis se réassemblent (la « découpe » se voit).

Tout est paramétrable via AnimParams (vitesses, temps de pause, fps, taille,
format de sortie…). Sortie MP4 (ffmpeg) et/ou GIF.

Usage rapide :
    python3 wbg_animate.py                 # MP4 + GIF avec les réglages par défaut
    python3 wbg_animate.py --check         # dump quelques images-clés (PNG) pour contrôle
"""
from __future__ import annotations
import math, sys, os
from dataclasses import dataclass

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MPLPoly
from matplotlib.animation import FuncAnimation, FFMpegWriter, PillowWriter

from wbg_core import P, poly_area
from wbg_pipeline import dissect_polygon, common_refinement, common_located

# ───────────────────────── identité visuelle (reprise des diapos) ─────────────────────────
PALETTE_A = ['#e9d39c','#e8bcae','#e0ac84','#f0d8c0','#d9b48e','#ecc9a4']  # A : chaud
PALETTE_B = ['#c2d3e6','#c4d8c2','#d2c6e0','#b6c4da','#bccdb0','#cbb8d6']  # B : froid
INK='#15151c'; PAPER='#fbf7ec'; ACCENT='#a8472a'; MUTED='#6e6857'

# polygones de la démo (aire 6 ; mêmes que les diapos)
_pi = math.pi
# Figures de ChatGPT : pentagone A (5 sommets) + hexagone B (6 sommets), de MÊME aire (≈ 5,966).
# B est l'homothétique de l'hexagone brut pour égaler exactement l'aire du pentagone A.
POLY_A = [P(0.00,0.00),P(2.60,-0.15),P(3.20,1.25),P(1.40,2.15),P(-0.55,1.35)]
_POLY_B_RAW = [P(0.00,0.00),P(2.00,-0.20),P(2.80,0.60),P(2.55,1.75),P(0.90,2.20),P(-0.60,1.10)]
_sB = (poly_area(POLY_A) / poly_area(_POLY_B_RAW)) ** 0.5
POLY_B = [P(p.x*_sB, p.y*_sB) for p in _POLY_B_RAW]


@dataclass
class AnimParams:
    # cadence et rendu
    fps: int = 30
    width_px: int = 1280
    height_px: int = 720
    dpi: int = 100
    # vitesses du mouvement
    trans_speed: float = 4.0      # unités par seconde (translations glissées)
    rot_speed:   float = 160.0    # degrés par seconde (rotations)
    min_move:    float = 0.35     # durée plancher d'un déplacement (s)
    # mise en scène
    stagger:     float = 0.05     # décalage de départ entre pièces successives (s)
    group_by_origin: bool = True  # faire partir ensemble les pièces d'un même triangle de A
    show_rect_phase: bool = True  # inclure l'étape rectangle 1×6 (sinon A -> B direct)
    gap: float = 1.7              # écart horizontal entre les « stations » A | rect | B
    # temps de pause (s)
    pause_start: float = 1.0
    pause_mid:   float = 0.9
    pause_end:   float = 1.6
    cut_dur:     float = 0.7      # durée du « flash » de coupe (scène méthode)
    read_scale:  float = 1.0      # facteur global sur les pauses de lecture (scène méthode)
    # sortie
    out_dir: str = "/mnt/user-data/outputs/anim_dissection"
    basename: str = "wbg_equidecoupage"
    make_mp4: bool = True
    make_gif: bool = True
    gif_fps: int = 18             # GIF allégé


# ───────────────────────── primitives géométriques (sur tuples (x,y)) ─────────────────────────
def _centroid(poly):
    n=len(poly); return (sum(p[0] for p in poly)/n, sum(p[1] for p in poly)/n)

def _rel_angle(p1, p2):
    """Rotation rigide (rad) alignant p1 sur p2 — Kabsch 2D, exacte si congruents."""
    c1=_centroid(p1); c2=_centroid(p2); num=0.0; den=0.0
    for (x1,y1),(x2,y2) in zip(p1,p2):
        ax_=x1-c1[0]; ay=y1-c1[1]; bx=x2-c2[0]; by=y2-c2[1]
        num += ax_*by - ay*bx
        den += ax_*bx + ay*by
    return math.atan2(num, den)

def _smooth(t):  # lissage accélération/décélération
    return t*t*(3-2*t)

def interp_pose(p1, p2, t):
    """Interpole rigidement p1 -> p2 ; à t=1 atterrit exactement sur p2."""
    if t<=0: return list(p1)
    if t>=1: return list(p2)
    c1=_centroid(p1); c2=_centroid(p2)
    ang=_rel_angle(p1,p2)*t; ca=math.cos(ang); sa=math.sin(ang)
    tx=c1[0]+t*(c2[0]-c1[0]); ty=c1[1]+t*(c2[1]-c1[1])
    out=[]
    for (x,y) in p1:
        dx=x-c1[0]; dy=y-c1[1]
        out.append((ca*dx-sa*dy+tx, sa*dx+ca*dy+ty))
    return out

def _bbox(points):
    xs=[p[0] for p in points]; ys=[p[1] for p in points]
    return min(xs),min(ys),max(xs),max(ys)


# ───────────────────────── construction de la scène ─────────────────────────
def build_scene(params: AnimParams):
    dA=dissect_polygon(POLY_A, PALETTE_A, "A", max_den=2)
    dB=dissect_polygon(POLY_B, PALETTE_B, "B", max_den=2)
    com=common_refinement(dA["column"], dB["column"], poly_area(POLY_A))
    loc=common_located(com, dA["column"], dB["column"])
    H=dA["colH"]   # hauteur du rectangle (6)

    # poses brutes (P -> tuples)
    rawA=[[(v.x,v.y) for v in c["inA"]]  for c in loc]
    rawR=[[(v.x,v.y) for v in c["rect"]] for c in loc]
    rawB=[[(v.x,v.y) for v in c["inB"]]  for c in loc]
    colors=[c["color"] for c in loc]          # couleur = triangle d'origine dans A
    origins=[c["ai"] for c in loc]

    # bboxes globales par station, pour centrer verticalement chaque forme
    def gbb(raws):
        pts=[p for poly in raws for p in poly]; return _bbox(pts)
    bA=gbb(rawA); bR=gbb(rawR); bB=gbb(rawB)
    wA=bA[2]-bA[0]; wB=bB[2]-bB[0]
    g=params.gap
    # positions horizontales des stations
    xA=0.0; xR=wA+g; xB=wA+g+(bR[2]-bR[0])+g
    def offset(raws, bb, X0):
        w=bb[2]-bb[0]; h=bb[3]-bb[1]
        ox=X0-bb[0]
        oy=H/2 - (bb[1]+h/2)            # centre vertical dans [0,H]
        return [[(x+ox, y+oy) for (x,y) in poly] for poly in raws]
    posA=offset(rawA,bA,xA); posR=offset(rawR,bR,xR); posB=offset(rawB,bB,xB)

    # ordre d'animation : par triangle d'origine puis de bas en haut
    idx=list(range(len(loc)))
    idx.sort(key=lambda i:(origins[i] if params.group_by_origin else 0,
                           _centroid(posA[i])[1], _centroid(posA[i])[0]))

    # durées de déplacement par pièce
    def dur(p1,p2):
        c1=_centroid(p1); c2=_centroid(p2)
        dist=math.hypot(c2[0]-c1[0], c2[1]-c1[1])
        ang=abs(math.degrees(_rel_angle(p1,p2)))
        return max(dist/params.trans_speed, ang/params.rot_speed, params.min_move)

    # planifie les départs (avec décalage) pour une phase
    def plan(src,dst):
        starts={}; durs={}
        for k,i in enumerate(idx):
            starts[i]=k*params.stagger
            durs[i]=dur(src[i],dst[i])
        length=max(starts[i]+durs[i] for i in idx)
        return starts,durs,length

    seq=[]   # liste de phases : (type, t0, length, payload)
    T=0.0
    seq.append(("hold", T, params.pause_start, "A"));            T+=params.pause_start
    if params.show_rect_phase:
        s,d,L=plan(posA,posR); seq.append(("move",T,L,(posA,posR,s,d,"Chaque pièce glisse et tourne : A → rectangle de largeur 1"))); T+=L
        seq.append(("hold",T,params.pause_mid,"rect"));          T+=params.pause_mid
        s,d,L=plan(posR,posB); seq.append(("move",T,L,(posR,posB,s,d,"Les mêmes pièces repartent : rectangle de largeur 1 → B"))); T+=L
    else:
        s,d,L=plan(posA,posB); seq.append(("move",T,L,(posA,posB,s,d,"Les mêmes pièces : A → B"))); T+=L
    seq.append(("hold",T,params.pause_end,"B"));                 T+=params.pause_end
    total=T

    # bornes du cadre
    allpts=[p for P_ in (posA,posR,posB) for poly in P_ for p in poly]
    bx=_bbox(allpts)
    frame={"xlim":(bx[0]-0.6, bx[2]+0.6), "ylim":(bx[1]-0.8, bx[3]+0.9),
           "xA":xA,"xR":xR,"xB":xB,"wA":wA,"wB":wB,"Rw":bR[2]-bR[0],"H":H}

    return dict(loc=loc, colors=colors, posA=posA, posR=posR, posB=posB,
                idx=idx, seq=seq, total=total, frame=frame, dA=dA, dB=dB, com=com)


def pose_and_label_at(scene, T):
    """Renvoie (liste de poses des 43 pièces à l'instant T, libellé de phase)."""
    posA=scene["posA"]; n=len(posA)
    cur=[None]*n; label="A"
    # localise la phase
    for (typ,t0,L,payload) in scene["seq"]:
        if T < t0+L or (typ,t0,L,payload) is scene["seq"][-1]:
            if typ=="hold":
                ref = {"A":scene["posA"],"rect":scene["posR"],"B":scene["posB"]}[payload]
                cur=[list(p) for p in ref]
                label={"A":f"Les {n} pièces communes, disposées comme dans A","rect":"Les mêmes pièces réunies en rectangle de largeur 1","B":"Les mêmes pièces réassemblées en B — CQFD"}[payload]
            else:
                src,dst,starts,durs,label=payload
                local=T-t0
                for i in range(n):
                    t=(local-starts[i])/durs[i]
                    t=0.0 if t<0 else (1.0 if t>1 else t)
                    cur[i]=interp_pose(src[i],dst[i],_smooth(t))
            return cur,label
    cur=[list(p) for p in scene["posB"]]
    return cur,"B"


# ───────────────────────── rendu ─────────────────────────
def _setup_fig(scene, params):
    fig=plt.figure(figsize=(params.width_px/params.dpi, params.height_px/params.dpi),
                   dpi=params.dpi)
    ax=fig.add_axes([0,0,1,1]); ax.set_aspect('equal'); ax.axis('off')
    fig.patch.set_facecolor(PAPER); ax.set_facecolor(PAPER)
    fr=scene["frame"]; ax.set_xlim(*fr["xlim"]); ax.set_ylim(*fr["ylim"])

    patches=[]
    for i in range(len(scene["posA"])):
        poly=MPLPoly(scene["posA"][i], closed=True, facecolor=scene["colors"][i],
                     edgecolor=INK, linewidth=0.5, joinstyle='round')
        ax.add_patch(poly); patches.append(poly)

    # titre + légende de phase + étiquettes des stations + règle
    fig.text(0.5,0.95,"Découpe, glissement, rotation : A et B, les mêmes pièces",
             ha='center',va='center',fontsize=16,color=INK,family='serif',weight='bold')
    phase=fig.text(0.5,0.895,"",ha='center',va='center',fontsize=12,color=MUTED,
                   family='serif',style='italic')
    fr=scene["frame"]; ybl=fr["ylim"][0]+0.25
    ax.text(fr["xA"]+fr["wA"]/2, ybl, "A", ha='center', va='top', fontsize=13,
            color=INK, family='serif', weight='bold')
    ax.text(fr["xR"]+fr["Rw"]/2, ybl, "rectangle de largeur 1", ha='center', va='top',
            fontsize=11, color=INK, family='serif', weight='bold')
    ax.text(fr["xB"]+fr["wB"]/2, ybl, "B", ha='center', va='top', fontsize=13,
            color=INK, family='serif', weight='bold')
    # règle 1 unité (bas-gauche)
    rx=fr["xlim"][0]+0.4; ry=fr["ylim"][0]+0.45
    ax.plot([rx,rx+1],[ry,ry],color=ACCENT,lw=1.6)
    ax.plot([rx,rx],[ry-0.08,ry+0.08],color=ACCENT,lw=1.6)
    ax.plot([rx+1,rx+1],[ry-0.08,ry+0.08],color=ACCENT,lw=1.6)
    ax.text(rx+0.5,ry-0.18,"1 unité",ha='center',va='top',fontsize=8,color=ACCENT,family='monospace')
    return fig,ax,patches,phase


def render(params: AnimParams):
    os.makedirs(params.out_dir, exist_ok=True)
    scene=build_scene(params)
    fig,ax,patches,phase=_setup_fig(scene,params)
    nframes=int(math.ceil(scene["total"]*params.fps))

    def update(f):
        T=f/params.fps
        poses,label=pose_and_label_at(scene,T)
        for i,poly in enumerate(patches):
            poly.set_xy(poses[i])
        phase.set_text(label)
        return patches+[phase]

    anim=FuncAnimation(fig,update,frames=nframes,interval=1000/params.fps,blit=False)
    outputs=[]
    if params.make_mp4:
        path=os.path.join(params.out_dir,f"{params.basename}.mp4")
        anim.save(path,writer=FFMpegWriter(fps=params.fps,bitrate=2600),dpi=params.dpi)
        outputs.append(path)
    if params.make_gif:
        path=os.path.join(params.out_dir,f"{params.basename}.gif")
        step=max(1,round(params.fps/params.gif_fps))
        anim.save(path,writer=PillowWriter(fps=params.gif_fps),dpi=max(60,params.dpi-30),
                  savefig_kwargs={})
        outputs.append(path)
    plt.close(fig)
    return outputs,scene


def dump_keyframes(params: AnimParams, fractions=(0.0,0.18,0.5,0.7,0.92)):
    """Rend quelques images-clés en PNG pour contrôle visuel rapide."""
    os.makedirs("/home/claude/preview",exist_ok=True)
    scene=build_scene(params)
    out=[]
    for fr in fractions:
        fig,ax,patches,phase=_setup_fig(scene,params)
        T=fr*scene["total"]
        poses,label=pose_and_label_at(scene,T)
        for i,poly in enumerate(patches): poly.set_xy(poses[i])
        phase.set_text(label)
        p=f"/home/claude/preview/anim_kf_{int(fr*100):03d}.png"
        fig.savefig(p,dpi=90,facecolor=PAPER); plt.close(fig); out.append(p)
    return out,scene


def _parse_cli(argv):
    import argparse
    p=argparse.ArgumentParser(description="Animation du découpage de Wallace–Bolyai–Gerwien (A → rectangle → B).")
    d=AnimParams()
    p.add_argument("--scene", choices=["reassembly","method","column","fusion","intro"], default="reassembly",
                   help="scène : 'reassembly' (A→rect→B), 'method' (triangle→rectangle), 'column' (empilement), 'fusion' (superposition des deux découpages)")
    p.add_argument("--check", action="store_true", help="ne rend que quelques images-clés PNG (contrôle rapide)")
    p.add_argument("--fps", type=int, default=d.fps)
    p.add_argument("--trans-speed", type=float, default=d.trans_speed, help="vitesse des translations (unités/s)")
    p.add_argument("--rot-speed", type=float, default=d.rot_speed, help="vitesse des rotations (degrés/s)")
    p.add_argument("--stagger", type=float, default=d.stagger, help="décalage de départ entre pièces (s)")
    p.add_argument("--gap", type=float, default=d.gap, help="écart entre les stations A | rect | B (unités)")
    p.add_argument("--pause-start", type=float, default=d.pause_start)
    p.add_argument("--pause-mid", type=float, default=d.pause_mid)
    p.add_argument("--pause-end", type=float, default=d.pause_end)
    p.add_argument("--read-scale", type=float, default=d.read_scale, help="facteur sur les pauses de lecture (scènes méthode/fusion)")
    p.add_argument("--width", type=int, default=d.width_px)
    p.add_argument("--height", type=int, default=d.height_px)
    p.add_argument("--no-rect", action="store_true", help="A -> B directement (sans l'étape rectangle)")
    p.add_argument("--no-group", action="store_true", help="ne pas regrouper par triangle d'origine")
    p.add_argument("--no-mp4", action="store_true")
    p.add_argument("--no-gif", action="store_true")
    p.add_argument("--basename", type=str, default=d.basename)
    p.add_argument("--out-dir", type=str, default=d.out_dir)
    a=p.parse_args(argv)
    return AnimParams(
        fps=a.fps, width_px=a.width, height_px=a.height,
        trans_speed=a.trans_speed, rot_speed=a.rot_speed, stagger=a.stagger, gap=a.gap,
        group_by_origin=not a.no_group, show_rect_phase=not a.no_rect,
        pause_start=a.pause_start, pause_mid=a.pause_mid, pause_end=a.pause_end,
        out_dir=a.out_dir, basename=a.basename,
        make_mp4=not a.no_mp4, make_gif=not a.no_gif, read_scale=a.read_scale,
    ), a.check, a.scene


# ════════════════════════ SCÈNE « MÉTHODE » : un triangle -> rectangle ════════════════════════
# Rejoue le JOURNAL d'événements (coupes + isométries) enregistré par le cœur.
from wbg_core import (make_rot180, par_basis, par_height, choose_simple_rational_side,
                      rationalize, q_cut_and_stack, p_cut_and_stack, par_to_rectangle,
                      rec_start, rec_stop, Piece)
from matplotlib.lines import Line2D

def _area_tup(verts):
    n=len(verts); s=0.0
    for i in range(n):
        x0,y0=verts[i]; x1,y1=verts[(i+1)%n]; s+=x0*y1-x1*y0
    return abs(s)/2

def _snap(state): return {pid:(list(v),c) for pid,(v,c) in state.items()}

def _rotate_pts(verts, ang, cx, cy):
    ca=math.cos(ang); sa=math.sin(ang)
    return [(cx+ca*(x-cx)-sa*(y-cy), cy+sa*(x-cx)+ca*(y-cy)) for (x,y) in verts]

def _interp_iso(before, after, iso, f):
    """Interpole une pièce de 'before' à 'after' selon l'isométrie enregistrée."""
    f=_smooth(max(0.0,min(1.0,f)))
    if iso[0]=='trans':
        return [(bx+f*(ax-bx), by+f*(ay-by)) for (bx,by),(ax,ay) in zip(before,after)]
    theta=iso[1]; cx=iso[2]; cy=iso[3]; ang=theta*f; ca=math.cos(ang); sa=math.sin(ang)
    out=[]
    for (bx,by) in before:
        dx=bx-cx; dy=by-cy
        out.append((cx+ca*dx-sa*dy, cy+sa*dx+ca*dy))
    return out

def _beat_dur(movers, params):
    d=params.min_move
    for (_pid,b,a,iso) in movers:
        cb=_centroid(b); ca=_centroid(a)
        dist=math.hypot(ca[0]-cb[0], ca[1]-cb[1])
        ang=abs(math.degrees(iso[1])) if iso[0]=='rot' else 0.0
        d=max(d, dist/params.trans_speed, ang/params.rot_speed)
    return d

def build_method(tri, color, max_den=2):
    """Construit triangle->parallélogramme (calculé) puis enregistre la suite de la chaîne."""
    pts=list(tri)
    edges=[]
    for i in range(3):
        b=pts[i]; c=pts[(i+1)%3]; a=pts[(i+2)%3]; edges.append((a,b,c,(c-b).norm()))
    edges.sort(key=lambda e:-e[3]); A,B,C,_=edges[0]
    M=(A+B)*0.5; N=(A+C)*0.5; D=2*N-M
    trap=Piece([M,B,C,N], color, 0, "trapèze")
    amn =Piece([A,M,N], color, 0, "demi-triangle")
    amnV_orig=[(v.x,v.y) for v in amn.verts]  # original [A,M,N] before rotation
    ndc =amn.apply(make_rot180(N))           # enregistreur OFF : pivot non enregistré
    corners=(B,C,D,M); pieces=[trap,ndc]
    _A,u,v=par_basis(corners); h,L=par_height(u,v)
    strict=abs(h-round(h))<1e-9
    p,q,val,txt=choose_simple_rational_side(h, max_den=max_den, strict=strict)
    rec_start(); step=2
    pieces,corners,_=rationalize(pieces,corners,val,step)
    if q>1: step+=1;cq=step;step+=1;sq=step; pieces,corners,_=q_cut_and_stack(pieces,corners,q,cq,sq)
    if p>1: step+=1;cp=step;step+=1;spp=step; pieces,corners,_=p_cut_and_stack(pieces,corners,p,cp,spp)
    step+=1; pieces,rect,_=par_to_rectangle(pieces,corners,step)
    ev=rec_stop()
    return dict(pts=[v.tup() for v in pts], color=color,
                trapV=[v.tup() for v in trap.verts], trap_pid=trap.pid,
                amnV=amnV_orig, ndcV=[v.tup() for v in ndc.verts], ndc_pid=ndc.pid,
                N=(N.x,N.y), MN=((M.x,M.y),(N.x,N.y)),
                rect_corners=[(c.x,c.y) for c in rect],
                rest=ev, p=p, q=q, h=h, val=val)

DIMCOL='#2f6d8c'   # couleur des cotes (longueurs)
CUTMARK='#5f5848'  # couleur stable des marques de découpe

def _fr(x): return f"{x:.2f}".replace('.',',')

def method_beats(md, params, detailed=True, label="", intro=None):
    color=md['color']; p=md['p']; q=md['q']; h=md['h']; frac=f"{p}/{q}"
    pts=md['pts']
    blen=max(math.hypot(pts[i][0]-pts[(i+1)%3][0], pts[i][1]-pts[(i+1)%3][1]) for i in range(3))
    rs=getattr(params,'read_scale',1.0)
    def H(x): return x*rs*(1.0 if detailed else 0.32)
    beats=[]
    if intro is not None:
        intro_title, intro_msg = intro
    elif detailed:
        intro_title="Un triangle quelconque"
        intro_msg=("On prend l'un des vrais triangles des figures — ici le plus « gras ».\n"
               "Sa plus longue arête sert de base. But : le transformer, par découpages, glissements\n"
               "et rotations (donc SANS déformation), en un rectangle de largeur exactement 1.")
    else:
        intro_title=(label if label else "Triangle suivant")
        intro_msg=((label+" : ") if label else "")+"même procédé, sans déformation."
    beats.append({'k':'show','state':{0:(pts,color)},
        'title':intro_title,'msg':intro_msg,
        'dims':[{'kind':'hdim','label':f"base ≈ {_fr(blen)}"}], 'hold':H(3.4 if detailed else 2.6)})
    beats.append({'k':'cut','state':{0:(pts,color)},'segs':[md['MN']],
        'title':"Découpe par la ligne des milieux",
        'msg':"On joint les milieux des deux autres côtés et on coupe.\nLe petit triangle du haut va pivoter d'un demi-tour.",
        'hold':H(2.6)})
    state={md['trap_pid']:(md['trapV'],color), md['ndc_pid']:(md['amnV'],color)}
    rot_iso=('rot',math.pi,md['N'][0],md['N'][1])
    _ndcV_landed=_interp_iso(md['amnV'], md['ndcV'], rot_iso, 1.0)  # true endpoint of the rotation
    beats.append({'k':'move','state':_snap(state),
        'movers':[(md['ndc_pid'], md['amnV'], md['ndcV'], rot_iso)],
        'title':"Demi-tour de 180° → parallélogramme",
        'msg':("Le demi-triangle pivote d'un demi-tour (180°).\n"
               f"On obtient un PARALLÉLOGRAMME de même aire, de hauteur h ≈ {_fr(h)}."),
        'dims':[{'kind':'vleft','label':f"h ≈ {_fr(h)}"}], 'hold':H(3.2)})
    state[md['ndc_pid']]=(_ndcV_landed, color)   # use actual landing position, no teleport
    ev=md['rest']; i=0; last='shear'
    cut_script={
        'shear':("Rationalisation : la coupe","Une coupe isole, à droite, le coin du parallélogramme qui dépasse."),
        'q-cut':(f"Découpe en q = {q} bandes",
                 f"Le dénominateur q = {q} donne le nombre de bandes : on coupe la base en {q} parts égales."),
        'p-cut':(f"Découpe en p = {p} bandes","On recoupe le grand côté pour le ramener à la longueur 1."),
        'par-rect':("Redressement : une tranche","On découpe une fine tranche du côté à redresser.")}
    move_script={
        'shear':(f"Le côté oblique devient {frac}",
                 f"On glisse le morceau de l'autre côté. Le côté oblique mesure maintenant exactement {frac}\n"
                 f"(une longueur RATIONNELLE) ; la hauteur h ≈ {_fr(h)} n'a pas bougé.", f"oblique = {frac}"),
        'q-cut':(f"Empilement → côté = {p}",
                 f"On empile les {q} bandes : le côté oblique passe de {frac} à {frac} × {q} = {p}.\n"
                 f"Il est maintenant ENTIER.", f"oblique = {p}"),
        'p-cut':("Empilement → côté = 1","On empile : le grand côté devient exactement 1.","côté = 1"),
        'par-rect':("…on la glisse","On glisse la tranche pour redresser le côté à angle droit.",None)}
    expl={
        'shear':("Pourquoi « rationaliser » le côté oblique ?",
                 f"Le côté oblique a une longueur irrationnelle. Pour finir avec une largeur EXACTE de 1,\n"
                 f"on l'amène à la fraction la plus simple ≥ h, soit p/q = {frac}. On ne touche pas à la hauteur\n"
                 f"h ≈ {_fr(h)} : on ne change que la longueur de ce côté, par un cisaillement (découpe + glissement)."),
        'q-cut':("Étape suivante : rendre ce côté ENTIER",
                 f"Le côté oblique vaut {frac}. Idée : couper la base en q = {q} bandes égales et les empiler.\n"
                 f"Le côté sera alors répété {q} fois : {frac} × {q} = {p}. Il deviendra un nombre ENTIER."),
        'par-rect':("Dernière étape : redresser en rectangle",
                 f"Le côté oblique mesure {p} (entier). En glissant de fines tranches, on redresse le dernier\n"
                 f"côté jusqu'à l'angle droit : on obtient enfin un rectangle de largeur exactement 1.")}
    explained=set()
    def _cen(vv):
        k=len(vv); return (sum(x for x,_ in vv)/k, sum(y for _,y in vv)/k)
    while i<len(ev):
        # ── REDRESSEMENT parallélogramme(côté 1) → rectangle : UN seul mouvement solidaire ──
        if ev[i]['t']=='cut' and ev[i].get('kind')=='par-rect':
            if detailed and 'par-rect' not in explained:
                explained.add('par-rect'); et,em=expl['par-rect']
                beats.append({'k':'show','state':_snap(state),'title':et,'msg':em,'dims':[],'hold':H(5.0)})
            S_before=_snap(state); disp={pid:(0.0,0.0) for pid in state}; cutsegs=[]
            while i<len(ev) and ((ev[i]['t']=='cut' and ev[i].get('kind')=='par-rect') or ev[i]['t']=='move'):
                e=ev[i]; i+=1
                if e['t']=='cut':
                    par=e['parent']; pd=disp.get(par,(0.0,0.0)); seg=e.get('segment')
                    if seg: cutsegs.append(((seg[0][0]-pd[0],seg[0][1]-pd[1]),(seg[1][0]-pd[0],seg[1][1]-pd[1])))
                    state.pop(par,None); disp.pop(par,None)
                    for (cid,cv,cc) in e['children']: state[cid]=(cv,cc); disp[cid]=pd
                else:
                    idd=e['id']; bf=e['before']; af=e['after']
                    dx=_cen(af)[0]-_cen(bf)[0]; dy=_cen(af)[1]-_cen(bf)[1]
                    col=state.get(idd,(None,None))[1]; state[idd]=(af,col)
                    pdv=disp.get(idd,(0.0,0.0)); disp[idd]=(pdv[0]+dx,pdv[1]+dy)
            beats.append({'k':'cut','state':S_before,'segs':cutsegs,
                'title':"Redressement : une seule découpe",
                'msg':"Une découpe sépare le morceau qui dépasse du rectangle de largeur 1.",'hold':H(2.6)})
            mv=[]; stt={}
            for pid,(fv,col) in state.items():
                d=disp.get(pid,(0.0,0.0)); sv=[(x-d[0],y-d[1]) for (x,y) in fv]
                stt[pid]=(sv,col); mv.append((pid,sv,fv,('trans',d[0],d[1])))
            beats.append({'k':'move','state':stt,'movers':mv,
                'title':"…les morceaux glissent ensemble",
                'msg':"Les deux morceaux glissent solidairement, d'un seul mouvement :\nle parallélogramme devient un rectangle de largeur exactement 1.",
                'labels':[],'hold':H(3.6),'slowmo':1.5})
            last='par-rect'; continue
        if ev[i]['t']=='cut':
            grp=[]
            while i<len(ev) and ev[i]['t']=='cut' and ev[i].get('kind')!='par-rect': grp.append(ev[i]); i+=1
            if not grp: grp=[ev[i]]; i+=1
            last=grp[0]['kind']
            if detailed and last in expl and last not in explained:
                explained.add(last); et,em=expl[last]
                dims=[{'kind':'vleft','label':f"h ≈ {_fr(h)}"}] if last=='shear' else []
                beats.append({'k':'show','state':_snap(state),'title':et,'msg':em,'dims':dims,'hold':H(5.2)})
            t,m=cut_script.get(last,("Découpe",""))
            chold={'shear':2.6,'q-cut':2.2,'p-cut':2.0}.get(last,2.0)
            cut_beat={'k':'cut','state':_snap(state),
                'segs':[g.get('segment') for g in grp if g.get('segment')],
                'title':t,'msg':m,'hold':H(chold)}
            if last=='shear':
                cut_beat['frac_label']=frac   # affiche p/q sur le segment de coupe
            beats.append(cut_beat)
            for ce in grp:
                state.pop(ce['parent'],None)
                for (cid,cv,cc) in ce['children']: state[cid]=(cv,cc)
        else:
            grp=[]
            while i<len(ev) and ev[i]['t']=='move': grp.append(ev[i]); i+=1
            movers=[(me['id'], me['before'], me['after'], me['iso']) for me in grp]
            t,m,lbl=move_script.get(last,("Translation","",None))
            labels=[{'anchor':'right','text':lbl}] if lbl else []
            mhold={'shear':4.2,'q-cut':3.6,'p-cut':2.6}.get(last,2.6)
            slow=({'shear':2.2}.get(last,1.0) if detailed else 1.0)
            beats.append({'k':'move','state':_snap(state),'movers':movers,
                'title':t,'msg':m,'labels':labels,'hold':H(mhold),'slowmo':slow})
            for me in grp:
                col=state.get(me['id'],(None,me['color']))[1]; state[me['id']]=(me['after'],col)
    rA=md['rect_corners'][0]; rB=md['rect_corners'][1]
    ang=-math.atan2(rB[1]-rA[1], rB[0]-rA[0])
    if abs(ang)>1e-4:
        movers=[(pid, v, _rotate_pts(v,ang,rA[0],rA[1]), ('rot',ang,rA[0],rA[1])) for pid,(v,c) in state.items()]
        beats.append({'k':'move','state':_snap(state),'movers':movers,
            'title':"On oriente le rectangle","msg":"On tourne le rectangle pour le poser bien droit.",'hold':H(2.2)})
        for pid,(v,c) in list(state.items()): state[pid]=(_rotate_pts(v,ang,rA[0],rA[1]), c)
    area=sum(_area_tup(v) for _,(v,_) in state.items())
    beats.append({'k':'show','state':_snap(state),
        'title':"Rectangle de largeur 1",
        'msg':(f"Largeur exactement 1, hauteur = aire ≈ {_fr(area)}.\n"
               "Chaque triangle subit ce procédé ; les rectangles obtenus s'empilent\n"
               "ensuite en une seule colonne de largeur 1."),
        'dims':[{'kind':'hdim','label':"largeur = 1"},{'kind':'vright','label':f"≈ {_fr(area)}"}],
        'hold':H(4.6)})
    return beats

def _setup_fig_simple(bbox, params, title, mx=0.6, my_top=1.4, my_bot=0.9, show_ruler=False):
    fig=plt.figure(figsize=(params.width_px/params.dpi, params.height_px/params.dpi), dpi=params.dpi)
    ax=fig.add_axes([0,0,1,1]); ax.set_aspect('equal'); ax.axis('off')
    fig.patch.set_facecolor(PAPER); ax.set_facecolor(PAPER)
    x0,y0,x1,y1=bbox
    ax.set_xlim(x0-mx, x1+mx); ax.set_ylim(y0-my_bot, y1+my_top)
    fig.text(0.5,0.965,title,ha='center',va='center',fontsize=16,color=INK,family='serif',weight='bold')
    phase=fig.text(0.5,0.918,"",ha='center',va='center',fontsize=13,color=ACCENT,family='serif',style='italic')
    if show_ruler:
        rx=x0-mx+0.3; ry=y0-my_bot+0.5
        ax.plot([rx,rx+1],[ry,ry],color=MUTED,lw=1.4)
        ax.plot([rx,rx],[ry-0.07,ry+0.07],color=MUTED,lw=1.4); ax.plot([rx+1,rx+1],[ry-0.07,ry+0.07],color=MUTED,lw=1.4)
        ax.text(rx+0.5,ry+0.13,"1 unité",ha='center',va='bottom',fontsize=8,color=MUTED,family='monospace')
    return fig,ax,phase

def _draw_state(ax, patches, pieces):
    for p in patches: p.remove()
    patches.clear()
    for pid,(verts,color) in pieces.items():
        poly=MPLPoly(verts, closed=True, facecolor=color, edgecolor=INK, linewidth=0.8, joinstyle='round')
        ax.add_patch(poly); patches.append(poly)

def _draw_annot(ax, store, beat, pieces, show):
    for a in store: a.remove()
    store.clear()
    if not show or not pieces: return
    pts=[v for _,(vv,_) in pieces.items() for v in vv]
    if not pts: return
    x0,y0,x1,y1=_bbox(pts); d=0.30; tk=0.08
    def line(xs,ys): store.append(ax.plot(xs,ys,color=DIMCOL,lw=1.3)[0])
    for dim in beat.get('dims',[]):
        k=dim['kind']; lab=dim['label']
        if k=='hdim':
            yb=y0-d; line([x0,x1],[yb,yb]); line([x0,x0],[yb-tk,yb+tk]); line([x1,x1],[yb-tk,yb+tk])
            store.append(ax.text((x0+x1)/2, yb-0.12, lab, ha='center', va='top', fontsize=11.5, color=DIMCOL, family='serif'))
        elif k=='vleft':
            xb=x0-d; line([xb,xb],[y0,y1]); line([xb-tk,xb+tk],[y0,y0]); line([xb-tk,xb+tk],[y1,y1])
            store.append(ax.text(xb-0.12, (y0+y1)/2, lab, ha='right', va='center', fontsize=11.5, color=DIMCOL, family='serif'))
        elif k=='vright':
            xb=x1+d; line([xb,xb],[y0,y1]); line([xb-tk,xb+tk],[y0,y0]); line([xb-tk,xb+tk],[y1,y1])
            store.append(ax.text(xb+0.12, (y0+y1)/2, lab, ha='left', va='center', fontsize=11.5, color=DIMCOL, family='serif'))
    for lb in beat.get('labels',[]):
        anch=lb.get('anchor','right'); txt=lb['text']
        if not txt: continue
        if anch=='right':
            store.append(ax.text(x1+0.30, (y0+y1)/2, txt, ha='left', va='center', fontsize=12, color=DIMCOL, family='serif', weight='600'))
        else:
            store.append(ax.text((x0+x1)/2, y1+0.25, txt, ha='center', va='bottom', fontsize=12, color=DIMCOL, family='serif', weight='600'))

def _method_draw(ax, patches, annot, msg_a, phase_a, flash, beat, pieces, in_hold, flashinfo):
    _draw_state(ax, patches, pieces)
    if flash is not None:
        if flashinfo:
            segs,f=flashinfo; alpha=math.sin(max(0,min(1,f))*math.pi); X=[];Y=[]
            for sgt in segs:
                if not sgt: continue
                (a0,b0),(a1,b1)=sgt; X+=[a0,a1,float('nan')]; Y+=[b0,b1,float('nan')]
            flash.set_data(X,Y); flash.set_alpha(0.9*alpha)
        else: flash.set_alpha(0.0)
    # fraction label on the cut segment, visible during the entire hold phase
    flab=beat.get('frac_label')
    if flab and in_hold:
        segs=beat.get('segs') or []
        for sgt in segs:
            if not sgt: continue
            (a0,b0),(a1,b1)=sgt
            # draw a persistent cut line + label
            annot.append(ax.plot([a0,a1],[b0,b1],color=ACCENT,lw=1.8,alpha=0.7)[0])
            annot.append(ax.text((a0+a1)/2+0.20, (b0+b1)/2, flab,
                                  ha='left', va='center', fontsize=14,
                                  color=ACCENT, family='serif', weight='bold'))
            break
    phase_a.set_text(beat.get('title','')); msg_a.set_text(beat.get('msg',''))
    _draw_annot(ax, annot, beat, pieces, in_hold)

def _method_timeline(beats, params):
    for b in beats:
        if b['k']=='move': b['motion']=_beat_dur(b['movers'], params)*b.get('slowmo',1.0)
        elif b['k']=='cut': b['motion']=params.cut_dur
        else: b['motion']=0.0
        b['dur']=b['motion']+b.get('hold',0.0)
    t=0.0
    for b in beats: b['t0']=t; b['t1']=t+b['dur']; t+=b['dur']
    return t

def _method_state_at(beats, color, T):
    for b in beats:
        if T<b['t1'] or b is beats[-1]:
            local=T-b['t0']; motion=b['motion']; in_hold=local>=motion-1e-9
            if b['k']=='show': return _snap(b['state']), b, True, None
            if b['k']=='cut':
                f=min(1.0,max(0.0,local/max(motion,1e-6)))
                return _snap(b['state']), b, in_hold, (b.get('segs') or [], f)
            f=min(1.0,max(0.0,local/max(motion,1e-6)))
            cur=_snap(b['state'])
            for (pid,bf,af,iso) in b['movers']:
                cur[pid]=(_interp_iso(bf,af,iso,f), cur.get(pid,(None,color))[1])
            return cur, b, in_hold, None
    return _snap(beats[-1]['state']), beats[-1], True, None

def _method_bbox(beats):
    pts=[]
    for b in beats:
        for pid,(v,c) in b['state'].items(): pts+=v
        for (pid,bf,af,iso) in b.get('movers',[]): pts+=bf; pts+=af
    return _bbox(pts)

def _reorient_horizontal(tri):
    """Tourne (isométrie) un triangle pour mettre sa plus longue arête à l'horizontale,
    3e sommet au-dessus. Sert à présenter proprement un VRAI triangle de A."""
    pts=list(tri)
    best=max(range(3), key=lambda i:(pts[i].x-pts[(i+1)%3].x)**2+(pts[i].y-pts[(i+1)%3].y)**2)
    a=pts[best]; b=pts[(best+1)%3]
    ang=-math.atan2(b.y-a.y, b.x-a.x); ca=math.cos(ang); sa=math.sin(ang)
    q=[P(ca*(p.x-a.x)-sa*(p.y-a.y), sa*(p.x-a.x)+ca*(p.y-a.y)) for p in pts]
    third=[p for i,p in enumerate(q) if i not in (best,(best+1)%3)][0]
    if third.y<0: q=[P(pp.x,-pp.y) for pp in q]
    return q

def _minang_tri(t):
    a=[]
    for i in range(3):
        u=t[i]; v=t[(i-1)%3]; w=t[(i+1)%3]
        den=math.hypot(v.x-u.x,v.y-u.y)*math.hypot(w.x-u.x,w.y-u.y) or 1.0
        d=((v.x-u.x)*(w.x-u.x)+(v.y-u.y)*(w.y-u.y))/den
        a.append(math.acos(max(-1,min(1,d))))
    return min(a)

def _vignette_for(o):
    """Construit le dict fig_vignette pour render_method à partir d'un entrée de _all_method_tris."""
    from wbg_core import ear_clip
    tag=o['tag']; idx=o['idx']
    poly=POLY_A if tag=='A' else POLY_B
    pal=PALETTE_A if tag=='A' else PALETTE_B
    tris_raw=[list(t) for t in ear_clip(list(poly))]
    poly_xy=[(p.x,p.y) for p in poly]
    tris_xy=[[(p.x,p.y) for p in t] for t in tris_raw]
    return dict(poly=poly_xy, tris=tris_xy, active_idx=idx, palette=pal)


def _all_method_tris():
    """Tous les triangles de A puis de B, orientés base horizontale. Le plus « gras » (détaillé) d'abord."""
    from wbg_core import ear_clip
    raw=[]
    for poly,pal,tag in [(POLY_A,PALETTE_A,'A'),(POLY_B,PALETTE_B,'B')]:
        tris=[list(t) for t in ear_clip(list(poly))]
        for i,t in enumerate(tris):
            raw.append(dict(tri=_reorient_horizontal(t), color=pal[i%len(pal)],
                            tag=tag, idx=i, ntag=len(tris), ang=_minang_tri(t)))
    fat=max(range(len(raw)), key=lambda k:raw[k]['ang'])
    ordered=[raw[fat]]+[o for k,o in enumerate(raw) if k!=fat]
    for k,o in enumerate(ordered): o['detailed']=(k==0)
    return ordered

def _method_default_tri():
    # VRAI triangle de A : le plus « gras » (angle minimal maximal) = le toit isocèle de la maison.
    # Rationalisation propre (pas de sliver), q = 2 et peu de redressements. On l'oriente base horizontale.
    from wbg_core import ear_clip
    tris=[list(t) for t in ear_clip(list(POLY_A))]
    def _minang(t):
        a=[]
        for i in range(3):
            u=t[i]; v=t[(i-1)%3]; w=t[(i+1)%3]
            den=math.hypot(v.x-u.x,v.y-u.y)*math.hypot(w.x-u.x,w.y-u.y)
            d=((v.x-u.x)*(w.x-u.x)+(v.y-u.y)*(w.y-u.y))/den
            a.append(math.acos(max(-1,min(1,d))))
        return min(a)
    return _reorient_horizontal(max(tris, key=_minang))

def render_method(params, tri=None, color=None, detailed=True, suffix="", label="",
                  max_den=2, intro=None, fig_vignette=None):
    """fig_vignette : dict(poly=[(x,y)…], tris=[[(x,y)…]…], active_idx=int, palette=[str…])
    Si fourni, dessine une petite vignette en haut à droite de la figure source avec
    le triangle actif mis en valeur."""
    os.makedirs(params.out_dir, exist_ok=True)
    if tri is None: tri=_method_default_tri()
    md=build_method(tri, color or PALETTE_A[0], max_den=max_den)
    beats=method_beats(md, params, detailed=detailed, label=label, intro=intro); total=_method_timeline(beats, params)
    fig,ax,phase=_setup_fig_simple(_method_bbox(beats), params,
        "Comment un triangle devient un rectangle de largeur 1", mx=1.2, my_top=1.5, my_bot=1.9)
    msg=fig.text(0.5,0.075,"",ha='center',va='center',fontsize=13.0,color=INK,family='serif',
                 linespacing=1.5, bbox=dict(boxstyle='round,pad=0.6', fc='#fbf7ec', ec='#ddd6c4', alpha=0.92))
    patches=[]; annot=[]; flash=Line2D([],[],color=ACCENT,lw=2.6,alpha=0.0,solid_capstyle='round'); ax.add_line(flash)
    # ── vignette : figure source avec triangle actif mis en valeur ──
    if fig_vignette is not None:
        fv=fig_vignette; vx=fv['poly']; vtris=fv['tris']
        aidx=fv['active_idx']; vpal=fv['palette']
        # inset axes en haut à droite (coordonnées de data de l'axe principal)
        bb=_method_bbox(beats); x0v,y0v,x1v,y1v=bb
        bw=fig.get_figwidth()*fig.dpi; bh=fig.get_figheight()*fig.dpi
        # position en fraction de figure
        from mpl_toolkits.axes_grid1.inset_locator import inset_axes
        # Compute inset position in figure coordinates
        ax_pos=ax.get_position()
        # Place inset at top-right corner of the main axes
        ins=fig.add_axes([ax_pos.x1-0.25, ax_pos.y1-0.28, 0.24, 0.27],
                         facecolor='#f5f0e8')
        ins.set_aspect('equal'); ins.axis('off')
        # draw source polygon outline
        vxs=[x for x,y in vx]+[vx[0][0]]; vys=[y for x,y in vx]+[vx[0][1]]
        ins.fill(vxs,vys,color='#EEE8D8',edgecolor=INK,linewidth=1.2)
        # draw triangles, active one bright, others dim
        for k,vt in enumerate(vtris):
            txs=[x for x,y in vt]; tys=[y for x,y in vt]
            if k==aidx:
                ins.fill(txs,tys,color=vpal[k%len(vpal)],alpha=1.0,edgecolor=INK,linewidth=1.4)
            else:
                ins.fill(txs,tys,color=vpal[k%len(vpal)],alpha=0.25,edgecolor='#9A9384',linewidth=0.8)
        ins.autoscale_view(); ins.set_title(label or "", fontsize=7, color=INK, pad=2, family='serif')
        ins.patch.set_edgecolor('#C8C0AE'); ins.patch.set_linewidth(1.0)
    nframes=int(math.ceil(total*params.fps))
    def update(fr):
        pieces,beat,in_hold,flashinfo=_method_state_at(beats, md['color'], fr/params.fps)
        _method_draw(ax, patches, annot, msg, phase, flash, beat, pieces, in_hold, flashinfo)
        return patches+annot+[flash,phase,msg]
    anim=FuncAnimation(fig,update,frames=nframes,interval=1000/params.fps,blit=False)
    outs=[]
    if params.make_mp4:
        path=os.path.join(params.out_dir,f"{params.basename}_methode{suffix}.mp4")
        anim.save(path,writer=FFMpegWriter(fps=params.fps,bitrate=2600),dpi=params.dpi); outs.append(path)
    if params.make_gif:
        path=os.path.join(params.out_dir,f"{params.basename}_methode{suffix}.gif")
        anim.save(path,writer=PillowWriter(fps=params.gif_fps),dpi=max(60,params.dpi-30)); outs.append(path)
    plt.close(fig)
    return outs,total,beats

def dump_method_keyframes(params, fractions=(0.04,0.16,0.30,0.46,0.62,0.78,0.93,0.99), tri=None):
    os.makedirs("/home/claude/preview",exist_ok=True)
    if tri is None: tri=_method_default_tri()
    md=build_method(tri, PALETTE_A[0], max_den=2)
    beats=method_beats(md, params); total=_method_timeline(beats, params)
    bb=_method_bbox(beats); out=[]
    for fr in fractions:
        fig,ax,phase=_setup_fig_simple(bb, params,
            "Comment un triangle devient un rectangle de largeur 1", mx=1.2, my_top=1.5, my_bot=1.9)
        msg=fig.text(0.5,0.075,"",ha='center',va='center',fontsize=13.0,color=INK,family='serif',
                     linespacing=1.5, bbox=dict(boxstyle='round,pad=0.6', fc='#fbf7ec', ec='#ddd6c4', alpha=0.92))
        patches=[]; annot=[]; flash=Line2D([],[],color=ACCENT,lw=2.6,alpha=0.0); ax.add_line(flash)
        pieces,beat,in_hold,flashinfo=_method_state_at(beats, md['color'], fr*total)
        _method_draw(ax, patches, annot, msg, phase, flash, beat, pieces, in_hold, flashinfo)
        pth=f"/home/claude/preview/method_kf_{int(fr*100):03d}.png"
        fig.savefig(pth,dpi=90,facecolor=PAPER); plt.close(fig); out.append(pth)
    return out,total,beats


# ════════════════════════ SCÈNE « COLONNE » : empiler les rectangles ════════════════════════
def build_column_scene(params, poly=None, palette=None):
    from wbg_pipeline import dissect_polygon
    if poly is None: poly=POLY_A
    if palette is None: palette=PALETTE_A
    d=dissect_polygon(poly, palette, "A", max_den=2)
    column=d['column']; rows=d['rect_rows']; n=len(rows)
    groups=[]; cutsegs=[]; H=[]; ycol=[]
    for (y,hh,i) in rows:
        pcs=[pc for pc in column if pc.origin==i]
        groups.append([([(p.x,p.y) for p in pc.verts], pc.color) for pc in pcs])
        outline=[((0,y),(1,y)),((1,y),(1,y+hh)),((1,y+hh),(0,y+hh)),((0,y+hh),(0,y))]
        cutsegs.append(_piece_segments(pcs)+outline)
        H.append(hh); ycol.append(y)
    gap=0.55; x=0.0; tray_dx=[]
    for i in range(n):
        tray_dx.append((x, -ycol[i])); x+=1.0+gap
    tray_w=x-gap; colx=tray_w+1.8
    col_dx=[(colx,0.0) for _ in range(n)]
    return dict(n=n, H=H, groups=groups, cutsegs=cutsegs, tray_dx=tray_dx, col_dx=col_dx,
                colx=colx, tray_w=tray_w, total_h=sum(H))

def render_column(params, poly=None, palette=None,
                  scene_title="Empiler les rectangles unité → la colonne 1 × aire",
                  suffix=""):
    os.makedirs(params.out_dir, exist_ok=True)
    sc=build_column_scene(params, poly, palette); n=sc['n']
    durs=[]
    for i in range(n):
        dx0,dy0=sc['tray_dx'][i]; dx1,dy1=sc['col_dx'][i]
        durs.append(max(math.hypot(dx1-dx0,dy1-dy0)/params.trans_speed, params.min_move))
    starts=[i*max(params.stagger,0.18) for i in range(n)]
    move_len=max(starts[i]+durs[i] for i in range(n))
    T0=params.pause_start; T1=T0+move_len; total=T1+params.pause_end
    allpts=[]
    for i in range(n):
        for (verts,col) in sc['groups'][i]:
            for (x,y) in verts:
                allpts.append((x+sc['tray_dx'][i][0], y+sc['tray_dx'][i][1]))
                allpts.append((x+sc['col_dx'][i][0], y+sc['col_dx'][i][1]))
    bb=_bbox(allpts)
    fig,ax,phase=_setup_fig_simple(bb, params, scene_title)
    ax.text(sc['colx']+0.5, sc['total_h']+0.3, "colonne de largeur 1",
            ha='center', va='bottom', fontsize=11, color=INK, family='serif', weight='bold')
    fills=[]
    for i in range(n):
        for (verts,col) in sc['groups'][i]:
            pp=MPLPoly(verts, closed=True, facecolor=col, edgecolor='none', alpha=0.92); ax.add_patch(pp); fills.append(pp)
    lc=LineCollection([], colors=CUTMARK, linewidths=0.9); ax.add_collection(lc)
    def trans_at(T):
        if T<T0: return [sc['tray_dx'][i] for i in range(n)]
        if T>=T1: return [sc['col_dx'][i] for i in range(n)]
        t=T-T0; out=[]
        for i in range(n):
            f=(t-starts[i])/durs[i]; f=0 if f<0 else (1 if f>1 else f); f=_smooth(f)
            out.append((sc['tray_dx'][i][0]+f*(sc['col_dx'][i][0]-sc['tray_dx'][i][0]),
                        sc['tray_dx'][i][1]+f*(sc['col_dx'][i][1]-sc['tray_dx'][i][1])))
        return out
    def label_at(T):
        if T<T0: return "Chaque triangle est devenu un rectangle de largeur 1 — coupes comprises"
        if T>=T1: return "Colonne de largeur 1 : les marques de découpe restent visibles"
        return "On empile les rectangles ; les marques de découpe sont conservées"
    nframes=int(math.ceil(total*params.fps))
    def update(fr):
        T=fr/params.fps; tr=trans_at(T); k=0; allseg=[]
        for i in range(n):
            dx,dy=tr[i]
            for (verts,col) in sc['groups'][i]:
                fills[k].set_xy([(x+dx,y+dy) for (x,y) in verts]); k+=1
            allseg+=[(((x0+dx),(y0+dy)),((x1+dx),(y1+dy))) for ((x0,y0),(x1,y1)) in sc['cutsegs'][i]]
        lc.set_segments(allseg); phase.set_text(label_at(T))
        return fills+[lc,phase]
    anim=FuncAnimation(fig,update,frames=nframes,interval=1000/params.fps,blit=False)
    outs=[]
    if params.make_mp4:
        path=os.path.join(params.out_dir,f"{params.basename}_colonne{suffix}.mp4")
        anim.save(path,writer=FFMpegWriter(fps=params.fps,bitrate=2600),dpi=params.dpi); outs.append(path)
    if params.make_gif:
        path=os.path.join(params.out_dir,f"{params.basename}_colonne{suffix}.gif")
        anim.save(path,writer=PillowWriter(fps=params.gif_fps),dpi=max(60,params.dpi-30)); outs.append(path)
    plt.close(fig); return outs,total

def dump_column_keyframes(params, fractions=(0.0,0.3,0.55,0.8,1.0)):
    os.makedirs("/home/claude/preview",exist_ok=True)
    sc=build_column_scene(params); n=sc['n']
    durs=[]
    for i in range(n):
        dx0,dy0=sc['tray_dx'][i]; dx1,dy1=sc['col_dx'][i]
        durs.append(max(math.hypot(dx1-dx0,dy1-dy0)/params.trans_speed, params.min_move))
    starts=[i*max(params.stagger,0.18) for i in range(n)]
    move_len=max(starts[i]+durs[i] for i in range(n))
    T0=params.pause_start; T1=T0+move_len; total=T1+params.pause_end
    allpts=[]
    for i in range(n):
        for (verts,col) in sc['groups'][i]:
            for (x,y) in verts:
                allpts.append((x+sc['tray_dx'][i][0], y+sc['tray_dx'][i][1]))
                allpts.append((x+sc['col_dx'][i][0], y+sc['col_dx'][i][1]))
    bb=_bbox(allpts); out=[]
    for fr in fractions:
        fig,ax,phase=_setup_fig_simple(bb, params, "Empiler les rectangles unité → la colonne 1 × aire")
        T=fr*total
        if T<T0: tr=[sc['tray_dx'][i] for i in range(n)]
        elif T>=T1: tr=[sc['col_dx'][i] for i in range(n)]
        else:
            t=T-T0; tr=[]
            for i in range(n):
                f=(t-starts[i])/durs[i]; f=0 if f<0 else (1 if f>1 else f); f=_smooth(f)
                tr.append((sc['tray_dx'][i][0]+f*(sc['col_dx'][i][0]-sc['tray_dx'][i][0]),
                           sc['tray_dx'][i][1]+f*(sc['col_dx'][i][1]-sc['tray_dx'][i][1])))
        allseg=[]
        for i in range(n):
            dx,dy=tr[i]
            for (verts,col) in sc['groups'][i]:
                ax.add_patch(MPLPoly([(x+dx,y+dy) for (x,y) in verts], closed=True, facecolor=col, edgecolor='none', alpha=0.92))
            allseg+=[(((x0+dx),(y0+dy)),((x1+dx),(y1+dy))) for ((x0,y0),(x1,y1)) in sc['cutsegs'][i]]
        ax.add_collection(LineCollection(allseg, colors=CUTMARK, linewidths=0.9))
        phase.set_text("empilement")
        pth=f"/home/claude/preview/col_kf_{int(fr*100):03d}.png"; fig.savefig(pth,dpi=90,facecolor=PAPER); plt.close(fig); out.append(pth)
    return out,total



# ════════════════════════ SCÈNE « FUSION » : superposer les deux découpages ════════════════════════
ACUT='#c0562a'; BCUT='#2f6d8c'; SYM='#4a463f'
from matplotlib.collections import LineCollection

def _piece_segments(pieces):
    segs=[]
    for pc in pieces:
        v=pc.verts; n=len(v)
        for i in range(n):
            a=v[i]; b=v[(i+1)%n]; segs.append(((a.x,a.y),(b.x,b.y)))
    return segs

def build_fusion_scene(params):
    dA=dissect_polygon(POLY_A, PALETTE_A, "A", max_den=2)
    dB=dissect_polygon(POLY_B, PALETTE_B, "B", max_den=2)
    H=dA['colH']
    com_raw=common_refinement(dA['column'], dB['column'], poly_area(POLY_A))
    com_loc=common_located(com_raw, dA['column'], dB['column'])
    com=[([(v.x,v.y) for v in c['rect']], c['color']) for c in com_loc]
    return dict(H=H, A_segs=_piece_segments(dA['column']), B_segs=_piece_segments(dB['column']),
                com=com, nA=len(dA['column']), nB=len(dB['column']), ncom=len(com_loc))

def _fusion_phases(sc, params):
    rs=getattr(params,'read_scale',1.0)
    P=[('apart',3.6*rs),('slide',2.4),('grid',3.8*rs),('fade',1.6),('hold',4.4*rs)]
    ts=[]; t=0.0
    for nm,du in P: ts.append((nm,t,du)); t+=du
    return ts,t

_FUS_TXT={
 'apart':("Deux découpages du même rectangle",
          "À gauche : le rectangle de largeur 1, découpé selon A (traits orange).\n"
          "À droite : LE MÊME rectangle, découpé selon B (traits bleus)."),
 'slide':("On les superpose",
          "Les deux rectangles sont identiques : largeur 1, même hauteur.\nOn les fait coïncider."),
 'grid':("Réunion des deux jeux de coupes",
         "Les coupes de A et de B réunies découpent le rectangle\nen {N} petites pièces communes."),
 'fade':("Le découpage commun","Ces {N} pièces forment le découpage commun."),
 'hold':("Le découpage commun",
         "Ces {N} pièces se réassemblent aussi bien en A qu'en B :\nc'est l'équidécomposition (Wallace–Bolyai–Gerwien)."),
}

def _fusion_state(ts, sc, T):
    oxC=-0.5; S=1.3
    for nm,t0,du in ts:
        if T<t0+du or (nm,t0,du)==ts[-1]:
            loc=min(1.0,max(0.0,(T-t0)/max(du,1e-6)))
            if nm=='apart': return oxC-S,oxC+S,0.0,nm,S
            if nm=='slide':
                e=_smooth(loc); return oxC-S+e*S, oxC+S-e*S, 0.0, nm, S
            if nm=='grid': return oxC,oxC,0.0,nm,S
            if nm=='fade': return oxC,oxC,_smooth(loc),nm,S
            return oxC,oxC,1.0,nm,S
    return oxC,oxC,1.0,'hold',S

def _fusion_setup(sc, params):
    H=sc['H']; bb=(-1.8,0.0,1.8,H)
    fig,ax,phase=_setup_fig_simple(bb, params, "Fusion des deux découpages (rectangle de largeur 1)",
                                   mx=0.7, my_top=1.4, my_bot=2.0, show_ruler=False)
    msg=fig.text(0.5,0.06,"",ha='center',va='center',fontsize=12.5,color=INK,family='serif',
                 linespacing=1.5, bbox=dict(boxstyle='round,pad=0.6',fc='#fbf7ec',ec='#ddd6c4',alpha=0.92))
    return fig,ax,phase,msg

def _fusion_artists(ax, sc):
    H=sc['H']
    outline=[((0,0),(1,0)),((1,0),(1,H)),((1,H),(0,H)),((0,H),(0,0))]
    fillA=MPLPoly([(-1.8,0),(-0.8,0),(-0.8,H),(-1.8,H)],closed=True,facecolor='#f5eedd',edgecolor=INK,lw=1.5,alpha=0.7); ax.add_patch(fillA)
    fillB=MPLPoly([(0.8,0),(1.8,0),(1.8,H),(0.8,H)],closed=True,facecolor='#f5eedd',edgecolor=INK,lw=1.5,alpha=0.7); ax.add_patch(fillB)
    lcA=LineCollection([],colors=ACUT,linewidths=0.75); ax.add_collection(lcA)
    lcB=LineCollection([],colors=BCUT,linewidths=0.75); ax.add_collection(lcB)
    plus=ax.text(0,H/2,"+",ha='center',va='center',fontsize=30,color=SYM,family='serif',weight='bold')
    return dict(outline=outline,fillA=fillA,fillB=fillB,lcA=lcA,lcB=lcB,plus=plus,com=[])

def _fusion_draw(ax, A, sc, ts, T):
    oxA,oxB,fill,nm,S=_fusion_state(ts,sc,T); H=sc['H']
    def tr(segs,ox): return [(((x0+ox),y0),((x1+ox),y1)) for ((x0,y0),(x1,y1)) in segs]
    def rectpoly(ox): return [(ox,0),(1+ox,0),(1+ox,H),(ox,H)]
    A['fillA'].set_xy(rectpoly(oxA)); A['fillB'].set_xy(rectpoly(oxB))
    A['fillA'].set_alpha(0.7*(1-fill)); A['fillB'].set_alpha(0.7*(1-fill))
    A['lcA'].set_segments(tr(sc['A_segs']+A['outline'],oxA)); A['lcA'].set_alpha(1.0-0.9*fill)
    A['lcB'].set_segments(tr(sc['B_segs']+A['outline'],oxB)); A['lcB'].set_alpha(1.0-0.9*fill)
    A['plus'].set_alpha(max(0.0,min(1.0,abs(oxB-oxA)/(2*S))))
    for pp in A['com']: pp.remove()
    A['com'].clear()
    if fill>0:
        for verts,color in sc['com']:
            vv=[(x-0.5,y) for (x,y) in verts]
            pp=MPLPoly(vv,closed=True,facecolor=color,edgecolor=INK,lw=0.35,alpha=fill); ax.add_patch(pp); A['com'].append(pp)
    t,m=_FUS_TXT[nm]; return t, m.replace("{N}",str(sc['ncom']))

def render_fusion(params):
    os.makedirs(params.out_dir, exist_ok=True)
    sc=build_fusion_scene(params); ts,total=_fusion_phases(sc,params)
    fig,ax,phase,msg=_fusion_setup(sc,params); A=_fusion_artists(ax,sc)
    nframes=int(math.ceil(total*params.fps))
    def update(fr):
        t,m=_fusion_draw(ax,A,sc,ts,fr/params.fps); phase.set_text(t); msg.set_text(m)
        return [A['fillA'],A['fillB'],A['lcA'],A['lcB'],A['plus'],phase,msg]+A['com']
    anim=FuncAnimation(fig,update,frames=nframes,interval=1000/params.fps,blit=False)
    outs=[]
    if params.make_mp4:
        path=os.path.join(params.out_dir,f"{params.basename}_fusion.mp4")
        anim.save(path,writer=FFMpegWriter(fps=params.fps,bitrate=2600),dpi=params.dpi); outs.append(path)
    if params.make_gif:
        path=os.path.join(params.out_dir,f"{params.basename}_fusion.gif")
        anim.save(path,writer=PillowWriter(fps=params.gif_fps),dpi=max(60,params.dpi-30)); outs.append(path)
    plt.close(fig)
    return outs,total,sc

def dump_fusion_keyframes(params, fractions=(0.06,0.30,0.55,0.80,0.99)):
    os.makedirs("/home/claude/preview",exist_ok=True)
    sc=build_fusion_scene(params); ts,total=_fusion_phases(sc,params)
    out=[]
    for fr in fractions:
        fig,ax,phase,msg=_fusion_setup(sc,params); A=_fusion_artists(ax,sc)
        t,m=_fusion_draw(ax,A,sc,ts,fr*total); phase.set_text(t); msg.set_text(m)
        pth=f"/home/claude/preview/fusion_kf_{int(fr*100):03d}.png"
        fig.savefig(pth,dpi=90,facecolor=PAPER); plt.close(fig); out.append(pth)
    return out,total,sc



# ════════════════════════ SCÈNE « INTRO » : polygones, même aire, théorème, triangulation ════════════════════════
def _tri_segments(tris):
    segs=[]
    for t in tris:
        t=list(t)
        for i in range(3):
            a=t[i]; b=t[(i+1)%3]; segs.append(((a.x,a.y),(b.x,b.y)))
    return segs

def build_intro_scene(params):
    from wbg_core import ear_clip, poly_area
    A=[(p.x,p.y) for p in POLY_A]; B=[(p.x,p.y) for p in POLY_B]
    axs=[x for x,y in A]; ays=[y for x,y in A]; bxs=[x for x,y in B]; bys=[y for x,y in B]
    Aw=max(axs)-min(axs); Ah=max(ays)-min(ays); Bw=max(bxs)-min(bxs); Bh=max(bys)-min(bys)
    gap=1.4; dxB=Aw+gap
    A=[(x-min(axs), y-min(ays)) for x,y in A]
    B=[(x-min(bxs)+dxB, y-min(bys)) for x,y in B]
    triA=_tri_segments(ear_clip(list(POLY_A))); triB=_tri_segments(ear_clip(list(POLY_B)))
    # recale les diagonales de B sur la position décalée
    triB=[((x0-min(bxs)+dxB,y0-min(bys)),(x1-min(bxs)+dxB,y1-min(bys))) for ((x0,y0),(x1,y1)) in triB]
    triA=[((x0-min(axs),y0-min(ays)),(x1-min(axs),y1-min(ays))) for ((x0,y0),(x1,y1)) in triA]
    # prologue « réciproque » : un polygone générique scindé en morceaux, recentré
    from wbg_core import P as _P
    bx1=dxB+Bw; byt=max(Ah,Bh); cx=bx1/2; cy=byt/2
    Qraw=[(0,0),(2.0,0),(2.55,1.3),(1.0,2.15),(-0.5,1.25)]
    qcx=sum(x for x,_ in Qraw)/len(Qraw); qcy=sum(y for _,y in Qraw)/len(Qraw)
    Q=[(x-qcx+cx, y-qcy+cy) for (x,y) in Qraw]
    qpal=[PALETTE_A[1],PALETTE_B[1],PALETTE_A[2],PALETTE_B[0]]
    asm=[]
    for k,t in enumerate(ear_clip([_P(x,y) for (x,y) in Q])):
        verts=[(pp.x,pp.y) for pp in t]
        tcx=sum(x for x,_ in verts)/3; tcy=sum(y for _,y in verts)/3
        d=math.hypot(tcx-cx,tcy-cy) or 1.0; ex=((tcx-cx)/d,(tcy-cy)/d)
        asm.append(dict(verts=verts,color=qpal[k%len(qpal)],ex=ex))
    def _cents(poly, sx, sy):
        out=[]
        for i,t in enumerate(ear_clip(list(poly))):
            out.append((sum(pp.x for pp in t)/3+sx, sum(pp.y for pp in t)/3+sy, i+1))
        return out
    centA=_cents(POLY_A, -min(axs), -min(ays))
    centB=_cents(POLY_B, -min(bxs)+dxB, -min(bys))
    return dict(A=A,B=B,triA=triA,triB=triB,centA=centA,centB=centB,
                Acx=Aw/2, Bcx=dxB+Bw/2, Atop=Ah, Btop=Bh,
                nA=len(ear_clip(list(POLY_A))), nB=len(ear_clip(list(POLY_B))),
                area=poly_area(POLY_A), bbox=(0.0,0.0,dxB+Bw,max(Ah,Bh)), asm=asm)

def _intro_phases(params):
    rs=getattr(params,'read_scale',1.0)
    P=[('a',2.6*rs),('b',2.8*rs),('area',3.0*rs),('theo',4.4*rs),('triA',3.8*rs),('triB',3.4*rs),('next',3.4*rs)]
    ts=[]; t=0.0
    for nm,du in P: ts.append((nm,t,du)); t+=du
    return ts,t

def _intro_text(sc):
    a=_fr(sc['area'])
    return {
     'assemble':("Le sens facile","Assemblez des morceaux : on obtient toujours un polygone,\nd'aire égale à la somme des morceaux. C'est évident."),
     'converse':("Le vrai problème : la réciproque","Deux polygones de MÊME aire : peut-on toujours découper l'un pour\nreconstituer EXACTEMENT l'autre ? C'est tout l'enjeu du théorème."),
     'a':("Deux polygones","Voici un polygone A."),
     'b':("Deux polygones","…et un polygone B, de forme très différente."),
     'area':("Même aire",f"Mais ils ont exactement la MÊME aire ≈ {a}."),
     'theo':("Le théorème","Wallace–Bolyai–Gerwien : puisque les aires sont égales, on peut découper A en\n"
                           "un nombre fini de morceaux et les réassembler EXACTEMENT en B."),
     'triA':("Étape 1 — trianguler",f"On découpe chaque polygone en triangles. A en donne {sc['nA']}."),
     'triB':("Étape 1 — trianguler",f"B de même : {sc['nB']} triangles."),
     'next':("La suite","Chaque triangle va devenir un rectangle de largeur 1."),
    }

def _t0(ts,name): return next(t for nm,t,du in ts if nm==name)

def _intro_alpha(ts, T, name, fade=0.5):
    return max(0.0,min(1.0,(T-_t0(ts,name))/fade))

def _assemble_offset(ts, T):
    for nm,t0,du in ts:
        if nm=='assemble':
            if T<t0: return 1.0
            if T>=t0+du: return 0.0
            return 1.0-_smooth((T-t0)/du)
    return 0.0

def render_intro(params):
    os.makedirs(params.out_dir, exist_ok=True)
    sc=build_intro_scene(params); ts,total=_intro_phases(params); TXT=_intro_text(sc)
    fig,ax,phase=_setup_fig_simple(sc['bbox'], params, "Wallace–Bolyai–Gerwien : découper A, réassembler B",
                                   mx=0.7, my_top=1.5, my_bot=1.9)
    msg=fig.text(0.5,0.075,"",ha='center',va='center',fontsize=13.0,color=INK,family='serif',linespacing=1.5,
                 bbox=dict(boxstyle='round,pad=0.6',fc='#fbf7ec',ec='#ddd6c4',alpha=0.92))
    cA=PALETTE_A[2]; cB=PALETTE_B[0]
    fillA=MPLPoly(sc['A'],closed=True,facecolor=cA,edgecolor=INK,lw=1.6); ax.add_patch(fillA)
    fillB=MPLPoly(sc['B'],closed=True,facecolor=cB,edgecolor=INK,lw=1.6); ax.add_patch(fillB)
    lcA=LineCollection(sc['triA'],colors=INK,linewidths=0.9); ax.add_collection(lcA)
    lcB=LineCollection(sc['triB'],colors=INK,linewidths=0.9); ax.add_collection(lcB)
    labA=ax.text(sc['Acx'],sc['Atop']+0.32,"A",ha='center',va='bottom',fontsize=20,color=ACCENT,family='serif',weight='bold')
    labB=ax.text(sc['Bcx'],sc['Btop']+0.32,"B",ha='center',va='bottom',fontsize=20,color='#2f6d8c',family='serif',weight='bold')
    arA=ax.text(sc['Acx'],-0.32,f"aire ≈ {_fr(sc['area'])}",ha='center',va='top',fontsize=11.5,color=MUTED,family='serif')
    arB=ax.text(sc['Bcx'],-0.32,f"aire ≈ {_fr(sc['area'])}",ha='center',va='top',fontsize=11.5,color=MUTED,family='serif')
    numA=[ax.text(cx,cy,str(k),ha='center',va='center',fontsize=15,color=ACCENT,family='serif',weight='bold') for (cx,cy,k) in sc['centA']]
    numB=[ax.text(cx,cy,str(k),ha='center',va='center',fontsize=15,color='#2f6d8c',family='serif',weight='bold') for (cx,cy,k) in sc['centB']]
    def phase_at(T):
        for nm,t0,du in ts:
            if T<t0+du or (nm,t0,du)==ts[-1]: return nm
        return 'next'
    nframes=int(math.ceil(total*params.fps))
    def update(fr):
        T=fr/params.fps; nm=phase_at(T)
        aA=_intro_alpha(ts,T,'a'); aB=_intro_alpha(ts,T,'b'); aAr=_intro_alpha(ts,T,'area')
        aTA=_intro_alpha(ts,T,'triA'); aTB=_intro_alpha(ts,T,'triB')
        fillA.set_alpha(aA); labA.set_alpha(aA)
        fillB.set_alpha(aB); labB.set_alpha(aB)
        arA.set_alpha(aAr); arB.set_alpha(aAr)
        lcA.set_alpha(aTA); lcB.set_alpha(aTB)
        for tnum in numA: tnum.set_alpha(aTA)
        for tnum in numB: tnum.set_alpha(aTB)
        t,m=TXT[nm]; phase.set_text(t); msg.set_text(m)
        return [fillA,fillB,lcA,lcB,labA,labB,arA,arB,phase,msg]+numA+numB
    anim=FuncAnimation(fig,update,frames=nframes,interval=1000/params.fps,blit=False)
    outs=[]
    if params.make_mp4:
        path=os.path.join(params.out_dir,f"{params.basename}_intro.mp4")
        anim.save(path,writer=FFMpegWriter(fps=params.fps,bitrate=2600),dpi=params.dpi); outs.append(path)
    if params.make_gif:
        path=os.path.join(params.out_dir,f"{params.basename}_intro.gif")
        anim.save(path,writer=PillowWriter(fps=params.gif_fps),dpi=max(60,params.dpi-30)); outs.append(path)
    plt.close(fig); return outs,total,sc

def _prologue_arrangements():
    """5 triangles isocèles congruents (base 2, hauteur 1, aire 1 chacun) formant
    3 polygones connexes clairement différents : maison, losange/trapèze, flèche."""
    # Les 5 pièces numérotées dans chaque configuration.
    # Maison : corps carré 2×2 (4 triangles sur les diagonales) + toit isocèle
    house = [
        [(0,0),(2,0),(1,1)],   # 1 bas
        [(2,0),(2,2),(1,1)],   # 2 droite
        [(2,2),(0,2),(1,1)],   # 3 haut
        [(0,2),(0,0),(1,1)],   # 4 gauche
        [(0,2),(2,2),(1,3)],   # 5 toit
    ]
    # Trapèze : rangée alternée haut/bas (5 triangles en zigzag)
    trapeze = [
        [(0,0),(2,0),(1,1)],   # 1 pointe haut
        [(1,1),(3,1),(2,0)],   # 2 pointe bas
        [(2,0),(4,0),(3,1)],   # 3 pointe haut
        [(3,1),(5,1),(4,0)],   # 4 pointe bas
        [(4,0),(6,0),(5,1)],   # 5 pointe haut
    ]
    # Flèche : pentagone pointant à droite (carré 2×2 + pointe droite)
    arrow = [
        [(0,0),(2,0),(1,1)],   # 1 bas
        [(0,2),(2,2),(1,1)],   # 2 haut (inversé)
        [(0,0),(0,2),(1,1)],   # 3 gauche
        [(2,0),(2,2),(1,1)],   # 4 centre
        [(2,0),(2,2),(3,1)],   # 5 pointe droite
    ]
    def center(tris):
        pts = [p for t in tris for p in t]
        cx = sum(x for x,y in pts)/len(pts)
        cy = sum(y for x,y in pts)/len(pts)
        return [[(x-cx, y-cy) for x,y in t] for t in tris]
    return [center(house), center(trapeze), center(arrow)]

def render_prologue(params):
    """Sens facile : on réarrange les MÊMES morceaux en plusieurs polygones ; l'aire ne change pas."""
    os.makedirs(params.out_dir, exist_ok=True)
    arrs = _prologue_arrangements()
    cols = [PALETTE_A[2], PALETTE_B[0], PALETTE_A[1], PALETTE_B[2], PALETTE_A[4]]
    rs = getattr(params, 'read_scale', 1.0)
    seq = [('h0',2.6*rs,0,0),('m01',1.6*rs,0,1),('h1',2.2*rs,1,1),
           ('m12',1.6*rs,1,2),('h2',2.4*rs,2,2),('cv',5.0*rs,2,2)]
    ts = []; t = 0.0
    for nm,du,a,b in seq: ts.append((nm,t,du,a,b)); t += du
    total = t
    bbox = (-3.8,-2.8,3.8,2.8)
    fig,ax,phase = _setup_fig_simple(bbox, params,
        "Le sens facile : réarranger des pièces ne change pas l'aire",
        mx=0.2, my_top=0.6, my_bot=0.6)
    msg = fig.text(0.5,0.075,"",ha='center',va='center',fontsize=13.0,color=INK,
                   family='serif',linespacing=1.5,
                   bbox=dict(boxstyle='round,pad=0.6',fc='#fbf7ec',ec='#ddd6c4',alpha=0.92))
    patches = [MPLPoly([(0,0)],closed=True,facecolor=cols[i],edgecolor=INK,lw=1.6)
               for i in range(5)]
    for p in patches: ax.add_patch(p)
    nums = [ax.text(0,0,str(i+1),ha='center',va='center',fontsize=11,color=INK,family='serif')
            for i in range(5)]
    areatag = ax.text(0,-2.55,"aire = 5 (5 triangles)",ha='center',va='top',
                      fontsize=12.5,color=ACCENT,family='serif',weight='bold')
    TXT = {
        'h0': ("Le sens facile", "On part de quelques pièces qui forment un polygone."),
        'm01': ("Le sens facile", "On les déplace…"),
        'h1': ("…une autre forme", "Mêmes pièces, AUTRE polygone."),
        'm12': ("…encore une autre", "On réarrange encore…"),
        'h2': ("Toujours la même aire", "Quelle que soit la forme, l'aire = somme des pièces. C'est ÉVIDENT."),
        'cv': ("Le vrai problème : la réciproque",
               "L'inverse est bien plus dur : deux polygones de MÊME aire,\n"
               "peut-on TOUJOURS découper l'un pour reconstituer EXACTEMENT l'autre ?"),
    }
    def pos_at(T):
        for nm,t0,du,a,b in ts:
            if T < t0+du or (nm,t0,du,a,b) == ts[-1]:
                f = _smooth(max(0.0,min(1.0,(T-t0)/du))) if a != b else 0.0
                return a,b,f,nm
        return ts[-1][3],ts[-1][4],0.0,ts[-1][0]
    nframes = int(math.ceil(total*params.fps))
    def update(fr):
        T = fr/params.fps; a,b,f,nm = pos_at(T)
        fade = 1.0
        if nm == 'cv':
            t0 = _t0c(ts,'cv'); fade = max(0.25, 1.0-0.75*_smooth(min(1.0,(T-t0)/2.0)))
        for i in range(5):
            ta = arrs[a][i]; tb = arrs[b][i]
            interp = [(ta[k][0]+(tb[k][0]-ta[k][0])*f,
                       ta[k][1]+(tb[k][1]-ta[k][1])*f) for k in range(3)]
            patches[i].set_xy(interp); patches[i].set_alpha(fade)
            cx = sum(x for x,y in interp)/3; cy = sum(y for x,y in interp)/3
            nums[i].set_position((cx,cy)); nums[i].set_alpha(fade)
        areatag.set_alpha(fade)
        tt,mm = TXT[nm]; phase.set_text(tt); msg.set_text(mm)
        return patches+nums+[areatag,phase,msg]
    anim = FuncAnimation(fig,update,frames=nframes,interval=1000/params.fps,blit=False)
    outs = []
    if params.make_mp4:
        path = os.path.join(params.out_dir,f"{params.basename}_prologue.mp4")
        anim.save(path,writer=FFMpegWriter(fps=params.fps,bitrate=2600),dpi=params.dpi)
        outs.append(path)
    plt.close(fig); return outs,total

def _t0c(ts,name): return next(t for nm,t,*_ in ts if nm==name)

def render_threetoone(params):
    """Cas plus riche : oblique 3/2, empilée 2 -> côté 3, puis étape 3 -> 1 (découpes ENTIÈRES, sans sliver)."""
    os.makedirs(params.out_dir, exist_ok=True)
    rs=getattr(params,'read_scale',1.0)
    cw,ch=1.0,0.62
    row=[(-1.5,-ch/2),(-0.5,-ch/2),(0.5,-ch/2)]            # 3 cellules en ligne (largeur 3)
    col=[(-0.5,-1.5*ch),(-0.5,-0.5*ch),(-0.5,0.5*ch)]      # empilées (largeur 1)
    cols=[PALETTE_A[2],PALETTE_A[1],PALETTE_A[4]]
    seq=[('lead',3.8*rs,0,0),('cut',2.6*rs,0,0),('stack',3.0*rs,0,1),('done',3.4*rs,1,1)]
    ts=[]; t=0.0
    for nm,du,a,b in seq: ts.append((nm,t,du,a,b)); t+=du
    total=t
    bbox=(-2.6,-2.0,2.6,2.0)
    fig,ax,phase=_setup_fig_simple(bbox, params, "Un cas qui demande une étape de plus : 3 → 1",
                                   mx=0.2, my_top=0.6, my_bot=0.6)
    msg=fig.text(0.5,0.075,"",ha='center',va='center',fontsize=12.5,color=INK,family='serif',linespacing=1.5,
                 bbox=dict(boxstyle='round,pad=0.6',fc='#fbf7ec',ec='#ddd6c4',alpha=0.92))
    cells=[MPLPoly([(0,0)],closed=True,facecolor=cols[i],edgecolor=INK,lw=1.6) for i in range(3)]
    for c in cells: ax.add_patch(c)
    nums=[ax.text(0,0,str(i+1),ha='center',va='center',fontsize=13,color=INK,family='serif') for i in range(3)]
    wlab=ax.text(0,0,"",ha='center',va='top',fontsize=13,color=ACCENT,family='serif',weight='bold')
    cutsegs=LineCollection([],colors=ACUT,linewidths=2.4); ax.add_collection(cutsegs)
    def at(T):
        for nm,t0,du,a,b in ts:
            if T<t0+du or (nm,t0,du,a,b)==ts[-1]:
                f=_smooth(max(0.0,min(1.0,(T-t0)/du))) if a!=b else 0.0
                return nm,a,b,f
        return ts[-1][0],ts[-1][3],ts[-1][4],0.0
    TXT={
     'lead':("Cas h ∈ [1 ; 1,5[","Ici l'oblique se rationalise en 3/2. Après empilement de 2 bandes,\nle côté vaut 3 — et non 1."),
     'cut':("Une étape de plus","Le côté mesure 3 : on le découpe en 3 morceaux égaux (largeur 1)."),
     'stack':("On empile","…puis on empile les 3 morceaux."),
     'done':("Largeur 1 obtenue","C'est l'étape 3 → 1 (vs 2 × 1/2 → 1 partout ailleurs) : on passe\nd'un côté entier 3 à la largeur voulue 1."),
    }
    nframes=int(math.ceil(total*params.fps))
    def update(fr):
        T=fr/params.fps; nm,a,b,f=at(T)
        arr=[row,col]
        for i in range(3):
            x0,y0=arr[a][i]; x1,y1=arr[b][i]; x=x0+(x1-x0)*f; y=y0+(y1-y0)*f
            cells[i].set_xy([(x,y),(x+cw,y),(x+cw,y+ch),(x,y+ch)])
            nums[i].set_position((x+cw/2,y+ch/2))
        if nm in ('lead','cut'):
            wlab.set_text("côté = 3"); wlab.set_position((0,-ch/2-0.18))
            if nm=='cut':
                cutsegs.set_segments([[(-0.5,-ch/2),(-0.5,ch/2)],[(0.5,-ch/2),(0.5,ch/2)]])
            else: cutsegs.set_segments([])
        else:
            cutsegs.set_segments([]); wlab.set_text("largeur = 1"); wlab.set_position((0.5+0.32,0))
            if nm=='done': wlab.set_position((0.5+0.32,0)); 
        if nm=='done':
            wlab.set_text("largeur = 1   (hauteur = 3 × h)"); wlab.set_position((0,-1.5*ch-0.18))
        tt,mm=TXT[nm]; phase.set_text(tt); msg.set_text(mm)
        return cells+nums+[wlab,cutsegs,phase,msg]
    anim=FuncAnimation(fig,update,frames=nframes,interval=1000/params.fps,blit=False)
    outs=[]
    if params.make_mp4:
        path=os.path.join(params.out_dir,f"{params.basename}_troisversun.mp4")
        anim.save(path,writer=FFMpegWriter(fps=params.fps,bitrate=2600),dpi=params.dpi); outs.append(path)
    plt.close(fig); return outs,total

def dump_intro_keyframes(params, fractions=(0.05,0.22,0.42,0.62,0.82,0.99)):
    os.makedirs("/home/claude/preview",exist_ok=True)
    sc=build_intro_scene(params); ts,total=_intro_phases(params); TXT=_intro_text(sc)
    out=[]
    for fr in fractions:
        fig,ax,phase=_setup_fig_simple(sc['bbox'], params, "Wallace–Bolyai–Gerwien : découper A, réassembler B",
                                       mx=0.7, my_top=1.5, my_bot=1.9)
        msg=fig.text(0.5,0.075,"",ha='center',va='center',fontsize=13.0,color=INK,family='serif',linespacing=1.5,
                     bbox=dict(boxstyle='round,pad=0.6',fc='#fbf7ec',ec='#ddd6c4',alpha=0.92))
        T=fr*total; cur=ts[-1][0]
        for nm,t0,du in ts:
            if T<t0+du: cur=nm; break
        cA=PALETTE_A[2]; cB=PALETTE_B[0]
        aA=_intro_alpha(ts,T,'a'); aB=_intro_alpha(ts,T,'b'); aAr=_intro_alpha(ts,T,'area')
        aTA=_intro_alpha(ts,T,'triA'); aTB=_intro_alpha(ts,T,'triB')
        ax.add_patch(MPLPoly(sc['A'],closed=True,facecolor=cA,edgecolor=INK,lw=1.6,alpha=aA))
        ax.add_patch(MPLPoly(sc['B'],closed=True,facecolor=cB,edgecolor=INK,lw=1.6,alpha=aB))
        ax.add_collection(LineCollection(sc['triA'],colors=INK,linewidths=0.9,alpha=aTA))
        ax.add_collection(LineCollection(sc['triB'],colors=INK,linewidths=0.9,alpha=aTB))
        if aA>0: ax.text(sc['Acx'],sc['Atop']+0.32,"A",ha='center',va='bottom',fontsize=20,color=ACCENT,family='serif',weight='bold',alpha=aA)
        if aB>0: ax.text(sc['Bcx'],sc['Btop']+0.32,"B",ha='center',va='bottom',fontsize=20,color='#2f6d8c',family='serif',weight='bold',alpha=aB)
        if aAr>0:
            ax.text(sc['Acx'],-0.32,f"aire ≈ {_fr(sc['area'])}",ha='center',va='top',fontsize=11.5,color=MUTED,family='serif',alpha=aAr)
            ax.text(sc['Bcx'],-0.32,f"aire ≈ {_fr(sc['area'])}",ha='center',va='top',fontsize=11.5,color=MUTED,family='serif',alpha=aAr)
        aASM=1.0-_intro_alpha(ts,T,'a'); off=_assemble_offset(ts,T)
        for d in sc['asm']:
            ax.add_patch(MPLPoly([(x+d['ex'][0]*0.5*off, y+d['ex'][1]*0.5*off) for (x,y) in d['verts']], closed=True, facecolor=d['color'], edgecolor=INK, lw=1.2, alpha=aASM))
        t,m=TXT[cur]; phase.set_text(t); msg.set_text(m)
        pth=f"/home/claude/preview/intro_kf_{int(fr*100):03d}.png"
        fig.savefig(pth,dpi=90,facecolor=PAPER); plt.close(fig); out.append(pth)
    return out,total,sc


if __name__=="__main__":
    params, check, scene = _parse_cli(sys.argv[1:])
    if scene=="method":
        if check:
            files,total,beats=dump_method_keyframes(params)
            print(f"[méthode] durée ≈ {total:.1f} s  ·  {len(beats)} temps")
            for f in files: print("  image-clé:",f)
        else:
            files,total,beats=render_method(params)
            print(f"[méthode] durée ≈ {total:.1f} s @ {params.fps} fps  ·  {len(beats)} temps")
            for f in files: print("  sortie:",f)
    elif scene=="column":
        if check:
            files,total=dump_column_keyframes(params)
            print(f"[colonne] durée ≈ {total:.1f} s")
            for f in files: print("  image-clé:",f)
        else:
            files,total=render_column(params)
            print(f"[colonne] durée ≈ {total:.1f} s @ {params.fps} fps")
            for f in files: print("  sortie:",f)
    elif scene=="intro":
        if check:
            files,total,sc=dump_intro_keyframes(params)
            print(f"[intro] durée ≈ {total:.1f} s")
            for f in files: print("  image-clé:",f)
        else:
            files,total,sc=render_intro(params)
            print(f"[intro] durée ≈ {total:.1f} s @ {params.fps} fps")
            for f in files: print("  sortie:",f)
    elif scene=="fusion":
        if check:
            files,total,sc=dump_fusion_keyframes(params)
            print(f"[fusion] durée ≈ {total:.1f} s  ·  {sc['ncom']} pièces communes")
            for f in files: print("  image-clé:",f)
        else:
            files,total,sc=render_fusion(params)
            print(f"[fusion] durée ≈ {total:.1f} s @ {params.fps} fps  ·  {sc['ncom']} pièces communes")
            for f in files: print("  sortie:",f)
    else:
        if check:
            files,sc=dump_keyframes(params)
            print(f"[reassemblage] durée totale ≈ {sc['total']:.1f} s  ·  {len(sc['loc'])} pièces")
            for f in files: print("  image-clé:",f)
        else:
            files,sc=render(params)
            print(f"[reassemblage] durée ≈ {sc['total']:.1f} s @ {params.fps} fps  ·  {len(sc['loc'])} pièces")
            for f in files: print("  sortie:",f)
WBG_ANIMATE_EOF

echo ">> build_all.py"
cat > build_all.py <<'WBG_BUILD_EOF'
#!/usr/bin/env python3
"""
build_all.py — Rend les 12 clips de la vidéo WBG puis assemble le master.

Ordre du master (fondus enchaînés xfade) :
  prologue → intro → méthode 0..5 → trois-vers-un → colonne → fusion → réassemblage

Usage :  python3 build_all.py [--out-dir DIR]
Sortie :  DIR/wbg_video_complete.mp4  (+ les 12 clips individuels)
"""
import argparse, dataclasses, math, os, subprocess, sys, time

import wbg_animate as W


def dur(f):
    return float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", f]).strip())


def render_all(params):
    t0 = time.time()
    log = []

    def done(name, outs, total):
        log.append((name, outs[0] if outs else "-", total))
        print(f"  [{time.time()-t0:6.0f}s] {name}: {total:.1f}s -> {outs}", flush=True)

    print("— prologue (sens facile : mêmes pièces, plusieurs polygones)", flush=True)
    outs, total = W.render_prologue(params); done("prologue", outs, total)

    print("— intro (A, B, même aire, théorème, triangulation)", flush=True)
    outs, total, _ = W.render_intro(params); done("intro", outs, total)

    print("— méthode : tous les triangles de A puis de B (le plus gras en détail)", flush=True)
    tris_by_tag = {'A': [], 'B': []}
    for k, o in enumerate(W._all_method_tris()):
        tris_by_tag[o['tag']].append((k, o))
    for tag in ('A', 'B'):
        for k, o in tris_by_tag[tag]:
            lab = f"Triangle {o['idx']+1} de {o['tag']}"
            vig = W._vignette_for(o)
            outs, total, _ = W.render_method(params, tri=o["tri"], color=o["color"],
                                             detailed=o["detailed"], suffix=f"_{k}",
                                             label=lab, fig_vignette=vig)
            done(f"methode_{k} ({lab}{' — détaillé' if o['detailed'] else ''})", outs, total)
        # colonne après chaque figure
        poly  = W.POLY_A if tag=='A' else W.POLY_B
        pal   = W.PALETTE_A if tag=='A' else W.PALETTE_B
        title = f"Colonne de largeur 1 — figure {tag}"
        sfx   = f"_{tag.lower()}"
        outs, total = W.render_column(params, poly=poly, palette=pal,
                                      scene_title=title, suffix=sfx)
        done(f"colonne_{tag}", outs, total)

    print("— méthode 2/3 : rationalisation réelle p = 2, q = 3", flush=True)
    tri23 = [W.P(0.0, 0.0), W.P(3.0, 0.0), W.P(1.5, 1.2)]
    intro23 = ("Le cas qui exige une vraie rationalisation : 2/3",
               "Ce triangle donne un parallélogramme de hauteur h ≈ 0,60 — entre 1/2 et 2/3.\n"
               "Le côté oblique ne peut pas valoir 1 : on l'amène à 2/3, puis q = 3 bandes\n"
               "(2/3 × 3 = 2), puis p = 2 tranches, pour revenir à la largeur exactement 1.")
    outs, total, _ = W.render_method(params, tri=tri23, color=W.PALETTE_B[1],
                                     detailed=True, max_den=3, suffix="_2sur3",
                                     intro=intro23)
    done("methode_2sur3 (rationalisation 2/3)", outs, total)

    print("— colonne (empilement des rectangles)", flush=True)
    outs, total = W.render_column(params); done("colonne", outs, total)

    print("— fusion (superposition des deux découpages)", flush=True)
    outs, total, sc = W.render_fusion(params)
    done(f"fusion ({sc['ncom']} pièces communes)", outs, total)

    print("— réassemblage (A → rectangle → B)", flush=True)
    outs, sc = W.render(params); done("reassemblage", outs, sc["total"])
    return log


def build_master(out_dir, basename):
    import glob, re
    b = basename
    meth = [p for p in glob.glob(f"{out_dir}/{b}_methode_*.mp4")
            if re.search(r"_methode_(\d+)\.mp4$", p)]
    meth.sort(key=lambda p: int(re.search(r"_methode_(\d+)\.mp4$", p).group(1)))
    # split method clips into A and B groups, interleave column clips
    import wbg_animate as W
    all_tris = W._all_method_tris()
    nA = sum(1 for o in all_tris if o['tag']=='A')
    methA = meth[:nA]; methB = meth[nA:]
    clips = ([f"{out_dir}/{b}_prologue.mp4", f"{out_dir}/{b}_intro.mp4"]
             + methA
             + [f"{out_dir}/{b}_colonne_a.mp4"]
             + methB
             + [f"{out_dir}/{b}_colonne_b.mp4",
                f"{out_dir}/{b}_methode_2sur3.mp4",
                f"{out_dir}/{b}_colonne.mp4",
                f"{out_dir}/{b}_fusion.mp4",
                f"{out_dir}/{b}.mp4"])
    for c in clips:
        assert os.path.exists(c), f"clip manquant : {c}"
    durs = [dur(f) for f in clips]
    # transitions dynamiques selon nb de clips
    nmA = len(methA); nmB = len(methB)
    ds = ([0.6, 0.6]                   # prologue→intro, intro→méthode A0
          + [0.4]*(nmA-1)              # entre les triangles A
          + [0.7]                      # dernier A → colonneA
          + [0.6]                      # colonneA → méthode B0
          + [0.4]*(nmB-1)              # entre les triangles B
          + [0.7]                      # dernier B → colonneB
          + [0.6, 0.6, 0.9, 0.6])     # colonneB→2/3, 2/3→colonne, colonne→fusion, fusion→réassemblage
    assert len(ds) == len(clips) - 1, f"ds={len(ds)} clips={len(clips)}"
    acc = durs[0]; offs = []
    for k in range(len(ds)):
        offs.append(acc - ds[k]); acc += durs[k + 1] - ds[k]
    prep = ";".join(f"[{i}:v]fps=30,format=yuv420p,setpts=PTS-STARTPTS[v{i}]"
                    for i in range(len(clips)))
    chain = []; cur = "v0"
    for k in range(len(ds)):
        out = "vout" if k == len(ds) - 1 else f"x{k}"
        chain.append(f"[{cur}][v{k+1}]xfade=transition=fade:duration={ds[k]}:"
                     f"offset={offs[k]:.3f}[{out}]")
        cur = out
    fc = prep + ";" + ";".join(chain)
    master = f"{out_dir}/wbg_video_complete.mp4"
    cmd = (["ffmpeg", "-v", "error"] + sum([["-i", c] for c in clips], [])
           + ["-filter_complex", fc, "-map", "[vout]", "-r", "30",
              "-pix_fmt", "yuv420p", "-c:v", "libx264", "-crf", "20", master, "-y"])
    print(f"master : {len(clips)} clips, attendu ≈ {acc:.0f}s ({acc/60:.1f} min)", flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-400:]
    time.sleep(1)
    print(f"master : durée réelle {dur(master):.1f}s -> {master}", flush=True)
    return master


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="/mnt/user-data/outputs/anim_dissection")
    ap.add_argument("--fps", type=int, default=30)
    a = ap.parse_args()
    params = W.AnimParams(out_dir=a.out_dir, fps=a.fps, make_gif=False)
    os.makedirs(a.out_dir, exist_ok=True)
    render_all(params)
    build_master(a.out_dir, params.basename)
WBG_BUILD_EOF

python - <<'PYCHK'
import wbg_animate as W
assert len(W.POLY_A)==5 and len(W.POLY_B)==6
assert len(W._prologue_arrangements())==3
assert hasattr(W,'_vignette_for')
print(f"OK — {len(W._all_method_tris())} triangles methode")
PYCHK
mkdir -p out
python build_all.py --out-dir out
echo ">> out/wbg_video_complete.mp4"
