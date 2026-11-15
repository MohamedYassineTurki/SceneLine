"""SceneLine · annuaire d'annonceurs volontaires pour le parcours « Recherche d'opportunités ».

L'annuaire (`demo_advertisers/annuaire.json`) est une liste statique, en lecture seule, d'annonceurs
qui se sont déclarés volontaires. Elle est marquée « Annuaire de démonstration » : aucun des
annonceurs n'est une entreprise réelle. Si aucun annonceur inscrit ne correspond à une opportunité,
`match()` renvoie des types de partenaires génériques, jamais le nom d'une entreprise non inscrite.

Aucun appel à un modèle ici : on ne fait que croiser des catégories, des marchés et des types
d'œuvre déjà déclarés, exactement comme `cultural_guard.guard` croise des signaux déjà calculés.
"""

import json
from pathlib import Path

from cultural_guard.guard import country_of, setting_country
from product_matcher.catalog import CATEGORIES, CATEGORY_KEYWORDS

ROOT = Path(__file__).resolve().parents[2]
ANNUAIRE = ROOT / "demo_advertisers" / "annuaire.json"


def load_directory():
    """Annuaire de démonstration : lu tel quel, jamais modifié par un projet."""
    if not ANNUAIRE.is_file():
        return []
    return json.loads(ANNUAIRE.read_text(encoding="utf-8"))


def _texts_mention(category, texts):
    """Un des textes libres (compatible_categories/avoid_categories) évoque-t-il cette catégorie ?

    Même heuristique que `product_matcher.matching.rule_check` : les mots-clés de la catégorie,
    recherchés dans le texte libre renvoyé par la revue de l'intervalle."""
    keywords = CATEGORY_KEYWORDS.get(category, [])
    for text in texts or []:
        plain = text.lower().replace("_", " ")
        if any(word in plain for word in keywords):
            return True
    return False


def _budget_text(advertiser):
    lo, hi = advertiser.get("budget_min"), advertiser.get("budget_max")
    currency = advertiser.get("currency", "EUR")
    if not (isinstance(lo, (int, float)) and isinstance(hi, (int, float))):
        return ""
    return f"{lo:g}–{hi:g} {currency}"


def _texts_mention_any(label, avoid_texts):
    plain = label.lower()
    return any(plain == text.strip().lower() for text in avoid_texts or [])


def match(opportunity, scene, context, directory):
    """Annonceurs inscrits compatibles avec cette opportunité, et des types de repli sinon.

    Retourne (matches, fallback) :
      - matches : [{advertiser, why}], annonceurs inscrits dont au moins une catégorie correspond
        aux catégories jugées compatibles par la revue de l'intervalle (et aucune aux catégories à
        éviter), et dont le type d'œuvre et le marché déclarés, s'ils existent, ne contredisent pas
        le projet ;
      - fallback : [str], types de partenaires à démarcher, construits uniquement à partir des
        catégories compatibles déjà relevées (jamais un nom d'entreprise non inscrite)."""
    compatible = opportunity.get("compatible_categories") or []
    avoid = opportunity.get("avoid_categories") or []
    work_type = (context or {}).get("work_type")
    country, _source = setting_country(context or {}, scene or {})

    matches = []
    for advertiser in directory:
        hit_categories = [c for c in advertiser.get("categories", [])
                          if c in CATEGORIES and _texts_mention(c, compatible) and not _texts_mention(c, avoid)]
        if not hit_categories:
            continue
        work_types = advertiser.get("work_types") or []
        if work_types and work_type and work_type not in work_types:
            continue
        markets = [m for m in (advertiser.get("markets") or []) if country_of(m)]
        if markets and country and country not in markets:
            continue
        reasons = ["catégorie(s) commune(s) : " + ", ".join(CATEGORIES[c] for c in hit_categories)]
        if country and markets:
            reasons.append(f"marché visé compatible avec {country}")
        budget = _budget_text(advertiser)
        if budget:
            reasons.append("budget déclaré : " + budget)
        matches.append({
            "id": advertiser["id"], "name": advertiser["name"], "description": advertiser.get("description", ""),
            "provenance": advertiser.get("provenance", "Annuaire de démonstration"),
            "budget": budget, "why": " ; ".join(reasons) + ".",
        })

    fallback = []
    if not matches:
        seen = set()
        for text in compatible:
            label = text.strip().rstrip(". ")
            if not label or label.lower() in seen or _texts_mention_any(label, avoid):
                continue
            seen.add(label.lower())
            suffix = f" visant le marché {country}" if country else ""
            fallback.append(f"Marque ou annonceur du secteur « {label} »{suffix}.")
    return matches, fallback
