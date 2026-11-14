"""SceneLine · Cultural Integrity Guard : risque culturel et narratif d'un placement.

Avant de recommander un placement, le Guard évalue cinq dimensions et donne un risque global
(faible, moyen, élevé) avec une justification pour chacune. Un risque élevé déclenche une alerte
qui déconseille l'insertion. La décision finale reste au réalisateur.

Le Guard ne fait aucun appel supplémentaire à un modèle : il rassemble et explique les signaux déjà
calculés (protection et contexte des scènes, ajustement éditorial, restrictions du producteur, règles
d'époque et de catégorie, point culturel relevé par l'appariement).
"""

import re

from product_matcher.catalog import CATEGORIES, effective

LEVELS = ["faible", "moyen", "eleve"]
LABELS = {"faible": "Risque faible", "moyen": "Risque moyen", "eleve": "Risque élevé"}
HISTORICAL = re.compile(r"(histor|ancien|m[ée]di[ée]val|colonial|18\d\d|19[0-7]\d|années?\s*(20|30|40|50|60|70))", re.I)
CULTURAL = re.compile(r"(rite|rituel|c[ée]r[ée]monie|religi|pri[èe]re|tradition|patrimoin|comm[ée]mor|deuil|fête religieuse|ramadan|mariage)", re.I)
NEAR_MS = 6000   # un placement à moins de 6 s d'une scène sensible est signalé

# Lieux reconnus. La langue parlée n'est jamais utilisée : seul un lieu déclaré par le producteur,
# ou un lieu explicitement relevé dans la scène, situe l'histoire.
PLACES = {
    "France": ["france", "paris", "lyon", "marseille", "toulouse", "lille", "bordeaux", "nantes", "strasbourg", "nice"],
    "Tunisie": ["tunisie", "tunis", "sfax", "sousse", "bizerte", "kairouan", "nabeul", "djerba", "monastir"],
    "Maroc": ["maroc", "casablanca", "rabat", "marrakech", "tanger", "agadir"],
    "Algérie": ["algerie", "alger", "oran", "constantine"],
    "Belgique": ["belgique", "bruxelles", "liege", "anvers"],
    "Suisse": ["suisse", "geneve", "lausanne", "zurich"],
    "Canada": ["canada", "quebec", "montreal"],
    "Sénégal": ["senegal", "dakar"],
    "Côte d'Ivoire": ["cote d'ivoire", "abidjan"],
    "Liban": ["liban", "beyrouth"],
    "Égypte": ["egypte", "le caire"],
}
ADJECTIVE = {"France": "française", "Tunisie": "tunisienne", "Maroc": "marocaine", "Algérie": "algérienne",
             "Belgique": "belge", "Suisse": "suisse", "Canada": "canadienne", "Sénégal": "sénégalaise",
             "Côte d'Ivoire": "ivoirienne", "Liban": "libanaise", "Égypte": "égyptienne"}


def _plain(text):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", (text or "").lower()) if unicodedata.category(c) != "Mn")


def country_of(text):
    plain = _plain(text)
    for country, words in PLACES.items():
        if any(re.search(r"\b" + re.escape(word) + r"\b", plain) for word in words):
            return country
    return None


def setting_country(context, scene):
    """Pays de l'action : déclaré par le producteur, sinon explicitement relevé dans la scène."""
    declared = country_of((context or {}).get("location", ""))
    if declared:
        return declared, "déclaré par le producteur"
    seen = country_of(scene.get("location", ""))
    return (seen, "relevé dans la scène") if seen else (None, None)


