"""Build a timestamped evidence bundle for SceneLine's placement analysis."""

import argparse
import json
from pathlib import Path
import subprocess
from time import perf_counter

from faster_whisper import WhisperModel
import numpy as np
from scenedetect import AdaptiveDetector, detect

from video_analyzer.transcribe import LANGUAGES as TRANSCRIBE_LANGUAGES, GeminiUnavailable
from video_analyzer.transcribe import transcribe as transcribe_with_gemini


def run_media(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def analyze(source, output, description, model_name, visual_only=False, language_hint=None, transcriber="whisper"):
    started = perf_counter()
    output.mkdir(parents=True, exist_ok=True)
    metadata = json.loads(run_media(
        "ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json",
        str(source),
    ))
    streams = metadata["streams"]
    if not any(stream["codec_type"] == "video" for stream in streams):
        raise ValueError("Le fichier ne contient aucune piste vidéo.")
    duration = round(float(metadata["format"]["duration"]) * 1000)

    print("Détection des plans…", flush=True)
    shots = detect(str(source), AdaptiveDetector(), start_in_scene=True)
    transcript = []
    language = None
    has_audio = any(stream["codec_type"] == "audio" for stream in streams)
    status = "skipped" if visual_only else "complete" if has_audio else "no_audio"
    transcription_metrics = None
    if has_audio and not visual_only and transcriber in TRANSCRIBE_LANGUAGES:
        # Darija, arabe : Whisper invente du français. Gemini reçoit la piste audio seule, par extraits.
        print("Transcription par Gemini…", flush=True)
        model_name = "gemini"
        try:
            transcript, language, transcription_metrics = transcribe_with_gemini(source, duration, transcriber)
            model_name = "gemini · " + ", ".join(transcription_metrics["models"])
        except GeminiUnavailable as error:
            # Mieux vaut aucune réplique qu'une transcription fausse : l'analyse continue sur les images.
            print(f"Transcription indisponible : {error}", flush=True)
            status = "unavailable"
    elif has_audio and not visual_only:
        print("Transcription locale…", flush=True)
        model = WhisperModel(model_name, device="cpu", compute_type="int8")
        pcm = subprocess.run(
            ["ffmpeg", "-nostdin", "-v", "error", "-i", str(source),
             "-map", "0:a:0", "-ac", "1", "-ar", "16000", "-f", "f32le", "pipe:1"],
            check=True, capture_output=True,
        ).stdout
        segments, info = model.transcribe(np.frombuffer(pcm, dtype="<f4"),
                                          vad_filter=True, beam_size=3,
                                          language=language_hint)
        language = info.language
        transcript = [
            {"start_ms": round(segment.start * 1000),
             "end_ms": min(duration, round(segment.end * 1000)),
             "text": segment.text.strip(),
             "mean_log_probability": round(segment.avg_logprob, 3)}
            for segment in segments if segment.text.strip()
        ]

    print("Extraction des images de référence…", flush=True)
    shot_records = []
    for index, (start, end) in enumerate(shots, 1):
        start_ms = round(start.seconds * 1000)
        end_ms = min(duration, round(end.seconds * 1000))
        if end_ms <= start_ms:
            continue
        midpoint = (start_ms + end_ms) // 2
        frame = f"plan-{index:03}.jpg"
        run_media("ffmpeg", "-nostdin", "-v", "error", "-y", "-ss",
                  f"{midpoint / 1000:.3f}", "-i", str(source), "-frames:v", "1",
                  "-vf", "scale=640:-2", str(output / frame))
        shot_records.append({
            "id": index, "start_ms": start_ms, "end_ms": end_ms,
            "frame": frame, "frame_ms": midpoint,
            "transcript_indices": [
                i for i, line in enumerate(transcript)
                if line["start_ms"] < end_ms and line["end_ms"] > start_ms
            ],
        })

    # Les surfaces sont maintenant cherchées par understand.py, après la compréhension des scènes.
    candidates = []
    result = {
        "source": source.name, "duration_ms": duration,
        "producer_description": description or None,
        "transcription_model": model_name, "dominant_language": language,
        "transcription_status": status, "transcription_language_choice": transcriber,
        "transcription_metrics": transcription_metrics,
        "transcript": transcript, "shots": shot_records,
        "placement_analysis_status": "visual_candidates_only",
        "placement_candidates": candidates,
        "elapsed_seconds": round(perf_counter() - started, 1),
    }
    temporary = output / "analysis.tmp"
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(output / "analysis.json")
    print(f"{len(shot_records)} plans, {len(transcript)} segments de dialogue.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--description", default="")
    parser.add_argument("--model", default="base")
    parser.add_argument("--visual-only", action="store_true")
    parser.add_argument("--language", default="fr", help="Langue parlée (fr par défaut). Vide pour détecter.")
    parser.add_argument("--transcriber", default="whisper", choices=["whisper", *TRANSCRIBE_LANGUAGES],
                        help="whisper (local) ou une langue transcrite par Gemini : darija, ar.")
    args = parser.parse_args()
    analyze(args.video, args.output, args.description, args.model, args.visual_only,
            args.language or None, args.transcriber)
