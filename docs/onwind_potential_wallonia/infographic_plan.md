# Infographie — « Où peut-on installer des éoliennes en Wallonie ? » — plan

Statut : réalisé le 23 septembre 2026. Les écarts au plan sont au §18.

- Les chiffres cités sont **indicatifs**. Ils sortent du dernier calcul de
  `workflow_onwind_wal/` et l'infographie les relira elle-même dans le
  workflow.
- Toute l'infographie est **en français** : textes, légendes, interface, textes
  alternatifs et exports. Il n'y a pas de version anglaise.

## 1. Objectif et public

Le rapport ([`onwind_potential_wallonia.pdf`](onwind_potential_wallonia.pdf))
répond à une question : combien d'éolien terrestre les règles wallonnes
permettent-elles ? Il y faut 32 pages ; l'infographie raconte la même chose en
une vingtaine de secondes.

L'histoire est un **entonnoir** :

- Au départ, toute la Région est disponible.
- Chaque famille de règles retire du terrain, jusqu'à ce qu'il ne reste que
  2,5 % du territoire.
- Les règles d'implantation (espacement, parcs, horizon des villages) divisent
  ensuite encore presque par deux le nombre de machines.
- Enfin, quelques choix politiques font varier le résultat de ± 40 %.

| public | support | usage |
|---|---|---|
| grand public, presse, élus | GIF / MP4 / carrousel PNG-PDF (LinkedIn, X, Instagram, Bluesky) | regarder l'entonnoir défiler, retenir un chiffre et une raison |
| administration, acteurs du secteur, modélisateurs | tableau de bord HTML interactif | parcourir les étapes, basculer les choix politiques, vérifier les chiffres |

**Une seule source.** Les images du GIF sont des captures du tableau de bord,
pas un second dessin. Les deux ne peuvent donc pas diverger, et tous deux lisent
leurs chiffres dans les mêmes sorties que le rapport.

## 2. Concept

```
┌────────────────────────────────────────────┬──────────────────────────────┐
│  CARTE DE LA WALLONIE                      │  FICHE DE L'ÉTAPE            │
│  terrain encore disponible = vert vif      │  [image]  [pictogramme]      │
│  terrain retiré = couleur de la famille    │  Loin des habitations        │
│  de règles qui l'a retiré                  │  592 m des zones d'habitat,  │
│  éoliennes = points (dès l'étape 6)        │  400 m de toute maison       │
│                        ┌──────────┐        │  −5 176 km² (−82 %)          │
│                        │  loupe   │        │                              │
│  ┌────────────────┐    │ (100 m)  │        │  ●─●─●─◉─○─○─○─○─○─○  étapes  │
│  │ 5 123 éoliennes│    └──────────┘        │  ▂▅▃▁▁▁▁▁▁▁  (MW par étape)  │
│  │ 20 492 MW      │                        │                              │
│  │ 1 098 km²·6,5 %│                        │  ET SI… ?                    │
│  └────────────────┘                        │  ☐ dérogation zone agricole  │
│                                            │  ☐ éoliennes isolées admises │
│                                            │  ○ aucune ○ 4 km ○ 6 km      │
│                                            │  ☐ distance à l'habitat 2013 │
└────────────────────────────────────────────┴──────────────────────────────┘
 Source · données · licence                                 [logo CC BY 4.0]
```

- **À gauche :** la carte, avec l'indicateur clé en surimpression (§6) et une
  loupe qui montre le motif réel à 100 m (§7).
- **À droite :** la fiche de l'étape en cours (image, pictogramme, titre, une
  ligne de texte, effet chiffré), puis le curseur d'étapes, qui sert aussi de
  mini-graphique en cascade, puis les choix « Et si… ? ».

## 3. Le récit en dix étapes

Le workflow compte une douzaine de couches d'exclusion et cinq règles
d'implantation. L'infographie montre **cinq familles de terrain**, **trois
règles d'implantation** et **une réserve**. Deux principes guident le
regroupement :

- **Chaque étape doit changer visiblement l'image.** Sur le calcul actuel,
  chaque famille de terrain retire entre 31 % et 82 % de ce qui reste. Aucune
  n'est une étape à 0,5 % qui gaspillerait une image.
- **Chaque famille doit se comprendre en trois mots par un non-spécialiste.**
  Tout ce qui est technique va dans « relief et sécurité ». Tout ce qui protège
  un lieu va dans « nature, paysage, patrimoine ».

L'ordre suit la hiérarchie des règles : l'affectation du sol d'abord, puis le
cadre de vie, les espaces protégés, les contraintes techniques, et enfin les
règles d'implantation. Là où deux familles se recouvrent, chaque km² est compté
dans la première famille qui l'exclut, ce que dit une note sur l'infographie.

