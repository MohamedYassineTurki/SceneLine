# `web/` · Interface

HTML, CSS et JavaScript **sans framework ni compilation** : l'interface se lit et s'audite directement.

| Fichier | Rôle |
|---|---|
| [`index.html`](index.html) | Les quatre étapes et la page Éthique 360 |
| [`app.js`](app.js) | Étape 1 : import, consentements, progression, carte de la vidéo, placements, scènes protégées |
| [`products.js`](products.js) | Étape 2 : contexte, catalogue, appariement, propositions, décisions |
| [`compare.js`](compare.js) | Étapes 3 et 4 : kit, génération Kling, intégration, comparaison Original / Version éditée, étiquette |
| [`ethics.js`](ethics.js) | Page Éthique 360 et repères d'angles en tête de chaque étape |
| [`style.css`](style.css) | Système de design : thème clair, Inter, une seule couche de cartes, accent réservé aux actions |

Accessibilité : contraste minimal 4,5:1, risques toujours doublés d'une forme et d'un texte, navigation au clavier,
régions `aria-live` pour la progression. Système de design de référence : [`design/`](../../design).
