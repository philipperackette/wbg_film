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

# Réglages éditables : textes courts, sous-titres marrons, pauses de fin.
try:
    import wbg_params as WBGCFG
except Exception:
    WBGCFG = None

SUBTITLE_BROWN = getattr(WBGCFG, "SUBTITLE_BROWN", "#7a4a2a") if WBGCFG else "#7a4a2a"

def _cfg_text(section, key, default):
    val = default
    if WBGCFG:
        val = getattr(WBGCFG, "SUBTITLE_TEXTS", {}).get(section, {}).get(key, default)
    return _one_line(val) if "_one_line" in globals() else " ".join(str(val).split())

def _cfg_end(section, key, default):
    if not WBGCFG:
        return default
    return getattr(WBGCFG, "END_HOLDS", {}).get(section, {}).get(key, default)

def _cfg_method_end(label, default):
    if not WBGCFG:
        return default
    d = getattr(WBGCFG, "END_HOLDS", {}).get("method", {})
    return d.get(label, d.get("default_final", default))

def _cfg_merge_pairs(section, base, **fmt):
    out = dict(base)
    if not WBGCFG:
        return out
    for k, v in getattr(WBGCFG, "SUBTITLE_TEXTS", {}).get(section, {}).items():
        if isinstance(v, (tuple, list)) and len(v) == 2:
            try:
                out[k] = (_one_line(str(v[0]).format(**fmt)), _one_line(str(v[1]).format(**fmt)))
            except Exception:
                out[k] = tuple(v)
    return out

def _cfg_merge_strings(section, base, **fmt):
    out = dict(base)
    if not WBGCFG:
        return out
    for k, v in getattr(WBGCFG, "SUBTITLE_TEXTS", {}).get(section, {}).items():
        if isinstance(v, str):
            try:
                out[k] = _one_line(v.format(**fmt))
            except Exception:
                out[k] = v
    return out

def _one_line(x):
    return " ".join(str(x).split())

def _cfg_method_pair(label, key, default_title, default_msg, **fmt):
    if not WBGCFG:
        return _one_line(default_title), _one_line(default_msg)
    method = getattr(WBGCFG, "SUBTITLE_TEXTS", {}).get("method", {})
    val = method.get(label, {}).get(key, method.get("global", {}).get(key, (default_title, default_msg)))
    if not (isinstance(val, (tuple, list)) and len(val) == 2):
        return _one_line(default_title), _one_line(default_msg)
    try:
        return _one_line(str(val[0]).format(**fmt)), _one_line(str(val[1]).format(**fmt))
    except Exception:
        return _one_line(default_title), _one_line(default_msg)


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
    trans_speed: float = 3.35     # unités par seconde (translations glissées) — ralenti légèrement
    rot_speed:   float = 130.0    # degrés par seconde (rotations) — plus lisible
    min_move:    float = 0.42     # durée plancher d'un déplacement (s)
    # mise en scène
    stagger:     float = 0.06     # décalage de départ entre pièces successives (s)
    group_by_origin: bool = True  # faire partir ensemble les pièces d'un même triangle de A
    show_rect_phase: bool = True  # inclure l'étape rectangle 1×6 (sinon A -> B direct)
    gap: float = 1.7              # écart horizontal entre les « stations » A | rect | B
    # temps de pause (s)
    pause_start: float = 0.85
    pause_mid:   float = 0.75
    pause_end:   float = 1.25
    cut_dur:     float = 0.7      # durée du « flash » de coupe (scène méthode)
    read_scale:  float = 0.90     # facteur global sur les pauses de lecture (scène méthode)
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
def build_scene(params: AnimParams, direction="AB"):
    """Scène de réassemblage à 3 stations (gauche | rectangle | droite).
    direction="AB" : A -> rectangle -> B, couleurs de A (clip historique).
    direction="BA" : B -> rectangle -> A, couleurs de B (clip symétrique).
    """
    dA=dissect_polygon(POLY_A, PALETTE_A, "A", max_den=2)
    dB=dissect_polygon(POLY_B, PALETTE_B, "B", max_den=2)
    com=common_refinement(dA["column"], dB["column"], poly_area(POLY_A))
    loc=common_located(com, dA["column"], dB["column"])
    H=dA["colH"]   # hauteur du rectangle (6)

    # poses brutes (P -> tuples) : A dans le polygone A, R dans le rectangle, B dans B
    rawA=[[(v.x,v.y) for v in c["inA"]]  for c in loc]
    rawR=[[(v.x,v.y) for v in c["rect"]] for c in loc]
    rawB=[[(v.x,v.y) for v in c["inB"]]  for c in loc]
    colA=[c["color"] for c in loc]                              # couleur = triangle de A
    colB=[PALETTE_B[c["bi"] % len(PALETTE_B)] for c in loc]     # couleur = triangle de B
    origA=[c["ai"] for c in loc]; origB=[c["bi"] for c in loc]

    # Disposition FIXE et identique pour les deux sens : A à gauche, rectangle au milieu,
    # B à droite. Le clip BA est le REJEU À L'ENVERS du clip AB (mêmes positions), avec
    # les couleurs de B : les pièces partent de B (à droite) et reconstituent A (à gauche).
    rawL,rawM,rawN = rawA,rawR,rawB
    labL,labN = "A","B"
    if direction=="AB":
        colors=colA; orig=origA; suffix=""
        title="Découpe, glissement, rotation : A et B, les mêmes pièces"
        path=["L","M","N"]
        cfg_section = "reassembly_AB"
        cap={("L","M"):_cfg_text(cfg_section, "move_LM", "Chaque pièce glisse et tourne : A → rectangle de largeur 1"),
             ("M","N"):_cfg_text(cfg_section, "move_MN", "Les mêmes pièces repartent : rectangle de largeur 1 → B"),
             ("L","N"):_cfg_text(cfg_section, "move_LN", "Les mêmes pièces : A → B")}
        hold={"L":_cfg_text(cfg_section, "hold_L", "Les {n} pièces communes, disposées comme dans A"),
              "M":_cfg_text(cfg_section, "hold_M", "Les mêmes pièces réunies en rectangle de largeur 1"),
              "N":_cfg_text(cfg_section, "hold_N", "Les mêmes pièces réassemblées en B — CQFD")}
    else:  # "BA" : même disposition, rejeu inversé, couleurs de B
        colors=colB; orig=origB; suffix="_BA"
        title="Sens inverse : B → A, les mêmes pièces (couleurs de B)"
        path=["N","M","L"]
        cfg_section = "reassembly_BA"
        cap={("N","M"):_cfg_text(cfg_section, "move_NM", "Chaque pièce glisse et tourne : B → rectangle de largeur 1"),
             ("M","L"):_cfg_text(cfg_section, "move_ML", "Les mêmes pièces repartent : rectangle de largeur 1 → A"),
             ("N","L"):_cfg_text(cfg_section, "move_NL", "Les mêmes pièces : B → A")}
        hold={"N":_cfg_text(cfg_section, "hold_N", "Les {n} pièces communes, disposées comme dans B"),
              "M":_cfg_text(cfg_section, "hold_M", "Les mêmes pièces réunies en rectangle de largeur 1"),
              "L":_cfg_text(cfg_section, "hold_L", "Les mêmes pièces réassemblées en A — CQFD")}

    # bboxes globales par station, pour centrer verticalement chaque forme
    def gbb(raws):
        pts=[p for poly in raws for p in poly]; return _bbox(pts)
    bL=gbb(rawL); bM=gbb(rawM); bN=gbb(rawN)
    wL=bL[2]-bL[0]; wM=bM[2]-bM[0]; wN=bN[2]-bN[0]
    g=params.gap
    xL=0.0; xM=wL+g; xN=wL+g+wM+g
    def offset(raws, bb, X0):
        ox=X0-bb[0]; oy=H/2 - (bb[1]+(bb[3]-bb[1])/2)   # centre vertical dans [0,H]
        return [[(x+ox, y+oy) for (x,y) in poly] for poly in raws]
    posL=offset(rawL,bL,xL); posM=offset(rawM,bM,xM); posN=offset(rawN,bN,xN)
    posByKey={"L":posL,"M":posM,"N":posN}

    # ordre d'animation : par triangle d'origine puis de bas en haut (station de DÉPART)
    start_pos=posByKey[path[0]]
    idx=list(range(len(loc)))
    idx.sort(key=lambda i:(orig[i] if params.group_by_origin else 0,
                           _centroid(start_pos[i])[1], _centroid(start_pos[i])[0]))

    def dur(p1,p2):
        c1=_centroid(p1); c2=_centroid(p2)
        dist=math.hypot(c2[0]-c1[0], c2[1]-c1[1])
        ang=abs(math.degrees(_rel_angle(p1,p2)))
        return max(dist/params.trans_speed, ang/params.rot_speed, params.min_move)

    def plan(src,dst):
        starts={}; durs={}
        for k,i in enumerate(idx):
            starts[i]=k*params.stagger
            durs[i]=dur(src[i],dst[i])
        length=max(starts[i]+durs[i] for i in idx)
        return starts,durs,length

    n=len(loc)
    seq=[]; T=0.0
    seq.append(("hold", T, params.pause_start, (path[0], hold[path[0]].format(n=n)))); T+=params.pause_start
    if params.show_rect_phase:
        a,b=path[0],path[1]; s,d,L=plan(posByKey[a],posByKey[b])
        seq.append(("move",T,L,(posByKey[a],posByKey[b],s,d,cap[(a,b)]))); T+=L
        seq.append(("hold",T,params.pause_mid, (path[1], hold[path[1]])));  T+=params.pause_mid
        a,b=path[1],path[2]; s,d,L=plan(posByKey[a],posByKey[b])
        seq.append(("move",T,L,(posByKey[a],posByKey[b],s,d,cap[(a,b)]))); T+=L
    else:
        a,b=path[0],path[2]; s,d,L=plan(posByKey[a],posByKey[b])
        seq.append(("move",T,L,(posByKey[a],posByKey[b],s,d,cap[(a,b)]))); T+=L
    end_hold = _cfg_end(cfg_section, "final", params.pause_end)
    seq.append(("hold",T,end_hold, (path[2], hold[path[2]])));         T+=end_hold
    total=T

    allpts=[p for Pset in (posL,posM,posN) for poly in Pset for p in poly]
    bx=_bbox(allpts)
    frame={"xlim":(bx[0]-0.6, bx[2]+0.6), "ylim":(bx[1]-1.1, bx[3]+0.9),
           "stations":[(xL+wL/2,labL,13),(xM+wM/2,"rectangle de largeur 1",11),
                       (xN+wN/2,labN,13)], "H":H}

    return dict(loc=loc, colors=colors, stations={"L":posL,"M":posM,"N":posN},
                idx=idx, seq=seq, total=total, frame=frame, title=title,
                basename_suffix=suffix, dA=dA, dB=dB, com=com)


