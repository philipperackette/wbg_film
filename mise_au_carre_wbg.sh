#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# Mise au carré de la documentation et des fichiers de livraison
# Dossier attendu :
# /Users/professeurrackette/Desktop/wbg_film
# ============================================================

PROJECT_DIR="/Users/professeurrackette/Desktop/wbg_film"
cd "$PROJECT_DIR"

echo "=== Vérification du dossier courant ==="
pwd
echo

# ------------------------------------------------------------
# 1. Vérification des fichiers indispensables
# ------------------------------------------------------------

REQUIRED_FILES=(
  "build_all.py"
  "build_resume.py"
  "wbg_animate.py"
  "wbg_core.py"
  "wbg_params.py"
  "wbg_pipeline.py"
  "setup.sh"
  "LISEZMOI.txt"
  "script_narration_WBG.md"
)

echo "=== Vérification des fichiers requis ==="
for f in "${REQUIRED_FILES[@]}"; do
  if [[ ! -f "$f" ]]; then
    echo "ERREUR : fichier manquant : $f"
    exit 1
  fi
  echo "OK : $f"
done
echo

# ------------------------------------------------------------
# 2. Sauvegarde des fichiers de documentation et checksums
# ------------------------------------------------------------

BACKUP_DIR="backup_doc_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

cp -p LISEZMOI.txt "$BACKUP_DIR/LISEZMOI.txt"
cp -p script_narration_WBG.md "$BACKUP_DIR/script_narration_WBG.md"
cp -p MD5SUMS.txt "$BACKUP_DIR/MD5SUMS.txt" 2>/dev/null || true
cp -p setup.sh "$BACKUP_DIR/setup.sh"

echo "=== Sauvegarde créée dans : $BACKUP_DIR ==="
echo

# ------------------------------------------------------------
# 3. Correction de setup.sh :
#    - vérifie les 6 fichiers Python principaux
#    - rend le script plus explicite
# ------------------------------------------------------------

cat > setup.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

echo "=== WBG film : vérification de l'environnement ==="

# Vérification Python
if ! command -v python >/dev/null 2>&1; then
  echo "ERREUR : python est introuvable dans cet environnement."
  echo "Active d'abord l'environnement conda, par exemple :"
  echo "conda activate wbgvideo"
  exit 1
fi

echo "Python utilisé : $(which python)"
python --version
echo

# Vérification ffmpeg
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ERREUR : ffmpeg est introuvable."
  echo "Installe-le par exemple avec :"
  echo "brew install ffmpeg"
  exit 1
fi

echo "ffmpeg trouvé : $(which ffmpeg)"
echo

# Vérification des fichiers Python du projet
REQUIRED_PY=(
  "build_all.py"
  "build_resume.py"
  "wbg_animate.py"
  "wbg_core.py"
  "wbg_params.py"
  "wbg_pipeline.py"
)

echo "=== Vérification des fichiers Python ==="
for f in "${REQUIRED_PY[@]}"; do
  if [[ ! -f "$f" ]]; then
    echo "ERREUR : fichier manquant : $f"
    exit 1
  fi
  echo "OK : $f"
done
echo

# Vérification des dépendances Python
echo "=== Vérification des modules Python ==="
python - <<'PY'
modules = [
    "numpy",
    "matplotlib",
    "moviepy",
]

missing = []

for m in modules:
    try:
        __import__(m)
        print(f"OK : {m}")
    except Exception as e:
        print(f"MANQUANT ou ERREUR : {m} -> {e}")
        missing.append(m)

if missing:
    print()
    print("Installe les dépendances manquantes avec par exemple :")
    print("pip install numpy matplotlib moviepy")
    raise SystemExit(1)
PY

echo
echo "=== Environnement prêt ==="
echo "Pour générer la vidéo complète :"
echo "python build_all.py"
echo
echo "Pour générer uniquement le résumé si prévu par le projet :"
echo "python build_resume.py"
EOF

chmod +x setup.sh

echo "=== setup.sh corrigé ==="
echo

# ------------------------------------------------------------
# 4. Calcul de la durée réelle du master vidéo, si présent
# ------------------------------------------------------------

MASTER_VIDEO="out/wbg_video_complete.mp4"
REAL_DURATION_SECONDS="inconnue"
REAL_DURATION_HUMAN="inconnue"

