# Changements apportés au modèle PyPSA-WAL depuis juin 2026

**Établi le :** 2026-09-15, pour la slide « Changements apportés au modèle depuis
juin 26 — PyPSA » de la présentation au cabinet.

**Base :** relecture des 243 commits depuis le 15 mai 2026 (toutes branches), de
[`instructions.md`](../../instructions.md) et du journal de lot
[`2026-09-13_cabinet_batch_all14_2010_1h.md`](2026-09-13_cabinet_batch_all14_2010_1h.md).
Le travail wallon redémarre effectivement le 2026-07-05 (`9669cdb0`) : tout ce
qui suit est donc postérieur à la présentation de juin.

> Ce document n'est pas un journal de solve et ne suit pas
> [`_TEMPLATE_solve_log.md`](_TEMPLATE_solve_log.md). Il est rangé ici parce que
> c'est là que vivent les traces datées des runs auxquels ces changements se
> rapportent.

---

## 1. Ce que la slide couvrait déjà

Les cinq encadrés de la slide de juin — disponibilité des dépôts, soft-linking
TIMES/PyPSA, chaleur et géothermie, réseau électrique, flexibilité VE,
trajectoire renouvelable — restent exacts. Les sections 2 et 3 ci-dessous sont
les compléments : §2 enrichit les encadrés existants, §3 liste les thèmes que la
slide ne couvrait pas.

---

## 2. Compléments aux encadrés existants

### 2.1 Lien entre TIMES et PyPSA-WAL

- Extraction automatique des grandeurs de couplage depuis le `.vd`, **par
  scénario** : autosuffisance électrique, part du PV en toiture, plancher de
  captage industriel (avant : recopiées du scénario central).
- Table de paramètres partagée TIMES/PyPSA (`config/input_parameters_for_models.csv`)
  + génération et vérification automatiques des fichiers de coûts, potentiels et
  plafonds de capacité — plus aucune valeur saisie à la main dans une
  configuration.
- Correction de deux conventions PyPSA-Eur inadaptées à la Wallonie :
  suppression du facteur « four à coke » sur le charbon industriel (la Wallonie
  n'en a pas dans TIMES) et mesure de la demande électrique au même point que
  TIMES (basse tension) → écarts TIMES/PyPSA ramenés de 1–37 % à < 0,1 %.
- Émissions de procédés industriels wallons reprises directement de TIMES.
- Bilan biomasse solide harmonisé (boues d'épuration comptées des deux côtés,
  offre et demande).

### 2.2 Chaleur et géothermie

- Le mix de chauffage décentralisé wallon est imposé **heure par heure** à
  partir de TIMES : écart moyen au mix TIMES de 0,0–0,6 point, contre 16–20
  points avec l'ancien couplage (PyPSA ré-optimisait le parc et mettait 51–85 %
  de PAC là où TIMES en a 8–38 %).
- Parc de l'année de base et répartition urbain/rural repris de TIMES ;
  vieillissement du parc de PAC hérité corrigé (il « mourait » entre 2025 et
  2030 et n'était pas reconstruit).
- Comparaison des coûts d'appareils TIMES ↔ PyPSA réalisée (TIMES 1,3 à 5× moins
  cher) : une partie de l'écart de mix venait d'une incohérence de paramètres,
  pas de structure.

### 2.3 Réseau électrique

- NTC 2030 = réseau de référence **TYNDP 2024** ; 2040 = projets identifiés du
  Plan de Développement Fédéral (Lonny–Achêne–Gramme, Van Eyck–Maasbracht,
  Nautilus, 2ᵉ HVDC BE–DE) ; 2050 = extrapolation ×1,6.
- Le réseau **peut désormais croître**, la NTC servant de plafond. Avant :
  réseau gelé, 8 lignes transfrontalières AC sur 10 chargées à 96–99 % en 2050.
- Corridors internes belges explicités (Wallonie–Flandre, Wallonie–Bruxelles,
  Bruxelles–Flandre) : Boucle du Hainaut décalée à 2032–2033, Wallonie–Bruxelles
  maintenu au niveau actuel (pas de 380 kV).
- BE–GB ramené à 1 000 MW (Nemo seul) avant mise en service de Nautilus.
- La NTC est maintenant une capacité **utilisable** : l'ancienne convention n'en
  délivrait que 70 % sur les liaisons AC.
- Plafond d'importation nette d'électricité de la Wallonie repris de TIMES :
  2,94 / 6,47 / 10,0 TWh en 2030/2040/2050 (contraignant en 2040 et 2050).

### 2.4 Trajectoire renouvelable

- Parc 2025 recalé (2 668 MWc PV, 1 560 MW éolien) et PV 2025 réparti
  toiture/sol (1,77 / 0,9 GW) ; part toiture imposée depuis TIMES à partir de
  2030.
- **Courbes d'apprentissage rétablies** : les coûts wallons étaient figés sur une
  valeur 2025 unique, ce qui faisait *augmenter* le coût annualisé du PV jusqu'en
  2050 (+2 à +3 %). Le niveau reste wallon, la trajectoire suit technology-data →
  LCOE PV toiture 2050 : 100 → 60 EUR/MWh.
- Planchers 2030 comparés explicitement au PACE et au rythme de déploiement
  observé (le plancher PV impliquait 766 MW/an contre ~100 MWc réellement
  installés en 2025).
- Durées de vie PV/éolien portées à 25 ans ; taux d'actualisation (hurdle rates)
  alignés sur les 11 groupes NCAP_DRATE de TIMES-WAL.

### 2.5 En complément — scénarios

- Surcouches CSV par scénario, superposées à la table partagée : un scénario ne
  modifie que ses propres lignes, et une vérification automatique détecte toute
  dérive.