def pose_and_label_at(scene, T):
    """Renvoie (liste de poses des pièces à l'instant T, libellé de phase)."""
    st=scene["stations"]; n=len(st["L"]); cur=[None]*n
    for (typ,t0,L,payload) in scene["seq"]:
        if T < t0+L or (typ,t0,L,payload) is scene["seq"][-1]:
            if typ=="hold":
                key,label=payload
                cur=[list(p) for p in st[key]]
            else:
                src,dst,starts,durs,label=payload
                local=T-t0
                for i in range(n):
                    t=(local-starts[i])/durs[i]
                    t=0.0 if t<0 else (1.0 if t>1 else t)
                    cur[i]=interp_pose(src[i],dst[i],_smooth(t))
            return cur,label
    last=scene["seq"][-1]
    return [list(p) for p in st["N"]], (last[3][1] if last[0]=="hold" else "")


# ───────────────────────── rendu ─────────────────────────
def _setup_fig(scene, params):
    fig=plt.figure(figsize=(params.width_px/params.dpi, params.height_px/params.dpi),
                   dpi=params.dpi)
    ax=fig.add_axes([0,0,1,1]); ax.set_aspect('equal'); ax.axis('off')
    fig.patch.set_facecolor(PAPER); ax.set_facecolor(PAPER)
    fr=scene["frame"]; ax.set_xlim(*fr["xlim"]); ax.set_ylim(*fr["ylim"])

    patches=[]
    L0=scene["stations"]["L"]
    for i in range(len(L0)):
        poly=MPLPoly(L0[i], closed=True, facecolor=scene["colors"][i],
                     edgecolor=INK, linewidth=0.5, joinstyle='round')
        ax.add_patch(poly); patches.append(poly)

    # titre + légende de phase + étiquettes des stations + règle
    fig.text(0.5,0.95, scene["title"],
             ha='center',va='center',fontsize=16,color=INK,family='serif',weight='bold')
    phase=fig.text(0.5,0.895,"",ha='center',va='center',fontsize=12,color=MUTED,
                   family='serif',style='italic')
    fr=scene["frame"]; ybl=fr["ylim"][0]+0.92
    for (xc,lab,fs) in fr["stations"]:
        ax.text(xc, ybl, lab, ha='center', va='top', fontsize=fs,
                color=INK, family='serif', weight='bold')
    # règle 1 unité (bas-gauche)
    rx=fr["xlim"][0]+0.4; ry=fr["ylim"][0]+0.52
    ax.plot([rx,rx+1],[ry,ry],color=ACCENT,lw=1.6)
    ax.plot([rx,rx],[ry-0.08,ry+0.08],color=ACCENT,lw=1.6)
    ax.plot([rx+1,rx+1],[ry-0.08,ry+0.08],color=ACCENT,lw=1.6)
    ax.text(rx+0.5,ry-0.18,"1 unité",ha='center',va='top',fontsize=8,color=ACCENT,family='monospace')
    return fig,ax,patches,phase


def render(params: AnimParams, direction="AB"):
    os.makedirs(params.out_dir, exist_ok=True)
    scene=build_scene(params, direction)
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
    sfx=scene["basename_suffix"]
    outputs=[]
    if params.make_mp4:
        path=os.path.join(params.out_dir,f"{params.basename}{sfx}.mp4")
        anim.save(path,writer=FFMpegWriter(fps=params.fps,bitrate=2600),dpi=params.dpi)
        outputs.append(path)
    if params.make_gif:
        path=os.path.join(params.out_dir,f"{params.basename}{sfx}.gif")
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

_SEQ_GAP = 0.16   # temps mort entre deux sous-ensembles de transformation différente (s)

