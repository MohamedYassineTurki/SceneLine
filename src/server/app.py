"""Local SceneLine upload and analysis interface."""
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock
import re
import subprocess
import sys
from uuid import uuid4

from flask import Flask, abort, jsonify, request, send_from_directory
from video_analyzer.review import gemini_keys, replace_json
from video_analyzer.understand import PRIMARY_MODEL as DEFAULT_GEMINI_MODEL
from product_matcher import catalog
from video_analyzer import context as project_context
from producer_review import decisions
from cultural_guard import guard
from product_matcher import matching
from generation import kit
from generation import kling
from integration import render

ROOT = Path(__file__).resolve().parents[2]  # racine du dépôt (src/<module>/<fichier>.py)
SRC = ROOT / "src"
RUNS = ROOT / "output" / "web-runs"
app = Flask(__name__, static_folder=str(SRC / "web"), static_url_path="/ui")
app.config["MAX_CONTENT_LENGTH"] = 513 * 1024 * 1024
worker = ThreadPoolExecutor(max_workers=1)
resume_lock = Lock()
# Travaux en cours dans CE processus. Après un redémarrage du serveur la liste est vide : un état
# « running » enregistré sur disque est alors périmé, et l'interface le signale au lieu de tourner sans fin.
ACTIVE_ANALYSES = set()
ACTIVE_MATCHINGS = set()
STALE_ANALYSIS = ("Le serveur a été redémarré pendant l’analyse. Elle peut reprendre là où elle s’est arrêtée.")
STALE_BEFORE_REVIEW = ("Le serveur a été redémarré pendant la préparation de la vidéo. Relancez l’analyse avec la même vidéo.")


def submit_analysis(folder, video, description, review_only=False):
    ACTIVE_ANALYSES.add(folder.name)
    worker.submit(run_analysis, folder, video, description, review_only)

def save_status(folder, **status):
    replace_json(folder / "status.json", status)

