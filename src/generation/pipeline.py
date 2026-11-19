"""SceneLine · étape 3, génération intégrée : tout le placement sans quitter SceneLine.

SceneLine propose deux façons de produire le plan modifié, toutes deux complètes :
  - avec les outils du producteur (kit, prompts, import : generation/kit.py, integration/render.py) ;
  - intégrée, ici : SceneLine appelle lui-même les API de génération. Elle demande des crédits d'API
    (OpenAI Images pour l'image de référence, Kling AI pour la vidéo), configurés sur le serveur.

Un seul bouton, après l'accord du producteur pour ce placement :
  1. Image de référence : la première image du plan, la photo du produit et sa planche d'angles sont envoyées à
     une API de génération d'image (OpenAI Images), avec le prompt mesuré du kit (place, taille, lumière, rendu).
     L'image reçue est vérifiée (cadrage) et devient l'image de référence du kit.
  2. Vidéo : le plan, le produit, la planche et l'image de référence partent vers Kling AI avec le prompt
     « MAIN REFERENCE » (generation/kling.py).
  3. Intégration : la vidéo reçue est vérifiée (bon placement), recalée et intégrée avec 1 s d'original avant
     et après, audio d'origine conservé (integration/render.py).

Clés sur le serveur uniquement, jamais dans l'interface : OPENAI_API_KEY (ou fichier .openai-key) pour l'image,
la clé Kling de SceneLine et son adresse publique pour la vidéo (voir generation/kling.py). Le modèle d'image se
règle avec SCENELINE_IMAGE_MODEL.
"""

import base64
import json
import os
import threading
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import cv2
import numpy as np

from generation import kit as kits
from generation import kling
from integration import render
from producer_review.decisions import read
from video_analyzer.review import replace_json

ROOT = Path(__file__).resolve().parents[2]
IMAGE_MODEL = os.environ.get("SCENELINE_IMAGE_MODEL", "gpt-image-1")
IMAGE_SIZE = (1536, 1024)          # format paysage de l'API ; le plan 16:9 y est posé, puis recadré au retour
LOCK = threading.RLock()
_RUNNING = set()


class PipelineError(Exception):
    pass


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())


def _secret(env, filename):
    value = os.environ.get(env, "").strip()
    if not value:
        try:
            value = (ROOT / filename).read_text(encoding="utf-8").strip()
        except OSError:
            value = ""
    return value or None


def status():
    """Ce que l'interface doit savoir pour proposer la génération intégrée."""
    image_key = bool(_secret("OPENAI_API_KEY", ".openai-key"))
    video_key = bool(kling.PLATFORM_KEY) and kling.public_url_ok(kling.platform_url())
    return {"image_ready": image_key, "video_ready": video_key, "ready": image_key and video_key,
            "image_model": IMAGE_MODEL}


# --------------------------------------------------------------------------- état d'un traitement

def get(folder, proposal_id):
    record = read(folder, "pipeline.json", {"runs": {}})["runs"].get(proposal_id)
    if not record:
        return {"state": "idle"}
    if record["state"] == "running" and (folder.name, proposal_id) not in _RUNNING:
        record = dict(record, state="error", message="Le traitement a été interrompu (serveur relancé). Relancez-le.")
    return record


def _save(folder, proposal_id, **changes):
    with LOCK:
        store = read(folder, "pipeline.json", {"runs": {}})
        record = store["runs"].setdefault(proposal_id, {})
        record.update(changes, updated_at=now())
        replace_json(folder / "pipeline.json", store)
        return dict(record)


# --------------------------------------------------------------------------- 1 · image de référence

def _letterbox(image, size):
    """Pose l'image dans le format de l'API sans la déformer. Retourne l'image et la zone utile (x, y, w, h)."""
    W, H = size
    h, w = image.shape[:2]
    scale = min(W / w, H / h)
    nw, nh = round(w * scale), round(h * scale)
    canvas = np.zeros((H, W, 3), np.uint8)
    x, y = (W - nw) // 2, (H - nh) // 2
    canvas[y:y + nh, x:x + nw] = cv2.resize(image, (nw, nh), interpolation=cv2.INTER_AREA)
    return canvas, (x, y, nw, nh)


def _png(image):
    return cv2.imencode(".png", image)[1].tobytes()


