"""Empreinte canonique d'une révision de placement, sans dépendance vidéo."""

import hashlib
import hmac
import json


REVISION_DIGEST_VERSION = 2


def digest(revision, version=REVISION_DIGEST_VERSION):
    """Calcule l'empreinte des paramètres approuvés d'une révision.

    La version 1, tronquée à 16 caractères, reste disponible pour relire les
    décisions déjà enregistrées. La version 2 couvre aussi la surface, la
    région et l'alignement temporel, et conserve le SHA-256 complet.
    """
    if version == 1:
        stable = {k: revision[k] for k in ("n", "product_id", "start_ms", "end_ms", "mode", "scale")}
        # Reproduit strictement la sérialisation historique (espaces et
        # ensure_ascii par défaut), afin de valider les décisions existantes.
        legacy = json.dumps(stable, sort_keys=True).encode()
        return hashlib.sha256(legacy).hexdigest()[:16]
    elif version == REVISION_DIGEST_VERSION:
        stable = {
            "n": revision["n"],
            "product_id": revision["product_id"],
            "start_ms": revision["start_ms"],
            "end_ms": revision["end_ms"],
            "mode": revision["mode"],
            "scale": revision["scale"],
            "surface": revision.get("surface"),
            "region": revision.get("region"),
            "starts_on_cut": bool(revision.get("starts_on_cut", False)),
            "ends_on_cut": bool(revision.get("ends_on_cut", False)),
            "outside_verified_window": bool(revision.get("outside_verified_window", False)),
            "reference_frame": revision.get("reference_frame"),
        }
    else:
        raise ValueError(f"Version d'empreinte inconnue : {version}")
    canonical = json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def decision_matches_revision(decision, revision):
    """Vérifie qu'une décision porte bien sur le contenu actuel de la révision."""
    try:
        version = int(decision.get("revision_digest_version", 1))
        expected = digest(revision, version)
    except (KeyError, TypeError, ValueError):
        return False
    return hmac.compare_digest(str(decision.get("revision_digest", "")), expected)
