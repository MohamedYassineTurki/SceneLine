"""SceneLine · Rapport d'opportunités (parcours « Recherche d'opportunités »).

Pour un créateur qui n'a pas encore de sponsor : quels emplacements sa vidéo permettrait de
monétiser, avant même de démarcher qui que ce soit. Ce module ne refait aucune analyse : il relit
`sceneline.json` (scènes, opportunités, scores déjà calculés par `video_analyzer.understand`) et
`context.json`, et y ajoute une lecture adaptée à la recherche de financement :
  - quatre indicateurs mesurés (jamais estimés) ;
  - les mêmes opportunités « keep » que le parcours habituel, dans le même ordre, avec les
    annonceurs de l'annuaire qui leur correspondent ;
  - des conseils de monétisation écrits en code à partir de ces mêmes chiffres ;
  - l'avertissement que la plateforme ne garantit aucun revenu.

Aucun appel à un modèle ici, exactement comme `cultural_guard.guard`.
"""

import json

from cultural_guard import guard
from opportunity_finder import advertisers

DISCLAIMER = ("La plateforme ne garantit pas l'obtention de financements : les revenus dépendent "
             "des accords conclus avec les annonceurs.")
DIRECTORY_NOTICE = ("Annuaire de démonstration : ces annonceurs sont fictifs. Aucun accord réel, "
                    "aucun partenariat, aucune entreprise non inscrite n'est jamais citée.")


def duration_text(ms):
    seconds = round(ms / 1000)
    minutes, seconds = divmod(seconds, 60)
    return f"{minutes} min {seconds:02d} s" if minutes else f"{seconds} s"


def build(folder):
    sceneline = json.loads((folder / "sceneline.json").read_text(encoding="utf-8"))
    if sceneline.get("status") != "complete":
        raise ValueError("L'analyse de la vidéo n'est pas terminée.")
    context_path = folder / "context.json"
    context = json.loads(context_path.read_text(encoding="utf-8")) if context_path.is_file() else {}
    scenes = {s["id"]: s for s in sceneline["scenes"]}
    opportunities = sceneline.get("opportunities", [])
    nonrejected = [o for o in opportunities if o.get("decision") not in (None, "reject")]
    kept = sorted((o for o in nonrejected if o["decision"] == "keep"), key=lambda o: o["rank"])

    verdicts = {o["key"]: guard.assess(o, scenes[o["scene_id"]], sceneline["scenes"], context) for o in nonrejected}
    directory = advertisers.load_directory()

    categories = {text.strip().lower() for o in nonrejected for text in o.get("compatible_categories", []) if text.strip()}
    total_screen_ms = sum(o["end_ms"] - o["start_ms"] for o in kept)
    discouraged = sum(1 for o in nonrejected if verdicts[o["key"]]["level"] == "eleve")

    report_items = []
    for item in kept:
        scene = scenes[item["scene_id"]]
        matches, fallback = advertisers.match(item, scene, context, directory)
        report_items.append(dict(item,
            guard=verdicts[item["key"]],
            scene_summary=scene["summary"], scene_location=scene["location"],
            scene_period=scene["period"], scene_tone=scene["tone"],
            advertiser_matches=matches, advertiser_fallback=fallback))

    indicators = {
        "potential_locations": len(nonrejected),
        "compatible_categories": len(categories),
        "total_screen_time_ms": total_screen_ms,
        "total_screen_time_text": duration_text(total_screen_ms),
        "guard_discouraged": discouraged,
    }

    tips = []
    if kept:
        tips.append(f"{len(kept)} emplacement(s) déjà vérifié(s) totalisent {duration_text(total_screen_ms)} "
                    "de visibilité à l'écran : un argument chiffré à présenter aux annonceurs.")
        avg_score = round(sum(o["overall_score"] for o in kept) / len(kept), 1)
        tips.append(f"Score moyen de {avg_score}/10 sur les placements retenus, chacun vérifié sur six images : "
                    "un gage de fiabilité technique, pas seulement une promesse.")
    if categories:
        tips.append("Les emplacements repérés sont surtout compatibles avec : " + ", ".join(sorted(categories)[:5])
                    + ". Démarchez d'abord les annonceurs de ces secteurs.")
    avoid = {text.strip().lower() for o in nonrejected for text in o.get("avoid_categories", []) if text.strip()}
    if avoid:
        tips.append("Évitez de démarcher les secteurs suivants, déconseillés par l'analyse de vos scènes : "
                    + ", ".join(sorted(avoid)[:5]) + ".")
    if discouraged:
        tips.append(f"{discouraged} emplacement(s) sont déconseillés par le Cultural Integrity Guard : "
                    "à exclure de toute proposition commerciale, quel que soit l'intérêt de l'annonceur.")
    if not tips:
        tips.append("Aucun emplacement retenu pour l'instant : revoyez le contexte déclaré ou le résultat de "
                    "l'analyse avant de démarcher un annonceur.")

    return {
        "indicators": indicators, "opportunities": report_items, "monetization_tips": tips[:5],
        "disclaimer": DISCLAIMER, "directory_notice": DIRECTORY_NOTICE,
    }
