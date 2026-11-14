"""Lance SceneLine : python run.py [--port 8000]

Le code est organisé par étape dans src/ ; ce point d'entrée le rend importable puis démarre le serveur.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from server.app import main  # noqa: E402

if __name__ == "__main__":
    main()