def _mover_groups(movers, params):
    """Regroupe les movers par isométrie IDENTIQUE.
    - les pièces qui subissent exactement la même transformation bougent ENSEMBLE ;
    - les sous-ensembles de transformations différentes s'enchaînent successivement ;
    - les pièces immobiles sont affichées fixes (pas de fenêtre de temps).
    Renvoie (static, groups, total) où groups = [(indices, start, dur), …] séquentiels."""
    def key(iso):
        if iso[0]=='trans': return ('trans', round(iso[1],6), round(iso[2],6))
        return ('rot', round(iso[1],6), round(iso[2],6), round(iso[3],6))
    def moves(iso):
        if iso[0]=='trans': return math.hypot(iso[1],iso[2])>1e-9
        return abs(iso[1])>1e-9
    static=[]; bykey={}; order=[]
    for idx,(pid,b,a,iso) in enumerate(movers):
        if not moves(iso): static.append(idx); continue
        k=key(iso)
        if k not in bykey: bykey[k]=[]; order.append(k)
        bykey[k].append(idx)
    groups=[]; t=0.0
    for gi,k in enumerate(order):
        idxs=bykey[k]; iso=movers[idxs[0]][3]
        if iso[0]=='trans':
            du=max(math.hypot(iso[1],iso[2])/params.trans_speed, params.min_move)
        else:
            du=max(abs(math.degrees(iso[1]))/params.rot_speed, params.min_move)
        if gi>0: t+=_SEQ_GAP
        groups.append((idxs, t, du)); t+=du
    return static, groups, t

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
    color=md['color']; p=md['p']; q=md['q']; h=md['h']; frac=(str(p) if q==1 else f"{p}/{q}")
    pts=md['pts']
    blen=max(math.hypot(pts[i][0]-pts[(i+1)%3][0], pts[i][1]-pts[(i+1)%3][1]) for i in range(3))
    rs=getattr(params,'read_scale',1.0)
    def H(x):
        # Rythmique : les longs panneaux détaillés sont resserrés,
        # tandis que les passages résumés respirent davantage.
        return x*rs*(0.88 if detailed else 0.46)
    beats=[]
    if intro is not None:
        intro_title, intro_msg = intro
    elif detailed:
        intro_title,intro_msg = _cfg_method_pair(
            label, "intro",
            "Triangle → rectangle de largeur 1",
            "On prend l'un des vrais triangles des figures — ici le plus « gras ».\n"
            "Sa plus longue arête sert de base. Objectif : le transformer par découpes, glissements\n"
            "et rotations, sans déformation, en un rectangle de largeur exactement 1."
        )
    else:
        intro_title=(label if label else "Triangle suivant")
        intro_msg=((label+" : ") if label else "")+"même procédé, sans déformation."
    beats.append({'k':'show','state':{0:(pts,color)},
        'title':intro_title,'msg':intro_msg,
        'dims':[{'kind':'hdim','label':f"base ≈ {_fr(blen)}"}], 'hold':H(3.4 if detailed else 2.6)})
    state={md['trap_pid']:(md['trapV'],color), md['ndc_pid']:(md['amnV'],color)}
    beats.append({'k':'cut','state':{0:(pts,color)},'state_after':_snap(state),'segs':[md['MN']],
        'title':_cfg_method_pair(label, "midline_cut", "Étape 1 — ligne des milieux", "On joint les milieux des deux côtés issus du sommet, puis on coupe.")[0],
        'msg':_cfg_method_pair(label, "midline_cut", "Étape 1 — ligne des milieux", "On joint les milieux des deux côtés issus du sommet, puis on coupe.")[1],
        'hold':H(2.6)})
    rot_iso=('rot',math.pi,md['N'][0],md['N'][1])
    _ndcV_landed=_interp_iso(md['amnV'], md['ndcV'], rot_iso, 1.0)  # true endpoint of the rotation
    beats.append({'k':'move','state':_snap(state),
        'movers':[(md['ndc_pid'], md['amnV'], md['ndcV'], rot_iso)],
        'title':_cfg_method_pair(label, "midline_move", "Demi-tour → parallélogramme", "Le petit triangle pivote de 180° : on obtient un parallélogramme de même aire.")[0],
        'msg':_cfg_method_pair(label, "midline_move", "Demi-tour → parallélogramme", "Le petit triangle pivote de 180° : on obtient un parallélogramme de même aire.")[1],
        'dims':[{'kind':'vleft','label':f"h ≈ {_fr(h)}"}], 'hold':H(3.2)})
    state[md['ndc_pid']]=(_ndcV_landed, color)   # use actual landing position, no teleport
    ev=md['rest']; i=0; last='shear'
    cut_script={
        'shear':_cfg_method_pair(label, "shear_cut", "Rationalisation — découpe", "Une coupe isole le petit coin qui dépasse.", frac=frac, p=p, q=q),
        'q-cut':_cfg_method_pair(label, "q_cut", f"Découpe en q = {q} bandes", f"On coupe la base en {q} parts égales.", frac=frac, p=p, q=q),
        'p-cut':_cfg_method_pair(label, "p_cut", f"Découpe en p = {p} bandes", "On recoupe le grand côté pour le ramener à 1.", frac=frac, p=p, q=q),
        'par-rect':_cfg_method_pair(label, "rect_cut", "Redressement — découpe finale", "Une découpe sépare le morceau qui dépasse.", frac=frac, p=p, q=q)}
    move_script={
        'shear':(*_cfg_method_pair(label, "shear_move", f"Le côté oblique devient {frac}", f"On glisse le morceau : le côté oblique vaut maintenant {frac}.", frac=frac, p=p, q=q), f"oblique = {frac}"),
        'q-cut':(*_cfg_method_pair(label, "q_move", f"Empilement → côté = {p}", f"On empile les {q} bandes : {frac} × {q} = {p}.", frac=frac, p=p, q=q), f"oblique = {p}"),
        'p-cut':(*_cfg_method_pair(label, "p_move", "Empilement → côté = 1", "On empile les morceaux : le grand côté devient exactement 1.", frac=frac, p=p, q=q), "côté = 1"),
        'par-rect':(*_cfg_method_pair(label, "rect_move", "Le morceau glisse à gauche", "Le morceau qui dépasse glisse d’un bloc : même translation pour toutes ses pièces.", frac=frac, p=p, q=q), None)}
    expl={
        'shear':_cfg_method_pair(label, "shear_explain", "Étape 2 — rationaliser l’oblique", "On ajuste le côté oblique pour obtenir une longueur rationnelle.", frac=frac, p=p, q=q),
        'q-cut':_cfg_method_pair(label, "q_explain", "Rendre le côté entier", f"On coupe en q = {q} bandes égales, puis on les empile.", frac=frac, p=p, q=q),
        'par-rect':_cfg_method_pair(label, "rect_explain", "Étape 3 — redresser en rectangle", "On tranche la partie qui dépasse, puis elle glisse pour combler le creux.", frac=frac, p=p, q=q)}
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
            mv=[]; stt={}
            for pid,(fv,col) in state.items():
                d=disp.get(pid,(0.0,0.0)); sv=[(x-d[0],y-d[1]) for (x,y) in fv]
                stt[pid]=(sv,col); mv.append((pid,sv,fv,('trans',d[0],d[1])))
            # La coupe CRÉE les pièces : elles sont affichées séparées (stt) dès la pause
            # d'après-coupe, AVANT le moindre glissement.
            # Segments de coupe du redressement : on place un codage d'angle droit
            # rouge sur CHAQUE coupe rouge visible.
            ra_segs=[]; wv=None
            for sg in cutsegs:
                (x0,y0),(x1,y1)=sg
                ln=math.hypot(x1-x0,y1-y0)
                if ln>1e-6:
                    ra_segs.append(sg)
                    if wv is None:
                        wv=((x1-x0)/ln,(y1-y0)/ln)
            beats.append({'k':'cut','state':S_before,'state_after':_snap(stt),'segs':cutsegs,
                'ra_wv':wv, 'ra_segs':ra_segs,
                'title':_cfg_method_pair(label, "rect_cut", "Redressement — découpe finale", "Une découpe sépare le morceau qui dépasse du rectangle de largeur 1.")[0],
                'msg':_cfg_method_pair(label, "rect_cut", "Redressement — découpe finale", "Une découpe sépare le morceau qui dépasse du rectangle de largeur 1.")[1],'hold':H(2.2)})

            # Pour le redressement du triangle 2 de A : les groupes mobiles doivent partir
            # visuellement de gauche à droite. _mover_groups conserve l'ordre de première
            # apparition des transformations ; on trie donc les movers par abscisse de départ.
            if "Triangle 2 de A" in label:
                mv.sort(key=lambda item: _cen(item[1])[0])

            beats.append({'k':'move','state':stt,'movers':mv,
                'title':_cfg_method_pair(label, "rect_move", "Le morceau glisse à gauche", "Le morceau qui dépasse glisse d’un bloc : même translation pour toutes ses pièces.")[0],
                'msg':_cfg_method_pair(label, "rect_move", "Le morceau glisse à gauche", "Le morceau qui dépasse glisse d’un bloc : même translation pour toutes ses pièces.")[1],
                'labels':[],'hold':H(3.0),'slowmo':1.25})
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
            # On applique la découpe TOUT DE SUITE, puis on mémorise l'état APRÈS coupe :
            # les pièces nouvellement créées seront affichées (séparées) pendant la pause.
            for ce in grp:
                state.pop(ce['parent'],None)
                for (cid,cv,cc) in ce['children']: state[cid]=(cv,cc)
            cut_beat['state_after']=_snap(state)
            beats.append(cut_beat)
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
        beats.append({'k':'move','state':_snap(state),'movers':movers,'together':True,
            'title':_cfg_method_pair(label, "rotate_rect", "On pose le rectangle droit", "Une dernière rotation met le rectangle à l’horizontale.")[0],
            'msg':_cfg_method_pair(label, "rotate_rect", "On pose le rectangle droit", "Une dernière rotation met le rectangle à l’horizontale.")[1],'hold':H(1.8)})
        for pid,(v,c) in list(state.items()): state[pid]=(_rotate_pts(v,ang,rA[0],rA[1]), c)
    area=sum(_area_tup(v) for _,(v,_) in state.items())
    final_title, final_msg = _cfg_method_pair(
        label, "final",
        "Rectangle de largeur 1",
        f"Largeur exactement 1 ; hauteur = aire ≈ {_fr(area)}.\n"
        "Chaque triangle subit ce procédé ; les rectangles obtenus s'empilent\n"
        "ensuite en une seule colonne de largeur 1.",
        area=_fr(area)
    )
    beats.append({'k':'show','state':_snap(state),
        'title':final_title,
        'msg':final_msg,
        'dims':[{'kind':'hdim','label':"largeur = 1"},{'kind':'vright','label':f"≈ {_fr(area)}"}],
        'hold':H(_cfg_method_end(label, 4.6))})
    return beats

def _setup_fig_simple(bbox, params, title, mx=0.6, my_top=1.4, my_bot=0.9, show_ruler=False):
    fig=plt.figure(figsize=(params.width_px/params.dpi, params.height_px/params.dpi), dpi=params.dpi)
    ax=fig.add_axes([0,0,1,1]); ax.set_aspect('equal'); ax.axis('off')
    fig.patch.set_facecolor(PAPER); ax.set_facecolor(PAPER)
    x0,y0,x1,y1=bbox
    ax.set_xlim(x0-mx, x1+mx); ax.set_ylim(y0-my_bot, y1+my_top)
    fig.text(0.5,0.965,title,ha='center',va='center',fontsize=16,color=INK,family='serif',weight='bold')
    phase=fig.text(0.5,0.918,"",ha='center',va='center',fontsize=13,color=SUBTITLE_BROWN,family='serif',style='italic')
    if show_ruler:
        rx=x0-mx+0.3; ry=y0-my_bot+0.5
        ax.plot([rx,rx+1],[ry,ry],color=MUTED,lw=1.4)
        ax.plot([rx,rx],[ry-0.07,ry+0.07],color=MUTED,lw=1.4); ax.plot([rx+1,rx+1],[ry-0.07,ry+0.07],color=MUTED,lw=1.4)
        ax.text(rx+0.5,ry+0.13,"1 unité",ha='center',va='bottom',fontsize=8,color=MUTED,family='monospace')
    return fig,ax,phase

