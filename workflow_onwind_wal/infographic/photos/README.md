# Photos au sol de l'infographie

Quatre fiches utilisent une photo au sol plutôt qu'une orthophoto. Déposez les
fichiers ici, sous ces noms exacts (JPG ou PNG, n'importe quelle taille, au
mieux ≥ 1 600 px de large) :

| fichier | fiche |
|---|---|
| `etape0.jpg` | 0 — La Wallonie (ouverture) |
| `etape4.jpg` | 4 — Nature, paysage, patrimoine |
| `etape9.jpg` | 9 — Pas encore cartographié |
| `bilan.jpg` | Bilan — ≈ 5 GW possibles |

`snakemake -c4 infographic --rerun-triggers mtime` les recadre en 4:3, les
réduit à 1 200 × 900 et harmonise leur colorimétrie avec les orthophotos. Une
fiche sans photo affiche son pictogramme.

Une vraie photo (personnelle, CC0 ou CC BY) vaut toujours mieux qu'une image
générée.

## Outils gratuits

- **Google Gemini** (gemini.google.com, compte Google gratuit) ou **Google AI
  Studio** (aistudio.google.com, choisir le modèle d'image « Nano Banana » /
  Gemini Image) : le plus fidèle aux consignes détaillées. Dans AI Studio, on
  peut fixer le format 4:3.
- **Microsoft Bing Image Creator / Copilot** (bing.com/create, compte Microsoft
  gratuit) : bon second avis.

Collez le prompt tel quel, en anglais (ces outils suivent mieux les consignes
dans cette langue ; l'image ne contient aucun texte). Générez 3 ou 4 variantes
et gardez la plus crédible.

## Prompts

**`etape0.jpg` — ouverture**

> Photorealistic documentary landscape photograph, 4:3 landscape format, of an
> open farming plateau in Hesbaye, Wallonia, Belgium: vast flat fields of
> winter wheat and sugar beet, a straight narrow country road, a red-brick
> farmstead with a row of pollarded willows, and a line of five modern
> three-bladed wind turbines on the horizon, white tubular towers about 110 m
> high, identical rotors about 150 m in diameter, realistic scale and spacing.
> Late afternoon, soft low sun under broken clouds, light haze, natural
> colours, no HDR. Full-frame camera, 35 mm lens, f/8, eye level. Editorial
> documentary photography. No people, no text, no logo, no watermark.

**`bilan.jpg` — conclusion** : même prompt que `etape0.jpg`, en remplaçant
« Late afternoon, soft low sun under broken clouds, light haze » par :

> Blue hour after sunset, the turbines seen against a deep blue sky, a faint
> glow on the horizon, the farmstead windows lit.

**`etape4.jpg` — nature, paysage, patrimoine**

> Photorealistic documentary photograph, 4:3 landscape format, of a deep
> wooded valley in the Belgian Ardennes: a river meander bordered by
> broad-leaved forest in early autumn colours, a small village of grey stone
> houses with dark slate roofs by the water, and the ruin of a medieval castle
> on the wooded ridge above. Overcast sky, soft diffuse light, a little morning
> mist over the river, natural muted colours. 24 mm lens from a high
> viewpoint, f/8. Editorial landscape photography. No people, no text, no wind
> turbines, no logo, no watermark.

**`etape9.jpg` — pas encore cartographié**

> Photorealistic wildlife photograph, 4:3 landscape format, of a red kite
> (Milvus milvus) in flight, wings fully spread, deeply forked rufous tail,
> pale grey head, sharp feather detail, against a pale overcast sky above
> farmland in southern Belgium. Telephoto 500 mm lens, fast shutter, shallow
> depth of field, natural colours. No text, no wind turbines, no logo, no
> watermark.

## Avant de garder une image

- **Éoliennes :** trois pales, rotors identiques et tournés dans le même sens,
  mât droit, taille cohérente avec la distance, pas de pales fusionnées.
- **Paysage :** architecture et cultures plausibles en Wallonie (pas de granges
  américaines, pas de pins méditerranéens), horizon droit, ombres cohérentes.
- **Défauts typiques :** objets fondus, arbres répétés, textures plastiques,
  lumière de studio.
- **Milan royal :** queue profondément fourchue, deux ailes, bon nombre de
  rémiges.
- **En vignette** (300 px de large), on doit encore reconnaître le sujet.