| n° | étape | contenu (couches du workflow) | à gauche | éoliennes | MW |
|---|---|---|---:|---:|---:|
| 0 | **La Wallonie** | — (aucune règle) | 16 905 km² | 29 261 | 117 044 |
| 1 | **Villes, forêts, parcs** | plan de secteur : habitat, forêt feuillue ou éloignée des grands axes, zones naturelles, espaces verts, parcs, plans d'eau | 9 189 km² | 21 974 | 87 896 |
| 2 | **Près des grands axes** | zone agricole à plus de 1,5 km d'une autoroute, d'une route 2 × 2 voies, d'une voie ferrée, d'une voie navigable ou d'un zoning | 6 274 km² | 16 488 | 65 952 |
| 3 | **Loin des habitations** | 500 m + la moitié de la hauteur autour des zones d'habitat ; 400 m autour de toute habitation | 1 098 km² | 5 123 | 20 492 |
| 4 | **Nature, paysage, patrimoine** | Natura 2000, réserves, zones humides, cavités ; périmètres d'intérêt paysager ; sites classés, zones tampon UNESCO | 761 km² | 3 869 | 15 476 |
| 5 | **Relief et sécurité** | pentes ≥ 7 %, zones inondables, karst, éboulements, captages ; routes, rails, lignes haute tension ; aérodromes ; radars | 418 km² | 2 865 | 11 460 |
| 6 | **750 m entre éoliennes** | cinq diamètres de rotor : l'empilement maximal ; les points apparaissent | 418 km² | 2 865 | 11 460 |
| 7 | **Des parcs d'au moins 4** | règle de parc, regroupement à 1,5 km | 418 km² | 2 162 | 8 648 |
| 8 | **Un horizon libre pour chaque village** | 130° sans éolienne dans un rayon de 4 km | 418 km² | 1 620 | **6 480** |
| 9 | **Pas encore cartographié** | réserve pour les zones d'oiseaux prioritaires et les contraintes partielles | — | ≈ 1 240 | **4 957** |

La conclusion affiche **≈ 5 GW possibles (entre 3,6 et 6,5 GW), environ trois
fois le parc actuel (1,5 GW)**.

- **Étapes 0 à 5 : l'empilement maximal.** L'indicateur y donne le plus grand
  nombre d'éoliennes que l'on peut placer à 750 m les unes des autres sur le
  terrain restant, pour que chaque étape porte un nombre d'éoliennes et une
  puissance.
  - L'étape 0 garde « 117 GW si chaque hectare était disponible », avec
    exactement cette mention, pour qu'une capture isolée ne puisse pas passer
    pour un potentiel.
- **L'étape 6 change l'image, pas le chiffre.** C'est le pivot du récit : les
  points apparaissent, et la fiche explique que c'est l'empilement maximal,
  avant les règles sur la manière de grouper les machines.
- **L'étape 9 n'est pas géographique.** La réserve ne dit pas *quelles*
  éoliennes disparaissent : aucun point n'est retiré, seul l'indicateur change,
  en affichant la fourchette.

## 4. « Et si… ? » — les choix politiques

Le §7 du rapport montre que ce sont des choix politiques, et non le terrain, qui
décident du résultat. Le tableau de bord expose les quatre choix qui comptent.

- Ils se combinent librement et s'appliquent à tout l'entonnoir : le curseur
  reste utilisable quand un choix est activé.
- Un choix qui augmente le potentiel est marqué d'une couleur chaude, un choix
  qui le diminue d'une couleur froide.
- La fiche rappelle chaque fois de quelle règle en vigueur le choix s'écarte.

| commande | libellé | effet sur la référence brute | étape modifiée |
|---|---|---:|---|
| case | *Dérogation : autoriser les terres agricoles loin des grands axes* | +40 % (9 076 MW) | 2 |
| case | *Autoriser les grandes éoliennes isolées (plus de 3,2 MW)* | +25 % (8 116 MW) | 7 |
| sélecteur à 3 positions | *Distance minimale entre parcs : aucune / 4 km / 6 km* | −16 % / −33 % | ajoute une étape après la 8 |
| case | *Règle de 2013 : 4 × la hauteur jusqu'aux zones d'habitat* | −28 % (4 660 MW) | 3 |

**Combinaisons.** Les effets ne s'additionnent pas, d'où le précalcul des
2 × 2 × 3 × 2 = 24 combinaisons. C'est peu coûteux : un placement prend quelques
secondes.

**Mode expert (optionnel, replié par défaut).** Il reprend les choix de
modélisation du rapport :

- périmètres ADESA ;
- seuil de pente 7 / 10 / 15 % ;
- anneaux aéronautiques ;
- classe d'éolienne ;
- espacement ;
- en option, le plafond actuel du modèle PyPSA-Wal (6,5 GW).

## 5. Mises en page et formats

| sortie | taille | disposition |
|---|---|---|
| tableau de bord, ordinateur | adaptatif, ≥ 1 280 px | carte à gauche (≈ 60 %), panneau à droite |
| tableau de bord, mobile | adaptatif | carte en haut, fiche en dessous, commandes dans un tiroir |
| GIF / MP4 paysage (X, LinkedIn, présentations) | 1 600 × 900 | carte à gauche, fiche à droite, comme au §2 |
| GIF / MP4 portrait (fil LinkedIn / Instagram) | 1 080 × 1 350 | carte en haut, fiche en bas, étapes en barre de progression |
| carrousel PNG / PDF (post « document » LinkedIn) | 1 080 × 1 350 par page | une page par étape, plus une page de titre et une page « Et si… ? » |