- 14 scénarios produits pour le cabinet : central, taxshift, taxshift+,
  biométhane industrie, réaliste (2 variantes), retard nucléaire, 6 points de
  balayage du coût du nucléaire, et le central sur année météo 2013.

---

## 3. Thèmes absents de la slide

### 3.1 Nucléaire

- Contrainte de fonctionnement en base (must-run) du parc nucléaire.
- Capacité nucléaire flamande explicitée horizon par horizon (hypothèse de
  siting, pas d'alignement TIMES).
- Balayage du coût d'investissement (9 500 → 4 500 EUR/kW) pour identifier le
  point de bascule, plus un scénario de retard de disponibilité.
- Convention d'énergie primaire (uranium ou électricité) rendue explicite dans
  les graphiques.

### 3.2 Gaz, biomasse et CO₂

- Suppression d'un stockage de gaz fantôme en Wallonie (les deux sites ont fermé
  en 2012) ; Loenhout corrigé — gaz utile au lieu du gaz coussin : 8 178 GWh au
  lieu de 545.
- CCGT avec captage ajouté ; plancher d'adéquation gaz rendu neutre
  technologiquement pour que le captage puisse concourir ; option pour interdire
  le captage sur les centrales avant une année donnée.
- Plancher de captage industriel repris de TIMES.
- Séquestration de CO₂ : plafond européen non sourcé remplacé par la géologie par
  pays (CO2StoP) + rampe de déploiement ; Belgique à zéro stockage documenté,
  export possible vers DE/NL/GB.
- **Aviation internationale sortie des plafonds CO₂ nationaux** (conservée dans
  le plafond global) : elle générait un prix du carbone wallon artificiel de
  ~1 200 EUR/t en 2050.
- Biogaz 4 TWh (2040) / 6,9 TWh (2050) ; biomasse solide locale portée à
  11 749 GWh/an ; plus d'import de pellets dans le scénario central.
- Prix charbon/pétrole/gaz mis à jour d'après l'administration wallonne,
  convertis en EUR 2025.

### 3.3 Résolution et capacité de calcul

- Résolution **horaire** (8 760 pas) pour tous les scénarios finaux, contre 6 h
  auparavant.
- Pas de temps de 5 ans possible (2025 → 2050 en six horizons) via une surcouche
  de configuration.
- Année météo 2010 par défaut, variante 2013 pour tester la sensibilité
  climatique.
- Les 13 scénarios 2010 tournent **en parallèle** sur le cluster NIC5 (une nuit
  pour le lot complet).

### 3.4 Rapportage et contrôle qualité

- Publication automatique du rapport HTML sur `pypsa.squoilin.eu`, export
  automatisé vers l'explorateur de résultats.
- Diagrammes de Sankey TIMES et pages « Indicateurs TIMES » (demande finale,
  émissions, chaleur, électricité) intégrés au même rapport.
- Diagnostic des contraintes actives sur réseau résolu (quelle contrainte fixe
  réellement le résultat) et procédure de revue critique obligatoire avant toute
  diffusion de résultats.
- Correction d'un défaut structurel de l'optique myope : les plafonds de capacité
  s'appliquaient à chaque nouvelle tranche et non au parc, donc chaque horizon
  pouvait en rajouter une par-dessus un plafond déjà atteint.
- Suite de tests automatiques : 41 fichiers, 477 tests, exécutés avant chaque
  lot.

---

## 4. Remarques sur la mise en page de la slide

- Les puces « Devises / Eurostat / EUR 2025 » et « Coûts de distribution » sont
  dans l'encadré « Trajectoire renouvelable » alors qu'elles concernent tous les
  vecteurs : elles iraient mieux dans un encadré « Coûts et devises » avec les
  courbes d'apprentissage (§2.4) et les taux d'actualisation.
- « Disponibilité des modèles » gagnerait à mentionner que chaque simulation est
  désormais accompagnée d'un journal de run et d'une revue critique documentée.

---

## 5. Principaux commits derrière chaque point

| Thème | Commits |
|---|---|
| Soft-link chaleur option B′ | `07cdc416`, `926b462b`, `88565911`, `97b02737` |
| Parc de base / âge des PAC | `aafa0445`, `71ef917a` |
| Taux d'actualisation TIMES | `d77df05f`, `fc450fa9`, `c40b0544` |
| Flexibilité VE (Elia) | `641e4cc3`, `00a0336e`, `6849d45f`, PR #2/#3 |
| NTC et croissance du réseau | `cdc16924`, `d1cd086b`, `a87471e5`, `d0b9e2ee`, `10494636`, `759e5e50` |
| Plafond d'import wallon | `f948c56b` |
| Apprentissage des coûts | `ecbe3215`, `99335b87` |
| Parc PV 2025 toiture/sol | `dbdd8cb0`, `0def1c0a`, `b4ba7733` |
| Nucléaire (must-run, sweep) | `506106f5`, `87552368`, `22f826a8`, `1d6424b8` |
| CCGT CC et captage | `33c24a36`, `d86d6ca3`, `72c9bef2` |
| Stockage gaz | `2aea1b01`, `46c2f485`, `6cdb085d` |
| Séquestration CO₂ | `816be537`, `80f3d279` |
| Aviation hors plafonds nationaux | `644cefd9` |
| Biomasse / biogaz | `907433a6`, `dc364b75`, `d9752839`, `4a4116aa` |
| Correction plafonds myopes | `8d1d6e10` |
| Pas de 5 ans | `50f95de0`, `de355403`, `64d084c4` |
| Rapport HTML / indicateurs TIMES | `5f87ef56`, `ae753bb3`, `13ccefa9`, `1597579a` |
| Lot de 14 scénarios | `de96e610`, `22f826a8`, `563eb26b` |