def generate_reference(folder, record):
    """Appelle l'API d'image (OpenAI, édition multi-images) et renvoie l'image de référence au format du plan."""
    key = _secret("OPENAI_API_KEY", ".openai-key")
    if not key:
        raise PipelineError("Aucune clé d'API de génération d'image n'est configurée sur le serveur.")
    frame = cv2.imread(str(folder / record["frames_native"]["debut"]))
    framed, (x, y, w, h) = _letterbox(frame, IMAGE_SIZE)
    images = [("plan.png", _png(framed)), ("produit.png", (folder / record["asset"]).read_bytes())]
    images += [("angles.png", (folder / name).read_bytes()) for name in record.get("views", [])[:1]]
    prompt = record["image_prompts"]["en"]
    boundary = uuid.uuid4().hex
    body = bytearray()
    for name, value in (("model", IMAGE_MODEL), ("prompt", prompt), ("size", f"{IMAGE_SIZE[0]}x{IMAGE_SIZE[1]}"),
                        ("quality", "high"), ("n", "1")):
        body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode("utf-8")
    for filename, data in images:
        body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"image[]\"; filename=\"{filename}\"\r\n"
                 "Content-Type: image/png\r\n\r\n").encode("utf-8") + data + b"\r\n"
    body += f"--{boundary}--\r\n".encode("utf-8")
    request = Request("https://api.openai.com/v1/images/edits", data=bytes(body), method="POST",
                      headers={"Authorization": "Bearer " + key,
                               "Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urlopen(request, timeout=300) as response:
            answer = json.load(response)
    except HTTPError as error:
        detail = error.read()[:300].decode("utf-8", "replace").replace(key, "***")
        raise PipelineError(f"L'API d'image a refusé la demande (HTTP {error.code}) : {detail}") from None
    except (URLError, TimeoutError, OSError):
        raise PipelineError("L'API d'image est injoignable.") from None
    data = base64.b64decode(((answer.get("data") or [{}])[0]).get("b64_json") or b"")
    image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise PipelineError("L'API d'image n'a renvoyé aucune image exploitable.")
    image = cv2.resize(image, IMAGE_SIZE)[y:y + h, x:x + w]       # on retire le cadre ajouté à l'envoi
    return _png(cv2.resize(image, (frame.shape[1], frame.shape[0]), interpolation=cv2.INTER_CUBIC))


# --------------------------------------------------------------------------- le traitement complet

def start(folder, proposal_id, consent, model="kling-3.0-omni"):
    """Kit média (si besoin) → image de référence → vidéo. L'intégration suit, à la demande du producteur."""
    if not consent:
        raise PipelineError("Cochez l'autorisation d'envoi pour ce placement.")
    if (folder.name, proposal_id) in _RUNNING:
        raise PipelineError("Un traitement est déjà en cours pour ce placement.")
    render.approved_revision(folder, proposal_id)          # placement approuvé, sinon erreur
    state = status()
    if not state["ready"]:
        raise PipelineError("Les clés des API de génération (image et vidéo) ne sont pas configurées sur le serveur.")
    _RUNNING.add((folder.name, proposal_id))
    run = _save(folder, proposal_id, state="running", stage="kit", started_at=now(), consent_at=now(),
                finished_at=None, message="Préparation du kit média : plan, produit, taille et place mesurées…",
                reference=None, video=None)
    threading.Thread(target=_run, args=(folder, proposal_id, model), daemon=True).start()
    return run


def _kit_ready(folder, proposal_id):
    record = kits.kits(folder).get(proposal_id)
    _, revision, _ = render.approved_revision(folder, proposal_id)
    return record if record and record["revision"] == revision["n"] and record.get("image_prompts") else None


def _run(folder, proposal_id, model):
    try:
        record = _kit_ready(folder, proposal_id) or kits.build_kit(folder, proposal_id)
        _save(folder, proposal_id, stage="reference", message="Génération de l'image de référence…")
        reference = generate_reference(folder, record)
        updated = kits.set_reference(folder, proposal_id, reference)
        _save(folder, proposal_id, stage="video", reference=updated["reference"],
              message="Génération de la vidéo avec Kling AI…")
        _, revision, _ = render.approved_revision(folder, proposal_id)
        kling.start(folder, proposal_id, model, "video", None, True)
        while True:
            time.sleep(4)
            generation = kling.get_generation(folder, proposal_id)
            if generation["state"] == "processing":
                _save(folder, proposal_id, message=generation.get("message", "Génération chez Kling…"))
            elif generation["state"] in ("downloading", "integrating", "done"):
                if generation["state"] != "done":
                    continue
                stored = next(iter(folder.glob(f"external-{proposal_id}-r{revision['n']}.*")), None)
                _save(folder, proposal_id, state="video_ready", stage="video", integrated=True,
                      video=stored.name if stored else None, message="Vidéo générée. Vérifiez-la, puis intégrez-la.")
                return
            elif generation["state"] == "error":
                raise PipelineError(generation.get("message", "La génération vidéo a échoué."))
    except (PipelineError, kling.KlingError, render.RenderError) as error:
        _save(folder, proposal_id, state="error", message=str(error))
    except Exception as error:   # jamais de trace brute vers l'interface
        _save(folder, proposal_id, state="error", message="Erreur inattendue : " + str(error)[:200])
    finally:
        _RUNNING.discard((folder.name, proposal_id))


def integrate(folder, proposal_id):
    """Le producteur a vu la vidéo générée : SceneLine la vérifie et l'intègre dans l'épisode."""
    run = get(folder, proposal_id)
    if run.get("state") != "video_ready":
        raise PipelineError("Aucune vidéo générée à intégrer pour ce placement.")
    if run.get("integrated"):                          # déjà intégrée par la génération Kling
        return _save(folder, proposal_id, state="done", stage="done", finished_at=now(), message="Placement intégré.")
    _RUNNING.add((folder.name, proposal_id))
    record = _save(folder, proposal_id, state="running", stage="integration",
                   message="Vérification du plan, recalage et intégration dans l'épisode…")

    def work():
        try:
            data = (folder / run["video"]).read_bytes()
            render.import_external(folder, proposal_id, data, ".mp4", run.get("tool", "Kling AI"), run.get("note", ""))
            _save(folder, proposal_id, state="done", stage="done", finished_at=now(), message="Placement intégré.")
        except (PipelineError, render.RenderError) as error:
            _save(folder, proposal_id, state="error", message=str(error))
        except Exception as error:
            _save(folder, proposal_id, state="error", message="Erreur inattendue : " + str(error)[:200])
        finally:
            _RUNNING.discard((folder.name, proposal_id))

    threading.Thread(target=work, daemon=True).start()
    return record
