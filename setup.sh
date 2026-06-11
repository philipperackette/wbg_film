#!/usr/bin/env bash
# setup.sh — prépare l'environnement conda puis régénère la vidéo WBG complète.
#
# IMPORTANT : ce script N'EMBARQUE PLUS les sources (fini la duplication).
# Il utilise les .py présents DANS CE MÊME DOSSIER :
#     wbg_core.py  wbg_pipeline.py  wbg_animate.py  build_all.py
# Lancer simplement :   bash setup.sh        (sortie : out/wbg_video_complete.mp4)
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

# vérifie que les .py présents portent bien les corrections attendues (sinon stop)
for f in wbg_core.py wbg_pipeline.py wbg_animate.py build_all.py; do
  [ -f "$f" ] || { echo "FICHIER MANQUANT : $f (placez les .py à côté de setup.sh)"; exit 1; }
done
python - <<'PYCHK'
import inspect, wbg_animate as W
src_beats = inspect.getsource(W.method_beats)
src_draw  = inspect.getsource(W._method_draw)
src_fus   = inspect.getsource(W._fusion_frame)
src_pro   = inspect.getsource(W.render_prologue)
src_scene = inspect.getsource(W.build_scene)
src_ds    = inspect.getsource(W._draw_state)
import re
m = re.search(r"linewidth=([0-9.]+)", src_ds)
assert m and float(m.group(1)) >= 1.2,            "bords des pieces trop fins"
assert "state_after" in src_beats,                "REGRESSION: pieces non creees a la coupe"
assert "Marque de coupe PERSISTANTE" in src_draw, "REGRESSION: marque de coupe persistante absente"
assert "recolor" in src_fus,                      "REGRESSION: recoloriage A->B absent (fusion)"
assert "interp_pose(ta, _align_tri(ta, tb), f)" in src_pro, "REGRESSION: prologue sans alignement <=60deg (retournement possible)"
assert "zigzag" in inspect.getsource(W._prologue_arrangements).lower(), "REGRESSION: prologue pas en triangles equilateraux (hexagone/zigzag)"
assert "_step_bar" in src_pro, "REGRESSION: indicateur d'etape minimaliste absent"
assert '"BA"' in src_scene,                       "REGRESSION: sens symetrique B->A absent"
assert "_mover_groups" in inspect.getsource(W._method_timeline), "REGRESSION: dissection pas groupee par transformation"
assert '"∪"' in inspect.getsource(W._fusion_artists), "REGRESSION: union ∪ absente (fusion)"
assert "top_pids" in src_ds, "REGRESSION: piece mobile pas au premier plan"
assert "ra_wv" in src_draw, "REGRESSION: codage d'angle droit du redressement absent"
assert 'path=["N","M","L"]' in src_scene, "REGRESSION: BA pas en rejeu inverse (B a droite, A a gauche)"
print("OK — coupes persistantes, fusion A->B, prologue equilateral plan, etape minimaliste, 1er plan mobile, angle droit, union, B->A inverse, dissection groupee")
PYCHK

mkdir -p out
python build_all.py --out-dir out
echo ">> out/wbg_video_complete.mp4"