def run_analysis(folder, video, description, review_only=False):
    """Étapes 1 à 3 : analyse locale. Étapes 4 à 6 : scènes, revue des zones, vérification (Gemini)."""
    review = review_only
    done = 0
    total = 0
    stage = 4 if review_only else 0
    try:
        commands = [
            [str(SRC / "video_analyzer" / "analyze.py"), str(video), "--output", str(folder),
             "--description=" + description, "--model", "base"],
            [str(SRC / "video_analyzer" / "understand.py"), str(folder), "--video", str(video),
             "--gemini-model", DEFAULT_GEMINI_MODEL],
        ]
        for command in commands[1 if review_only else 0:]:
            stage = 4 if review else 1
            save_status(folder, state="running", stage=stage, done=done, total=total)
            with subprocess.Popen([sys.executable, "-u", *command], cwd=ROOT,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  encoding="utf-8", errors="replace",
                                  env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONPATH": str(SRC)}) as process:
                with (folder / "run.log").open("a", encoding="utf-8") as log:
                    for line in process.stdout:
                        log.write(line)
                        log.flush()
                        if review:
                            if line.startswith("Total "):
                                total = int(line.split()[-1])
                                stage = 5
                            elif line.startswith("Reprise · "):
                                done = int(line.split()[-1])
                            elif line.startswith("Plan "):
                                done += 1
                            elif line.startswith("Vérification"):
                                stage = 6
                            else:
                                continue
                            save_status(folder, state="running", stage=stage, done=done, total=total)
                        else:
                            for number, prefix in enumerate(("Détection", "Transcription", "Extraction"), 1):
                                if line.startswith(prefix):
                                    stage = number
                                    save_status(folder, state="running", stage=stage)
                if process.wait():
                    raise RuntimeError("Échec de la compréhension des scènes. Consultez le journal pour le détail." if review else
                                       "Échec de l’analyse. Vérifiez que la vidéo est lisible.")
            review = True
        save_status(folder, state="complete", stage=7, done=done, total=total)
    except Exception as error:
        save_status(folder, state="error", stage=stage, done=done, total=total, message=str(error))
    finally:
        ACTIVE_ANALYSES.discard(folder.name)

def job_folder(job_id):
    if not re.fullmatch(r"[0-9a-f]{32}", job_id):
        abort(404)
    folder = RUNS / job_id
    if not (folder / "status.json").is_file():
        abort(404)
    return folder

@app.get("/")
def index():
    return app.send_static_file("index.html")

@app.errorhandler(413)
def too_large(_error):
    return jsonify(message="La vidéo dépasse la limite de 512 Mo."), 413

@app.post("/api/jobs")
def create_job():
    upload = request.files.get("video")
    if not upload or Path(upload.filename).suffix.lower() != ".mp4":
        return jsonify(message="Choisissez une vidéo MP4."), 400
    if not gemini_keys():
        return jsonify(message="Aucune clé Gemini configurée sur le serveur."), 503
    try:
        context = project_context.build_context(request.form)
    except ValueError as error:
        return jsonify(message=str(error)), 400
    description = project_context.to_description(context)
    job_id = uuid4().hex
    folder = RUNS / job_id
    folder.mkdir(parents=True)
    video = folder / "source.mp4"
    upload.save(video)
    if not 0 < video.stat().st_size <= 512 * 1024 * 1024:
        video.unlink()
        folder.rmdir()
        return jsonify(message="Choisissez une vidéo MP4 non vide de 512 Mo maximum."), 400
    replace_json(folder / "context.json", context)
    save_status(folder, state="queued", stage=0)
    submit_analysis(folder, video, description)
    return jsonify(id=job_id), 202

def attach_guard(folder, result):
    """Verdict du Cultural Integrity Guard pour chaque scène et chaque intervalle examiné."""
    context = project_context.load_context(folder)
    scenes = result.get("scenes", [])
    by_id = {scene["id"]: scene for scene in scenes}
    result["guard"] = {
        "scenes": {str(scene["id"]): guard.assess_scene(scene) for scene in scenes},
        "opportunities": {o["key"]: guard.assess(o, by_id[o["scene_id"]], scenes, context)
                          for o in result.get("opportunities", []) if o.get("decision") and o["scene_id"] in by_id},
    }


@app.get("/api/jobs/<job_id>")
def job(job_id):
    folder = job_folder(job_id)
    status = json.loads((folder / "status.json").read_text(encoding="utf-8"))
    if status["state"] in {"queued", "running"} and job_id not in ACTIVE_ANALYSES:
        resumable = status.get("stage", 0) >= 4 and (folder / "analysis.json").is_file()
        status = dict(status, state="error", message=STALE_ANALYSIS if resumable else STALE_BEFORE_REVIEW)
        save_status(folder, **status)
    if status["state"] in {"complete", "error"}:
        result = folder / "sceneline.json"
        if not result.is_file():
            result = folder / "analysis.json"
        if result.is_file():
            status["result"] = json.loads(result.read_text(encoding="utf-8"))
            if status["result"].get("pipeline_version"):
                attach_guard(folder, status["result"])
    return jsonify(status)


@app.post("/api/jobs/<job_id>/resume")
def resume(job_id):
    folder = job_folder(job_id)
    with resume_lock:
        status = json.loads((folder / "status.json").read_text(encoding="utf-8"))
        if status["state"] != "error" or status["stage"] < 4 or not (folder / "analysis.json").is_file():
            return jsonify(message="Cette analyse ne peut pas être reprise."), 409
        save_status(folder, state="queued", stage=4, done=status.get("done", 0))
        submit_analysis(folder, folder / "source.mp4", "", True)
    return jsonify(id=job_id), 202


def ready_job(job_id):
    """Dossier d'un projet dont l'analyse vidéo est terminée."""
    folder = job_folder(job_id)
    if not (folder / "sceneline.json").is_file() or json.loads(
            (folder / "sceneline.json").read_text(encoding="utf-8")).get("status") != "complete":
        abort(409, description="L'analyse de la vidéo n'est pas terminée.")
    return folder

@app.errorhandler(409)
def conflict(error):
    return jsonify(message=getattr(error, "description", "Conflit.")), 409

def matching_status(folder):
    status = matching.get_status(folder)
    if status.get("state") == "running" and folder.name not in ACTIVE_MATCHINGS:
        status = {"state": "error", "message": "Le serveur a été redémarré pendant l’appariement. Relancez-le : les scores déjà calculés sont conservés."}
        matching.set_status(folder, **status)
    return status


def matching_view(folder):
    data = decisions.view(folder) if (folder / "proposals.json").is_file() else {
        "proposals": [], "unmatched": [], "exclusions": [], "catalog_version": None, "decisions": []}
    return dict(data, status=matching_status(folder), context=project_context.load_context(folder),
                catalog=[catalog.public(p) for p in catalog.load_catalog(folder)["products"]],
                catalog_version=catalog.load_catalog(folder)["version"],
                renders=render.renders(folder), kits=kit.kits(folder), external_label=render.EXTERNAL_LABEL,
                labels={"categories": catalog.CATEGORIES, "modes": catalog.MODES})

@app.get("/api/jobs/<job_id>/project")
def project(job_id):
    return jsonify(matching_view(ready_job(job_id)))

@app.post("/api/jobs/<job_id>/products")
def add_product(job_id):
    folder = ready_job(job_id)
    image = request.files.get("image")
    if not image:
        return jsonify(message="Ajoutez le visuel du produit."), 400
    try:
        product = catalog.add_product(
            folder, request.form.get("name", ""), request.form.get("description", ""),
            {"category": request.form.get("category"), "modes": request.form.getlist("modes"),
             "size_class": request.form.get("size_class"), "dimensions": request.form.get("dimensions"),
             "exclusions": request.form.get("exclusions"), "origin": request.form.get("origin"),
             "markets": request.form.get("markets")},
            image.read(), Path(image.filename or "").suffix or ".png", request.form.get("provenance", ""))
    except ValueError as error:
        return jsonify(message=str(error)), 400
    return jsonify(catalog.public(product)), 201

@app.post("/api/jobs/<job_id>/products/demo")
def demo_products(job_id):
    added = catalog.load_demo(ready_job(job_id))
    return jsonify(added=[p["id"] for p in added])

@app.patch("/api/jobs/<job_id>/products/<product_id>")
def correct_product(job_id, product_id):
    try:
        product = catalog.correct_product(ready_job(job_id), product_id, request.get_json(silent=True) or {})
    except KeyError:
        abort(404)
    except ValueError as error:
        return jsonify(message=str(error)), 400
    return jsonify(catalog.public(product))

def run_matching_job(folder):
    try:
        matching.set_status(folder, state="running", done=0, total=0)
        matching.run_matching(folder)
    except Exception as error:
        matching.set_status(folder, state="error", message=str(error))
    finally:
        ACTIVE_MATCHINGS.discard(folder.name)

@app.post("/api/jobs/<job_id>/match")
def start_matching(job_id):
    folder = ready_job(job_id)
    if matching_status(folder).get("state") == "running":
        return jsonify(message="Un appariement est déjà en cours."), 409
    if not catalog.load_catalog(folder)["products"]:
        return jsonify(message="Le catalogue est vide."), 400
    matching.set_status(folder, state="running", done=0, total=0)
    ACTIVE_MATCHINGS.add(folder.name)
    worker.submit(run_matching_job, folder)
    return jsonify(ok=True), 202

@app.post("/api/jobs/<job_id>/proposals/<proposal_id>/decision")
def decide(job_id, proposal_id):
    folder = ready_job(job_id)
    body = request.get_json(silent=True) or {}
    try:
        entry = decisions.decide(folder, proposal_id, body.get("action"), body.get("reviewer"),
                                 body.get("comment", ""), body.get("adjustment"), body.get("revision"))
    except decisions.DecisionError as error:
        return jsonify(message=str(error)), error.status
    return jsonify(entry), 201


@app.patch("/api/jobs/<job_id>/context")
def edit_context(job_id):
    folder = job_folder(job_id)
    return jsonify(project_context.update_context(folder, request.get_json(silent=True) or {}))

@app.post("/api/jobs/<job_id>/opportunities/<key>/retain")
def retain_opportunity(job_id, key):
    """Le producteur retient un placement que SceneLine avait laissé en réserve ou jugé incertain.

    Un placement écarté par une règle (titre, scène protégée, absence de surface) ne peut pas être retenu."""
    from datetime import datetime, timezone
    folder = ready_job(job_id)
    reviewer = ((request.get_json(silent=True) or {}).get("reviewer") or "").strip()[:80] or "Producteur"
    path = folder / "sceneline.json"
    with resume_lock:
        data = json.loads(path.read_text(encoding="utf-8"))
        item = next((o for o in data["opportunities"] if o["key"] == key), None)
        if not item:
            abort(404)
        if item.get("decision") == "keep":
            return jsonify(item)
        scene = next((s for s in data["scenes"] if s["id"] == item["scene_id"]), {})
        if item.get("decision") == "reject" or scene.get("protection") == "protected":
            return jsonify(message="Ce placement a été écarté par une règle (titre, scène protégée ou surface absente) : il ne peut pas être retenu."), 409
        labels = {"reserve": "en réserve", "uncertain": "incertain"}
        previous = item.get("decision")
        rank = max([o.get("rank") or 0 for o in data["opportunities"] if o.get("decision") == "keep"] + [0]) + 1
        item.update(decision="keep", rank=rank,
                    retained={"by": reviewer, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                              "was": previous, "note": item.get("decision_note", "")},
                    decision_note=f"Retenu par le producteur ({reviewer}) ; SceneLine l’avait classé {labels.get(previous, previous)}.")
        replace_json(path, data)
    return jsonify(item)

@app.post("/api/jobs/<job_id>/opportunities/<key>/surfaces")
def find_surfaces(job_id, key):
    """Le producteur demande d'autres surfaces dans l'intervalle (un seul appel Gemini, sur six images)."""
    from video_analyzer import understand
    folder = ready_job(job_id)
    data = json.loads((folder / "sceneline.json").read_text(encoding="utf-8"))
    item = next((o for o in data["opportunities"] if o["key"] == key), None)
    if not item:
        abort(404)
    scene = next((s for s in data["scenes"] if s["id"] == item["scene_id"]), {})
    if item.get("decision") == "reject" or scene.get("protection") == "protected":
        return jsonify(message="Intervalle écarté par une règle : SceneLine n'y cherche pas de surface."), 409
    try:
        client = understand.Gemini(understand.BACKUP_MODEL, understand.PRIMARY_MODEL, understand.Metrics())
        options = understand.alternative_surfaces(item, scene, data, folder / "source.mp4", client)
    except Exception as error:
        return jsonify(message="Recherche impossible : " + str(error)), 502
    with resume_lock:
        data = json.loads((folder / "sceneline.json").read_text(encoding="utf-8"))
        item = next(o for o in data["opportunities"] if o["key"] == key)
        item["surface_options"] = options
        replace_json(folder / "sceneline.json", data)
    return jsonify(options=options)


@app.post("/api/jobs/<job_id>/opportunities/<key>/surface")
def choose_surface(job_id, key):
    """Le producteur choisit une des surfaces trouvées : elle remplace la surface proposée, l'ancienne est gardée."""
    from datetime import datetime, timezone
    folder = ready_job(job_id)
    body = request.get_json(silent=True) or {}
    reviewer = (body.get("reviewer") or "").strip()[:80] or "Producteur"
    path = folder / "sceneline.json"
    with resume_lock:
        data = json.loads(path.read_text(encoding="utf-8"))
        item = next((o for o in data["opportunities"] if o["key"] == key), None)
        if not item:
            abort(404)
        options = item.get("surface_options") or []
        index = body.get("index")
        if not isinstance(index, int) or not 0 <= index < len(options):
            return jsonify(message="Surface inconnue : relancez la recherche."), 400
        chosen = options[index]
        fields = ("surface", "surface_type", "placement_mode", "region", "visible_throughout", "occlusion_risk",
                  "action_distraction", "context_fit", "editorial_fit", "visual_feasibility",
                  "compatible_categories", "avoid_categories", "product_example", "reason", "overall_score")
        item.setdefault("original_surface", {k: item.get(k) for k in fields})
        item.update({k: chosen[k] for k in fields if k in chosen})
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if item.get("decision") != "keep":
            previous = item.get("decision")
            rank = max([o.get("rank") or 0 for o in data["opportunities"] if o.get("decision") == "keep"] + [0]) + 1
            item.update(decision="keep", rank=rank, retained={"by": reviewer, "at": now, "was": previous,
                                                              "note": item.get("decision_note", "")})
        item["surface_choice"] = {"by": reviewer, "at": now, "was": item["original_surface"]["surface"]}
        item["decision_note"] = (f"Surface choisie par le producteur ({reviewer}) : « {chosen['surface']} », "
                                 f"à la place de « {item['original_surface']['surface']} » proposée par SceneLine.")
        replace_json(path, data)
    return jsonify(item)


@app.post("/api/jobs/<job_id>/proposals/<proposal_id>/kit")
def build_kit(job_id, proposal_id):
    folder = ready_job(job_id)
    try:
        return jsonify(kit.build_kit(folder, proposal_id))
    except render.RenderError as error:
        return jsonify(message=str(error)), error.status
    except Exception as error:   # indisponibilité du fournisseur d'analyse, fichier illisible, etc.
        return jsonify(message="Impossible de préparer le kit : " + str(error)), 502

@app.post("/api/jobs/<job_id>/proposals/<proposal_id>/export")
def export_source(job_id, proposal_id):
    try:
        return jsonify(render.export_source(ready_job(job_id), proposal_id))
    except render.RenderError as error:
        return jsonify(message=str(error)), error.status

@app.post("/api/jobs/<job_id>/proposals/<proposal_id>/external")
def import_external(job_id, proposal_id):
    upload = request.files.get("video")
    if not upload:
        return jsonify(message="Choisissez le plan édité."), 400
    try:
        record = render.import_external(ready_job(job_id), proposal_id, upload.read(),
                                        Path(upload.filename or "").suffix or ".mp4",
                                        request.form.get("tool"), request.form.get("note"),
                                        request.form.get("fit", "contain"), request.form.get("anchor", 0.5),
                                        request.form.get("lead_ms", 0))
    except render.RenderError as error:
        return jsonify(message=str(error)), error.status
    return jsonify(record), 201

@app.post("/api/jobs/<job_id>/proposals/<proposal_id>/reassemble")
def reassemble(job_id, proposal_id):
    body = request.get_json(silent=True) or {}
    try:
        return jsonify(render.reassemble(ready_job(job_id), proposal_id, body.get("lead_ms", 0)))
    except render.RenderError as error:
        return jsonify(message=str(error)), error.status

@app.get("/api/jobs/<job_id>/modifications.json")
def modifications(job_id):
    response = jsonify(render.modification_log(ready_job(job_id)))
    response.headers["Content-Disposition"] = "attachment; filename=releve-des-modifications.json"
    return response

@app.get("/api/jobs/<job_id>/files/<name>")
def job_file(job_id, name):
    folder = job_folder(job_id)
    if not re.fullmatch(r"(?:source\.mp4|plan-\d+\.jpg|win-\d+-\d+\.jpg|analysis\.json|sceneline\.json|run\.log|product-[a-z0-9-]+\.(?:png|jpe?g|webp)|(?:render|export)-p-\d+-\d+-r\d+(?:-original|-edited)?\.mp4|kit-p-\d+-\d+-r\d+(?:-plan\.mp4|-(?:debut|fin)(?:-16x9)?\.png|-produit\.png|-prompt-(?:en|fr)\.txt|-LISEZ-MOI\.md|\.zip))", name):
        abort(404)
    return send_from_directory(folder, name)


# ----------------------------------------------------------------------------- génération automatique (Kling)

@app.before_request
def only_the_clip_when_public():
    """Atteint par un tunnel (autre nom d'hôte que localhost), SceneLine ne sert que le lien temporaire du plan."""
    host = (request.host or "").lower()
    host = host[1:].split("]")[0] if host.startswith("[") else host.split(":")[0]
    if host not in {"localhost", "127.0.0.1", "::1"} and not request.path.startswith("/pub/"):
        abort(403)


@app.get("/pub/<token>/plan.mp4")
def public_clip(token):
    entry = kling.public_clip(token)
    if not entry:
        abort(404)
    folder, name = entry
    return send_from_directory(folder, name, mimetype="video/mp4")


@app.get("/api/providers/kling")
def kling_status():
    return jsonify(kling.status())


@app.post("/api/providers/kling/key")
def kling_connect():
    try:
        return jsonify(kling.connect((request.get_json(silent=True) or {}).get("api_key")))
    except kling.KlingError as error:
        return jsonify(message=str(error)), error.status


@app.delete("/api/providers/kling/key")
def kling_disconnect():
    return jsonify(kling.disconnect())


@app.post("/api/jobs/<job_id>/proposals/<proposal_id>/generate")
def kling_generate(job_id, proposal_id):
    folder = ready_job(job_id)
    body = request.get_json(silent=True) or {}
    try:
        record = kling.start(folder, proposal_id, body.get("model", "kling-4.0"), body.get("mode", "video"),
                             body.get("public_base"), body.get("consent") is True)
    except (kling.KlingError, render.RenderError) as error:
        return jsonify(message=str(error)), error.status
    return jsonify(record), 202


@app.get("/api/jobs/<job_id>/proposals/<proposal_id>/generation")
def kling_generation(job_id, proposal_id):
    return jsonify(kling.get_generation(ready_job(job_id), proposal_id))


@app.post("/api/jobs/<job_id>/proposals/<proposal_id>/generation/resume")
def kling_resume(job_id, proposal_id):
    try:
        return jsonify(kling.resume(ready_job(job_id), proposal_id))
    except kling.KlingError as error:
        return jsonify(message=str(error)), error.status


def main():
    """Point d'entrée : `python run.py --port 8000`."""
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--resume-review")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if args.resume_review:
        if not re.fullmatch(r"[0-9a-f]{32}", args.resume_review):
            parser.error("Identifiant d'analyse invalide.")
        folder = RUNS / args.resume_review
        video = folder / "source.mp4"
        if not video.is_file() or not (folder / "analysis.json").is_file():
            parser.error("Vidéo ou analyse locale introuvable.")
        save_status(folder, state="queued", stage=4)
        submit_analysis(folder, video, "", True)
    app.run(host="127.0.0.1", port=args.port, threaded=True)


if __name__ == "__main__":
    main()
