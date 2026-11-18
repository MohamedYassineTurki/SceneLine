# Étape 3 · Génération

> **Objectif :** produire le plan modifié **uniquement pour un placement approuvé**, avec l'outil de génération
> choisi par le créateur, et **seulement après son accord explicite** pour ce placement.

![Étape 3](../media/etape-3.jpg)

## Deux façons de produire le plan

| | **Automatique avec Kling AI** | **Manuelle, avec l'outil de votre choix** |
|---|---|---|
| Principe | SceneLine envoie le plan, le produit et le prompt à Kling AI, suit la tâche, récupère la vidéo et l'intègre | SceneLine prépare un kit complet (ZIP) ; le créateur génère dans Google Flow, Kling, Runway… puis importe le résultat |
| Clé | **Aucune pour le créateur** : SceneLine génère avec son propre compte Kling (clé sur le serveur). Sans clé serveur, le créateur peut connecter la sienne, **en mémoire seulement** | Aucune clé |
| Accord | Case à cocher **par placement**, vérifiée **côté serveur** | Le créateur envoie lui-même |
| Code | [`generation/kling.py`](../../src/generation/kling.py) | [`generation/kit.py`](../../src/generation/kit.py) |

## Le kit de génération
Pour un placement approuvé, [`generation/kit.py`](../../src/generation/kit.py) assemble :
- **la scène** : le plan source exact (sans audio), découpé sur l'intervalle approuvé ;
- **l'asset** : le visuel propre du produit, sur un fond carré de 1024 px, et sa **planche d'angles** si le producteur l'a importée ;
- **le prompt**, en français et en anglais : la description du plan (rédigée par Gemini à partir de trois images),
  l'emplacement précis sur une surface existante, **ce qui ne doit pas changer** (personnes, décor, cadrage,
  rythme des gestes), un **prompt négatif** et des réglages conseillés ;
- **le réalisme**, décrit par Gemini à partir des images du plan : la **taille réelle** du produit, sa **taille
  apparente** comparée aux objets voisins et en pourcentage de l'image, la **direction et la couleur de la
  lumière**, l'**ombre** cohérente avec celles du décor, le **rendu de caméra** (netteté, grain, étalonnage) et ce
  qui passe devant. Le produit doit sembler filmé avec le plan, jamais plus net ni plus propre que son entourage ;
- une **empreinte du prompt**, qui suivra le résultat jusqu'au relevé de l'étape 4.

## Génération automatique avec Kling AI

```mermaid
sequenceDiagram
    actor C as Créateur
    participant S as SceneLine
    participant K as API Kling AI
    C->>S: Connecte sa clé (mémoire du serveur uniquement)
    C->>S: Coche « J'autorise l'envoi… pour ce placement »
    S->>S: Vérifie l'accord côté serveur
    S->>S: Ouvre un lien aléatoire qui ne sert que ce plan
    S->>K: POST /omni-video/kling-4.0 (plan + produit + prompt)
    loop Suivi
        S->>K: GET /tasks?task_ids=…
    end
    K-->>S: URL de la vidéo générée
    S->>S: Ferme le lien, télécharge, intègre (étape 4)
```

### Configuration du serveur
Le compte Kling de SceneLine se configure sur le serveur, jamais dans l'interface :

| Réglage | Variable d'environnement | ou fichier (non versionné) |
|---|---|---|
| Clé d'API Kling de SceneLine | `KLING_API_KEY` | `.kling-key` |
| Adresse publique du serveur (https), par laquelle Kling télécharge le plan | `SCENELINE_PUBLIC_URL` | `.sceneline-public-url` |

Sur un poste local, l'adresse publique est celle d'un tunnel (par exemple `cloudflared tunnel --url http://localhost:8002`) ; le fichier est relu à chaque génération, il suffit donc de le mettre à jour quand l'adresse du tunnel change.

### Sécurité et vie privée, par conception
- **La clé** de SceneLine reste sur le serveur : jamais affichée, jamais dans un journal, jamais versionnée,
  envoyée uniquement à l'API de Kling. Une clé personnelle, si un créateur en connecte une, reste en mémoire
  et un bouton la fait oublier immédiatement.
- **Rien ne part sans accord** : chaque placement demande sa propre autorisation, vérifiée côté serveur
  (une requête sans accord est refusée).
- **Ce qui sera envoyé est listé** avant l'envoi : le plan, l'image du produit, le prompt.
- **Le plan vidéo** n'est exposé que par un lien aléatoire, valable pendant la génération seulement,
  qui ne sert que ce fichier. Le serveur refuse toute autre route aux hôtes non locaux.
- **Seul le plan vidéo** est envoyé, jamais des images de début et de fin : générer à partir de deux images
  réinvente la scène, alors que partir du plan conserve le jeu des acteurs.

## Pourquoi c'est sobre
La génération vidéo est l'opération la plus coûteuse en énergie. SceneLine ne la déclenche **que** pour les
placements que le créateur a approuvés, un par un. Aucune génération spéculative, aucun lot automatique.
