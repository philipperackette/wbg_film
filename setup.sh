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