**Pourquoi un format portrait.** À 1 080 px de large, une disposition
gauche/droite rend les deux moitiés illisibles. Le format portrait est celui
que la plupart des gens verront.

## 6. Emplacement de l'indicateur clé

**Décision : sur la carte, en surimpression, dans le coin sud-ouest vide du
cadre de la Wallonie** (au-dessus de la France, au sud du Hainaut, là où les
cartes du rapport placent déjà leur légende), plutôt que dans le panneau droit.

Pourquoi à cet endroit :

1. **C'est là que l'œil se trouve.** Le regard suit la carte ; le chiffre qui
   change à côté rend la cause et l'effet évidents.
2. **Il survit à tous les recadrages.** En portrait, la carte est en haut, et
   dans les vignettes ou les aperçus de fil le panneau droit est souvent coupé
   ou illisible.
3. **Il ne cache aucun terrain wallon.**

L'indicateur affiche :

- le **nombre d'éoliennes** (grand) ;
- les **MW** (grand) ;
- les km² et le % de la Région encore disponibles (petit) ;
- un libellé qui passe de *« place pour… »* (étapes 0 à 5) à *« éoliennes
  autorisées »* (étapes 6 à 9).

Dans le tableau de bord, le chiffre défile d'une valeur à l'autre ; chaque
image du GIF montre la valeur finale.

La fiche de droite porte l'**effet de l'étape** (« −5 176 km² »,
« −542 éoliennes », « −25 % »). Le curseur d'étapes sert aussi de mini-cascade
des MW : tout l'entonnoir reste visible à chaque instant.

## 7. La carte

- **Le terrain retiré prend la couleur de sa raison.** Chaque cellule prend la
  couleur de la première famille qui l'a exclue. Au fil des étapes, le vert
  recule et la carte se remplit des couleurs des raisons. À la dernière étape de
  terrain, la carte est une légende du *pourquoi*, pas un pays vide.
- **Le terrain disponible doit rester visible à petite échelle.** À 1 080 px de
  large, un pixel d'écran vaut ≈ 250 à 370 m, et la parcelle disponible médiane
  fait 2 ha. La carte principale montre donc le terrain disponible **agrégé**
  (part de chaque cellule d'affichage, avec une taille minimale visible et un
  léger halo), et le dit en petit. Les calculs restent faits à 100 m.
- **La loupe.** Une fenêtre fixe d'environ 12 × 12 km à la vraie résolution de
  100 m, choisie là où toutes les règles sont visibles, par exemple le long de
  l'E42 entre Mons et Charleroi ou sur le plateau hesbignon. À l'étape 8, elle
  dessine les angles de 130° libres des villages de la fenêtre : c'est la
  meilleure explication de la règle d'horizon.
- **Éoliennes :** des points à partir de l'étape 6, avec un liseré fin pour
  qu'ils se lisent sur tous les fonds.
- **Repères, légers :** contour de la Région ; autoroutes en traits fins, qui
  rendent l'étape 2 lisible ; cinq ou six villes (Mons, Charleroi, Namur, Liège,
  Arlon, Tournai).
- **Couche optionnelle : le parc actuel**, les 652 éoliennes existantes,
  affichable pour comparaison.

## 8. Images et textes de chaque étape

### 8.1 Principes

1. **Une seule grammaire visuelle.** Toutes les fiches ont le même format
   d'image (4:3), le même traitement (photo légèrement désaturée, règle dessinée
   par-dessus dans la couleur de la famille) et un pictogramme du même jeu. Une
   série cohérente fait professionnel ; un mélange de sources fait bricolé.
2. **Le type d'image suit la nature de la règle.**
   - **Une règle qui se mesure au sol** (une distance, une bande, une zone) se
     comprend le mieux **vue d'en haut**. Ces fiches utilisent une vraie
     **orthophoto wallonne** (SPW, campagne 2025) avec la règle tracée
     par-dessus : un anneau de 400 m autour d'une maison, la bande de 1,5 km le
     long d'une autoroute, les cercles de 750 m autour d'éoliennes existantes,
     le secteur de 130° d'un village.
     - C'est réel, sans ambiguïté et dans le même registre que la carte. Cela
       ressemble à un document d'urbanisme plutôt qu'à une publicité.
     - C'est reproductible : les tracés viennent des couches du workflow.
   - **Une règle qui protège une valeur** (nature, paysage, patrimoine,
     oiseaux) se comprend par une **photo au sol** qui montre ce que l'on
     protège. Une vue aérienne d'une zone Natura 2000 ne dit rien à personne.
   - **L'ouverture et la conclusion** utilisent une grande photo de paysage
     wallon avec des éoliennes, qui donne le ton.