def geographic(product, attrs, context, scene):
    """Cohérence entre le lieu de l'action et le marché du produit. Retourne (niveau, texte) ou None."""
    if not product:
        return None
    origin = country_of(attrs.get("origin", ""))
    markets = [m for m in (country_of(x) for x in attrs.get("markets", [])) if m]
    if not origin and not markets:
        return None
    country, source = setting_country(context, scene)
    if not country:
        return ("faible", "Lieu de l'action non déclaré : la cohérence géographique de " + product["name"] +
                " n'est pas évaluée (la langue parlée ne suffit pas à situer l'histoire).")
    kind = ("marque " + ADJECTIVE[origin]) if origin else "marque"
    if markets and country not in markets:
        return ("eleve", f"L'action se passe en {country} ({source}). {product['name']} est une {kind} dont la campagne "
                         f"vise : {', '.join(markets)}. Dans ce décor, elle ne correspondrait ni au lieu ni au public de "
                         "l'œuvre et nuirait à son authenticité culturelle.")
    return ("faible", f"L'action se passe en {country} ({source}) ; {product['name']} ({kind}) y est cohérent.")


def worst(*levels):
    return max(levels, key=LEVELS.index)


def dim(key, label, level, text):
    return {"key": key, "label": label, "level": level, "text": text}


def assess_scene(scene):
    """Verdict du Guard pour une scène entière."""
    if scene["protection"] == "protected":
        level = "eleve"
        text = ("Scène protégée : " + (scene["protection_reason"] or "contenu à ne pas modifier").rstrip(". ") +
                ". Aucun placement ne doit y être inséré.")
    elif scene["protection"] == "uncertain":
        level, text = "moyen", "Sensibilité à vérifier par le réalisateur : " + (scene["protection_reason"] or "contexte incertain") + "."
    else:
        level, text = "faible", "Aucun élément sensible relevé dans cette scène."
    return {"level": level, "label": LABELS[level], "text": text,
            "alert": level == "eleve", "kind": scene["kind"]}


def _near_sensitive(opp, scene, scenes):
    for other in scenes:
        if other["id"] == scene["id"] or other["kind"] == "generique" or other["protection"] != "protected":
            continue
        gap = max(other["start_ms"] - opp["end_ms"], opp["start_ms"] - other["end_ms"], 0)
        if gap <= NEAR_MS:
            return other, gap
    return None, None


