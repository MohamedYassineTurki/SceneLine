"""Compare les placements de SceneLine à l'annotation manuelle (validation/*-verite.json)."""
import argparse
import json
from pathlib import Path


def overlap(a_start, a_end, b_start, b_end):
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def evaluate(result, truth):
    items = result["opportunities"]
    kept = [i for i in items if i["decision"] == "keep"]
    report = {"retenus": len(kept), "examines": len(items), "exclusions": [], "pistes": []}
    for zone in truth["exclure"]:
        bad = [i for i in kept if overlap(i["start_ms"] / 1000, i["end_ms"] / 1000, zone["debut"], zone["fin"]) > 0]
        report["exclusions"].append({**zone, "faux_positifs": [f"{i['start_ms']/1000:.1f}-{i['end_ms']/1000:.1f}" for i in bad]})
    for zone in truth["pistes"]:
        hits = [i for i in items if overlap(i["start_ms"] / 1000, i["end_ms"] / 1000, zone["debut"], zone["fin"]) > 0]
        report["pistes"].append({**zone, "trouvee_dans": [
            f"{i['start_ms']/1000:.1f}-{i['end_ms']/1000:.1f} {i['decision']} ({i['overall_score']}/10) {i['reason']}" for i in hits]})
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sceneline_json", type=Path)
    parser.add_argument("--verite", type=Path, default=Path("validation/baltringue-verite.json"))
    args = parser.parse_args()
    report = evaluate(json.loads(args.sceneline_json.read_text(encoding="utf-8")),
                      json.loads(args.verite.read_text(encoding="utf-8")))
    print(json.dumps(report, ensure_ascii=False, indent=2))
