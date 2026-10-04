# Tableau de bord — « Où peut-on installer du photovoltaïque au sol en Wallonie ? »

Pendant du tableau de bord éolien
([`../onwind_potential_wallonia/infographic_plan.md`](../onwind_potential_wallonia/infographic_plan.md)),
dont il reprend la charte, la grammaire (carte à gauche, fiche à droite, frise
d'étapes en haut, « Et si… ? » sous la carte) et le principe : **une seule
source**, les chiffres sortent du même calcul que le rapport
(`workflow_pv_wal/scripts/pv_lib.py`) et la construction échoue s'ils
divergent.

Tout est en français. Les chiffres cités ici sont indicatifs.

## 1. Ce qui change par rapport à l'éolien

- **Pas d'éoliennes à placer.** Le potentiel est une surface multipliée par une
  densité ; l'étape « placer les machines » devient « assez grand pour un
  parc » (1 ha d'un seul tenant, 60 m de large).
- **Deux couches au lieu d'une.** Le terrain ne manque pas : ce qui décide,
  c'est quelle catégorie de terrain (« gisement ») la règle ouvre. La carte
  change donc de sens à l'étape 6 : elle ne montre plus *pourquoi* un terrain
  est retiré, mais *ce qu'il est* (friche, zone d'activité, prairie, culture,
  plan d'eau). À l'étape 7, les gisements fermés par la circulaire passent en
  gris.
- **Les choix « Et si… ? » sont de l'arithmétique.** Seules 24 combinaisons de
  terrain ouvert changent la géométrie (le filtre de taille des parcs est
  réappliqué au seul terrain ouvert) ; elles sont précalculées. Les parts, le
  quota agrivoltaïque et les densités sont appliqués dans la page, avec la
  même formule que `pv_lib.policy_total`, vérifiée à la construction contre
  les dix cas du rapport.

## 2. Le récit en huit étapes

| n° | étape | contenu | indicateur |
|---|---|---|---|
| 0 | La Wallonie | aucune règle | « place pour » (0,8 MWc/ha partout, mention « si chaque hectare était couvert ») |
| 1 | Nature protégée | Natura 2000, réserves, ZHIB, CSIS, zones naturelles et parcs, liaisons écologiques, terrils en place | idem |
| 2 | Forêts et espaces verts | zone forestière, espaces verts, bois (WALOUS) | idem |
| 3 | Paysage et patrimoine | périmètres d'intérêt paysager et culturel, sites classés, UNESCO | idem |
| 4 | Risques et relief | inondation (aléa élevé), karst, éboulements, captages, pentes > 15 %, versants nord > 7 % | idem |
| 5 | Bâti, réseaux et eau | bâtiments, revêtements, routes, rails, lignes HT, plans d'eau | idem |
| 6 | Assez grand pour un parc | 1 ha, 60 m ; la carte passe aux couleurs des gisements | potentiel technique |
| 7 | Ce que les règles permettent | friches, CET, terrils, extraction, bords d'autoroute, bassins, ¼ des zones d'activité ; la part démontrable des sols médiocres ; l'agrivoltaïsme à 0,6 % de la SAU | potentiel selon les règles |
| ★ | Bilan | comparaison : règles actuelles, choix, plafond du modèle, objectif PACE | idem |

## 3. « Et si… ? »

| choix | options | réf. |
|---|---|---|
| Agrivoltaïsme | projets pilotes seulement (règle actuelle) ; prairies avec quota 0,6 / 1 / 2 % de la SAU ; toutes les prairies ; toutes les parcelles | 0,6 % (Livre blanc, chiffre pour 2030 ; horizon du modèle : 2050) |
| Sols médiocres en zone agricole (dérogation) | aucune ; la part démontrable (≈ 5 %) ; tous ces sols | la part démontrable |
| Friches | règle actuelle (panneaux admis en attendant la réindustrialisation) ; réservées à la réindustrialisation | règle actuelle |
| Zones d'activité et de services | aucune ; un quart ; tout le terrain libre | un quart |
| Photovoltaïque flottant | bassins industriels et lacs de carrière ; tous les plans d'eau | bassins |

Chaque option affiche ce qu'elle change (± GWc) par rapport à l'option de
référence de ce choix, les autres choix restant ce qu'ils sont. Le « mode expert » (replié) liste les hypothèses de l'étude, une à une.

## 4. Couleurs

- Familles d'exclusion : les cinq teintes sourdes du tableau de bord éolien
  (même série, même rôle).
- Gisements : cinq teintes validées toutes paires avec le validateur de
  palette (daltonisme ΔE ≥ 13, vision normale ΔE ≥ 16) — violet (terrains
  dégradés), magenta (zones d'activité), vert (prairies), jaune (cultures),
  bleu (eau) — et un gris neutre pour « autres ».
- Terrain fermé par les règles : gris clair.

## 5. Construction

```bash
cd workflow_pv_wal
snakemake infographic --rerun-triggers mtime
cd results/infographic && python -m http.server 8000
snakemake infographic_publish --rerun-triggers mtime   # pypsa.squoilin.eu/pv_sol_wallonie/
```

## 6. Écarts assumés par rapport au tableau de bord éolien

- Pas de vignettes d'orthophotos ni de photos au sol : les fiches portent un
  pictogramme. À ajouter si le tableau de bord doit être diffusé largement.
- Pas encore d'exports GIF / MP4 / carrousel ; le crochet `window.renderState()`
  est en place pour la capture Playwright du tableau de bord éolien.

## 7. Publication

Publié le 29 septembre 2026 sur <https://pypsa.squoilin.eu/pv_sol_wallonie/>
(`snakemake infographic_publish`). La page et ses modules portent un tampon
de construction (`?v=…`) pour qu'une republication ne soit jamais mélangée à
une version en cache.