def _draw_state(ax, patches, pieces, top_pids=()):
    for p in patches: p.remove()
    patches.clear()
    top_pids=set(top_pids)
    # pièces immobiles d'abord, puis les pièces EN MOUVEMENT par-dessus (1er plan)
    order=[pid for pid in pieces if pid not in top_pids]+[pid for pid in pieces if pid in top_pids]
    for rank,pid in enumerate(order):
        verts,color=pieces[pid]
        zz = 5 if pid in top_pids else 2          # le morceau qui bouge passe devant
        poly=MPLPoly(verts, closed=True, facecolor=color, edgecolor=INK, linewidth=1.4,
                     joinstyle='round', zorder=zz)
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

def _rect_right_angle(ax, pieces, wv, store, size=0.22):
    """Code d'angle droit au coin du rectangle obtenu après redressement : un petit carré
    aligné sur le côté unité (wv) et sur la base perpendiculaire (no). Affiché juste après
    la coupe, retiré ensuite (store nettoyé à chaque frame)."""
    if not wv or not pieces: return
    wx,wy=wv; nx,ny=-wy,wx                      # base ⊥ au côté unité
    pts=[v for _,(vv,_) in pieces.items() for v in vv]
    if not pts: return
    pw=[x*wx+y*wy for (x,y) in pts]; pn=[x*nx+y*ny for (x,y) in pts]
    aw=min(pw); an=min(pn)                       # coin bas-gauche dans le repère (wv,no)
    cx=aw*wx+an*nx; cy=aw*wy+an*ny
    P1=(cx+size*wx, cy+size*wy)
    P2=(cx+size*wx+size*nx, cy+size*wy+size*ny)
    P3=(cx+size*nx, cy+size*ny)
    store.append(ax.plot([P1[0],P2[0],P3[0]],[P1[1],P2[1],P3[1]],
                         color=INK,lw=1.6,solid_capstyle='round',zorder=8)[0])

def _cut_right_angle(ax, seg, pieces, store, size=0.16, color=ACCENT):
    """Codage d'angle droit attaché à une vraie extrémité de la coupe rouge.

    La coupe de redressement est perpendiculaire au côté unité. Le petit carré ne
    doit donc pas flotter au milieu du trait : il doit être ancré à une extrémité
    du segment rouge, du côté où le carré est contenu dans la figure.
    """
    if not seg:
        return

    def point_in_poly(pt, poly):
        x, y = pt
        inside = False
        n = len(poly)
        if n < 3:
            return False
        j = n - 1
        for i in range(n):
            xi, yi = poly[i]
            xj, yj = poly[j]
            if (yi > y) != (yj > y):
                xcross = (xj - xi) * (y - yi) / ((yj - yi) + 1e-15) + xi
                if x < xcross:
                    inside = not inside
            j = i
        return inside

    polys = [vv for _, (vv, _) in pieces.items() if len(vv) >= 3]

    def in_union(pt):
        return any(point_in_poly(pt, poly) for poly in polys)

    (x0, y0), (x1, y1) = seg
    dx = x1 - x0
    dy = y1 - y0
    ln = math.hypot(dx, dy)
    if ln < 1e-6:
        return

    ux, uy = dx / ln, dy / ln              # direction de la coupe rouge
    vx0, vy0 = -uy, ux                     # direction perpendiculaire = côté unité, au signe près
    a = min(size, 0.22 * ln)

    candidates = []

    # On essaie les deux extrémités du segment rouge.
    # À chaque extrémité, la direction "le long de la coupe" doit entrer dans le segment.
    endpoint_data = [
        ((x0, y0), ( ux,  uy)),
        ((x1, y1), (-ux, -uy)),
    ]

    for E, along in endpoint_data:
        ex, ey = E
        axu, ayu = along

        # On essaie les deux côtés perpendiculaires possibles.
        for side in (1.0, -1.0):
            vx, vy = side * vx0, side * vy0

            P = (ex, ey)
            Q = (ex + a * axu, ey + a * ayu)
            S = (ex + a * vx,  ey + a * vy)
            R = (Q[0] + a * vx, Q[1] + a * vy)

            # Points de contrôle strictement dans le petit carré.
            C  = (ex + 0.50 * a * axu + 0.50 * a * vx,
                  ey + 0.50 * a * ayu + 0.50 * a * vy)
            C1 = (ex + 0.30 * a * axu + 0.30 * a * vx,
                  ey + 0.30 * a * ayu + 0.30 * a * vy)
            C2 = (ex + 0.70 * a * axu + 0.30 * a * vx,
                  ey + 0.70 * a * ayu + 0.30 * a * vy)
            C3 = (ex + 0.30 * a * axu + 0.70 * a * vx,
                  ey + 0.30 * a * ayu + 0.70 * a * vy)
            C4 = (ex + 0.70 * a * axu + 0.70 * a * vx,
                  ey + 0.70 * a * ayu + 0.70 * a * vy)

            controls = (C, C1, C2, C3, C4)
            score = sum(1 for pt in controls if in_union(pt))

            # Le centre du carré dans la matière est prioritaire.
            if in_union(C):
                score += 5

            candidates.append((score, P, Q, R, S))

    if not candidates:
        return

    candidates.sort(key=lambda z: z[0], reverse=True)
    score, P, Q, R, S = candidates[0]

    if score <= 0:
        return

    # On trace un petit carré ouvert sur le sommet P : P→Q→R→S→P.
    store.append(ax.plot(
        [P[0], Q[0], R[0], S[0], P[0]],
        [P[1], Q[1], R[1], S[1], P[1]],
        color=color,
        lw=1.8,
        solid_capstyle='round',
        solid_joinstyle='round',
        zorder=9
    )[0])


def _method_draw(ax, patches, annot, msg_a, phase_a, flash, beat, pieces, in_hold, flashinfo, moving=()):
    _draw_state(ax, patches, pieces, top_pids=moving)
    if flash is not None:
        if flashinfo:
            segs,f=flashinfo; alpha=math.sin(max(0,min(1,f))*math.pi); X=[];Y=[]
            for sgt in segs:
                if not sgt: continue
                (a0,b0),(a1,b1)=sgt; X+=[a0,a1,float('nan')]; Y+=[b0,b1,float('nan')]
            flash.set_data(X,Y); flash.set_alpha(0.9*alpha)
        else:
            flash.set_alpha(0.0); flash.set_data([], [])
    phase_a.set_text(beat.get('title',''))
    # Bandeau du bas minimaliste : le texte verbeux n'apparaît que sur les écrans
    # d'explication ('show'). Pendant l'action (coupe/glissement) le bas reste épuré
    # (l'indicateur d'étape suffit ; le commentaire est porté par le script lu).
    mtext = beat.get('msg','') if beat.get('k')=='show' else ''
    msg_a.set_text(mtext); msg_a.set_visible(bool(mtext))
    _draw_annot(ax, annot, beat, pieces, in_hold)
    # Codage de l'angle droit : synchronisé avec les coupures rouges du redressement.
    # Un seul carré rouge suffit : les autres coupes sont parallèles.
    if in_hold and beat.get('k') == 'cut' and beat.get('ra_segs'):
        sg = min(beat['ra_segs'], key=lambda e: (e[0][0] + e[1][0]) / 2)
        _cut_right_angle(ax, sg, pieces, annot, color=ACCENT)
    # Fraction sur la coupe : visible DÈS l'apparition du trait (tracé + maintien),
    # dessinée APRÈS _draw_annot pour ne pas être effacée par son store.clear().
    flab=beat.get('frac_label')
    if flab:
        segs=beat.get('segs') or []
        for sgt in segs:
            if not sgt: continue
            (a0,b0),(a1,b1)=sgt
            annot.append(ax.plot([a0,a1],[b0,b1],color=ACCENT,lw=2.4,alpha=0.92,
                                 solid_capstyle='round',zorder=6)[0])
            mx,my=(a0+a1)/2,(b0+b1)/2
            annot.append(ax.text(mx+0.18, my, "= "+flab, ha='left', va='center',
                                  fontsize=15, color=ACCENT, family='serif',
                                  weight='bold', zorder=7))
            break
    # Marque de coupe PERSISTANTE pendant la pause d'après-coupe : la coupe « rouge »
    # reste visible le temps que les pièces qu'elle vient de créer soient bien vues, AVANT
    # qu'elles ne glissent (cas des coupes sans étiquette de fraction). 'partout'.
    if in_hold and beat.get('k')=='cut' and not flab:
        for sgt in (beat.get('segs') or []):
            if not sgt: continue
            (a0,b0),(a1,b1)=sgt
            annot.append(ax.plot([a0,a1],[b0,b1],color=ACCENT,lw=2.2,alpha=0.80,
                                 solid_capstyle='round',zorder=6)[0])

