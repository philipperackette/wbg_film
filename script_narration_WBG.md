# Script de narration — Théorème de Wallace–Bolyai–Gerwien
### Vidéo : `wbg_video_complete.mp4` — durée ~5 min 23

> **Convention de lecture**
> Les timecodes sont ceux du master avec fondus enchaînés.
> Les indications *en italique* décrivent ce que l'on voit à l'écran.
> Les textes en clair sont à lire à voix haute.
> ⏸ = moment de silence (laissez l'animation respirer).
> L'affichage à l'écran est volontairement **minimal** : un petit indicateur « étape k/6 · … » en bas situe l'avancement dans la démarche. Tout le commentaire est porté par cette narration (les longues légendes du bas ont été retirées).

---

## 00:00 — PROLOGUE : le sens facile

*Six triangles équilatéraux colorés, numérotés 1 à 6, forment un hexagone régulier.*

Voici six pièces identiques — six triangles équilatéraux. Assemblées, elles forment un **hexagone**.

*Les pièces glissent et pivotent — sans jamais se retourner — pour former une silhouette en zigzag, pleine, sans trou.*

On les déplace : chacune tourne d'un sixième de tour au plus, et glisse à sa place. Mêmes six pièces, mais cette fois un **zigzag**.

*Les six triangles quittent le zigzag et se réassemblent en un parallélogramme plein.*

Encore une forme différente — un **parallélogramme**. ⏸

*L'aire affichée, « 6 triangles — constante », ne bouge jamais.*

C'est évident : réarranger des pièces ne change pas l'aire. Elle vaut toujours la somme des aires des pièces, quelle que soit la forme obtenue.

Mais la question réciproque est bien plus difficile. On se donne **deux polygones de même aire** — ils peuvent être complètement différents. Peut-on **toujours** découper l'un en morceaux pour reconstituer exactement l'autre ? C'est ça, le vrai problème.

---

## 00:15 — INTRO : les deux figures, même aire, le théorème

*Deux polygones apparaissent : un pentagone A (tons chauds) et un hexagone B (tons froids).*

Voici nos deux figures. A est un pentagone, B est un hexagone. Leurs formes sont très différentes. Et pourtant, leur aire est **exactement la même**.

*L'aire est affichée pour chaque figure.*

⏸

*Les deux figures se rapprochent. Le signe « = aire » s'affiche.*

Le théorème de **Wallace–Bolyai–Gerwien**, démontré au début du XIX° siècle indépendamment par ces trois mathématiciens, affirme que la réponse est toujours **oui** : deux polygones de même aire sont toujours équidécomposables.

*Les triangulations apparaissent sur chaque figure.*

La démonstration repose sur une idée simple : on **triangule** chaque polygone — on le découpe en triangles. Puis on montre comment transformer **n'importe quel triangle** en un rectangle de largeur exactement 1. Une fois que les deux figures sont toutes les deux des empilements de rectangles de largeur 1 et de même hauteur totale, on peut lire le découpage commun.

---

## 00:38 — MÉTHODE : triangle 1 de A *(détaillé — ~47 s)*

*Un triangle du pentagone est isolé et agrandi.*

Voici comment transformer ce triangle en rectangle de largeur 1. C'est le cœur de la construction — on va le voir étape par étape.

*Trait rouge sur la ligne des milieux. Immédiatement après, deux pièces séparées.*

**Étape 1 — la ligne des milieux.** On joint les milieux des deux côtés qui encadrent le sommet, et on coupe. On obtient un petit triangle et un trapèze.

*Le petit triangle pivote de 180° et vient se coller sous le trapèze.*

Le petit triangle fait un **demi-tour** et se place de l'autre côté. Le trapèze et le triangle forment maintenant un **parallélogramme**.

*Écran d'explication : côté oblique irrationnel.*

**Étape 2 — rationaliser le côté oblique.** Ce parallélogramme a un côté oblique de longueur irrationnelle. On ne peut pas le diviser en bandes entières comme ça. Il faut d'abord ajuster ce côté pour lui donner une longueur **rationnelle**.

*Trait rouge, une fine tranche se sépare à droite.*

Une seule coupe isole le petit coin qui dépasse.

*La tranche glisse de l'autre côté.*

On le déplace de l'autre côté. Le côté oblique mesure maintenant exactement **1** — c'est un entier, pas besoin d'aller plus loin pour ce triangle.

*Écran d'explication : le redressement final.*

**Étape 3 — redresser en rectangle.** Le côté oblique vaut 1. Il reste à « redresser » le parallélogramme en rectangle.

*Écran d'explication : le redressement final.*

**Étape 3 — redresser en rectangle.** Regardez ce parallélogramme : il a la bonne largeur — 1 — mais ses côtés sont encore obliques. Imaginez un jeu de cartes légèrement étalé en biais. On le tranche en bandes de largeur 1, et le morceau qui dépasse à droite vient combler le vide à gauche : c'est l'**empilement final** de la figure 8.4 de Boyer.

*Trait rouge vertical. Immédiatement après, les pièces découpées sont visibles séparées.*

Une seule coupe verticale sépare la partie qui dépasse.

*Le bloc qui dépasse glisse d'un seul mouvement vers la gauche.*

Tout ce bloc subit **exactement la même translation** : il glisse donc d'un seul tenant, et vient se loger dans le creux de gauche. Ce glissement horizontal ne déforme rien. ⏸

*Rotation finale : le rectangle se pose à l'horizontale. Un petit carré d'angle droit marque brièvement un coin du rectangle, puis s'efface.*

On pose le rectangle bien droit. Le petit carré confirme l'**angle droit** : c'est bien un rectangle — **largeur exactement 1**, hauteur égale à l'aire du triangle. ⏸

*Vue d'ensemble avec la vignette du pentagone.*

Ce rectangle, c'est le triangle 1 de A, transformé. On fait pareil pour les deux autres triangles de A.

---

## 01:24 — MÉTHODE : triangles 2 et 3 de A *(résumé rapide — ~17 s chacun)*

*Triangle 2 puis triangle 3, transformation accélérée.*

Les deux autres triangles du pentagone suivent exactement le même procédé. Pour eux, la rationalisation donne directement un côté entier valant 1, donc les étapes d'empilement ne sont pas nécessaires. ⏸

---

## 01:58 — COLONNE A

*Les trois rectangles s'empilent en une colonne de largeur 1.*

Les trois rectangles obtenus s'empilent. On obtient une **colonne de largeur 1** dont la hauteur est exactement l'aire du pentagone A. ⏸

---

## 02:01 — MÉTHODE : triangle 1 de B *(détaillé — ~58 s)*

*On passe à l'hexagone B. Premier triangle isolé.*

Même chose maintenant pour l'hexagone B. Premier triangle.

Les étapes sont identiques — ligne des milieux, demi-tour, rationalisation, redressement. ⏸

---

## 02:59 — MÉTHODE : triangles 2 et 3 de B *(rapides — ~17 s chacun)*

*Triangles 2 et 3 de B, transformés rapidement.*

Triangles 2 et 3 de B — même procédé, côté déjà entier. ⏸

---

## 03:33 — MÉTHODE : triangle 4 de B *(détaillé, cas 2/3 — ~64 s)*

*Triangle 4 de B isolé. Le plus grand triangle de B.*

Voici le triangle 4 de B — le plus grand. Et là, la rationalisation ne donne **pas** un entier directement : le côté oblique vaut **2/3**.

*Trait rouge. Deux pièces. Le coin glisse.*

On coupe et on déplace le coin. Le côté oblique vaut 2/3 — rationnel, mais pas encore entier.

*Écran d'explication : couper en q = 3 bandes.*

Pour se ramener à un côté entier, on va **empiler** des copies. L'idée : si on coupe en **3 bandes** égales et qu'on les empile, le côté passe de 2/3 à 2/3 × 3 = **2**.

*Trait rouge : trois coupures verticales. Puis les bandes s'empilent — chaque bande va à sa propre place.*

Trois coupes, puis empilement. Chaque bande rejoint une position différente, donc elles montent **l'une après l'autre** sur la pile. ⏸ Le côté oblique vaut maintenant **2** — un entier !

*Écran d'explication : redécouper en p = 2.*

Mais on voulait un côté égal à **1**, pas 2. On recoupe donc ce grand parallélogramme en **2 moitiés** et on les empile.

*Deux coupes, puis les deux moitiés s'empilent.*

⏸ Le côté oblique vaut maintenant **1**. Exactement 1.

*Écran d'explication avant le redressement.*

Maintenant, même si ce parallélogramme a traversé bien plus d'étapes que le précédent, le principe de l'empilement final — figure 8.4 — est **exactement le même** : on tranche en bandes de largeur 1, et la partie qui dépasse vient s'empiler à gauche.

Ici, parce que le parallélogramme est le résultat de plusieurs empilements successifs — trois bandes, puis deux — la partie qui dépasse contient **plusieurs petites pièces**. Mais elles appartiennent toutes à la même bande qui dépasse.

*Trait rouge vertical. Les pièces découpées apparaissent séparées.*

Une coupe sépare la bande qui dépasse à droite.

*Le bloc qui dépasse glisse d'un seul mouvement vers la gauche.*

Toutes ces pièces subissent **la même translation** : elles glissent donc **ensemble, d'un bloc**, et viennent se loger à gauche. ⏸ C'est exactement la figure 8.4 : on n'a pas déplacé les pièces une par une, mais le morceau qui dépasse **en entier**. Aucune déformation — translation pure.

*Rotation finale, rectangle posé droit. Le carré d'angle droit apparaît brièvement à un coin.*

On pose le rectangle droit — l'angle droit marqué confirme le rectangle. **Largeur exactement 1.** ⏸

---

## 04:36 — COLONNE B

*Les quatre rectangles de B s'empilent.*

Les quatre rectangles de B s'empilent. La colonne de B a exactement la même largeur — 1 — et la même hauteur que la colonne de A, puisque les deux polygones ont la même aire. ⏸

---

## 04:40 — FUSION : le découpage commun

*À gauche, le rectangle de A (traits orange). Au centre, le symbole **∪**. À droite, le même rectangle découpé selon B (traits bleus).*

Voici les deux colonnes — c'est **le même rectangle de largeur 1**, découpé de deux façons différentes : les traits orange montrent les coupes de A, les traits bleus celles de B. Le symbole **∪** rappelle qu'on va prendre la **réunion** des deux découpages.

*Les deux rectangles se rapprochent et se superposent.*

On les superpose. Les deux découpages coexistent maintenant dans le même rectangle.

*Le rectangle avec les deux grilles, sans couleur intérieure.*

Ensemble, les coupes de A et de B divisent le rectangle en **81 pièces communes** — pour l'instant sans couleur. Ce sont ces pièces qui vont constituer le découpage.

*Les pièces s'allument progressivement aux couleurs chaudes de A. La figure A se reconstitue.*

Ces 81 pièces, regroupées selon leur triangle d'origine dans A, redonnent exactement **la figure A**, colorée par sa triangulation.

*La figure A se déforme lentement pour remplir le rectangle.*

Et maintenant, ces mêmes pièces vont se déplacer pour remplir le rectangle commun — toujours aux couleurs de A.

*Le rectangle colorié selon A.*

⏸

*Les couleurs changent progressivement, des tons chauds (A) vers les tons froids (B).*

On recolorie chaque pièce selon le triangle de B auquel elle appartient.

*Le rectangle aux couleurs de B.*

⏸

*Les pièces repartent et se regroupent en l'hexagone B, aux couleurs de B.*

Ces mêmes pièces — les 81 mêmes — se regroupent en **la figure B**. C'est l'**équidécomposition** : les deux polygones sont constitués exactement des mêmes pièces. Wallace–Bolyai–Gerwien.

---

## 05:09 — RÉASSEMBLAGE A → B

*À gauche A, au centre le rectangle, à droite B. Les pièces (couleurs de A) glissent de A vers le rectangle.*

On voit maintenant le processus en entier, avec les deux figures côte à côte. Les pièces quittent le pentagone A, traversent le rectangle de largeur 1, et arrivent dans l'hexagone B.

*Les pièces s'immobilisent dans le rectangle.*

⏸

*Les pièces repartent du rectangle vers B.*

Mêmes pièces, autre destination. ⏸

---

## 05:22 — RÉASSEMBLAGE B → A *(si rendu)*

*Disposition identique au sens précédent : A à gauche, le rectangle au centre, B à droite. Mais cette fois les pièces partent de **B, à droite** (aux couleurs de B) et reconstituent **A, à gauche**.*

Et dans l'autre sens : les pièces quittent B, à droite, traversent le rectangle de largeur 1, et reconstituent A, à gauche. C'est exactement le film précédent **rejoué à l'envers**, avec les couleurs de B. Le théorème est **symétrique** — l'équidécomposition va dans les deux sens. ⏸

---

*Fin.*

---

## Notes de production

| Timecode | Clip | Durée |
|---|---|---|
| 00:00 | Prologue (6 triangles équilatéraux : hexagone → zigzag plein → parallélogramme) | 16 s |
| 00:15 | Intro | 23 s |
| 00:38 | Méthode A1 (détaillé, h=1) | 47 s |
| 01:24 | Méthode A2 (rapide) | 17 s |
| 01:41 | Méthode A3 (rapide) | 17 s |
| 01:58 | Colonne A | 4 s |
| 02:01 | Méthode B1 (détaillé) | 58 s |
| 02:59 | Méthode B2 (rapide) | 17 s |
| 03:16 | Méthode B3 (rapide) | 17 s |
| 03:33 | Méthode B4 (détaillé, h=2/3) | 64 s |
| 04:36 | Colonne B | 4 s |
| 04:40 | Fusion | 30 s |
| 05:09 | Réassemblage A→B | 14 s |
| 05:22 | Réassemblage B→A (B à droite, rejeu inversé) | ~14 s |

> Les timecodes sont indicatifs (≈ ±2 s) : le prologue dure désormais ~16 s, ce qui peut décaler légèrement la suite.

**Points d'attention à l'oral :**
- Le prologue utilise 6 triangles équilatéraux : hexagone plein, zigzag plein sans trou, puis parallélogramme plein ; tous les mouvements sont des rotations ≤ 60° dans le plan — **aucun retournement**, rien « en entourloupe ».
- L'affichage du bas est minimal (indicateur « étape k/6 ») : c'est la **narration** qui porte tout le propos ; n'hésitez pas à développer.
- Les triangles détaillés (A1, B1, B4) demandent le plus de narration ; laisser les silences ⏸ pour que les animations individuelles respirent.
- Empilements/redressement : les pièces bougent par GROUPES (même transformation = même mouvement), et **le morceau qui bouge passe toujours au premier plan**. Laisser chaque bloc finir son glissement avant de parler du suivant.
- Redressement : un **codage d'angle droit** apparaît au coin du rectangle obtenu, puis s'efface.
- La fusion est le climax : ralentir la voix sur « les 81 mêmes pièces » ; le symbole **∪** marque la réunion des deux découpages.
