"""SceneLine · étape 3, version finale : tout le placement sans quitter SceneLine.

Un seul bouton, après l'accord du producteur pour ce placement :
  1. Image de référence : la première image du plan, la photo du produit et sa planche d'angles sont envoyées à
     une API de génération d'image (OpenAI Images), avec le prompt mesuré du kit (place, taille, lumière, rendu).
     L'image reçue est vérifiée (cadrage) et devient l'image de référence du kit.
  2. Vidéo : le plan, le produit, la planche et l'image de référence partent vers Kling AI avec le prompt
     « MAIN REFERENCE » (generation/kling.py).
  3. Intégration : la vidéo reçue est vérifiée (bon placement), recalée et intégrée avec 1 s d'original avant
     et après, audio d'origine conservé (integration/render.py).

Clés sur le serveur uniquement : OPENAI_API_KEY (ou fichier .openai-key) pour l'image, la clé Kling de SceneLine
pour la vidéo. Le modèle d'image se règle avec SCENELINE_IMAGE_MODEL.

Mode démonstration (fichier .sceneline-demo ou SCENELINE_DEMO=1) : tant que ces API ne sont pas financées,
SceneLine rejoue, pour un plan déjà traité, l'image et la vidéo réellement générées plus tôt avec ces outils
(dossier output/demo-assets/). Le parcours, la vérification et l'intégration sont les vrais ; l'interface et le
relevé des modifications indiquent clairement qu'il s'agit d'un résultat enregistré.
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
DEMO_DIR = ROOT / "output" / "demo-assets"
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


def demo_mode():
    return os.environ.get("SCENELINE_DEMO") == "1" or (ROOT / ".sceneline-demo").is_file()


def status():
    """Ce que l'interface doit savoir pour proposer la version finale."""
    image_key = bool(_secret("OPENAI_API_KEY", ".openai-key"))
    video_key = bool(kling.PLATFORM_KEY) and kling.public_url_ok(kling.platform_url())
    return {"demo": demo_mode(), "image_ready": image_key, "video_ready": video_key,
            "ready": demo_mode() or (image_key and video_key), "image_model": IMAGE_MODEL}


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


def demo_assets(folder, record):
    """Résultats réellement générés plus tôt pour CE plan (même vidéo source, même intervalle), s'il y en a."""
    source = (folder / "source.mp4").stat().st_size
    _, revision, _ = render.approved_revision(folder, record["proposal_id"])
    where = DEMO_DIR / f"{source}-{revision['start_ms']}-{revision['end_ms']}"
    reference, video = where / "reference.png", where / "video.mp4"
    if not (reference.is_file() and video.is_file()):
        raise PipelineError("Mode démonstration : aucun résultat enregistré pour ce plan. "
                            "La démonstration rejoue un placement déjà généré avec les API.")
    info = {}
    try:
        info = json.loads((where / "info.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    return reference.read_bytes(), video.read_bytes(), info


# --------------------------------------------------------------------------- le traitement complet

def start(folder, proposal_id, consent, model="kling-3.0-omni"):
    if not consent:
        raise PipelineError("Cochez l'autorisation d'envoi pour ce placement.")
    if (folder.name, proposal_id) in _RUNNING:
        raise PipelineError("Un traitement est déjà en cours pour ce placement.")
    record = kits.kits(folder).get(proposal_id)
    _, revision, _ = render.approved_revision(folder, proposal_id)
    if not record or record["revision"] != revision["n"] or not record.get("image_prompts"):
        raise PipelineError("Préparez d'abord le kit de ce placement (taille et place mesurées).")
    state = status()
    if not state["ready"]:
        raise PipelineError("Les API de génération ne sont pas encore configurées sur le serveur.")
    _RUNNING.add((folder.name, proposal_id))
    demo = state["demo"]
    run = _save(folder, proposal_id, state="running", stage="reference", demo=demo, started_at=now(),
                consent_at=now(), finished_at=None, message="Génération de l'image de référence…", reference=None)
    threading.Thread(target=_run, args=(folder, proposal_id, model, demo), daemon=True).start()
    return run


def _run(folder, proposal_id, model, demo):
    try:
        record = kits.kits(folder)[proposal_id]
        if demo:
            reference, video, info = demo_assets(folder, record)
            time.sleep(6)                                       # le rythme d'un vrai appel, pour la démonstration
        else:
            reference = generate_reference(folder, record)
        updated = kits.set_reference(folder, proposal_id, reference)
        _save(folder, proposal_id, stage="video", reference=updated["reference"],
              message="Image de référence prête. Génération de la vidéo avec Kling AI…")
        if demo:
            time.sleep(8)
            _save(folder, proposal_id, stage="integration", message="Vidéo reçue. Vérification et intégration…")
            tool = info.get("tool", "Kling AI") + " · résultat enregistré (démonstration)"
            note = info.get("note", "Résultat généré plus tôt avec les mêmes API, rejoué pour la démonstration.")
            render.import_external(folder, proposal_id, video, ".mp4", tool, note)
        else:
            kling.start(folder, proposal_id, model, "video", None, True)
            while True:
                time.sleep(4)
                generation = kling.get_generation(folder, proposal_id)
                if generation["state"] in ("downloading", "integrating"):
                    _save(folder, proposal_id, stage="integration", message="Vidéo reçue. Vérification et intégration…")
                elif generation["state"] == "processing":
                    _save(folder, proposal_id, stage="video", message=generation.get("message", "Génération chez Kling…"))
                elif generation["state"] == "done":
                    break
                elif generation["state"] == "error":
                    raise PipelineError(generation.get("message", "La génération vidéo a échoué."))
        _save(folder, proposal_id, state="done", stage="done", finished_at=now(), message="Placement intégré.")
    except (PipelineError, kling.KlingError, render.RenderError) as error:
        _save(folder, proposal_id, state="error", message=str(error))
    except Exception as error:   # jamais de trace brute vers l'interface
        _save(folder, proposal_id, state="error", message="Erreur inattendue : " + str(error)[:200])
    finally:
        _RUNNING.discard((folder.name, proposal_id))