def _method_timeline(beats, params):
    for b in beats:
        if b['k']=='move':
            sm=b.get('slowmo',1.0)
            if b.get('together'):                      # bloc rigide : tout bouge ensemble
                b['motion']=_beat_dur(b['movers'], params)*sm
                b.pop('mstatic',None); b.pop('mgroups',None)
            else:                                      # groupes par transformation identique
                static,groups,total=_mover_groups(b['movers'], params)
                b['mstatic']=static
                b['mgroups']=[(idxs, s*sm, d*sm) for (idxs,s,d) in groups]
                b['motion']=total*sm
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
            if b['k']=='show': return _snap(b['state']), b, True, None, set()
            if b['k']=='cut':
                f=min(1.0,max(0.0,local/max(motion,1e-6)))
                if in_hold and b.get('state_after') is not None:
                    # Pièces CRÉÉES dès la coupe : on affiche les enfants (séparés), immobiles,
                    # AVANT tout mouvement. La marque de coupe reste tracée par _method_draw.
                    return _snap(b['state_after']), b, in_hold, None, set()
                return _snap(b['state']), b, in_hold, (b.get('segs') or [], f), set()
            f=min(1.0,max(0.0,local/max(motion,1e-6)))
            cur=_snap(b['state']); moving=set()
            mgroups=b.get('mgroups')
            if mgroups is not None:
                for k in b.get('mstatic',[]):
                    pid,bf,af,iso=b['movers'][k]
                    cur[pid]=(af, cur.get(pid,(None,color))[1])
                for (idxs,s,d) in mgroups:
                    fk = 0.0 if local<=s else (1.0 if local>=s+d else (local-s)/d)
                    for k in idxs:
                        pid,bf,af,iso=b['movers'][k]
                        cur[pid]=(_interp_iso(bf,af,iso,fk), cur.get(pid,(None,color))[1])
                        if 1e-6<fk<1-1e-6: moving.add(pid)   # ce morceau bouge -> 1er plan
            else:                                      # together : tout bouge ensemble
                for (pid,bf,af,iso) in b['movers']:
                    cur[pid]=(_interp_iso(bf,af,iso,f), cur.get(pid,(None,color))[1])
                    if not in_hold: moving.add(pid)
            return cur, b, in_hold, None, moving
    return _snap(beats[-1]['state']), beats[-1], True, None, set()

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
    """Triangles de A puis de B, du plus simple au plus complexe (nb pièces croissant).
    Le triangle détaillé (le plus gras) est toujours présenté EN DERNIER pour chaque figure,
    après les triangles rapides — progression pédagogique simple → complexe.
    B T2 (idx=2, h~0.56 -> 2/3, 13 pièces) est exclu : clip 2sur3 séparé.
    L'ordre A-avant-B garantit que build_all peut insérer colonneA/colonneB."""
    from wbg_core import ear_clip
    import wbg_pipeline as _PL
    result = []
    for poly, pal, tag in [(POLY_A, PALETTE_A, 'A'), (POLY_B, PALETTE_B, 'B')]:
        tris = [list(t) for t in ear_clip(list(poly))]
        fat = max(range(len(tris)), key=lambda k: _minang_tri(tris[k]))
        # triangles rapides (non-détaillés) : triés par nb de pièces croissant
        others = [(k, tris[k]) for k in range(len(tris))
                  if k != fat and not (tag == 'B' and k == 2)]
        others.sort(key=lambda kt: len(_PL.dissect_triangle(
            list(kt[1]), pal[0], kt[0], step0=1, max_den=2)['pieces']))
        # ordre final : simples d'abord, détaillé en dernier
        ordered = others + [(fat, tris[fat])]
        for pos, (oi, t) in enumerate(ordered):
            result.append(dict(tri=_reorient_horizontal(t), color=pal[oi % len(pal)],
                               tag=tag, idx=oi, ntag=len(tris),
                               ang=_minang_tri(t), detailed=(pos == len(ordered) - 1)))
    return result


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
        "Triangle → rectangle de largeur 1", mx=1.2, my_top=1.5, my_bot=1.0, show_ruler=True)
    msg=fig.text(0.5,0.075,"",ha='center',va='center',fontsize=13.0,color=INK,family='serif',
                 linespacing=1.5, alpha=0.0)
    patches=[]; annot=[]; flash=Line2D([],[],color=ACCENT,lw=2.6,alpha=0.0,solid_capstyle='round'); ax.add_line(flash)
    # ── vignette : figure source avec triangle actif mis en valeur ──
    if fig_vignette is not None:
        fv=fig_vignette; vx=fv['poly']; vtris=fv['tris']
        aidx=fv['active_idx']; vpal=fv['palette']
        # Médaillon : petit, coin supérieur droit, dans la marge my_top (hors zone animée)
        ins = fig.add_axes([0.875, 0.845, 0.105, 0.12], facecolor='#f5f0e8')
        ins.set_aspect('equal'); ins.axis('off')
        # contour de la figure source
        vxs = [x for x,y in vx] + [vx[0][0]]; vys = [y for x,y in vx] + [vx[0][1]]
        ins.fill(vxs, vys, color='#EEE8D8', edgecolor=INK, linewidth=0.9)
        # triangles : actif en couleur, autres estompés
        for k, vt in enumerate(vtris):
            txs = [x for x,y in vt]; tys = [y for x,y in vt]
            if k == aidx:
                ins.fill(txs, tys, color=vpal[k % len(vpal)], alpha=0.95,
                         edgecolor=INK, linewidth=1.0)
            else:
                ins.fill(txs, tys, color=vpal[k % len(vpal)], alpha=0.20,
                         edgecolor='#AEA89A', linewidth=0.5)
        ins.autoscale_view()
        tag_str = f"▲ {label}" if label else ""
        ins.set_title(tag_str, fontsize=6, color=MUTED, pad=1.5, family='serif', loc='center')
        ins.patch.set_edgecolor('#C0B8A8'); ins.patch.set_linewidth(0.7)
    nframes=int(math.ceil(total*params.fps))
    def update(fr):
        pieces,beat,in_hold,flashinfo,moving=_method_state_at(beats, md['color'], fr/params.fps)
        _method_draw(ax, patches, annot, msg, phase, flash, beat, pieces, in_hold, flashinfo, moving)
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
            "Triangle → rectangle de largeur 1", mx=1.2, my_top=1.5, my_bot=1.0, show_ruler=True)
        msg=fig.text(0.5,0.075,"",ha='center',va='center',fontsize=13.0,color=INK,family='serif',
                     linespacing=1.5, alpha=0.0)
        patches=[]; annot=[]; flash=Line2D([],[],color=ACCENT,lw=2.6,alpha=0.0); ax.add_line(flash)
        pieces,beat,in_hold,flashinfo,moving=_method_state_at(beats, md['color'], fr*total)
        _method_draw(ax, patches, annot, msg, phase, flash, beat, pieces, in_hold, flashinfo, moving)
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
                  scene_title="Empilement → colonne de largeur 1",
                  suffix=""):
    os.makedirs(params.out_dir, exist_ok=True)
    sc=build_column_scene(params, poly, palette); n=sc['n']
    durs=[]
    for i in range(n):
        dx0,dy0=sc['tray_dx'][i]; dx1,dy1=sc['col_dx'][i]
        durs.append(max(math.hypot(dx1-dx0,dy1-dy0)/params.trans_speed, params.min_move))
    starts=[i*max(params.stagger,0.18) for i in range(n)]
    move_len=max(starts[i]+durs[i] for i in range(n))
    col_section = 'column_b' if suffix == '_b' else 'column_a'
    end_hold = _cfg_end(col_section, 'final', params.pause_end)
    T0=params.pause_start; T1=T0+move_len; total=T1+end_hold
    allpts=[]
    for i in range(n):
        for (verts,col) in sc['groups'][i]:
            for (x,y) in verts:
                allpts.append((x+sc['tray_dx'][i][0], y+sc['tray_dx'][i][1]))
                allpts.append((x+sc['col_dx'][i][0], y+sc['col_dx'][i][1]))
    bb=_bbox(allpts)
    fig,ax,phase=_setup_fig_simple(bb, params, scene_title, show_ruler=True)
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
        if T<T0: return _cfg_text("column", "start", "Chaque triangle est devenu un rectangle de largeur 1 — coupes comprises")
        if T>=T1: return _cfg_text("column", "final", "Colonne de largeur 1 : les marques de découpe restent visibles")
        return _cfg_text("column", "move", "On empile les rectangles ; les marques de découpe sont conservées")
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
    col_section = 'column_b' if suffix == '_b' else 'column_a'
    end_hold = _cfg_end(col_section, 'final', params.pause_end)
    T0=params.pause_start; T1=T0+move_len; total=T1+end_hold
    allpts=[]
    for i in range(n):
        for (verts,col) in sc['groups'][i]:
            for (x,y) in verts:
                allpts.append((x+sc['tray_dx'][i][0], y+sc['tray_dx'][i][1]))
                allpts.append((x+sc['col_dx'][i][0], y+sc['col_dx'][i][1]))
    bb=_bbox(allpts); out=[]
    for fr in fractions:
        fig,ax,phase=_setup_fig_simple(bb, params, "Empilement → colonne de largeur 1", show_ruler=True)
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

