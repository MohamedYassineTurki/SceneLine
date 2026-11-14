"""SceneLine · propositions, révisions et décisions du producteur (F05).

proposals.json : une proposition par opportunité retenue, avec des révisions numérotées.
decisions.json : journal des décisions, uniquement ajouté, jamais modifié.
Seule la dernière révision peut être décidée. Une révision approuvée n'est jamais modifiée :
un changement de produit, d'intervalle ou de taille crée une nouvelle révision à approuver.
"""

import hashlib
import json
import threading
from datetime import datetime, timezone

from cultural_guard import guard
from product_matcher.catalog import load_catalog
from product_matcher.matching import load_matching, producer_interval_exclusion, rule_check
from video_analyzer.context import load_context
from video_analyzer.review import replace_json

LOCK = threading.RLock()
ACTIONS = {"accepter", "refuser", "ajuster", "reviser"}
ADJUSTMENTS = {"decaler", "reduire", "changer_produit", "intervalle", "autre"}
MIN_DURATION_MS = 1500


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read(folder, name, empty):
    path = folder / name
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else empty


def digest(revision):
    stable = {k: revision[k] for k in ("n", "product_id", "start_ms", "end_ms", "mode", "scale")}
    return hashlib.sha256(json.dumps(stable, sort_keys=True).encode()).hexdigest()[:16]


def decision_for(decisions, pid, n):
    # « reviser » ouvre une nouvelle révision : ce n'est pas une décision sur cette révision.
    found = [d for d in decisions if d["proposal_id"] == pid and d["revision"] == n and d["action"] != "reviser"]
    return found[-1] if found else None


def new_revision(n, opp, product_id, score, origin, extra=None):
    revision = {
        "n": n, "product_id": product_id, "start_ms": opp["start_ms"], "end_ms": opp["end_ms"],
        "mode": opp["placement_mode"], "scale": 1.0, "region": opp["region"],
        "starts_on_cut": opp.get("starts_on_cut", False), "ends_on_cut": opp.get("ends_on_cut", False),
        "reference_frame": opp["reference_frame"], "surface": opp["surface"],
        "score": score, "origin": origin, "created_at": now(), "adjustment_request": None,
    }
    revision.update(extra or {})
    return revision


def sync_proposals(folder):
    """Crée ou révise les propositions d'après le dernier matching. Les décisions restent intactes."""
    sceneline = json.loads((folder / "sceneline.json").read_text(encoding="utf-8"))
    opps = {o["key"]: o for o in sceneline["opportunities"]}
    matching = load_matching(folder)
    with LOCK:
        store = read(folder, "proposals.json", {"proposals": {}})
        decisions = read(folder, "decisions.json", {"decisions": []})["decisions"]
        for key, entry in matching["opportunities"].items():
            opp = opps.get(key)
            if not opp:
                continue
            pid = f"p-{key}"
            proposal = store["proposals"].get(pid)
            best = entry.get("best")
            if proposal:
                proposal["no_suitable_reason"] = None if best else entry.get("no_suitable_reason")
            if not best:
                continue
            score = entry["scores"][best]
            if not proposal:
                store["proposals"][pid] = {
                    "id": pid, "opportunity_key": key, "no_suitable_reason": None,
                    "revisions": [new_revision(1, opp, best, score, "matching")]}
                continue
            latest = proposal["revisions"][-1]
            if latest["product_id"] == best:
                latest["score"] = score
                continue
            if decision_for(decisions, pid, latest["n"]) is None and latest["origin"] != "matching":
                continue  # révision demandée par le réviseur, en attente de décision : on n'y touche pas
            if decision_for(decisions, pid, latest["n"]) is None:
                proposal["revisions"][-1] = new_revision(latest["n"], opp, best, score, "matching")
            else:
                proposal["revisions"].append(new_revision(latest["n"] + 1, opp, best, score, "matching"))
        replace_json(folder / "proposals.json", store)


def status_of(proposal, decisions):
    latest = proposal["revisions"][-1]
    decision = decision_for(decisions, proposal["id"], latest["n"])
    if not decision:
        return "en_attente"
    return {"accepter": "approuvee", "refuser": "refusee", "ajuster": "ajustement_demande"}[decision["action"]]


def source_of(opp, sceneline):
    """Traçabilité : l'opportunité de l'étape 1 dont la proposition est issue."""
    scene = next(s for s in sceneline["scenes"] if s["id"] == opp["scene_id"])
    return {
        "key": opp["key"], "rank": opp.get("rank"), "shot_id": opp["shot_id"],
        "start_ms": opp["start_ms"], "end_ms": opp["end_ms"], "overall_score": opp["overall_score"],
        "surface": opp["surface"], "reason": opp["reason"], "alignment": opp.get("alignment", ""),
        "trimmed": opp.get("trimmed"),
        "verification": (opp.get("verification") or {}).get("note", ""),
        "scene": {k: scene[k] for k in ("id", "start_ms", "end_ms", "summary", "location", "period", "tone")},
        "compatible_categories": opp.get("compatible_categories", []),
        "avoid_categories": opp.get("avoid_categories", []),
    }


