# `product_matcher/` · Étape 2 · Catalogue et appariement

> Associer chaque placement au produit le plus cohérent, **ou à aucun**, avec une explication.

## Fichiers

| Fichier | Rôle |
|---|---|
| [`catalog.py`](catalog.py) | Fiches produit : catégorie, taille, modes d'intégration, **origine**, **marchés visés**, **provenance obligatoire du visuel** ; analyse du visuel par Gemini Flash-Lite ; attributs effectifs (déclarés > analysés) ; catalogue de démonstration |
| [`matching.py`](matching.py) | Règles explicites produit × placement, puis classement Gemini des paires restantes (cohérence narrative, discrétion, faisabilité) ; scores mis en cache |

## Le pipeline

```
Produit ajouté ──► analyse du visuel ──► attributs effectifs
                                              │
Placements de l'étape 1 ─────────────────────►├──► règles écrites ──► paire écartée (raison affichée)
                                              │
                                              └──► classement Gemini ──► Cultural Integrity Guard ──► proposition
```

## Règles d'appariement (avant tout modèle)
Une paire est écartée, avec sa raison, si : la catégorie ou l'intervalle est exclu par le producteur, le mode
d'intégration n'est pas possible, l'objet est trop grand pour la surface, la scène recommande d'éviter cette
catégorie, ou le produit est contemporain dans une scène d'époque. Sous **6,5/10** (ou un critère sous 5), le
résultat est « aucun produit convenable », **un résultat valide**.

Ajouter un sponsor ne recalcule que les paires nouvelles (`RANKING_VERSION` invalide le cache si le barème change).

📖 Détails : [docs/etapes/2-produits-et-guard.md](../../docs/etapes/2-produits-et-guard.md)
