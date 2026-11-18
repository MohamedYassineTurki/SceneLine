# `generation/` · Étape 3 · Génération

> Produire le plan modifié **uniquement pour un placement approuvé**, avec l'outil choisi par le créateur,
> et **seulement après son accord** pour ce placement.

## Fichiers

| Fichier | Rôle |
|---|---|
| [`kit.py`](kit.py) | Kit de génération : plan source exact (sans audio), asset du produit (1024 px), prompt détaillé FR/EN rédigé à partir de trois images, prompt négatif, réglages, archive ZIP, empreinte du prompt |
| [`placement.py`](placement.py) | Placement **mesuré** : taille apparente calculée par le code à partir d'un objet repère, produit accordé à la scène (luminosité, couleur, netteté, grain), maquette sur la première image, prompt pour un outil d'image |
| [`kling.py`](kling.py) | Génération automatique avec l'API Kling AI : connexion de la clé, envoi, suivi de tâche, téléchargement, intégration |

## Kling AI : sécurité par conception
- La clé reste **en mémoire du serveur** : jamais sur disque, jamais dans un journal, envoyée uniquement à Kling.
- **Accord par placement**, vérifié côté serveur : une requête sans accord est refusée.
- Le plan est exposé par un **lien aléatoire éphémère** qui ne sert que ce fichier, pendant la génération.
- Seul le **plan vidéo** est envoyé (jamais des images de début et de fin) : le jeu des acteurs est conservé.

```
POST /omni-video/kling-4.0  ──►  GET /tasks?task_ids=…  (suivi)  ──►  vidéo  ──►  integration/render.py
```

📖 Détails : [docs/etapes/3-generation.md](../../docs/etapes/3-generation.md)