3. **Priorité aux vraies images.**
   - D'abord des photos personnelles ou libres de droits compatibles, et les
     orthophotos du SPW.
   - L'IA seulement pour les photos d'ambiance au sol, quand aucune vraie
     photo ne convient (§8.4).
   - Jamais d'image générée pour représenter un lieu réel précis.
4. **Un texte court, avec un chiffre.** La fiche porte :
   - un titre de 2 à 5 mots ;
   - une ligne de règle de 12 mots au maximum, avec sa distance ou son seuil ;
   - l'effet, écrit automatiquement ;
   - dans le tableau de bord seulement, un « pourquoi » de 25 mots au maximum
     qui cite le texte (« Cadre de référence 2024, §3.2 »).

### 8.2 Fiche par étape

| n° | titre | ligne de règle | image | règle dessinée sur l'image | pictogramme |
|---|---|---|---|---|---|
| 0 | La Wallonie | 16 905 km² : aucune règle n'est encore appliquée | photo au sol : plateau agricole et parc éolien | — | contour de la Wallonie |
| 1 | Villes, forêts, parcs | Le plan de secteur exclut l'habitat, la forêt feuillue, les zones naturelles et les parcs | orthophoto : lisière d'un village ardennais, prairies, forêt feuillue et résineux | aplats semi-transparents des zones exclues (habitat, forêt, nature) | arbre et maison |
| 2 | Près des grands axes | En zone agricole, seulement à moins de 1,5 km d'une autoroute, d'une voie ferrée ou d'un zoning | orthophoto : autoroute traversant des champs | bande de 1,5 km de part et d'autre, l'extérieur assombri | autoroute |
| 3 | Loin des habitations | 592 m des zones d'habitat, 400 m de toute maison | orthophoto : village condrusien et fermes isolées | anneaux de 592 m et de 400 m ; le terrain restant en vert | maison et flèche de distance |
| 4 | Nature, paysage, patrimoine | Natura 2000, réserves naturelles, paysages protégés, sites classés | photo au sol : vallée ardennaise boisée, rivière, village et ruine ancienne | — (étiquette discrète « Natura 2000 ») | feuille et monument |
| 5 | Relief et sécurité | Pentes fortes, zones inondables ; routes, rails, lignes à haute tension, aérodromes | orthophoto : versant de vallée avec voie ferrée et ligne à haute tension | hachures des pentes ≥ 7 % ; bandes de sécurité | relief et pylône |
| 6 | 750 m entre éoliennes | Cinq diamètres de rotor pour limiter les pertes de sillage : l'empilement maximal | orthophoto : parc existant (ombres des mâts visibles) | cercles de 750 m autour de chaque mât | éolienne et cercle |
| 7 | Des parcs d'au moins 4 | Pas d'éolienne isolée : les machines sont groupées en parcs | même lieu, plus large | contour du parc ; une machine isolée barrée | quatre éoliennes |
| 8 | Un horizon libre pour chaque village | 130° de l'horizon de chaque village restent sans éolienne, sur 4 km | orthophoto : village entouré d'éoliennes (ou, en variante, photo au sol depuis le village) | secteur libre de 130° et rayon de 4 km | angle de 130° |
| 9 | Pas encore cartographié | Zones d'oiseaux prioritaires et contraintes partielles : environ −24 % | photo au sol : milan royal en vol | — | oiseau et point d'interrogation |
| — | ≈ 5 GW possibles | Entre 3,6 et 6,5 GW, environ trois fois le parc actuel | photo au sol : même paysage qu'à l'étape 0, lumière du soir | — | — |

**Les fiches « Et si… ? »** (GIF 2) reprennent la vignette de l'étape concernée
avec la variante dessinée :

- dérogation : la bande de 1,5 km disparaît ;
- éoliennes isolées : la machine barrée est réhabilitée ;
- 4 / 6 km : flèches entre deux parcs ;
- règle de 2013 : l'anneau s'élargit à 740 m.

### 8.3 D'où viennent les images

- **Orthophotos.** Service `IMAGERIE/ORTHO_2025_ETE` du Géoportail de la
  Wallonie, crédit « SPW (2026) ». Elles s'extraient par le même export d'image
  que celui déjà utilisé pour la carte des pentes ; les tracés viennent des
  couches du workflow. **La licence des orthophotos est à confirmer** sur la
  fiche du catalogue avant publication.
- **Choix des lieux.** Pour chaque règle, le script propose deux ou trois
  fenêtres où elle se voit le mieux (par exemple la plus forte part de terrain
  retiré par la règle, ou un parc réel bien lisible). Le choix final se fait à
  l'œil, en évitant de stigmatiser un village précis. Il n'y a pas de nom de lieu
  sur les vignettes.
- **Photos au sol.**
  - D'abord des photos personnelles (le meilleur choix : ni droits, ni doute
    sur l'authenticité).
  - Puis des banques libres compatibles : CC0 ou CC BY. **Éviter le CC BY-SA**,
    dont le partage à l'identique contaminerait la licence CC BY 4.0 de
    l'infographie.
  - L'IA en dernier recours (§8.4).
