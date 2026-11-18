# `video_analyzer/` · Étape 1 · Analyse de la vidéo

> Comprendre l'œuvre **avant** de chercher où placer un produit, protéger ce qui doit l'être, puis proposer
> seulement les meilleurs emplacements, chacun justifié et vérifié.

## Fichiers

| Fichier | Rôle |
|---|---|
| [`analyze.py`](analyze.py) | Préparation **locale** : métadonnées (ffprobe), plans (PySceneDetect), transcription horodatée (faster-whisper), une image par plan (FFmpeg) → `analysis.json` |
| [`transcribe.py`](transcribe.py) | Transcription de la **darija tunisienne** et de l'arabe par Gemini (audio seul, extraits d'une minute) : réplique d'origine + traduction française, horodatées |
| [`understand.py`](understand.py) | Compréhension : scènes et contexte (Gemini Flash), protection éditoriale, intervalles de coupe à coupe, revue des surfaces (Gemini Flash-Lite), **règles de décision** `classify()`, vérification des finalistes → `sceneline.json` |
| [`context.py`](context.py) | Contexte déclaré par le producteur (lieu, époque, intention, exclusions) et consentements horodatés |
| [`review.py`](review.py) | Utilitaires partagés : clés Gemini, écriture JSON atomique `replace_json()`, revue par modèle visuel local (llama.cpp) |
| [`placements.py`](placements.py) | Repérage visuel sans modèle : régions stables et peu texturées de chaque plan (OpenCV) |

## Entrées et sorties

```
source.mp4 + context.json
   │  analyze.py      (local, aucune donnée ne sort)
   ▼
analysis.json + plan-NNN.jpg
   │  understand.py   (Gemini, avec consentement)
   ▼
sceneline.json : scènes, protection, opportunités classées, mesures
```

## Les décisions clés
- **Les temps viennent de PySceneDetect**, jamais du modèle.
- **Le contexte avant la surface** : une scène protégée n'est jamais envoyée à la recherche de surface.
- **Le modèle note, le code décide** : `classify()` applique des règles écrites ; toute réponse hors schéma devient « incertain ».
- **Sobriété** : 1 appel au modèle complet pour le contexte, le modèle léger pour les volumes, quotas mémorisés, modèle de secours.

## Utilisation seule
```bash
PYTHONPATH=src python src/video_analyzer/analyze.py episode.mp4 --output output/essai
PYTHONPATH=src python src/video_analyzer/understand.py output/essai --video episode.mp4
```

📖 Détails : [docs/etapes/1-analyse.md](../../docs/etapes/1-analyse.md)
