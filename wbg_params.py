# Réglages faciles pour wbg_animate.py
# Règle éditoriale : tous les sous-titres visibles doivent tenir sur UNE SEULE LIGNE.
# Le détail mathématique est porté par la narration, pas par les textes à l'écran.

SUBTITLE_BROWN = "#7a4a2a"


# Durées de fin de séquence, en secondes.
# Ajuster ici les respirations finales, scène par scène.
END_HOLDS = {
    "prologue": {"final": 3.0},
    "intro": {"final": 2.8},
    "fusion": {"final": 2.6},
    "column_a": {"final": 2.25},
    "column_b": {"final": 2.25},
    "reassembly_AB": {"final": 2.25},
    "reassembly_BA": {"final": 2.25},

    "method": {
        "default_final": 4.4,

        "Triangle 1 de A": 4.6,
        "Triangle 2 de A": 3.8,
        "Triangle 3 de A": 3.8,

        "Triangle 1 de B": 4.6,
        "Triangle 2 de B": 3.8,
        "Triangle 3 de B": 3.8,
        "Triangle 4 de B": 4.8,
    },
}


# Textes de sous-titres affichés à l’écran.
# Format :
#   "clé": "texte"                       pour les scènes simples
#   "clé": ("ligne visible", "")          pour les scènes qui attendent un couple titre/message
#
# Important :
# - ne pas mettre de "\n" ;
# - éviter les textes longs ;
# - laisser la seconde chaîne vide quand on ne veut qu'une seule ligne visible.
SUBTITLE_TEXTS = {
    "prologue": {
        "vrac": "Six pièces identiques",
        "mv0": "Elles s’assemblent…",
        "h0": "Un hexagone",
        "m01": "On les déplace…",
        "h1": "Un zigzag de même aire",
        "m12": "Encore une autre forme…",
        "h2": "Un parallélogramme de même aire",
        "cv": "Le vrai problème : la réciproque",
    },

    "intro": {
        "a": ("Deux polygones…", ""),
        "b": ("Deux formes très différentes", ""),
        "area": ("Mais une même aire ≈ {area}", ""),
        "theo": ("Même aire : peut-on découper et réassembler ?", ""),
        "triA": ("On triangule A : {nA} triangles", ""),
        "triB": ("On triangule B : {nB} triangles", ""),
        "next": ("Chaque triangle devient un rectangle de largeur 1", ""),
    },

    "fusion": {
        "apart": ("Deux découpages du même rectangle", ""),
        "slide": ("On superpose les deux rectangles", ""),
        "neutral": ("Réunion des coupes : {N} pièces communes", ""),
        "revealA": ("Ces {N} pièces redonnent la figure A", ""),
        "holdA": ("A, colorée par sa triangulation", ""),
        "A2rect": ("A se transforme en rectangle commun", ""),
        "holdRectA": ("Rectangle commun — lecture selon A", ""),
        "recolor": ("Les mêmes pièces passent aux couleurs de B", ""),
        "holdRectB": ("Rectangle commun — lecture selon B", ""),
        "rect2B": ("Les mêmes pièces reconstituent B", ""),
        "holdB": ("Équidécomposition : les mêmes pièces composent A et B", ""),
    },

    "column": {
        "start": "Rectangles de largeur 1 — coupes conservées",
        "move": "On empile les rectangles",
        "final": "Colonne de largeur 1",
    },

    "reassembly_AB": {
        "hold_L": "Les pièces communes, disposées comme dans A",
        "hold_M": "Les mêmes pièces dans le rectangle commun",
        "hold_N": "Les mêmes pièces réassemblées en B",
        "move_LM": "A → rectangle de largeur 1",
        "move_MN": "Rectangle de largeur 1 → B",
        "move_LN": "A → B",
    },

    "reassembly_BA": {
        "hold_N": "Les pièces communes, disposées comme dans B",
        "hold_M": "Les mêmes pièces dans le rectangle commun",
        "hold_L": "Les mêmes pièces réassemblées en A",
        "move_NM": "B → rectangle de largeur 1",
        "move_ML": "Rectangle de largeur 1 → A",
        "move_NL": "B → A",
    },

    "method": {
        "global": {
            "intro": ("Triangle → rectangle de largeur 1", ""),

            "midline_cut": ("Ligne des milieux", ""),
            "midline_move": ("Demi-tour → parallélogramme", ""),

            "shear_explain": ("Rationaliser le côté oblique", ""),
            "shear_cut": ("Rationalisation — découpe", ""),
            "shear_move": ("Le côté oblique devient {frac}", ""),

            "q_explain": ("Rendre le côté entier", ""),
            "q_cut": ("Découpe en q = {q} bandes", ""),
            "q_move": ("Empilement : {frac} × {q} = {p}", ""),

            "p_cut": ("Découpe en p = {p} bandes", ""),
            "p_move": ("Empilement → côté = 1", ""),

            "rect_explain": ("Redresser en rectangle", ""),
            "rect_cut": ("Redressement — découpe finale", ""),
            "rect_move": ("Le morceau glisse d’un bloc", ""),

            "rotate_rect": ("On pose le rectangle droit", ""),
            "final": ("Rectangle de largeur 1", ""),
        },

        "Triangle 1 de A": {
            "intro": ("Triangle 1 de A → rectangle", ""),
            "midline_cut": ("Triangle 1 de A — ligne des milieux", ""),
            "midline_move": ("Triangle 1 de A → parallélogramme", ""),
            "shear_explain": ("Triangle 1 de A : oblique → 1/2", ""),
            "shear_cut": ("Triangle 1 de A — découpe oblique", ""),
            "shear_move": ("Le côté oblique devient 1/2", ""),
            "q_explain": ("Triangle 1 de A : deux bandes", ""),
            "q_cut": ("Découpe en 2 bandes", ""),
            "q_move": ("Empilement : 1/2 × 2 = 1", ""),
            "p_cut": ("Côté déjà égal à 1", ""),
            "p_move": ("Aucun empilement final nécessaire", ""),
            "rect_explain": ("Triangle 1 de A : redressement final", ""),
            "rect_cut": ("Triangle 1 de A — découpe finale", ""),
            "rect_move": ("Le morceau glisse d’un bloc", ""),
            "rotate_rect": ("On pose le rectangle droit", ""),
            "final": ("Triangle 1 de A transformé", ""),
        },

        "Triangle 2 de A": {
            "intro": ("Triangle 2 de A → rectangle", ""),
            "midline_cut": ("Triangle 2 de A — ligne des milieux", ""),
            "midline_move": ("Triangle 2 de A → parallélogramme", ""),
            "shear_explain": ("Triangle 2 de A : oblique déjà entière", ""),
            "shear_cut": ("Triangle 2 de A — ajustement", ""),
            "shear_move": ("Le côté oblique devient 1", ""),
            "q_explain": ("Aucune bande supplémentaire", ""),
            "q_cut": ("Pas de découpe en q", ""),
            "q_move": ("Le côté vaut déjà 1", ""),
            "p_cut": ("Pas de découpe en p", ""),
            "p_move": ("Aucun empilement final nécessaire", ""),
            "rect_explain": ("Triangle 2 de A : redressement final", ""),
            "rect_cut": ("Triangle 2 de A — découpe finale", ""),
            "rect_move": ("Le morceau glisse d’un bloc", ""),
            "rotate_rect": ("On pose le rectangle droit", ""),
            "final": ("Triangle 2 de A transformé", ""),
        },

        "Triangle 3 de A": {
            "intro": ("Triangle 3 de A → rectangle", ""),
            "midline_cut": ("Triangle 3 de A — ligne des milieux", ""),
            "midline_move": ("Triangle 3 de A → parallélogramme", ""),
            "shear_explain": ("Triangle 3 de A : oblique → 1/2", ""),
            "shear_cut": ("Triangle 3 de A — découpe oblique", ""),
            "shear_move": ("Le côté oblique devient 1/2", ""),
            "q_explain": ("Triangle 3 de A : deux bandes", ""),
            "q_cut": ("Découpe en 2 bandes", ""),
            "q_move": ("Empilement : 1/2 × 2 = 1", ""),
            "p_cut": ("Côté déjà égal à 1", ""),
            "p_move": ("Aucun empilement final nécessaire", ""),
            "rect_explain": ("Triangle 3 de A : redressement final", ""),
            "rect_cut": ("Triangle 3 de A — découpe finale", ""),
            "rect_move": ("Le morceau glisse d’un bloc", ""),
            "rotate_rect": ("On pose le rectangle droit", ""),
            "final": ("Triangle 3 de A transformé", ""),
        },

        "Triangle 1 de B": {
            "intro": ("Triangle 1 de B → rectangle", ""),
            "midline_cut": ("Triangle 1 de B — ligne des milieux", ""),
            "midline_move": ("Triangle 1 de B → parallélogramme", ""),
            "shear_explain": ("Triangle 1 de B : oblique → 1/2", ""),
            "shear_cut": ("Triangle 1 de B — découpe oblique", ""),
            "shear_move": ("Le côté oblique devient 1/2", ""),
            "q_explain": ("Triangle 1 de B : deux bandes", ""),
            "q_cut": ("Découpe en 2 bandes", ""),
            "q_move": ("Empilement : 1/2 × 2 = 1", ""),
            "p_cut": ("Côté déjà égal à 1", ""),
            "p_move": ("Aucun empilement final nécessaire", ""),
            "rect_explain": ("Triangle 1 de B : redressement final", ""),
            "rect_cut": ("Triangle 1 de B — découpe finale", ""),
            "rect_move": ("Le morceau glisse d’un bloc", ""),
            "rotate_rect": ("On pose le rectangle droit", ""),
            "final": ("Triangle 1 de B transformé", ""),
        },

        "Triangle 2 de B": {
            "intro": ("Triangle 2 de B → rectangle", ""),
            "midline_cut": ("Triangle 2 de B — ligne des milieux", ""),
            "midline_move": ("Triangle 2 de B → parallélogramme", ""),
            "shear_explain": ("Triangle 2 de B : oblique → 1/2", ""),
            "shear_cut": ("Triangle 2 de B — découpe oblique", ""),
            "shear_move": ("Le côté oblique devient 1/2", ""),
            "q_explain": ("Triangle 2 de B : deux bandes", ""),
            "q_cut": ("Découpe en 2 bandes", ""),
            "q_move": ("Empilement : 1/2 × 2 = 1", ""),
            "p_cut": ("Côté déjà égal à 1", ""),
            "p_move": ("Aucun empilement final nécessaire", ""),
            "rect_explain": ("Triangle 2 de B : redressement final", ""),
            "rect_cut": ("Triangle 2 de B — découpe finale", ""),
            "rect_move": ("Le morceau glisse d’un bloc", ""),
            "rotate_rect": ("On pose le rectangle droit", ""),
            "final": ("Triangle 2 de B transformé", ""),
        },

        "Triangle 3 de B": {
            "intro": ("Triangle 3 de B → cas rationnel 2/3", ""),
            "midline_cut": ("Triangle 3 de B — ligne des milieux", ""),
            "midline_move": ("Triangle 3 de B → parallélogramme", ""),
            "shear_explain": ("Triangle 3 de B : oblique → 2/3", ""),
            "shear_cut": ("Triangle 3 de B — découpe oblique", ""),
            "shear_move": ("Le côté oblique devient 2/3", ""),
            "q_explain": ("Trois bandes pour un côté entier", ""),
            "q_cut": ("Découpe en 3 bandes", ""),
            "q_move": ("Empilement : 2/3 × 3 = 2", ""),
            "p_cut": ("Découpe en 2 bandes", ""),
            "p_move": ("Empilement final → côté = 1", ""),
            "rect_explain": ("Triangle 3 de B : redressement final", ""),
            "rect_cut": ("Triangle 3 de B — découpe finale", ""),
            "rect_move": ("Le morceau glisse d’un bloc", ""),
            "rotate_rect": ("On pose le rectangle droit", ""),
            "final": ("Triangle 3 de B transformé", ""),
        },

        "Triangle 4 de B": {
            "intro": ("Triangle 4 de B → rectangle", ""),
            "midline_cut": ("Triangle 4 de B — ligne des milieux", ""),
            "midline_move": ("Triangle 4 de B → parallélogramme", ""),
            "shear_explain": ("Triangle 4 de B : oblique → 1/2", ""),
            "shear_cut": ("Triangle 4 de B — découpe oblique", ""),
            "shear_move": ("Le côté oblique devient 1/2", ""),
            "q_explain": ("Triangle 4 de B : deux bandes", ""),
            "q_cut": ("Découpe en 2 bandes", ""),
            "q_move": ("Empilement : 1/2 × 2 = 1", ""),
            "p_cut": ("Côté déjà égal à 1", ""),
            "p_move": ("Aucun empilement final nécessaire", ""),
            "rect_explain": ("Triangle 4 de B : redressement final", ""),
            "rect_cut": ("Triangle 4 de B — découpe finale", ""),
            "rect_move": ("Le morceau glisse d’un bloc", ""),
            "rotate_rect": ("On pose le rectangle droit", ""),
            "final": ("Triangle 4 de B transformé", ""),
        },
    },
}