def view(folder):
    """Données affichées dans l'interface de revue."""
    store = read(folder, "proposals.json", {"proposals": {}})
    decisions = read(folder, "decisions.json", {"decisions": []})["decisions"]
    matching = load_matching(folder)
    catalog = {p["id"]: p for p in load_catalog(folder)["products"]}
    sceneline = json.loads((folder / "sceneline.json").read_text(encoding="utf-8"))
    opps = {o["key"]: o for o in sceneline["opportunities"]}
    proposals = []
    for proposal in store["proposals"].values():
        latest = proposal["revisions"][-1]
        approved = [r for r in proposal["revisions"] if (decision_for(decisions, proposal["id"], r["n"]) or {}).get("action") == "accepter"]
        status = status_of(proposal, decisions)
        proposals.append(dict(
            proposal, status=status, latest=latest,
            product_name=catalog.get(latest["product_id"], {}).get("name", latest["product_id"]),
            approved_revision=approved[-1]["n"] if approved else None,
            render_eligible=status == "approuvee",
            history=[d for d in decisions if d["proposal_id"] == proposal["id"]],
            scene_id=opps[proposal["opportunity_key"]]["scene_id"],
            guard=guard.assess(
                opps[proposal["opportunity_key"]],
                next(sc for sc in sceneline["scenes"] if sc["id"] == opps[proposal["opportunity_key"]]["scene_id"]),
                sceneline["scenes"], load_context(folder), catalog.get(latest["product_id"]), latest.get("score"), latest),
            source=source_of(opps[proposal["opportunity_key"]], sceneline),
            alternatives=sorted(
                ({"product_id": pid, "name": catalog.get(pid, {}).get("name", pid), "overall": s["overall"],
                  "verdict": s["verdict"], "justification": s["justification"],
                  "guard_level": s.get("guard_level"), "guard_summary": s.get("guard_summary", "")}
                 for pid, s in matching["opportunities"].get(proposal["opportunity_key"], {}).get("scores", {}).items()),
                key=lambda item: -item["overall"])))
    proposals.sort(key=lambda p: p["latest"]["start_ms"])
    unmatched = []
    for key, entry in matching["opportunities"].items():
        if f"p-{key}" not in store["proposals"] and key in opps:
            unmatched.append({"opportunity_key": key, "start_ms": opps[key]["start_ms"], "end_ms": opps[key]["end_ms"],
                              "surface": opps[key]["surface"], "reason": entry.get("no_suitable_reason") or "Aucun produit évalué."})
    exclusions = []
    for key, entry in matching["opportunities"].items():
        for pid, reason in entry.get("rule_exclusions", {}).items():
            exclusions.append({"opportunity_key": key, "product_id": pid,
                               "product_name": catalog.get(pid, {}).get("name", pid), "reason": reason,
                               "start_ms": opps[key]["start_ms"] if key in opps else 0})
    return {"proposals": proposals, "unmatched": unmatched, "exclusions": exclusions,
            "catalog_version": matching.get("catalog_version"), "decisions": decisions}


class DecisionError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def decide(folder, proposal_id, action, reviewer, comment="", adjustment=None, revision=None):
    if action not in ACTIONS:
        raise DecisionError("Action inconnue.")
    reviewer = (reviewer or "").strip()[:80]
    if not reviewer:
        raise DecisionError("Indiquez le nom du réviseur.")
    comment = (comment or "").strip()[:500]
    with LOCK:
        store = read(folder, "proposals.json", {"proposals": {}})
        proposal = store["proposals"].get(proposal_id)
        if not proposal:
            raise DecisionError("Proposition introuvable.", 404)
        latest = proposal["revisions"][-1]
        if revision is not None and revision != latest["n"]:
            raise DecisionError("Cette révision n'est plus la dernière : rechargez la proposition.", 409)
        log = read(folder, "decisions.json", {"decisions": []})
        already = decision_for(log["decisions"], proposal_id, latest["n"])
        if action == "reviser" and not already:
            raise DecisionError("Décidez d'abord la révision en cours.", 409)
        if action != "reviser" and already:
            raise DecisionError("Cette révision a déjà fait l'objet d'une décision.", 409)
        payload = None
        if action == "accepter":
            sceneline = json.loads((folder / "sceneline.json").read_text(encoding="utf-8"))
            opp = next(o for o in sceneline["opportunities"] if o["key"] == proposal["opportunity_key"])
            scene = next(s for s in sceneline["scenes"] if s["id"] == opp["scene_id"])
            product = next((p for p in load_catalog(folder)["products"] if p["id"] == latest["product_id"]), None)
            if not product:
                raise DecisionError("Le produit n'existe plus dans le catalogue.", 409)
            reason = (producer_interval_exclusion(dict(opp, start_ms=latest["start_ms"], end_ms=latest["end_ms"]), load_context(folder))
                      or rule_check(dict(opp, placement_mode=latest["mode"]), scene, product, load_context(folder)))
            if reason:
                raise DecisionError("Approbation impossible : " + reason, 409)
        subject = latest
        if action in {"ajuster", "reviser"}:
            payload, revised = apply_adjustment(folder, proposal, latest, adjustment or {}, comment)
            proposal["revisions"].append(revised)
            if action == "reviser":
                subject = revised   # l'entrée décrit la nouvelle révision ; l'ancienne décision reste intacte
        entry = {
            "id": f"d-{len(log['decisions']) + 1}", "proposal_id": proposal_id, "revision": subject["n"],
            "revision_digest": digest(subject), "action": action, "reviewer": reviewer,
            "comment": comment, "payload": payload, "at": now()}
        log["decisions"].append(entry)
        replace_json(folder / "decisions.json", log)
        replace_json(folder / "proposals.json", store)
    return entry