def _hex_lerp(c1, c2, t):
    """Interpolation linéaire entre deux couleurs hex (#rrggbb)."""
    t=max(0.0,min(1.0,t)); a=c1.lstrip('#'); b=c2.lstrip('#')
    ar=[int(a[i:i+2],16) for i in (0,2,4)]; br=[int(b[i:i+2],16) for i in (0,2,4)]
    return '#%02x%02x%02x' % tuple(round(ar[k]+(br[k]-ar[k])*t) for k in range(3))

def build_fusion_scene(params):
    """Géométrie de la fusion : les pièces communes sous leurs trois poses
    CONGRUENTES (dans A, dans le rectangle, dans B), recentrées au MÊME endroit
    (le rectangle, centre (0,H/2)), pour une métamorphose « sur place ».
    Couleurs : colA = triangle d'origine dans A (chaud) ; colB = triangle dans B (froid)."""
    dA=dissect_polygon(POLY_A, PALETTE_A, "A", max_den=2)
    dB=dissect_polygon(POLY_B, PALETTE_B, "B", max_den=2)
    H=dA['colH']
    com_raw=common_refinement(dA['column'], dB['column'], poly_area(POLY_A))
    loc=common_located(com_raw, dA['column'], dB['column'])
    rawA=[[(v.x,v.y) for v in c['inA']]  for c in loc]
    rawR=[[(v.x,v.y) for v in c['rect']] for c in loc]
    rawB=[[(v.x,v.y) for v in c['inB']]  for c in loc]
    colA=[c['color'] for c in loc]
    colB=[PALETTE_B[c['bi'] % len(PALETTE_B)] for c in loc]
    origins=[c['ai'] for c in loc]
    # recentrage de chaque jeu de poses sur le centre du rectangle (0, H/2)
    def recenter(raws):
        pts=[p for poly in raws for p in poly]; bb=_bbox(pts)
        ox=0.0-(bb[0]+bb[2])/2; oy=H/2-(bb[1]+bb[3])/2
        return [[(x+ox,y+oy) for (x,y) in poly] for poly in raws]
    posA=recenter(rawA); posR=recenter(rawR); posB=recenter(rawB)
    # jeux de coupes (centrés, repère du rectangle [-0.5,0.5]x[0,H])
    def cc(segs): return [((x0-0.5,y0),(x1-0.5,y1)) for ((x0,y0),(x1,y1)) in segs]
    Asegs=cc(_piece_segments(dA['column'])); Bsegs=cc(_piece_segments(dB['column']))
    rectOutline=[((-0.5,0),(0.5,0)),((0.5,0),(0.5,H)),((0.5,H),(-0.5,H)),((-0.5,H),(-0.5,0))]
    idx=sorted(range(len(loc)), key=lambda i:(origins[i], _centroid(posA[i])[1], _centroid(posA[i])[0]))
    rank={i:r for r,i in enumerate(idx)}
    return dict(H=H, posA=posA, posR=posR, posB=posB, colA=colA, colB=colB,
                Asegs=Asegs, Bsegs=Bsegs, rectOutline=rectOutline, idx=idx, rank=rank,
                ncom=len(loc), nA=len(dA['column']), nB=len(dB['column']))

def _fusion_phases(sc, params):
    rs=getattr(params,'read_scale',1.0)
    P=[('apart',2.7*rs),('slide',2.8),('neutral',2.4*rs),
       ('revealA',2.1),('holdA',1.4*rs),('A2rect',4.9),('holdRectA',1.1*rs),
       ('recolor',3.1),('holdRectB',1.1*rs),('rect2B',4.9),('holdB',_cfg_end('fusion','final',2.6)*rs)]
    ts=[]; t=0.0
    for nm,du in P: ts.append((nm,t,du)); t+=du
    return ts,t

_FUS_TXT={
 'apart':("Deux découpages du même rectangle",
          "À gauche : le rectangle de largeur 1, découpé selon A (traits orange).\n"
          "À droite : LE MÊME rectangle, découpé selon B (traits bleus)."),
 'slide':("On les superpose",
          "Les deux rectangles sont identiques : largeur 1, même hauteur.\nOn les fait coïncider."),
 'neutral':("La réunion des deux découpages",
            "Ensemble, les coupes de A et de B partagent le rectangle\nen {N} pièces communes — pour l'instant SANS couleur."),
 'revealA':("Ce sont exactement les pièces de A",
            "Regroupées par triangle d'origine, ces {N} pièces redonnent la figure A."),
 'holdA':("La figure A, colorée par sa triangulation",
          "Chaque teinte chaude correspond à un triangle de A."),
 'A2rect':("La figure A se transforme en la fusion",
           "Les pièces de A glissent et tournent (sans déformation)\net forment le rectangle commun, aux couleurs de A."),
 'holdRectA':("La fusion, aux couleurs de A",
              "Le rectangle commun, colorié selon la triangulation de A."),
 'recolor':("On passe aux couleurs de B",
            "Les MÊMES pièces, recoloriées selon la triangulation de la figure B."),
 'holdRectB':("La fusion, aux couleurs de B",
              "Le même rectangle commun, colorié selon la triangulation de B."),
 'rect2B':("La figure B est reconstituée",
           "Les pièces repartent et se regroupent en la figure B, aux couleurs de B."),
 'holdB':("Équidécomposition",
          "Les {N} mêmes pièces composent A ET B :\nc'est l'équidécomposition (Wallace–Bolyai–Gerwien)."),
}
_FUS_TXT = _cfg_merge_pairs("fusion", _FUS_TXT)

def _fusion_frame(sc, ts, T):
    """État de dessin à l'instant T : poses, couleurs, opacités, décalages des grilles."""
    n=len(sc['posR']); SUP=1.15
    nm,t0,du=ts[-1]
    for cand in ts:
        if T < cand[1]+cand[2]:
            nm,t0,du=cand; break
    loc=min(1.0,max(0.0,(T-t0)/max(du,1e-6)))
    # progression DÉCALÉE par pièce (vague groupée par triangle, de bas en haut)
    S0=0.42
    def prog(i):
        st=(sc['rank'][i]/max(n-1,1))*S0
        return _smooth(min(1.0,max(0.0,(loc-st)/(1-S0))))
    poses=sc['posR']; fills=sc['colA']; pa=0.0
    gA=0.0; gB=0.0; gal=0.0; plus=0.0
    if nm=='apart':
        gA=-SUP; gB=SUP; gal=1.0; plus=1.0
    elif nm=='slide':
        e=_smooth(loc); gA=-SUP*(1-e); gB=SUP*(1-e); gal=1.0; plus=1.0-e
    elif nm=='neutral':
        gal=1.0
    elif nm=='revealA':
        e=_smooth(loc); gal=1.0-e; pa=e; poses=sc['posA']; fills=sc['colA']
    elif nm=='holdA':
        pa=1.0; poses=sc['posA']; fills=sc['colA']
    elif nm=='A2rect':
        poses=[interp_pose(sc['posA'][i],sc['posR'][i],prog(i)) for i in range(n)]
        fills=sc['colA']; pa=1.0
    elif nm=='holdRectA':
        poses=sc['posR']; fills=sc['colA']; pa=1.0
    elif nm=='recolor':
        e=_smooth(loc); poses=sc['posR']
        fills=[_hex_lerp(sc['colA'][i],sc['colB'][i],e) for i in range(n)]; pa=1.0
    elif nm=='holdRectB':
        poses=sc['posR']; fills=sc['colB']; pa=1.0
    elif nm=='rect2B':
        poses=[interp_pose(sc['posR'][i],sc['posB'][i],prog(i)) for i in range(n)]
        fills=sc['colB']; pa=1.0
    else:  # holdB
        poses=sc['posB']; fills=sc['colB']; pa=1.0
    return dict(nm=nm, poses=poses, fills=fills, pa=pa, gA=gA, gB=gB, gal=gal, plus=plus)

def _fusion_setup(sc, params):
    H=sc['H']; bb=(-1.85,-0.25,1.85,H+0.25)
    fig,ax,phase=_setup_fig_simple(bb, params, "Superposition des deux découpages — raffinement commun",
                                   mx=0.7, my_top=1.4, my_bot=1.0, show_ruler=True)
    msg=fig.text(0.5,0.092,"",ha='center',va='center',fontsize=12.5,color=INK,family='serif',
                 linespacing=1.5, alpha=0.0)
    return fig,ax,phase,msg

