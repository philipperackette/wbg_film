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

    # ── Triangles de A puis colonneA ──
    for tag in ('A',):
        for k, o in tris_by_tag[tag]:
            lab = f"Triangle {o['idx']+1} de {o['tag']}"
            vig = W._vignette_for(o)
            outs, total, _ = W.render_method(params, tri=o["tri"], color=o["color"],
                                             detailed=o["detailed"], suffix=f"_{k}",
                                             label=lab, fig_vignette=vig)
            done(f"methode_{k} ({lab}{' — détaillé' if o['detailed'] else ''})", outs, total)
        poly = W.POLY_A; pal = W.PALETTE_A
        outs, total = W.render_column(params, poly=poly, palette=pal,
                                      scene_title="Colonne de largeur 1 — figure A",
                                      suffix="_a")
        done("colonne_A", outs, total)

    # ── Triangles de B (sans T2) puis 2/3 (= T2) puis colonneB ──
    for k, o in tris_by_tag['B']:
        lab = f"Triangle {o['idx']+1} de B"
        vig = W._vignette_for(o)
        outs, total, _ = W.render_method(params, tri=o["tri"], color=o["color"],
                                         detailed=o["detailed"], suffix=f"_{k}",
                                         label=lab, fig_vignette=vig)
        done(f"methode_{k} ({lab}{' — détaillé' if o['detailed'] else ''})", outs, total)

    # B T2 (idx=2) : rationalisation 2/3 — dernière dissection de B, avant colonneB
    print("— méthode 2/3 : triangle 2 de B (rationalisation réelle p=2, q=3)", flush=True)
    from wbg_core import ear_clip
    trisB_raw = [list(t) for t in ear_clip(list(W.POLY_B))]
    t2 = W._reorient_horizontal(trisB_raw[2])
    vig2 = dict(poly=[(p.x,p.y) for p in W.POLY_B],
                tris=[[(p.x,p.y) for p in t] for t in trisB_raw],
                active_idx=2, palette=W.PALETTE_B)
    outs, total, _ = W.render_method(params, tri=t2, color=W.PALETTE_B[2],
                                     detailed=True, max_den=3, suffix="_2sur3",
                                     label="Triangle 2 de B",
                                     fig_vignette=vig2)
    done("methode_2sur3 (triangle B T2, rationalisation 2/3)", outs, total)

    # colonneB après tous les triangles de B (y compris T2)
    outs, total = W.render_column(params, poly=W.POLY_B, palette=W.PALETTE_B,
                                  scene_title="Colonne de largeur 1 — figure B",
                                  suffix="_b")
    done("colonne_B", outs, total)

    print("— fusion (superposition des deux découpages)", flush=True)
    outs, total, sc = W.render_fusion(params)
    done(f"fusion ({sc['ncom']} pièces communes)", outs, total)

    print("— réassemblage (A → rectangle → B)", flush=True)
    outs, sc = W.render(params); done("reassemblage", outs, sc["total"])

    print("— réassemblage symétrique (B → rectangle → A, couleurs de B)", flush=True)
    outs, sc = W.render(params, direction="BA"); done("reassemblage_BA", outs, sc["total"])
    return log


def build_master(out_dir, basename):
    import glob, re
    b = basename
    meth = [p for p in glob.glob(f"{out_dir}/{b}_methode_*.mp4")
            if re.search(r"_methode_(\d+)\.mp4$", p)]
    meth.sort(key=lambda p: int(re.search(r"_methode_(\d+)\.mp4$", p).group(1)))
    import wbg_animate as W
    all_tris = W._all_method_tris()
    nA = sum(1 for o in all_tris if o['tag']=='A')
    methA = meth[:nA]; methB = meth[nA:]
    # Sequence: prologue intro | A tris | colonneA | B tris | 2sur3 | colonneB | fusion | reassembly
    clips = ([f"{out_dir}/{b}_prologue.mp4", f"{out_dir}/{b}_intro.mp4"]
             + methA
             + [f"{out_dir}/{b}_colonne_a.mp4"]
             + methB
             + [f"{out_dir}/{b}_methode_2sur3.mp4",
                f"{out_dir}/{b}_colonne_b.mp4",
                f"{out_dir}/{b}_fusion.mp4",
                f"{out_dir}/{b}.mp4",
                f"{out_dir}/{b}_BA.mp4"])
    for c in clips:
        assert os.path.exists(c), f"clip manquant : {c}"
    durs = [dur(f) for f in clips]
    nmA = len(methA); nmB = len(methB)
    ds = ([0.6, 0.6]          # prologue→intro, intro→méthode A0
          + [0.4]*(nmA-1)     # entre les triangles A
          + [0.7]             # dernier A → colonneA
          + [0.6]             # colonneA → méthode B0
          + [0.4]*(nmB-1)     # entre les triangles B
          + [0.5]             # dernier B → 2sur3
          + [0.7]             # 2sur3 → colonneB
          + [0.9, 0.6, 0.6])  # colonneB→fusion, fusion→réassemblage, réassemblage→symétrique
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
