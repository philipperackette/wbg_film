# WBG Film — Wallace–Bolyai–Gerwien Equidecomposition

Python animation pipeline for an educational film illustrating the Wallace–Bolyai–Gerwien theorem.

The generated video is available here:

https://youtu.be/CJGhOOM5CqI

## Purpose

This project generates a pedagogical animation about equidecomposition of plane polygons.

The Wallace–Bolyai–Gerwien theorem states that two polygons with the same area can be cut into finitely many polygonal pieces so that one polygon can be reassembled into the other.

The film illustrates the constructive idea behind the proof:

1. triangulate the two polygons;
2. transform each triangle into a rectangle of width 1;
3. stack these rectangles into a common column;
4. refine the two decompositions into a common set of pieces;
5. reassemble the pieces from one polygon into the other.

## Repository contents

Main files:

- `build_all.py` — renders all clips and assembles the complete video.
- `build_resume.py` — renders the shorter/resume version, if used.
- `wbg_animate.py` — animation scenes and rendering logic.
- `wbg_core.py` — geometric core routines.
- `wbg_params.py` — animation parameters.
- `wbg_pipeline.py` — auxiliary pipeline functions.
- `setup.sh` — environment and dependency checker.
- `script_narration_WBG.md` — narration and production notes.
- `LISEZMOI.txt` — French project notes.
- `MD5SUMS.txt` — checksums for the project files.

Generated videos are written to:

```text
out/