def assess(opp, scene, scenes, context=None, product=None, score=None, revision=None):
    """Risque culturel et narratif d'un placement. `product`, `score` et `revision` sont facultatifs
    (avant l'appariement, seul le placement existe)."""
    start = (revision or opp)["start_ms"]
    end = (revision or opp)["end_ms"]
    span = {"start_ms": start, "end_ms": end}
    attrs = effective(product) if product else None
    period = scene.get("period", "Inconnu")

    # 1. Contexte historique
    if attrs and attrs["era_constraint"] == "contemporain_seulement" and HISTORICAL.search(period):
        historical = dim("historique", "Contexte historique", "eleve", f"Produit contemporain dans une scène d'époque ({period}).")
    elif HISTORICAL.search(period):
        historical = dim("historique", "Contexte historique", "moyen", f"Œuvre d'époque ({period}) : vérifier que le produit y existait.")
    elif period.lower().startswith("inconnu"):
        historical = dim("historique", "Contexte historique", "faible", "Époque non précisée : aucune contradiction détectée.")
    else:
        historical = dim("historique", "Contexte historique", "faible", f"Époque représentée : {period.lower()}. Aucun anachronisme détecté.")

    # 2. Contexte culturel (dont la cohérence géographique du produit)
    geo = geographic(product, attrs or {}, context, scene)
    flag = (score or {}).get("cultural_flag") or ""
    protected_reason = scene.get("protection_reason", "")
    cues = scene.get("cultural_cues", "")
    if scene["protection"] == "protected" and CULTURAL.search(protected_reason):
        cultural = dim("culturel", "Contexte culturel", "eleve", "Élément culturel ou traditionnel à préserver : " + protected_reason)
    elif geo and geo[0] == "eleve":
        cultural = dim("culturel", "Contexte culturel", "eleve", geo[1])
    elif geo and flag:
        cultural = dim("culturel", "Contexte culturel", "moyen", geo[1] + " Point culturel à valider : " + flag)
    elif flag:
        cultural = dim("culturel", "Contexte culturel", "moyen", "Point culturel à valider : " + flag)
    elif geo:
        cultural = dim("culturel", "Contexte culturel", "faible", geo[1])
    elif cues and cues != "Aucun indice relevé":
        cultural = dim("culturel", "Contexte culturel", "faible", "Indices culturels relevés : " + cues.rstrip(". ") + ". Aucun conflit avec le placement.")
    else:
        cultural = dim("culturel", "Contexte culturel", "faible", "Aucun élément culturel sensible relevé dans l'image ni dans le dialogue.")

    # 3. Cohérence narrative
    coherence = (score or {}).get("narrative_coherence", opp.get("editorial_fit"))
    distraction = opp.get("action_distraction", "moyen")
    if coherence is None:
        narrative = dim("narratif", "Cohérence narrative", "moyen", "Cohérence non évaluée.")
    else:
        level = "faible" if coherence >= 8 else "moyen" if coherence >= 6 else "eleve"
        if distraction == "eleve":
            level = worst(level, "eleve")
        elif distraction == "moyen":
            level = worst(level, "moyen") if coherence < 9 else level
        narrative = dim("narratif", "Cohérence narrative", level,
                        f"Cohérence avec l'histoire {coherence}/10 ; gêne pour l'action : {distraction}. Ton de la scène : {scene.get('tone', 'inconnu').lower()}.")

    # 4. Sensibilité de la scène
    if scene["protection"] == "protected":
        sensitivity = dim("sensibilite", "Sensibilité de la scène", "eleve", "Scène protégée : " + (protected_reason or "contenu sensible") + ".")
    elif scene["protection"] == "uncertain":
        sensitivity = dim("sensibilite", "Sensibilité de la scène", "moyen", "Sensibilité à vérifier : " + (protected_reason or "contexte incertain") + ".")
    else:
        other, gap = _near_sensitive(span, scene, scenes)
        if other:
            sensitivity = dim("sensibilite", "Sensibilité de la scène", "moyen",
                              f"Scène elle-même sans sensibilité, mais à {gap / 1000:.1f} s d'une scène protégée ({other['protection_reason'].rstrip('.')}).")
        else:
            sensitivity = dim("sensibilite", "Sensibilité de la scène", "faible", "Ni religieuse, ni commémorative, ni émotionnellement sensible.")

    # 5. Intention artistique (restrictions du réalisateur)
    violated = []
    if context:
        for zone in context.get("excluded_intervals", []):
            if span["start_ms"] < zone["end_ms"] and zone["start_ms"] < span["end_ms"]:
                violated.append("intervalle exclu par le réalisateur")
        if attrs and attrs["category"] in context.get("excluded_categories", []):
            violated.append("catégorie exclue : " + CATEGORIES[attrs["category"]])
    declared = len((context or {}).get("excluded_categories", [])) + len((context or {}).get("excluded_intervals", []))
    if violated:
        artistic = dim("intention", "Intention artistique", "eleve", "Restriction du réalisateur non respectée : " + " ; ".join(violated) + ".")
    elif declared:
        artistic = dim("intention", "Intention artistique", "faible", f"{declared} restriction(s) du réalisateur déclarée(s), toutes respectées.")
    else:
        artistic = dim("intention", "Intention artistique", "faible", "Aucune restriction du réalisateur enfreinte (aucune déclarée pour cet intervalle).")

    dimensions = [historical, cultural, narrative, sensitivity, artistic]
    level = worst(*(d["level"] for d in dimensions))
    drivers = [d for d in dimensions if d["level"] == level and level != "faible"]
    if level == "faible":
        summary = "Aucun point de vigilance : le placement respecte l'époque, la culture, l'histoire et les consignes."
    else:
        summary = " ".join(d["label"] + " : " + d["text"] for d in drivers)
    alert = None
    if level == "eleve":
        alert = {"title": "Alerte : insertion déconseillée",
                 "text": "SceneLine recommande de ne pas insérer ce placement. La décision finale appartient au réalisateur."}
    return {"level": level, "label": LABELS[level], "dimensions": dimensions, "summary": summary, "alert": alert}
