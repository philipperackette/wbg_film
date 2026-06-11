#!/usr/bin/env python3
"""Resumable build: renders each clip only if missing, then builds the master."""
import argparse, os, subprocess, time, sys
import wbg_animate as W

def dur(f):
    return float(subprocess.check_output(
        ["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",f]).strip())

def have(path):
    try: return os.path.exists(path) and dur(path) > 0.5
    except Exception: return False

def render_all(params):
    b=params.basename; OD=params.out_dir; t0=time.time()
    def log(m): print(f"[{time.time()-t0:6.0f}s] {m}", flush=True)
    P=f"{OD}/{b}"

    if not have(f"{P}_prologue.mp4"):
        log("prologue…"); W.render_prologue(params); log("prologue OK")
    else: log("prologue (skip)")

    if not have(f"{P}_intro.mp4"):
        log("intro…"); W.render_intro(params); log("intro OK")
    else: log("intro (skip)")

    tris_by_tag={'A':[],'B':[]}
    for k,o in enumerate(W._all_method_tris()):
        tris_by_tag[o['tag']].append((k,o))

    for tag in ('A',):
        for k,o in tris_by_tag[tag]:
            lab=f"Triangle {o['idx']+1} de {o['tag']}"
            if not have(f"{P}_methode_{k}.mp4"):
                log(f"methode_{k} ({lab})…")
                W.render_method(params, tri=o["tri"], color=o["color"], detailed=o["detailed"],
                                suffix=f"_{k}", label=lab, fig_vignette=W._vignette_for(o))
                log(f"methode_{k} OK")
            else: log(f"methode_{k} (skip)")
        if not have(f"{P}_colonne_a.mp4"):
            log("colonne_A…")
            W.render_column(params, poly=W.POLY_A, palette=W.PALETTE_A,
                            scene_title="Colonne de largeur 1 — figure A", suffix="_a")
            log("colonne_A OK")
        else: log("colonne_A (skip)")

    for k,o in tris_by_tag['B']:
        lab=f"Triangle {o['idx']+1} de B"
        if not have(f"{P}_methode_{k}.mp4"):
            log(f"methode_{k} ({lab})…")
            W.render_method(params, tri=o["tri"], color=o["color"], detailed=o["detailed"],
                            suffix=f"_{k}", label=lab, fig_vignette=W._vignette_for(o))
            log(f"methode_{k} OK")
        else: log(f"methode_{k} (skip)")

    if not have(f"{P}_methode_2sur3.mp4"):
        log("methode_2sur3…")
        from wbg_core import ear_clip
        trisB_raw=[list(t) for t in ear_clip(list(W.POLY_B))]
        t2=W._reorient_horizontal(trisB_raw[2])
        vig2=dict(poly=[(p.x,p.y) for p in W.POLY_B],
                  tris=[[(p.x,p.y) for p in t] for t in trisB_raw], active_idx=2, palette=W.PALETTE_B)
        W.render_method(params, tri=t2, color=W.PALETTE_B[2], detailed=True, max_den=3,
                        suffix="_2sur3", label="Triangle 2 de B", fig_vignette=vig2)
        log("methode_2sur3 OK")
    else: log("methode_2sur3 (skip)")

    if not have(f"{P}_colonne_b.mp4"):
        log("colonne_B…")
        W.render_column(params, poly=W.POLY_B, palette=W.PALETTE_B,
                        scene_title="Colonne de largeur 1 — figure B", suffix="_b")
        log("colonne_B OK")
    else: log("colonne_B (skip)")

    if not have(f"{P}_fusion.mp4"):
        log("fusion…"); _,_,scF=W.render_fusion(params); log(f"fusion OK ({scF['ncom']} pièces)")
    else: log("fusion (skip)")

    if not have(f"{P}.mp4"):
        log("reassemblage…"); W.render(params); log("reassemblage OK")
    else: log("reassemblage (skip)")
    log("ALL CLIPS DONE")

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="/mnt/user-data/outputs/anim_dissection")
    ap.add_argument("--fps", type=int, default=30)
    a=ap.parse_args()
    params=W.AnimParams(out_dir=a.out_dir, fps=a.fps, make_gif=False)
    os.makedirs(a.out_dir, exist_ok=True)
    render_all(params)