if [[ -f "$MASTER_VIDEO" ]] && command -v ffprobe >/dev/null 2>&1; then
  REAL_DURATION_SECONDS="$(ffprobe -v error -show_entries format=duration -of default=nk=1:nw=1 "$MASTER_VIDEO" | awk '{printf "%.2f", $1}')"

  # conversion en min/sec arrondies
  TOTAL_ROUNDED="$(printf "%.0f" "$REAL_DURATION_SECONDS")"
  MINUTES=$((TOTAL_ROUNDED / 60))
  SECONDS=$((TOTAL_ROUNDED % 60))
  REAL_DURATION_HUMAN="$(printf "%d min %02d" "$MINUTES" "$SECONDS")"
fi

echo "=== Durée master détectée : $REAL_DURATION_HUMAN ($REAL_DURATION_SECONDS s) ==="
echo

# ------------------------------------------------------------
# 5. Remplacement de LISEZMOI.txt par une version cohérente
# ------------------------------------------------------------

cat > LISEZMOI.txt <<EOF
WBG FILM — LISEZMOI

Dossier de projet :
$PROJECT_DIR

Ce dossier contient les sources Python, la documentation de narration,
les fichiers de paramétrage et, si présent, le dossier out/ contenant les
vidéos générées.

FICHIERS PYTHON À CONSERVER DANS CE DOSSIER

Les 6 fichiers Python principaux doivent rester ensemble :

- build_all.py
- build_resume.py
- wbg_animate.py
- wbg_core.py
- wbg_params.py
- wbg_pipeline.py

Le fichier setup.sh permet de vérifier rapidement l'environnement.

ENVIRONNEMENT

L'environnement conda attendu est par exemple :

    conda activate wbgvideo

Vérification :

    ./setup.sh

Génération de la vidéo complète :

    python build_all.py

Génération du résumé, si utilisé :

    python build_resume.py

SORTIES VIDÉO

Les vidéos générées sont placées dans le dossier :

    out/

Le master principal attendu est :

    out/wbg_video_complete.mp4

Durée actuellement détectée du master, si présent lors de cette mise à jour :

    $REAL_DURATION_HUMAN

POINT IMPORTANT SUR LE PROLOGUE

Le prologue part de 6 triangles équilatéraux congruents.
Certaines zones sont ensuite subdivisées, ce qui produit 9 pièces visibles
numérotées 1 à 9. Il n'y a donc pas contradiction entre :

- la structure géométrique de départ : 6 triangles équilatéraux ;
- le découpage final visible : 9 pièces colorées.

CHECKSUMS

Le fichier MD5SUMS.txt est régénéré par le script mise_au_carre_wbg.sh.
Après modification des sources ou de la documentation, il faut le régénérer.

ARCHIVE DE LIVRAISON

Pour produire une archive propre sans fichiers temporaires :

    zip -r ../wbg_film_clean.zip . \\
      -x "__pycache__/*" \\
      -x ".git/*" \\
      -x "__MACOSX/*" \\
      -x "*.DS_Store"

Si l'on veut exclure les vidéos générées, ajouter aussi :

      -x "out/*"

NOTES

Les fichiers suivants sont volontairement exclus d'une archive propre :

- __pycache__/
- .DS_Store
- __MACOSX/
- .git/

Le dossier out/ peut être conservé si l'archive doit contenir les rendus vidéo.
EOF

echo "=== LISEZMOI.txt réécrit ==="
echo

# ------------------------------------------------------------
# 6. Correction ciblée du script de narration
#    On ne remplace pas toute la narration littéraire :
#    on ajoute un bloc de cohérence en tête.
# ------------------------------------------------------------

TMP_NARRATION="$(mktemp)"

cat > "$TMP_NARRATION" <<EOF
# Script de narration — WBG film