def _fusion_artists(ax, sc):
    H=sc['H']; n=len(sc['posR'])
    lcA=LineCollection([],colors=ACUT,linewidths=0.85); ax.add_collection(lcA)
    lcB=LineCollection([],colors=BCUT,linewidths=0.85); ax.add_collection(lcB)
    patches=[]
    for i in range(n):
        pp=MPLPoly(sc['posR'][i],closed=True,facecolor=sc['colA'][i],edgecolor=INK,
                   linewidth=0.5,joinstyle='round',alpha=0.0)
        ax.add_patch(pp); patches.append(pp)
    plus=ax.text(0,H/2,"∪",ha='center',va='center',fontsize=34,color=SYM,family='serif',weight='bold')
    return dict(lcA=lcA,lcB=lcB,patches=patches,plus=plus)

def _fusion_draw(ax, A, sc, ts, T):
    fr=_fusion_frame(sc,ts,T)
    def shift(segs,ox): return [((x0+ox,y0),(x1+ox,y1)) for ((x0,y0),(x1,y1)) in segs]
    grid=sc['rectOutline']
    A['lcA'].set_segments(shift(sc['Asegs']+grid, fr['gA'])); A['lcA'].set_alpha(fr['gal'])
    A['lcB'].set_segments(shift(sc['Bsegs']+grid, fr['gB'])); A['lcB'].set_alpha(fr['gal'])
    A['plus'].set_alpha(fr['plus'])
    pa=fr['pa']; poses=fr['poses']; fills=fr['fills']
    for i,pp in enumerate(A['patches']):
        pp.set_xy(poses[i]); pp.set_facecolor(fills[i]); pp.set_alpha(pa)
        pp.set_linewidth(0.5 if pa>0.01 else 0.0)
    t,m=_FUS_TXT[fr['nm']]
    nstr=str(sc['ncom'])
    return t.replace("{N}", nstr), m.replace("{N}", nstr)

def render_fusion(params):
    os.makedirs(params.out_dir, exist_ok=True)
    sc=build_fusion_scene(params); ts,total=_fusion_phases(sc,params)
    fig,ax,phase,msg=_fusion_setup(sc,params); A=_fusion_artists(ax,sc)
    nframes=int(math.ceil(total*params.fps))
    def update(fr):
        t,m=_fusion_draw(ax,A,sc,ts,fr/params.fps); phase.set_text(t); msg.set_text(m)
        return [A['lcA'],A['lcB'],A['plus'],phase,msg]+A['patches']
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

def dump_fusion_keyframes(params, fractions=(0.06,0.20,0.34,0.46,0.60,0.74,0.88,0.99)):
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
    # triangles comme polygones colorés (couleurs de la palette de dissection)
    trisA_raw=list(ear_clip(list(POLY_A))); trisB_raw=list(ear_clip(list(POLY_B)))
    def offset_tri(t, ox, oy): return [(p.x+ox, p.y+oy) for p in t]
    ox_a=-min(axs); oy_a=-min(ays); ox_b=-min(bxs)+dxB; oy_b=-min(bys)
    trisA_verts=[offset_tri(t,ox_a,oy_a) for t in trisA_raw]
    trisB_verts=[offset_tri(t,ox_b,oy_b) for t in trisB_raw]
    trisA_colors=[PALETTE_A[i%len(PALETTE_A)] for i in range(len(trisA_raw))]
    trisB_colors=[PALETTE_B[i%len(PALETTE_B)] for i in range(len(trisB_raw))]
    triA=_tri_segments(trisA_raw); triB=_tri_segments(trisB_raw)
    triB=[((x0-min(bxs)+dxB,y0-min(bys)),(x1-min(bxs)+dxB,y1-min(bys))) for ((x0,y0),(x1,y1)) in triB]
    triA=[((x0-min(axs),y0-min(ays)),(x1-min(axs),y1-min(ays))) for ((x0,y0),(x1,y1)) in triA]
    # prologue « réciproque »
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
    return dict(A=A,B=B,triA=triA,triB=triB,
                trisA_verts=trisA_verts,trisB_verts=trisB_verts,
                trisA_colors=trisA_colors,trisB_colors=trisB_colors,
                centA=centA,centB=centB,
                Acx=Aw/2, Bcx=dxB+Bw/2, Atop=Ah, Btop=Bh,
                nA=len(trisA_raw), nB=len(trisB_raw),
                area=poly_area(POLY_A), bbox=(0.0,0.0,dxB+Bw,max(Ah,Bh)), asm=asm)

def _intro_phases(params):
    rs=getattr(params,'read_scale',1.0)
    P=[('a',2.3*rs),('b',2.5*rs),('area',2.6*rs),('theo',3.7*rs),('triA',4.0*rs),('triB',3.8*rs),('next',_cfg_end('intro','final',2.8)*rs)]
    ts=[]; t=0.0
    for nm,du in P: ts.append((nm,t,du)); t+=du
    return ts,t

