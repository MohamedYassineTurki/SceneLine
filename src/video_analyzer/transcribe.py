"""SceneLine · transcription des dialogues par Gemini (darija tunisienne, arabe).

Whisper, exécuté en local, convient au français mais ne comprend pas la darija tunisienne : il produit des
phrases françaises inventées. Pour ces langues, le producteur choisit une transcription par Gemini, qui
reçoit uniquement la piste audio, découpée en extraits de deux minutes, compressée en mono.

Chaque réplique garde le texte tel qu'il est prononcé (`original`) et sa traduction française (`text`),
utilisée par la suite de l'analyse. Les horodatages sont ceux du modèle, bornés à l'extrait.
"""

import base64
import subprocess

from video_analyzer.understand import BACKUP_MODEL, PRIMARY_MODEL, Gemini, GeminiUnavailable, Metrics

CHUNK_S = 60      # au-delà, les horodatages du modèle dérivent

LANGUAGES = {
    "darija": ("ar", "la darija tunisienne (arabe tunisien), souvent mêlée de français"),
    "ar": ("ar", "l'arabe (standard ou dialectal), éventuellement mêlé de français"),
}

SEGMENT = {
    "type": "object",
    "properties": {
        "debut": {"type": "string", "description": "Début de la réplique dans l'extrait, au format MM:SS"},
        "fin": {"type": "string", "description": "Fin de la réplique dans l'extrait, au format MM:SS"},
        "original": {"type": "string", "description": "La réplique telle qu'elle est prononcée"},
        "francais": {"type": "string", "description": "Traduction française fidèle de la réplique"},
    },
    "required": ["debut", "fin", "original", "francais"],
}
PROPERTIES = {"repliques": {"type": "array", "items": SEGMENT}}


def audio_chunk(source, start_s, length_s):
    """Extrait audio mono 16 kHz compressé (Opus) : quelques centaines de Ko pour deux minutes."""
    return subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{start_s:.3f}", "-t", f"{length_s:.3f}",
         "-i", str(source), "-map", "0:a:0", "-vn", "-ac", "1", "-ar", "16000",
         "-c:a", "libopus", "-b:a", "24k", "-f", "ogg", "pipe:1"],
        check=True, capture_output=True,
    ).stdout


def prompt(language, start_s, length_s):
    return (
        f"Transcris les dialogues de cet extrait audio d'une œuvre de fiction, parlé en {language}. "
        f"L'extrait dure {length_s:.0f} secondes. Donne les temps au format MM:SS depuis le début de "
        f"l'extrait (de 00:00 à {int(length_s) // 60:02}:{int(length_s) % 60:02}), au moment exact où la "
        "réplique commence et se termine. "
        "Une entrée par réplique. Écris `original` tel qu'il est prononcé : la darija en caractères arabes, "
        "les mots français en français. Écris `francais` : une traduction française fidèle, sans résumer. "
        "Ignore la musique et les bruits. N'invente rien : si un passage est inaudible, écris [inaudible]. "
        "Une phrase peut être coupée au début ou à la fin de l'extrait. S'il n'y a aucun dialogue, "
        "renvoie une liste vide."
    )


def seconds(value):
    """« 01:05 », « 1:05.4 » ou « 65 » → secondes."""
    text = str(value).strip().replace(",", ".")
    total = 0.0
    for part in text.split(":"):
        total = total * 60 + float(part)
    return total


def transcribe(source, duration_ms, choice):
    """Renvoie (transcription, langue, mesures). Lève GeminiUnavailable si Gemini ne répond pas."""
    code, language = LANGUAGES[choice]
    metrics = Metrics()
    client = Gemini(PRIMARY_MODEL, BACKUP_MODEL, metrics)
    duration_s = duration_ms / 1000
    transcript, models = [], set()
    start_s = 0.0
    while start_s < duration_s - 0.5:
        length_s = min(CHUNK_S, duration_s - start_s)
        audio = audio_chunk(source, start_s, length_s)
        parts = [{"inlineData": {"mimeType": "audio/ogg", "data": base64.b64encode(audio).decode("ascii")}},
                 {"text": prompt(language, start_s, length_s)}]
        data, model = client.call(parts, PROPERTIES, timeout=180)
        models.add(model)
        for line in sorted(data.get("repliques") or [], key=lambda l: l.get("debut", 0)):
            text = str(line.get("francais", "")).strip()
            try:
                begin = min(max(seconds(line["debut"]), 0), length_s)
                end = min(max(seconds(line["fin"]), begin), length_s)
            except (KeyError, TypeError, ValueError):
                continue
            if not text:
                continue
            transcript.append({
                "start_ms": round((start_s + begin) * 1000),
                "end_ms": min(duration_ms, round((start_s + max(end, begin + 0.5)) * 1000)),
                "text": text,
                "original": str(line.get("original", "")).strip(),
            })
        print(f"Transcription · {start_s / 60:02.0f}:{start_s % 60:02.0f} · {len(transcript)} répliques",
              flush=True)
        start_s += length_s
    used = sorted(models)
    return transcript, code, {"api_calls": metrics.data["api_calls"],
                              "failed_attempts": metrics.data["failed_attempts"],
                              "audio_seconds": round(duration_s), "models": used}


__all__ = ["LANGUAGES", "transcribe", "GeminiUnavailable"]
