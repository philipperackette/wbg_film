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
    for k, o in enumerate(W._all_method_tris()):
        lab = f"Triangle {o['idx']+1} de {o['tag']}"
        outs, total, _ = W.render_method(params, tri=o["tri"], color=o["color"],
                                         detailed=o["detailed"], suffix=f"_{k}",
                                         label=lab)
        done(f"methode_{k} ({lab}{' — détaillé' if o['detailed'] else ''})",
             outs, total)

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
    clips = ([f"{out_dir}/{b}_prologue.mp4", f"{out_dir}/{b}_intro.mp4"]
             + meth
             + [f"{out_dir}/{b}_methode_2sur3.mp4", f"{out_dir}/{b}_colonne.mp4",
                f"{out_dir}/{b}_fusion.mp4", f"{out_dir}/{b}.mp4"])
    for c in clips:
        assert os.path.exists(c), f"clip manquant : {c}"
    durs = [dur(f) for f in clips]
    # transitions : prologue→intro, intro→méthode0, (entre méthodes), dernière méthode→2/3,
    # 2/3→colonne, colonne→fusion (marquée), fusion→réassemblage
    nmeth = len(meth)
    ds = [0.6, 0.6] + [0.4] * (nmeth - 1) + [0.6, 0.6, 0.9, 0.6]
    assert len(ds) == len(clips) - 1, (len(ds), len(clips))
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