def _intro_text(sc):
    a=_fr(sc['area'])
    base = {
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
    return _cfg_merge_pairs("intro", base, area=a, nA=sc['nA'], nB=sc['nB'])

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
    fig,ax,phase=_setup_fig_simple(sc['bbox'], params, "Wallace–Bolyai–Gerwien — deux polygones, même aire",
                                   mx=0.7, my_top=1.5, my_bot=1.0, show_ruler=True)
    msg=fig.text(0.5,0.092,"",ha='center',va='center',fontsize=13.0,color=INK,family='serif',linespacing=1.5,
                 alpha=0.0)
    cA=PALETTE_A[2]; cB=PALETTE_B[0]
    fillA=MPLPoly(sc['A'],closed=True,facecolor=cA,edgecolor=INK,lw=1.6); ax.add_patch(fillA)
    fillB=MPLPoly(sc['B'],closed=True,facecolor=cB,edgecolor=INK,lw=1.6); ax.add_patch(fillB)
    lcA=LineCollection(sc['triA'],colors=INK,linewidths=1.4); ax.add_collection(lcA)
    lcB=LineCollection(sc['triB'],colors=INK,linewidths=1.4); ax.add_collection(lcB)
    # triangles colorés (même palette que la dissection) — s'affichent avec la triangulation
    triA_fills=[MPLPoly(v,closed=True,facecolor=c,edgecolor=INK,lw=1.2,alpha=0.0)
                for v,c in zip(sc['trisA_verts'],sc['trisA_colors'])]
    triB_fills=[MPLPoly(v,closed=True,facecolor=c,edgecolor=INK,lw=1.2,alpha=0.0)
                for v,c in zip(sc['trisB_verts'],sc['trisB_colors'])]
    for p in triA_fills+triB_fills: ax.add_patch(p)
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
        # triangles colorés : apparaissent avec la triangulation (légèrement décalés)
        for p in triA_fills: p.set_alpha(min(aTA, 0.88))
        for p in triB_fills: p.set_alpha(min(aTB, 0.88))
        # numéros apparaissent après les couleurs
        num_aTA = max(0.0, aTA - 0.3)
        num_aTB = max(0.0, aTB - 0.3)
        for tnum in numA: tnum.set_alpha(num_aTA)
        for tnum in numB: tnum.set_alpha(num_aTB)
        t,m=TXT[nm]; phase.set_text(t); msg.set_text(m)
        return [fillA,fillB,lcA,lcB,labA,labB,arA,arB,phase,msg]+numA+numB+triA_fills+triB_fills
    anim=FuncAnimation(fig,update,frames=nframes,interval=1000/params.fps,blit=False)
    outs=[]
    if params.make_mp4:
        path=os.path.join(params.out_dir,f"{params.basename}_intro.mp4")
        anim.save(path,writer=FFMpegWriter(fps=params.fps,bitrate=2600),dpi=params.dpi); outs.append(path)
    if params.make_gif:
        path=os.path.join(params.out_dir,f"{params.basename}_intro.gif")
        anim.save(path,writer=PillowWriter(fps=params.gif_fps),dpi=max(60,params.dpi-30)); outs.append(path)
    plt.close(fig); return outs,total,sc

_STEPS = ["Le sens facile", "Le théorème", "Triangle → rectangle",
          "Empiler en colonne", "Superposer les découpages (∪)", "Réassembler A ↔ B"]

def _step_bar(fig, idx):
    """Indicateur minimaliste de position dans la démarche, en bas de l'écran."""
    n=len(_STEPS); name=_STEPS[idx-1]
    pips="".join("●" if k<idx else "○" for k in range(n))
    fig.text(0.5, 0.045, pips, ha='center', va='center', fontsize=11,
             color=ACCENT, family='monospace', alpha=0.9)
    fig.text(0.5, 0.018, f"étape {idx}/{n}   ·   {name}", ha='center', va='center',
             fontsize=10.5, color=MUTED, family='serif', alpha=0.9)

def _align_tri(src, dst):
    """dst avec sommets permutés circulairement (orientation CONSERVÉE) pour minimiser
    la rotation src→dst. Pour un triangle équilatéral (symétrie d'ordre 3) toute rotation
    se ramène ainsi à ≤ 60° : aucune pièce ne fait de demi-tour ni de retournement."""
    best=dst; ba=float('inf')
    for r in range(3):
        d=dst[r:]+dst[:r]; a=abs(_rel_angle(src,d))
        if a<ba: ba=a; best=d
    return best

def _prologue_arrangements():
    """6 triangles équilatéraux congruents (côté s) formant 3 figures pleines :
    hexagone → zigzag/éclair → parallélogramme.

    Point important : les trois figures sont des polyiamants pleins, sans trou et sans
    chevauchement. Combiné à _align_tri, chaque transition est translation + rotation
    ≤ 60° dans le plan — jamais de retournement."""
    s=1.5; h=s*math.sqrt(3)/2
    V=[(s*math.cos(math.radians(60*k)), s*math.sin(math.radians(60*k))) for k in range(6)]
    def ccw(t):
        (x0,y0),(x1,y1),(x2,y2)=t
        return t if (x1-x0)*(y2-y0)-(x2-x0)*(y1-y0)>0 else [t[0],t[2],t[1]]

    # 1) Parallélogramme plein : trois losanges côte à côte, chaque losange étant
    # découpé en deux triangles équilatéraux. Contrairement à l'ancienne version,
    # on utilise bien le pas s partout : les 6 triangles sont équilatéraux.
    para=[]
    for j in range(3):
        A=(j*s,0.0); B=((j+1)*s,0.0)
        C=(j*s+s/2,h); D=((j+1)*s+s/2,h)
        para.extend([ccw([A,B,C]), ccw([B,D,C])])

    # 2) Hexagone régulier plein : les 6 triangles ont un sommet commun au centre.
    hexg=[ccw([(0.0,0.0),V[k],V[(k+1)%6]]) for k in range(6)]

    # 3) Zigzag / éclair plein : une silhouette brisée, sans trou.
    # On évite volontairement la bande droite de 6 triangles, qui ressemble trop
    # à un simple parallélogramme allongé.
    def P(i,j):
        # Réseau triangulaire : le niveau j est décalé d'un demi-côté.
        return (s*(i + 0.5*j), h*j)

    def U(i,j):
        # Triangle pointant vers le haut.
        return ccw([P(i,j), P(i+1,j), P(i,j+1)])

    def D(i,j):
        # Triangle pointant vers le bas.
        return ccw([P(i+1,j), P(i,j+1), P(i+1,j+1)])

    # Vrai zigzag plein : deux losanges en bas, puis un coude qui remonte.
    # Les 6 triangles sont toujours équilatéraux, de même taille, et adjacents.
    #
    # Schéma approximatif :
    #
    #           /\
    #          /__\
    #      /\  /\
    #     /__\/__\
    #
    zig = [
        U(0,0), D(0,0),
        U(1,0), D(1,0),
        U(1,1), D(1,1),
    ]

    def center(tris):
        pts=[p for t in tris for p in t]
        cx=sum(x for x,y in pts)/len(pts); cy=sum(y for x,y in pts)/len(pts)
        return [[(x-cx, y-cy) for x,y in t] for t in tris]
    return [center(hexg), center(zig), center(para)]


def _prologue_vrac():
    """6 triangles équilatéraux éparpillés aléatoirement — position de départ
    avant qu'ils se rassemblent en hexagone. Positions fixes (seed) pour que
    le rendu soit déterministe."""
    import random
    rng = random.Random(7)
    s = 1.5
    # triangle équilatéral centré : même gabarit que _prologue_arrangements
    base = [(-s/2, -s*0.2887), (s/2, -s*0.2887), (0, s*0.5774)]
    def rotated(tri, angle):
        import math
        ca, sa = math.cos(angle), math.sin(angle)
        return [(x*ca - y*sa, x*sa + y*ca) for x,y in tri]
    def translated(tri, dx, dy):
        return [(x+dx, y+dy) for x,y in tri]
    positions = [(-2.2, 1.6), (0.0, 1.8), (2.3, 1.4),
                 (-2.4,-1.5), (0.1,-1.7), (2.2,-1.3)]
    result = []
    for i, (bx, by) in enumerate(positions):
        angle = rng.uniform(-2.8, 2.8)
        dx = bx + rng.uniform(-0.4, 0.4)
        dy = by + rng.uniform(-0.3, 0.3)
        result.append(translated(rotated(base, angle), dx, dy))
    return result

def render_prologue(params):
    """Sens facile : on réarrange les MÊMES 6 triangles équilatéraux en plusieurs figures ;
    l'aire ne change pas. Mouvements purement plans (≤60°), sans retournement."""
    os.makedirs(params.out_dir, exist_ok=True)
    vrac = _prologue_vrac()                    # positions éparpillées (départ)
    arrs_base = _prologue_arrangements()       # [hexagone, zigzag/éclair, parallélogramme]
    arrs = [vrac] + arrs_base                  # index : 0=vrac, 1=hexagone, 2=zigzag, 3=para
    cols = [PALETTE_A[2], PALETTE_B[0], PALETTE_A[1], PALETTE_B[2], PALETTE_A[4], PALETTE_B[1]]
    rs = getattr(params, 'read_scale', 1.0)
    seq = [('vrac',1.6*rs,0,0),                 # pièces en vrac
           ('mv0',2.1*rs,0,1),                  # vrac → hexagone
           ('h0',1.7*rs,1,1),('m01',2.2*rs,1,2),('h1',1.8*rs,2,2),
           ('m12',2.2*rs,2,3),('h2',1.8*rs,3,3),('cv',_cfg_end('prologue','final',4.0)*rs,3,3)]
    ts = []; t = 0.0
    for nm,du,a,b in seq: ts.append((nm,t,du,a,b)); t += du
    total = t
    bbox = (-3.4,-3.1,3.4,3.1)
    fig,ax,phase = _setup_fig_simple(bbox, params,
        "Réarranger des pièces ne change pas l'aire",
        mx=0.2, my_top=0.6, my_bot=0.6)
    patches = [MPLPoly([(0,0)],closed=True,facecolor=cols[i],edgecolor=INK,lw=1.6)
               for i in range(6)]
    for p in patches: ax.add_patch(p)
    nums = [ax.text(0,0,str(i+1),ha='center',va='center',fontsize=10,color=INK,family='serif')
            for i in range(6)]
    areatag = ax.text(0,-2.95,"aire = 6 triangles — constante",ha='center',va='top',
                      fontsize=12.5,color=SUBTITLE_BROWN,family='serif',weight='bold')
    TITLE = _cfg_merge_strings("prologue", {
        'vrac': "Six pièces identiques",
        'mv0': "Elles s'assemblent…",
        'h0': "Un hexagone", 'm01': "On les déplace…", 'h1': "Un zigzag plein, sans trou",
        'm12': "…encore une autre", 'h2': "Un parallélogramme plein",
        'cv': "Le vrai problème : et la réciproque ?",
    })
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
        for i in range(6):
            ta = arrs[a][i]; tb = arrs[b][i]
            # rotation ≤ 60° (via _align_tri) + translation : mouvement plan, pas de retournement
            interp = interp_pose(ta, _align_tri(ta, tb), f) if a != b else list(ta)
            patches[i].set_xy(interp); patches[i].set_alpha(fade)
            cx = sum(x for x,y in interp)/3; cy = sum(y for x,y in interp)/3
            nums[i].set_position((cx,cy)); nums[i].set_alpha(fade)
        areatag.set_alpha(0.0 if nm in ('vrac','mv0') else fade)
        phase.set_text(TITLE[nm])
        return patches+nums+[areatag,phase]
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
                 alpha=0.0)
    cells=[MPLPoly([(0,0)],closed=True,facecolor=cols[i],edgecolor=INK,lw=1.6) for i in range(3)]
    for c in cells: ax.add_patch(c)
    nums=[ax.text(0,0,str(i+1),ha='center',va='center',fontsize=13,color=INK,family='serif') for i in range(3)]
    wlab=ax.text(0,0,"",ha='center',va='top',fontsize=13,color=SUBTITLE_BROWN,family='serif',weight='bold')
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
        fig,ax,phase=_setup_fig_simple(sc['bbox'], params, "Wallace–Bolyai–Gerwien — deux polygones, même aire",
                                       mx=0.7, my_top=1.5, my_bot=1.9)
        msg=fig.text(0.5,0.075,"",ha='center',va='center',fontsize=13.0,color=INK,family='serif',linespacing=1.5,
                     alpha=0.0)
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