def apply_adjustment(folder, proposal, latest, adjustment, comment):
    kind = adjustment.get("type")
    if kind not in ADJUSTMENTS:
        raise DecisionError("Type d'ajustement inconnu.")
    sceneline = json.loads((folder / "sceneline.json").read_text(encoding="utf-8"))
    opp = next(o for o in sceneline["opportunities"] if o["key"] == proposal["opportunity_key"])
    shot = next(s for s in sceneline["shots"] if s["id"] == opp["shot_id"])
    revised = dict(latest, n=latest["n"] + 1, origin="ajustement", created_at=now(),
                   adjustment_request={"type": kind, "comment": comment})
    payload = {"type": kind}
    if kind == "decaler":
        try:
            shift = int(adjustment.get("shift_ms"))
        except (TypeError, ValueError):
            raise DecisionError("Indiquez le décalage en millisecondes.") from None
        length = latest["end_ms"] - latest["start_ms"]
        start = max(shot["start_ms"], min(shot["end_ms"] - length, latest["start_ms"] + shift))
        if length < MIN_DURATION_MS:
            raise DecisionError("Intervalle trop court.")
        revised.update(start_ms=start, end_ms=start + length)
        revised["outside_verified_window"] = not (opp["start_ms"] <= start and start + length <= opp["end_ms"])
        revised["starts_on_cut"] = abs(start - shot["start_ms"]) <= 40
        revised["ends_on_cut"] = abs(start + length - shot["end_ms"]) <= 40
        payload["shift_ms"] = start - latest["start_ms"]
        payload["requested_shift_ms"] = shift
        revised["adjustment_request"]["requested_shift_ms"] = shift
        revised["adjustment_request"]["applied_shift_ms"] = payload["shift_ms"]
        if payload["shift_ms"] == 0:
            raise DecisionError("Le décalage reste dans les limites du plan : aucun changement possible.")
    elif kind == "intervalle":
        try:
            first = round(float(adjustment.get("start_s")) * 1000)
            last = round(float(adjustment.get("end_s")) * 1000)
        except (TypeError, ValueError):
            raise DecisionError("Indiquez le début et la fin en secondes dans la vidéo source.") from None
        if not shot["start_ms"] <= first < last <= shot["end_ms"]:
            raise DecisionError("L'intervalle doit rester dans le plan : "
                                f"{shot['start_ms'] / 1000:.2f} s à {shot['end_ms'] / 1000:.2f} s.")
        if last - first < MIN_DURATION_MS:
            raise DecisionError("Intervalle trop court.")
        revised.update(start_ms=first, end_ms=last,
                       starts_on_cut=abs(first - shot["start_ms"]) <= 40,
                       ends_on_cut=abs(last - shot["end_ms"]) <= 40)
        revised["outside_verified_window"] = not (opp["start_ms"] <= first and last <= opp["end_ms"])
        payload.update(start_ms=first, end_ms=last)
    elif kind == "reduire":
        try:
            scale = round(float(adjustment.get("scale")), 2)
        except (TypeError, ValueError):
            raise DecisionError("Indiquez une taille entre 30 % et 95 %.") from None
        if not 0.3 <= scale <= 0.95:
            raise DecisionError("La taille doit être comprise entre 30 % et 95 %.")
        revised["scale"] = round(latest["scale"] * scale, 2)
        payload["scale"] = scale
    elif kind == "changer_produit":
        pid = adjustment.get("product_id")
        product = next((p for p in load_catalog(folder)["products"] if p["id"] == pid), None)
        if not product or pid == latest["product_id"]:
            raise DecisionError("Choisissez un autre produit du catalogue.")
        scene = next(s for s in sceneline["scenes"] if s["id"] == opp["scene_id"])
        reason = rule_check(opp, scene, product, load_context(folder))
        if reason:
            raise DecisionError("Produit incompatible : " + reason, 422)
        score = load_matching(folder)["opportunities"].get(opp["key"], {}).get("scores", {}).get(pid)
        revised.update(product_id=pid, score=score)
        payload["product_id"] = pid
    elif not comment:
        raise DecisionError("Décrivez l'ajustement souhaité.")
    return payload, revised
