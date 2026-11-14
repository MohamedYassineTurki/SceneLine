# `cultural_guard/` · Cultural Integrity Guard

> Avant de recommander un placement, évaluer s'il respecte **l'époque, la culture, l'histoire et l'intention**
> de l'œuvre, et l'expliquer.

## Fichier

| Fichier | Rôle |
|---|---|
| [`guard.py`](guard.py) | `assess_scene()` : verdict par scène · `assess()` : verdict par placement (et par produit) sur cinq critères · `geographic()` : cohérence entre le lieu de l'action et les marchés du produit |

## Cinq critères, un risque global

| Critère | Risque élevé quand… |
|---|---|
| Contexte historique | un produit contemporain apparaît dans une scène d'époque |
| Contexte culturel | la scène porte un rite, une tradition, un deuil, une fête religieuse ; ou le produit vise un autre marché que le lieu de l'action |
| Cohérence narrative | la cohérence avec l'histoire est faible ou le produit gêne l'action |
| Sensibilité de la scène | la scène est protégée (un placement à moins de 6 s d'une scène protégée est signalé) |
| Intention artistique | un intervalle ou une catégorie exclus par le réalisateur ne sont pas respectés |

Le niveau global est **le pire des cinq**. Un risque élevé déclenche l'alerte « insertion déconseillée » ;
la décision finale reste au réalisateur.

## Principes
- **Aucun appel supplémentaire à un modèle** : le Guard rassemble et explique des signaux déjà calculés. Il est
  déterministe, rapide et testable.
- **La langue parlée ne décide jamais du pays** : le lieu est déclaré par le producteur, ou relevé explicitement dans
  la scène.
- Chaque verdict porte une **justification lisible** pour chaque critère.

## Exemple réel
Dans une cuisine de restaurant à Paris (lieu déclaré) :
- **Badoit 1 L** (France, marché France) → risque faible ;
- **Boga Cidre** (Tunisie, marché Tunisie) → **risque élevé** : *« Dans ce décor, elle ne correspondrait ni au lieu ni
  au public de l'œuvre et nuirait à son authenticité culturelle. »*

📖 Détails : [docs/etapes/2-produits-et-guard.md](../../docs/etapes/2-produits-et-guard.md) · [docs/ETHIQUE-360.md](../../docs/ETHIQUE-360.md)
