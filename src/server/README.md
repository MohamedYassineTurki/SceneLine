# `server/` · Serveur et API REST

## Fichier

| Fichier | Rôle |
|---|---|
| [`app.py`](app.py) | Application Flask : sert l'interface (`src/web/`), expose l'API REST, lance les analyses dans une file de travaux, reprend une analyse interrompue |

## Points clés
- **Une analyse à la fois**, dans des processus séparés (`video_analyzer/analyze.py` puis `understand.py`) : le serveur
  reste réactif et suit la progression en direct.
- **Reprise** : une analyse interrompue reprend là où elle s'est arrêtée ; un appariement relancé garde ses scores.
- **Garde d'hôte** : atteint par un autre nom d'hôte que `localhost` (tunnel pour Kling), le serveur ne sert que le lien
  temporaire du plan (`/pub/<jeton>/plan.mp4`) et refuse tout le reste.
- **Fichiers servis sur liste blanche** : seuls les fichiers attendus d'un projet sont accessibles.
- Chaque projet vit dans `output/web-runs/<id>/`.

## Lancer
```bash
python run.py --port 8000
```

📖 Liste complète des routes : [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md#4-api-rest)
