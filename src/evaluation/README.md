# `evaluation/` · Mesurer la qualité des placements

## Fichier

| Fichier | Rôle |
|---|---|
| [`evaluate.py`](evaluate.py) | Compare les placements de `sceneline.json` à une annotation manuelle de référence |

L'annotation de référence de l'épisode de test est dans [`validation/`](../../validation) : génériques à écarter,
surfaces attendues, moments où le cadrage change.

```bash
PYTHONPATH=src python src/evaluation/evaluate.py output/web-runs/<id>/sceneline.json
```