- **Pictogrammes.**
  - Un jeu libre et homogène : Tabler Icons (licence MIT) ou Lucide (ISC), trait
    de 2 px, extrémités arrondies.
  - Dessin maison en SVG, dans le même style, pour ce qu'aucun jeu ne propose :
    éolienne moderne, angle de 130°.
  - Pour dessiner tout le jeu d'un coup dans un style unique, **Recraft**
    (sortie vectorielle SVG) est l'outil adapté.

### 8.4 Images générées par IA : quand, avec quoi, comment

**Quand.** Seulement pour les **photos d'ambiance au sol** des étapes 0, 4 et
9, de la conclusion et, en option, de la variante de l'étape 8, et seulement
faute de vraie photo convenable. Jamais pour les vignettes aériennes, qui
doivent être réelles. Jamais pour représenter un lieu réel nommé.

**Quel outil.**

| outil | pour quoi | réglages |
|---|---|---|
| **Midjourney v7** (ou version ultérieure) | l'outil principal : le rendu photographique le plus naturel pour des paysages | `--style raw` (moins « esthétique IA »), `--stylize` bas (50 à 100), `--ar 4:3` |
| **Google Gemini, modèle d'image « Nano Banana Pro »** (ou Imagen 4 Ultra) | le second avis : très fidèle aux consignes détaillées (architecture, cultures, proportions des éoliennes) ; filigrane invisible SynthID | prompt en langage naturel, format 4:3, « photoréaliste » |
| FLUX 1.1 Pro Ultra, mode *Raw* (Black Forest Labs) | option si les deux premiers gardent un aspect « trop propre » | mode Raw activé |

- Les versions évoluent vite. Il faut tester la version courante et vérifier les
  conditions d'utilisation commerciale de l'abonnement avant publication.
- Méthode : générer chaque image avec les deux premiers outils, garder la plus
  crédible, l'agrandir, puis harmoniser la colorimétrie avec les autres photos.

**Les prompts** sont en anglais : ces outils sont entraînés surtout sur des
légendes anglaises et suivent mieux les consignes dans cette langue. L'image
produite ne contient aucun texte, donc cela ne change rien au « tout en
français ». Chaque prompt décrit :

- le sujet ;
- le type de paysage wallon :
  - Hesbaye : brique, champs immenses de betteraves et de blé ;
  - Condroz : calcaire gris, vallonnements ;
  - Ardenne : ardoise, forêts, vallées encaissées ;
- la lumière belge (ciel couvert, lumière douce) ;
- l'appareil et l'objectif ;
- ce qu'il ne faut pas montrer.

Les éoliennes sont le point faible des générateurs, d'où une description
précise : trois pales identiques, mât tubulaire blanc, nacelle, proportions
d'une machine moderne.

**A. Ouverture (étape 0) et conclusion**

> Documentary landscape photograph of an open farming plateau in Hesbaye,
> Wallonia, Belgium: vast flat fields of winter wheat and sugar beet, a straight
> narrow country road, a red-brick farmstead with a row of pollarded willows,
> and a line of five modern three-bladed wind turbines on the horizon, white
> tubular towers about 110 m high, identical rotors about 150 m in diameter,
> realistic scale and spacing. Late afternoon, soft low sun under broken clouds,
> light haze, natural colours, no HDR. Shot on a full-frame camera, 35 mm lens,
> f/8, eye level. Editorial documentary photography, no people, no text, no
> logo. `--ar 4:3 --style raw --stylize 75 --v 7 --no text, logo, watermark`

Pour la conclusion, même prompt avec *« blue hour after sunset, the turbines
seen against a deep blue sky, the farmstead windows lit »*.

**B. Nature, paysage, patrimoine (étape 4)**

> Documentary photograph of a deep wooded valley in the Belgian Ardennes: a
> river meander bordered by broad-leaved forest in early autumn colours, a small
> village of grey stone houses with dark slate roofs by the water, and the ruin
> of a medieval castle on the wooded ridge above. Overcast sky, soft diffuse
> light, a little morning mist over the river, natural muted colours. 24 mm
> lens from a high viewpoint, f/8. Editorial landscape photography, no people,
> no text, no wind turbines. `--ar 4:3 --style raw --stylize 50 --v 7 --no text,
> logo, wind turbine`

Variante nature pure : *« a high peat-bog plateau in the eastern Belgian
Ardennes, purple moor grass, heather, a wooden boardwalk, scattered birches,
overcast sky »*.

**C. Pas encore cartographié (étape 9)**

> Wildlife photograph of a red kite (Milvus milvus) in flight, wings fully
> spread, deeply forked rufous tail, pale grey head, sharp feather detail,
> against a pale overcast sky above farmland in southern Belgium. Telephoto
> 500 mm lens, fast shutter, shallow depth of field, natural colours. No text,
> no wind turbines. `--ar 4:3 --style raw --stylize 50 --v 7 --no text, logo`

**D. Variante au sol de l'étape 8 (optionnelle)**

