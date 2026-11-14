# Vidéo motion design SceneLine : sources et matériel

Dossier préparé pour une vidéo explicative en français (problème → solution → les six angles « IA éthique 360 »),
réalisée en code avec HyperFrames (HTML + GSAP → MP4). Remotion n'est pas nécessaire.

Skill de réalisation : `product-launch-motion` (installé dans `~/.claude/skills/`), type le plus proche :
**T07 · Problème → Solution** (aperçu : `~/.claude/skills/product-launch-motion/preview-gifs/T07-problem-solution.gif`).
Autres styles possibles : T03 (visite cinématique de l'interface), T11 (film « kinetic shape », plus long).

## Contraintes du cahier des charges (à respecter)
- Première soumission : vidéo de **1 à 2 minutes, en français**, avec les slides et le dépôt GitHub (15 novembre 2026, 23 h 59).
- Grande finale : 1 min de démo dans le pitch.
- Critères de la première soumission : 30 % pertinence du problème (réel, justifié, méthode de détection expliquée),
  25 % innovation et place de l'IA, 25 % démarche éthique à 360° (six angles, risques et pistes d'atténuation),
  20 % faisabilité.

## Les six angles « IA éthique 360 » (questions du cahier)
| Angle | Question du cahier | Ce que SceneLine fait réellement |
|---|---|---|
| Les créateurs | Qui garde la main sur l'œuvre et sur les décisions ? | Rien n'est modifié sans accord signé ; accepter, refuser, ajuster, retenir, choisir une autre surface ; journal des décisions ; l'original n'est jamais modifié. |
| Les droits | Consentement, droits d'auteur, rémunération. | Deux autorisations obligatoires à l'import ; provenance et licence de chaque visuel ; autorisation par placement avant tout envoi à Kling. |
| Les données | D'où viennent-elles ? Sont-elles utilisées légalement ? | Plans et transcription en local ; seuls des images échantillonnées et le dialogue voisin vont à Gemini, avec consentement ; clé Kling gardée en mémoire seulement. |
| Cultures et langues | Quelles cultures le modèle met-il en avant, ou efface-t-il ? | Cultural Integrity Guard : 5 critères, risque faible / moyen / élevé ; scènes sacrées, sensibles et génériques protégées ; cohérence géographique (le lieu est déclaré, jamais déduit de la langue). |
| La transparence | Le public sait-il ce qui a été généré par l'IA ? | Étiquette « Placement virtuel · [Produit] » dans le lecteur ; relevé des modifications (outil, approbateur, empreintes). |
| La planète | Quel coût énergétique pour quel bénéfice ? | Aucune génération vidéo par SceneLine ; génération seulement pour les placements approuvés ; travail lourd en local ; nombre d'appels affiché. Aucune mesure d'énergie : ne pas afficher de kWh ni de CO₂. |

## Faits utilisables à l'écran (tous vérifiés dans le produit)
- Principe : « L'IA propose, le créateur décide, le spectateur est informé. »
- Les 4 étapes : Analyse → Produits → Génération → Intégration.
- Démo réelle (projet `deb74f…`, épisode « BALTRINGUE #1 », cuisine d'un restaurant) :
  - analyse : 11 scènes, 48 plans, 9 placements proposés, 4 scènes protégées ;
  - lieu déclaré : Paris, France ;
  - plan 8 (00:30 – 00:40), plan de travail en inox : **Badoit 1 L proposée (7,7/10)** ;
  - **Boga Cidre écartée, risque élevé** : « L'action se passe en France (déclaré par le producteur). Boga Cidre est une
    marque tunisienne dont la campagne vise : Tunisie. Dans ce décor, elle ne correspondrait ni au lieu ni au public de l'œuvre. »
  - résultat généré avec Kling (édition vidéo), recalé de 7,0 s à 9,5 s, intégré avec l'audio d'origine.
- Ne jamais inventer de statistique de marché, de témoignage ou de logo client.

## Matériel dans ce dossier
| Fichier | Contenu |
|---|---|
| `assets/brand/logo.svg`, `logo-mark.svg`, `logo-mark-dark.svg` | Logo SceneLine (vectoriel) |
| `assets/brand/tokens.css` | Couleurs, rayons, ombres, durées du système de design |
| `assets/fonts/inter.css`, `inter-latin.woff2`, `inter-latin-ext.woff2`, `OFL.txt` | Police Inter locale (variable, graisses 400 à 600), licence SIL OFL 1.1. Copier le dossier dans le projet HyperFrames et lier `fonts/inter.css`. Vérifiée au rendu. |
| `assets/products/badoit.png`, `boga-cidre.png` | Produits détourés (photos fournies par l'équipe) |
| `assets/footage/cuisine-original.mp4`, `cuisine-badoit-kling.mp4`, `plan-source.mp4` | Extrait original, version éditée (Kling), plan source. **Extraits d'une série : droits à vérifier avant publication publique. Dossier ignoré par git.** |
| `assets/screens/00…05-*.png` | Captures 1440 px de l'interface réelle : accueil, analyse, produits (Guard), génération (Kling), intégration, Éthique 360 |
| `reference/scenline-design-system.html`, `scenline-prototype.html` | Système de design et prototype Claude Design, pour reconstruire les écrans en HTML |

## Encore à décider ou à fournir
- **Le problème, avec ses sources** (30 % de la note) : témoignages, observations, chiffres sourcés. Rien n'est inventé dans la vidéo.
- **Format** : 16:9, 1 min 30 environ (1 à 2 min exigées).
- **Voix off** : aucune, ou ElevenLabs en français (clé d'API à fournir), ou voix locale (Kokoro, à installer).
- **Musique** : un morceau sous licence, ou une musique originale (ElevenLabs Music), ou aucune.
