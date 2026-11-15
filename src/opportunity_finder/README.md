# `opportunity_finder/` · Recherche d'opportunités

> 🔭 **En développement · vision de SceneLine.** Une première version est intégrée à l'application ;
> nous continuons à l'enrichir (voir [Prochaines étapes](#prochaines-étapes)).

> Pour un créateur qui n'a **pas encore** de sponsor : quels emplacements de son œuvre permettraient
> de financer sa production, avant même de démarcher un annonceur.

## Fichiers

| Fichier | Rôle |
|---|---|
| [`report.py`](report.py) | `build()` : quatre indicateurs mesurés, les opportunités déjà retenues par l'étape 1 avec l'avis du Guard et les annonceurs compatibles, des conseils de monétisation, l'avertissement |
| [`advertisers.py`](advertisers.py) | `load_directory()` et `match()` : croise les catégories, marchés et types d'œuvre déjà déclarés avec l'annuaire de démonstration |
| [`mediakit.py`](mediakit.py) | `build_pdf()` : dossier de présentation PDF, mêmes données que le rapport affiché à l'écran |

## Principes
- **Aucun appel supplémentaire à un modèle** : comme [`cultural_guard.guard`](../cultural_guard), ce
  module relit des signaux déjà calculés par `video_analyzer.understand` (scènes, opportunités,
  scores) et par `cultural_guard.guard` (verdict). Il n'invente ni ne réévalue rien.
- **Le pipeline d'analyse ne change pas** : les mêmes scènes, les mêmes opportunités et le même
  Guard servent aux deux parcours (« Placement après contrat » et « Recherche d'opportunités »).
  Seule la lecture à l'étape 1 change.
- **L'annuaire est une démonstration** : [`demo_advertisers/annuaire.json`](../../demo_advertisers)
  contient 3 à 5 annonceurs fictifs, marqués « Annuaire de démonstration ». Si aucun ne correspond,
  `advertisers.match()` renvoie des types de partenaires génériques (construits à partir des
  catégories déjà jugées compatibles par l'étape 1) — jamais le nom d'une entreprise réelle non
  inscrite.
- **Aucune garantie de revenu** : chaque rapport et chaque PDF portent l'avertissement que les
  revenus dépendent des accords conclus avec les annonceurs.

📖 Détails : [docs/ETHIQUE-360.md](../../docs/ETHIQUE-360.md)

## Prochaines étapes
- **Annuaire réel** : annonceurs volontaires, inscrits et vérifiés, à la place de l'annuaire de démonstration.
- **Une analyse, deux lectures** : passer du parcours « Placement après contrat » au rapport d'opportunités sans
  relancer l'analyse.
- **Dossier PDF multilingue**, dont l'arabe, avec une police et une mise en forme adaptées.
- **Mise en relation** créateur-annonceur, toujours à l'initiative et avec l'accord du créateur.
