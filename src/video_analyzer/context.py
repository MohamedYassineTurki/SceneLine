"""SceneLine · contexte éditorial et consentements d'un projet (F01)."""

import json
import re
from datetime import datetime, timezone

from product_matcher.catalog import CATEGORIES

WORK_TYPES = ["Série", "Film", "Court métrage", "Documentaire", "Autre"]
TEXT_FIELDS = {"location": "Lieu de l'action", "period": "Époque de l'action",
               "languages": "Langues parlées", "intention": "Intention narrative"}
INTERVAL = re.compile(r"(\d{1,2}):(\d{2})\s*[-–]\s*(\d{1,2}):(\d{2})")


def parse_intervals(text):
    result = []
    for m in INTERVAL.finditer(text or ""):
        start = (int(m[1]) * 60 + int(m[2])) * 1000
        end = (int(m[3]) * 60 + int(m[4])) * 1000
        if end > start:
            result.append({"start_ms": start, "end_ms": end})
    return result


def build_context(form):
    """Valide le formulaire. Lève ValueError avec un message exploitable."""
    if form.get("consent_processing") != "on":
        raise ValueError("Confirmez que vous êtes autorisé à traiter cette vidéo.")
    if form.get("consent_provider") != "on":
        raise ValueError("Confirmez l'envoi d'images et de dialogue au fournisseur d'analyse (Gemini).")
    unknown = []
    context = {"work_type": form.get("work_type") if form.get("work_type") in WORK_TYPES else "Autre"}
    for key in TEXT_FIELDS:
        if form.get(key + "_unknown") == "on" or not form.get(key, "").strip():
            context[key] = "Inconnu"
            unknown.append(key)
        else:
            context[key] = form[key].strip()[:200]
    excluded = [c for c in form.getlist("excluded_categories") if c in CATEGORIES] \
        if hasattr(form, "getlist") else []
    context["excluded_categories"] = excluded
    context["excluded_intervals_text"] = form.get("excluded_intervals", "").strip()[:300]
    context["excluded_intervals"] = parse_intervals(context["excluded_intervals_text"])
    context["extra_description"] = form.get("description", "").strip()[:1000]
    context["unknown_fields"] = unknown
    context["consent"] = {"processing": True, "provider": True,
                          "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                          "provider_name": "Google Gemini (images échantillonnées, dialogue voisin, description)"}
    return context


def to_description(context):
    """Texte fourni au modèle, présenté comme donnée du producteur."""
    parts = [f"Type d'œuvre : {context['work_type']}."]
    for key, label in TEXT_FIELDS.items():
        parts.append(f"{label} : {context[key]}.")
    if context["excluded_categories"]:
        parts.append("Catégories de produits exclues par le producteur : "
                     + ", ".join(CATEGORIES[c] for c in context["excluded_categories"]) + ".")
    if context["excluded_intervals_text"]:
        parts.append("Intervalles à ne pas modifier : " + context["excluded_intervals_text"] + ".")
    if context["extra_description"]:
        parts.append(context["extra_description"])
    return " ".join(parts)[:2000]


def load_context(folder):
    path = folder / "context.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


EDITABLE = {"location", "period", "languages", "intention"}


def update_context(folder, changes):
    """Le producteur complète ou corrige le contexte après l'import (lieu, époque, langues, intention)."""
    from video_analyzer.review import replace_json
    context = load_context(folder) or {"work_type": "Autre", "excluded_categories": [], "excluded_intervals": [],
                                       "excluded_intervals_text": "", "extra_description": "", "unknown_fields": []}
    for key in EDITABLE:
        if key in changes:
            value = (changes.get(key) or "").strip()[:200]
            context[key] = value or "Inconnu"
    context["unknown_fields"] = [k for k in TEXT_FIELDS if context.get(k, "Inconnu") == "Inconnu"]
    context["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    replace_json(folder / "context.json", context)
    return context
