# Réglages faciles pour wbg_animate.py

# Couleur des sous-titres / indicateurs marrons
SUBTITLE_BROWN = "#7a4a2a"


# Durées de fin de séquence, en secondes.
# Pour les scènes méthode, les clés correspondent aux labels générés par build_all.py.
END_HOLDS = {
    "prologue": {"final": 4.0},
    "intro": {"final": 2.8},
    "fusion": {"final": 2.6},
    "column_a": {"final": 1.25},
    "column_b": {"final": 1.25},
    "reassembly_AB": {"final": 1.25},
    "reassembly_BA": {"final": 1.25},

    "method": {
        "default_final": 4.6,

        "Triangle 1 de A": 4.6,
        "Triangle 2 de A": 3.8,
        "Triangle 3 de A": 3.8,

        "Triangle 1 de B": 4.6,
        "Triangle 2 de B": 4.8,
        "Triangle 3 de B": 3.8,
        "Triangle 4 de B": 4.8,
    },
}


# Textes de sous-titres affichés à l’écran.
# Format général : "clé": ("Titre", "Sous-titre")
# Pour les textes simples : "clé": "texte"
SUBTITLE_TEXTS = {
    "prologue": {
        "vrac": "Six pièces identiques",
        "mv0": "Elles s'assemblent…",
        "h0": "Un hexagone",
        "m01": "On les déplace…",
        "h1": "Un autre hexagone de même aire",
        "m12": "…encore une autre forme",
        "h2": "Un parallélogramme de même aire",
        "cv": "Le vrai problème : et la réciproque ?",
    },

    "intro": {
        "a": ("Deux polygones", "Voici un polygone A."),
        "b": ("Deux polygones", "…et un polygone B, de forme très différente."),
        "area": ("Même aire", "Mais ils ont exactement la MÊME aire ≈ {area}."),
        "theo": (
            "Peut-on les découper en une même collection de pièces ?",
            "Wallace–Bolyai–Gerwien : mêmes aires ⇒ découpage fini\n"
            "et réassemblage exact."
        ),
        "triA": ("Étape 1 — trianguler", "On découpe chaque polygone en triangles. A en donne {nA}."),
        "triB": ("Étape 1 — trianguler", "B de même : {nB} triangles."),
        "next": (
            "Chaque triangle va être transformé en rectangle de largeur 1",
            "Chaque triangle devient un rectangle de largeur 1 ;\n"
            "les rectangles s'empilent ensuite en colonne."
        ),
    },

    "fusion": {
        "apart": (
            "Deux découpages du même rectangle",
            "À gauche : découpage selon A. À droite : découpage selon B."
        ),
        "slide": (
            "On les superpose",
            "Les deux rectangles sont identiques : largeur 1, même hauteur."
        ),
        "neutral": (
            "Réunion des deux découpages",
            "Les coupes de A et de B divisent le rectangle\n"
            "en {N} pièces communes."
        ),
        "revealA": (
            "Ce sont exactement les pièces de A",
            "Regroupées par triangle d'origine, ces {N} pièces redonnent A."
        ),
        "holdA": (
            "La figure A, colorée par sa triangulation",
            "Chaque teinte chaude correspond à un triangle de A."
        ),
        "A2rect": (
            "A se transforme en rectangle commun",
            "Les pièces glissent et tournent, sans déformation."
        ),
        "holdRectA": (
            "Rectangle commun — couleurs de A",
            "Le rectangle est découpé selon A."
        ),
        "recolor": (
            "On passe aux couleurs de B",
            "Les MÊMES pièces sont recoloriées selon la triangulation de B."
        ),
        "holdRectB": (
            "Rectangle commun — couleurs de B",
            "Le même rectangle est maintenant lu selon B."
        ),
        "rect2B": (
            "La figure B est reconstituée",
            "Les pièces repartent et se regroupent en B."
        ),
        "holdB": (
            "Équidécomposition",
            "Les {N} mêmes pièces composent A ET B :\n"
            "Wallace–Bolyai–Gerwien."
        ),
    },

    "column": {
        "start": "Chaque triangle est devenu un rectangle de largeur 1 — coupes comprises",
        "move": "On empile les rectangles ; les marques de découpe sont conservées",
        "final": "Colonne de largeur 1 : les marques de découpe restent visibles",
    },

    "reassembly_AB": {
        "hold_L": "Les {n} pièces communes, disposées comme dans A",
        "hold_M": "Les mêmes pièces réunies en rectangle de largeur 1",
        "hold_N": "Les mêmes pièces réassemblées en B — CQFD",
        "move_LM": "Chaque pièce glisse et tourne : A → rectangle de largeur 1",
        "move_MN": "Les mêmes pièces repartent : rectangle de largeur 1 → B",
        "move_LN": "Les mêmes pièces : A → B",
    },

    "reassembly_BA": {
        "hold_N": "Les {n} pièces communes, disposées comme dans B",
        "hold_M": "Les mêmes pièces réunies en rectangle de largeur 1",
        "hold_L": "Les mêmes pièces réassemblées en A — CQFD",
        "move_NM": "Chaque pièce glisse et tourne : B → rectangle de largeur 1",
        "move_ML": "Les mêmes pièces repartent : rectangle de largeur 1 → A",
        "move_NL": "Les mêmes pièces : B → A",
    },

    "method": {
        "global": {
            "intro": (
                "Triangle → rectangle de largeur 1",
                "Sa plus longue arête sert de base. Objectif : découpes,\n"
                "glissements et rotations, sans déformation."
            ),
            "final": (
                "Rectangle de largeur 1",
                "Largeur exactement 1 ; hauteur = aire ≈ {area}.\n"
                "Ce rectangle s'empilera ensuite dans la colonne."
            ),
        },

        # Exemple de personnalisation pour un triangle précis.
        "Triangle 2 de B": {
            "final": (
                "Rectangle de largeur 1",
                "Largeur exactement 1 ; hauteur = aire ≈ {area}.\n"
                "Ici, le passage par 2/3 a demandé plus d'empilements."
            ),
        },
    },
}