> Documentation remise d'équerre automatiquement le $(date +"%Y-%m-%d").
>
> Durée du master détectée, si le fichier \`out/wbg_video_complete.mp4\` existe :
> **$REAL_DURATION_HUMAN**.
>
> Remarque de cohérence :
> le prologue part de **6 triangles équilatéraux congruents**.
> Certaines zones sont subdivisées pour produire **9 pièces visibles**
> numérotées 1 à 9. Les pièces visibles ne sont donc pas nécessairement
> toutes des triangles équilatéraux entiers.

## Table de cohérence technique

Les scènes actuellement attendues par le montage sont les suivantes.

| Partie | Commentaire documentaire |
|---|---|
| Prologue | 6 triangles équilatéraux de base, subdivisés en 9 pièces visibles |
| Introduction | Présentation du but du film |
| Méthode A | Les triangles effectivement utilisés dépendent de l'ordre défini dans \`build_all.py\` |
| Colonne A | Assemblage / lecture de la colonne A |
| Méthode B | Les triangles effectivement utilisés dépendent de l'ordre défini dans \`build_all.py\` |
| Cas 2/3 | Dans l'état vérifié, le cas 2/3 correspond au triangle 3 de B |
| Colonne B | Assemblage / lecture de la colonne B |
| Fusion | Fusion des constructions |
| Réassemblage A→B | Passage de A vers B |
| Réassemblage B→A | Passage de B vers A |
| Fin | Conclusion |

## Timecodes indicatifs vérifiés

Ces timecodes sont indicatifs : ils doivent être régénérés si les durées des clips
ou les fondus changent dans le code.

| Scène | Début indicatif |
|---|---:|
| Prologue | 00:00 |
| Intro | 00:14 |
| Méthode A, clip 0 | 00:33 |
| Méthode A, clip 1 | 00:56 |
| Méthode A, clip 2 | 01:18 |
| Colonne A | 02:00 |
| Méthode B, clip 3 | 02:06 |
| Méthode B, clip 4 | 02:28 |
| Méthode B, clip 5 | 02:52 |
| Méthode 2/3 | 03:44 |
| Colonne B | 04:42 |
| Fusion | 04:48 |
| Réassemblage A→B | 05:15 |
| Réassemblage B→A | 05:31 |
| Fin approximative | $REAL_DURATION_HUMAN |

---

EOF

# On conserve l'ancien contenu sous le nouveau bloc, mais on évite de dupliquer
# le même en-tête si le script a déjà été passé.
awk '
BEGIN {skip=0}
/^# Script de narration — WBG film/ {skip=1; next}
/^---$/ && skip==1 {skip=0; next}
skip==0 {print}
' script_narration_WBG.md >> "$TMP_NARRATION"

mv "$TMP_NARRATION" script_narration_WBG.md

echo "=== script_narration_WBG.md complété avec un bloc de cohérence ==="
echo

# ------------------------------------------------------------
# 7. Nettoyage des fichiers temporaires locaux
# ------------------------------------------------------------

echo "=== Nettoyage des fichiers temporaires ==="
rm -rf __pycache__
find . -name ".DS_Store" -delete
find . -name "__MACOSX" -type d -prune -exec rm -rf {} +
echo "OK"
echo

# ------------------------------------------------------------
# 8. Régénération de MD5SUMS.txt
# ------------------------------------------------------------

echo "=== Régénération de MD5SUMS.txt ==="

# Sur macOS, md5 fonctionne différemment de md5sum.
# On génère un format proche de md5sum : hash + deux espaces + fichier.
{
  for f in \
    build_all.py \
    build_resume.py \
    wbg_animate.py \
    wbg_core.py \
    wbg_params.py \
    wbg_pipeline.py \
    setup.sh \
    LISEZMOI.txt \
    script_narration_WBG.md
  do
    if [[ -f "$f" ]]; then
      HASH="$(md5 -q "$f")"
      printf "%s  %s\n" "$HASH" "$f"
    fi
  done
} > MD5SUMS.txt

cat MD5SUMS.txt
echo

# ------------------------------------------------------------
# 9. Vérification immédiate des checksums
# ------------------------------------------------------------

echo "=== Vérification immédiate des MD5 ==="

while read -r HASH FILE; do
  [[ -z "${HASH:-}" || -z "${FILE:-}" ]] && continue
  CURRENT="$(md5 -q "$FILE")"
  if [[ "$CURRENT" != "$HASH" ]]; then
    echo "FAILED : $FILE"
    exit 1
  fi
  echo "OK : $FILE"
done < MD5SUMS.txt

echo

# ------------------------------------------------------------
# 10. Création optionnelle d'une archive propre
# ------------------------------------------------------------

ARCHIVE="../wbg_film_clean_$(date +%Y%m%d_%H%M%S).zip"

echo "=== Création d'une archive propre ==="
zip -r "$ARCHIVE" . \
  -x "__pycache__/*" \
  -x ".git/*" \
  -x "__MACOSX/*" \
  -x "*.DS_Store" \
  >/dev/null

echo "Archive créée : $ARCHIVE"
echo

echo "=== Terminé ==="
echo "Fichiers mis à jour :"
echo "- setup.sh"
echo "- LISEZMOI.txt"
echo "- script_narration_WBG.md"
echo "- MD5SUMS.txt"
echo
echo "Sauvegarde disponible dans : $BACKUP_DIR"