> Documentary photograph taken at eye level from the edge of a small village in
> the Condroz, Wallonia: grey limestone houses and a stone wall in the
> foreground, gently rolling fields beyond, and a group of four modern
> three-bladed wind turbines occupying only a narrow part of the horizon on the
> left, the rest of the horizon completely open. Overcast soft light, natural
> colours, 28 mm lens, f/8. Editorial documentary photography, no people, no
> text. `--ar 16:9 --style raw --stylize 75 --v 7 --no text, logo`

Pour Gemini, on utilise le même texte sans les paramètres `--…`, en ajoutant
« photorealistic, 4:3 aspect ratio ».

**Transparence.**

- Chaque image générée porte un petit symbole ✦ et la mention « Image générée
  par IA » dans les crédits.
- Le règlement européen sur l'IA (art. 50, applicable depuis le 2 août 2026)
  impose de signaler une image réaliste générée qui ressemble à des lieux
  existants.
- Pour une publication scientifique, c'est de toute façon indispensable à la
  crédibilité.

### 8.5 Contrôle qualité des images

Avant de retenir une image, vérifier :

- **Éoliennes :** trois pales, rotors identiques et tournés dans le même sens,
  mât droit, taille cohérente avec la distance, pas de pales fusionnées.
- **Paysage :** architecture et cultures plausibles pour la Wallonie (pas de
  granges américaines, pas de pins méditerranéens), marquages routiers belges,
  ombres cohérentes avec le soleil, horizon droit.
- **Défauts typiques de l'IA :** objets fondus, arbres répétés, textures
  plastiques, lumière de studio.
- **Cohérence de série :** même format, même traitement colorimétrique, même
  hauteur d'horizon d'une image à l'autre.
- **Lisibilité en vignette :** à 300 px de large, on doit encore reconnaître le
  sujet.

## 9. Charte graphique

- **Reprendre l'identité du graphique « pompes à chaleur »**
  (`heat_pumps_belgium/belgium/belgium_heating_market.png`) :
  - fond crème `#F5F0E8` ;
  - titre gras en haut à gauche ;
  - sources en gris `#888888` en bas à gauche ;
  - **logo CC BY 4.0** en bas à droite
    (`/home/sylvain/labo/AI-misc/heat_pumps_belgium/belgium/cc_by_logo.png`).

  Les publications de la même série se reconnaîtront.
- **Couleurs.**
  - Terrain disponible : vert vif (famille `#2B8A3E` du rapport).
  - Les cinq familles d'exclusion : cinq teintes sourdes bien distinctes,
    vérifiées pour les daltonismes courants.
  - Éoliennes : points sombres à liseré blanc.
  - « Et si… ? » : une couleur chaude pour « augmente », une froide pour
    « diminue ».
- **Typographie.** Une police libre intégrée, Inter ou Source Sans 3 (licence
  SIL OFL, accents français complets), pour un rendu identique à l'écran et dans
  le GIF. Corps minimal ≈ 28 px à 1 080 px de large, pour que la fiche se lise
  sur un téléphone.
- **Typographie française des nombres :**
  - espace fine insécable pour les milliers (« 11 460 ») ;
  - virgule décimale (« 2,5 % », « 6,5 GW ») ;
  - espace avant « % », « : » et « ; ».

## 10. Données

Tout vient de `workflow_onwind_wal/`, par de nouvelles règles Snakemake.
L'infographie se régénère avec le rapport et ne peut pas citer de chiffres
périmés.

1. **Cartes d'attribution.** Pour chaque variante de terrain (dérogation oui/non
   × règle d'habitat 2024 ou 2013, soit 4 cartes), un octet par cellule de
   100 m : le numéro de la première famille qui l'exclut, 0 si elle est
   disponible. Elles sont construites à partir des brûlages couche par couche
   que fait déjà le script de sensibilité, et stockées en petits PNG sans perte.
2. **Table des états** (JSON). Pour chaque étape et chaque combinaison
   « Et si… ? » : surface, nombre d'éoliennes, MW, écart à l'étape précédente.
3. **Positions des éoliennes** pour chaque état de placement (étapes 6 à 8 sous
   chaque combinaison : quelques dizaines de jeux de 3 000 points au plus),
   ramenées à la grille de 100 m.
4. **Repères :** contour de la Région, autoroutes, noms de villes et fenêtre de
   la loupe, déjà projetés sur la grille de pixels. Le navigateur n'a donc
   besoin d'aucune bibliothèque de projection.
5. **Vignettes :** extraits d'orthophotos et tracés des règles, par étape.
6. **Textes :** un fichier unique de libellés français, relu avec le rapport.

Un contrôle fait échouer la construction si la table des états diffère de
`headline.json` ou de `sensitivity_cases.json`.

## 11. Technologies

