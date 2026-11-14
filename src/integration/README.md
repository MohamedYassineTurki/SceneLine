# `integration/` · Étape 4 · Intégration et transparence

> Replacer le plan généré dans l'œuvre **sans toucher à l'original**, garder l'audio d'origine,
> et dire au spectateur ce qui a été modifié.

## Fichier

| Fichier | Rôle |
|---|---|
| [`render.py`](render.py) | `bar_crop()` retire les bandes noires · `retime()` recale le plan généré · `assemble()` produit l'extrait Original / Version éditée · relevé des modifications |

## Recalage temporel par programmation dynamique
Un outil génératif peut raccourcir ou accélérer un geste. `retime()` associe **chaque image de l'original**
à l'image du plan généré qui lui ressemble le plus, **hors de la zone du produit**, sous contrainte d'ordre
(comme un alignement de séquences). Les gestes retombent sur le rythme du dialogue d'origine.
Exemple réel : un plan Kling de **7,0 s** recalé sur l'intervalle de **9,5 s** de l'original.

## Assemblage
```
[ original avant ] ─► [ plan édité, intervalle approuvé ] ─► [ original après ]
                 audio d'origine conservé de bout en bout
```
Seule la **révision approuvée** reçoit un rendu ; il lui est lié par son empreinte.

## Relevé des modifications
Produit, support, intervalle, révision et empreinte, **approbateur et date**, **outil qui a produit l'image**
(`generated_by_sceneline: false`), empreinte du prompt, audio, recalage, avertissements. Dans le lecteur,
l'étiquette **« Placement virtuel · Produit »** reste affichée pendant tout le placement.

📖 Détails : [docs/etapes/4-integration.md](../../docs/etapes/4-integration.md)