| couche | choix | pourquoi | alternative écartée |
|---|---|---|---|
| export des données | Python dans le workflow existant (numpy, rasterio, geopandas, `placement_lib`) | réutilise le code et les masques validés | un notebook séparé (divergerait) |
| page | un fichier HTML autonome : modules ES sans outil de construction, **D3 v7** (échelles, animations des chiffres, mini-cascade), **Canvas 2D** (carte et points), SVG (contour, noms, secteurs d'horizon) | léger, sans compilation, fonctionne en local | Svelte + Vite (code d'état plus propre, mais exige une compilation) ; MapLibre / deck.gl (vrai zoom, mais disproportionné pour une seule région et plus difficile à rendre identique à l'export) |
| recoloration de la carte | table de couleurs appliquée à la carte d'attribution | changement d'étape ou de choix instantané ; une carte sert dix étapes | une image pré-rendue par état (des centaines) |
| état et liens | paramètres dans l'URL (`#etape=8&derogation=0&interdistance=4&habitat=2024`) | liens partageables ; l'export pilote la page de la même façon | — |
| service | **local pour l'instant** : `python -m http.server` dans `results/infographic/` | aucun hébergement à gérer ; les données se chargent sans restriction du navigateur | publication en ligne, plus tard |
| capture | **Playwright** (Chromium sans interface), qui appelle un crochet `renderState()` de la page | images déterministes : le GIF est littéralement le tableau de bord | enregistrement dans le navigateur (gif.js, ffmpeg.wasm), plus lourd et moins reproductible |
| GIF | **gifski** (palettes de qualité), puis **gifsicle** (`-O3 --lossy`) | fichiers légers avec des aplats | ffmpeg `palettegen` / `paletteuse` |
| MP4 | **ffmpeg** (H.264, yuv420p, fondus entre images) | Instagram refuse le GIF ; le MP4 est bien plus léger | — |
| carrousel | **img2pdf** à partir des PNG | posts « document » LinkedIn | — |

## 12. Scénarios d'export

**GIF 1 : l'entonnoir** (par défaut).

- Titre : 3 s.
- Étapes 0 à 9 : environ 2 s chacune.
- Conclusion : 5 s (≈ 5 GW, 3,6 à 6,5 GW, environ trois fois le parc actuel).
- Total ≈ 28 s.
- Le MP4 fait des fondus de 0,4 s ; le GIF coupe net, ou insère deux ou trois
  images intermédiaires si le budget de taille le permet.

**GIF 2 : « Et si… ? »** Cinq images à partir de la référence : dérogation
+40 %, éoliennes isolées +25 %, 4 km −16 %, 6 km −33 %, règle de 2013 −28 %.
Chacune montre le changement de carte et l'indicateur. Dernière image :
l'enveloppe des choix politiques, de 3,2 à 10,7 GW.

**Budget de taille.** Moins de 5 Mo par GIF en 1 080 × 1 350 (X accepte
15 Mo). Pour tenir ce budget :

- des aplats et au plus 64 couleurs sur la carte ;
- des photos réduites au format de la vignette ;
- des zones inchangées d'une image à l'autre, que gifsicle peut éliminer.

## 13. Accessibilité, licence, crédits

- **Texte alternatif en français** pour chaque export : les dix étapes en un
  paragraphe, livré avec les fichiers.
- **Lecture sans les couleurs.** Chaque famille est aussi nommée sur la fiche,
  dans la légende et dans le curseur.
- **Licence de l'infographie :** CC BY 4.0 (logo fourni).
- **Ligne de crédits** sur chaque image, exigée par les licences des données :

  > Source : étude PyPSA-Wal, Université de Liège, 2026 · Données : Géoportail
  > de la Wallonie (CC BY 4.0), © les contributeurs d'OpenStreetMap (ODbL),
  > orthophotos © SPW · ✦ image générée par IA

  plus la date du calcul et le lien (ou un QR code) vers le rapport.
- **Pictogrammes.** Les licences MIT et ISC demandent de conserver l'avis de
  licence dans les sources, pas sur l'image.

## 14. Livrables et arborescence

```
workflow_onwind_wal/
  infographic/                  # sources de la page (HTML, JS, CSS, pictogrammes, libellés)
  scripts/infographic_data.py   # cartes, table des états, points, repères, vignettes
  scripts/infographic_export.py # capture Playwright → GIF, MP4, PNG, PDF
  results/infographic/          # tableau de bord construit + exports (ignoré par git, comme results/)
docs/onwind_potential_wallonia/
  infographic_plan.md           # ce fichier
```

Nouvelles cibles Snakemake :

- `infographic` : le tableau de bord ;
- `infographic_export` : tous les formats.

Un paragraphe du README indique la commande de service local.

## 15. Étapes du projet

1. **Données.** Exporter les cartes, états et points, et les vérifier contre les
   chiffres du rapport.
2. **Squelette.** Carte, indicateur et curseur sur le chemin de référence.
3. **Images et fiches.**
   - Choisir et extraire les vignettes d'orthophotos, tracer les règles.
   - Rassembler les photos au sol (personnelles ou libres, sinon IA avec les
     prompts du §8.4).
   - Dessiner les pictogrammes, écrire et relire les textes.
4. **« Et si… ? ».** Les quatre choix, dans les 24 combinaisons.
5. **Export.** Capture Playwright, GIF, MP4, carrousel ; réglage des tailles.
6. **Relecture.**
   - Lecture sur téléphone.
   - Test daltonisme.
   - Vérification des chiffres contre le rapport.
   - Essai par un lecteur extérieur sans explication, puis publication.

## 16. Risques et parades

| risque | parade |
|---|---|
| terrain disponible invisible à l'échelle des réseaux sociaux | affichage agrégé et loupe à 100 m (§7) |
| « 117 GW » ou « empilement maximal » repris comme « le potentiel » | mentions « si chaque hectare était disponible » et « place pour… » ; la conclusion ne donne qu'un chiffre |
| surfaces retirées dépendant de l'ordre des étapes | ordre fixe et hiérarchique, note sur l'infographie, coûts indépendants de l'ordre dans le rapport |
| effets « Et si… ? » lus comme additifs | toutes les combinaisons précalculées et affichées telles quelles |
| chiffres qui divergent du rapport | générés depuis les mêmes sorties ; la construction échoue en cas d'écart |
| image IA prise pour une photo réelle, ou défauts visibles | IA limitée aux ambiances, symbole ✦ et mention, contrôle qualité du §8.5 |
| licence d'une image incompatible avec CC BY 4.0 | photos personnelles, CC0 ou CC BY uniquement ; licence des orthophotos confirmée avant publication |
| GIF trop lourd | aplats, réutilisation des zones fixes, MP4 comme format vidéo principal |
| réserve prise pour une exclusion cartographiée | aucun point retiré à l'étape 9 ; l'indicateur affiche la fourchette |

## 17. Décisions

**Prises (23 septembre 2026) :**

- 117 GW conservé à l'étape 0, avec la mention « si chaque hectare était
  disponible » ;
- aucune mention d'autres études ;
- tout en français ;
- licence CC BY 4.0 avec le logo fourni ;
- tableau de bord servi localement pour l'instant.

**Encore ouvertes :**

1. **Logo.** Le logo fourni dit « University of Liège ». Faut-il une variante
   « Université de Liège », pour rester entièrement en français ?
2. **Photos personnelles.** Existe-t-il des photos personnelles d'un paysage ou
   d'un parc éolien wallon ? Elles valent mieux que toute image générée.
3. **Emplacement de la loupe et des vignettes**, à choisir parmi deux ou trois
   propositions quand les premiers rendus existent.
4. **Plafond du modèle (6,5 GW) :** l'afficher dans le mode expert, ou pas du
   tout ?

## 18. Réalisation (23 septembre 2026)

Le tableau de bord, les GIF, les MP4 et le carrousel sont construits par
`workflow_onwind_wal/` (voir son README, section « Infographic »). Ils sont
publiés provisoirement sur <https://pypsa.squoilin.eu/eolien_wallonie_20260923/>.

**Chiffres.** Les 24 combinaisons sont calculées ; la construction vérifie la
référence, les six cas politiques et les deux cas combinés contre
`headline.json` et `sensitivity_cases.json`. Seule différence avec le §3 :
l'étape 3 donne 5 122 éoliennes, au lieu de 5 123.

**Écarts au plan :**

- **Orthophotos de l'été 2023**, et non de 2025 : la campagne `ORTHO_2025_ETE`
  ne couvre que le sud-est de la Région. Elles relèvent des conditions
  d'utilisation des services de visualisation du SPW, pas de la licence
  CC BY : à revoir avant toute publication.
- **Vignettes 6 à 8 tirées du calcul**, et non d'un parc existant : un parc
  existant est espacé d'environ 430 m, et des cercles de 750 m autour de ses
  mâts se chevaucheraient.
- **Police Inter** (la vignette et la page partagent la même police), en
  JavaScript sans bibliothèque (pas de D3).
- **Mention « image générée par IA » retirée** à la demande de l'auteur
  (tableau de bord interne). Les quatre photos au sol (étapes 0, 4, 9 et
  bilan) ont été générées avec Gemini et portent son petit symbole ✦.
- **Libellé « éoliennes possibles »** aux étapes 9 et bilan (au lieu
  d'« autorisées ») : la réserve est une perte attendue, pas une autorisation.
- **Disposition** : les étapes forment une frise en haut de la page, et
  « Et si… ? » est placé sous la carte ; les formats d'export gardent la
  disposition du §2.

**Décisions encore ouvertes (§17) :**

1. **Logo** : le logo fourni, en anglais, est conservé.
2. **Photos** : des photos personnelles restent préférables aux images
   générées.
3. **Loupe et vignettes** : la loupe se trouve dans le Condroz, au premier
   candidat de `results/infographic/data/loupe_candidates.json` ; elle se
   déplace avec `config.infographic.loupe.centre`. Les autres vignettes
   proposées sont dans `results/infographic/review/vignette_candidates.jpg` et
   se choisissent dans `config.infographic.vignettes`.
4. **Plafond du modèle (6,5 GW)** : affiché dans le mode expert seulement.
