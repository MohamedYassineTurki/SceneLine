"""SceneLine · génération automatique avec l'API de Kling AI (option de l'étape 3).

Deux modes :
  - plateforme : SceneLine utilise SON compte Kling. La clé est lue sur le serveur (variable KLING_API_KEY ou
    fichier .kling-key, jamais versionné) ; l'utilisateur n'a ni clé ni compte à fournir. L'adresse publique
    par laquelle Kling télécharge le plan vient de SCENELINE_PUBLIC_URL ou du fichier .sceneline-public-url ;
  - personnel : sans clé sur le serveur, l'utilisateur connecte son propre compte Kling.
En mode personnel, l'utilisateur connecte SON compte Kling (clé d'API). SceneLine envoie alors le plan, l'image du produit et le
prompt du kit, attend la vidéo, puis l'intègre comme un résultat importé à la main (étape 4). SceneLine ne
génère toujours rien lui-même : l'image vient de Kling, et le relevé des modifications le dit.

Sécurité et vie privée :
  - la clé n'est conservée qu'en mémoire du serveur (jamais sur disque, jamais dans un journal) ;
  - elle n'est envoyée qu'à l'API de Kling ;
  - rien ne part sans l'accord explicite de l'utilisateur pour CE placement (case à cocher, vérifiée côté serveur) ;
  - le plan vidéo n'est exposé que par un lien aléatoire, valable le temps de la génération, qui ne sert que ce fichier.

Interface de Kling (documentation officielle, https://kling.ai/document-api/) : en-tête Authorization: Bearer <clé>,
création POST /omni-video/<modèle>, suivi GET /tasks?task_ids=<id>. Une vidéo ne peut être donnée que par une
adresse publique ; les images peuvent l'être en base64.
"""

import base64
import json
import os
import secrets
import threading
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from pathlib import Path

from integration import render
from producer_review.decisions import read
from video_analyzer.review import replace_json

BASE = os.environ.get("SCENELINE_KLING_BASE", "https://api-singapore.klingai.com").rstrip("/")
MODELS = {
    "kling-4.0": {"label": "Kling 4.0", "prompt_max": 26000, "seconds": (3, 30)},
    "kling-3.0-omni": {"label": "Kling 3.0 Omni", "prompt_max": 3072, "seconds": (3, 15)},
}
MODES = {"video": "À partir du plan vidéo (adresse publique temporaire)"}
POLL_S = float(os.environ.get("SCENELINE_KLING_POLL_S", "6"))
TIMEOUT_S = 25 * 60
ACTIVE = {"submitting", "processing", "downloading", "integrating"}
AUTH_CODES = {1000, 1001, 1002, 1003, 1004}

ROOT = Path(__file__).resolve().parents[2]


def _secret(env, filename):
    value = os.environ.get(env, "").strip()
    if not value:
        try:
            value = (ROOT / filename).read_text(encoding="utf-8").strip()
        except OSError:
            value = ""
    return value or None


LOCK = threading.RLock()
PLATFORM_KEY = _secret("KLING_API_KEY", ".kling-key")     # compte Kling de SceneLine (mode plateforme)
_KEY = {"value": PLATFORM_KEY}


def platform_url():
    """Adresse publique du serveur, relue à chaque génération : l'adresse d'un tunnel change à chaque lancement."""
    return _secret("SCENELINE_PUBLIC_URL", ".sceneline-public-url")
_RUNNING = set()          # (dossier, proposition) dont un fil de génération tourne
_TOKENS = {}              # jeton aléatoire -> (dossier, nom du plan)


class KlingError(Exception):
    def __init__(self, message, status=400, final=False):
        super().__init__(message)
        self.status = status
        self.final = final      # échec définitif chez Kling : inutile de reprendre le suivi


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def clean(text):
    """Message sans la clé, au cas où un service la renverrait."""
    text = str(text)
    key = _KEY["value"]
    return text.replace(key, "***") if key else text


# --------------------------------------------------------------------------- clé

def status():
    key = _KEY["value"]
    managed = bool(PLATFORM_KEY)
    return {"connected": bool(key), "managed": managed, "hint": key[-4:] if key and not managed else None,
            "public_ready": public_url_ok(platform_url()),
            "models": {k: v["label"] for k, v in MODELS.items()}, "modes": MODES}


def api(method, path, body=None, timeout=60, key=None):
    """Appel JSON à l'API de Kling. Retourne (statut HTTP, JSON)."""
    key = key or _KEY["value"]
    if not key:
        raise KlingError("Connectez d’abord votre clé d’API Kling.", 409)
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = Request(BASE + path, data=data, method=method,
                      headers={"Authorization": "Bearer " + key, "Content-Type": "application/json", "User-Agent": "SceneLine"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        try:
            payload = json.loads(error.read()[:4000].decode("utf-8", "replace"))
        except ValueError:
            payload = {}
        error.close()
        return error.code, payload
    except (URLError, TimeoutError, OSError) as error:
        raise KlingError("Kling est injoignable : " + clean(getattr(error, "reason", error)), 502) from None


def connect(api_key):
    """Enregistre la clé en mémoire après une vérification qui ne consomme aucun crédit."""
    if PLATFORM_KEY:
        raise KlingError("SceneLine génère avec son propre compte Kling : aucune clé à fournir.", 409)
    key = (api_key or "").strip()
    if len(key) < 8 or any(c.isspace() for c in key):
        raise KlingError("Collez la clé d’API Kling telle quelle, sans espace.")
    code, payload = api("GET", "/tasks?task_ids=sceneline-verification", key=key, timeout=30)
    if code in (401, 403) or payload.get("code") in AUTH_CODES:
        raise KlingError("Kling a refusé cette clé : " + clean(payload.get("message") or "authentification échouée"), 401)
    with LOCK:
        _KEY["value"] = key
    return {**status(), "verified": code == 200 and payload.get("code") == 0}


def disconnect():
    if PLATFORM_KEY:
        raise KlingError("Le compte Kling de SceneLine se gère sur le serveur.", 409)
    with LOCK:
        _KEY["value"] = None
    return status()


# --------------------------------------------------------------------------- requête

def b64(path):
    return base64.b64encode(path.read_bytes()).decode("ascii")


def public_url_ok(url):
    parts = urlparse(url or "")
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or not host:
        return False
    private = host in {"localhost"} or host.endswith((".local", ".internal", ".lan")) or \
        host.startswith(("127.", "10.", "192.168.", "169.254.")) or host == "::1"
    return not private


def build_request(folder, proposal_id, model, mode, public_base=None, token=None):
    """Corps de la requête et liste de ce qui sera envoyé. Lève KlingError si le kit ou les choix sont invalides."""
    if model not in MODELS:
        raise KlingError("Modèle inconnu.")
    if mode not in MODES:
        raise KlingError("Mode d’envoi inconnu.")
    proposal, revision, _ = render.approved_revision(folder, proposal_id)
    kit = read(folder, "kits.json", {"kits": {}})["kits"].get(proposal_id)
    if not kit or kit["revision"] != revision["n"]:
        raise KlingError("Préparez d’abord le kit de la révision approuvée.", 409)
    spec = MODELS[model]
    prompt = kit["prompt_en"] + ("\n\nThe product to add is the object shown in the reference image @image_1 "
                                 "(white background): reproduce its shape, colors and label faithfully.")
    extra = "\n\nDo not: " + kit["negative_en"]
    if len(prompt) + len(extra) <= spec["prompt_max"]:
        prompt += extra
    elif len(prompt) > spec["prompt_max"]:
        # Prompt trop long pour ce modèle : la version compacte du kit garde taille, position, lumière et références.
        prompt = kit.get("prompt_short_en") or ""
        if not prompt or len(prompt) > spec["prompt_max"]:
            raise KlingError(f"Le prompt dépasse la limite de {spec['label']} ({spec['prompt_max']} caractères). Refaites le kit.")
    if not public_url_ok(public_base):
        raise KlingError("L’adresse publique du serveur n’est pas configurée : la génération est momentanément indisponible."
                         if PLATFORM_KEY else
                         "Indiquez l’adresse publique (https) de votre tunnel : Kling doit pouvoir télécharger le plan.", 503 if PLATFORM_KEY else 400)
    asset = {"type": "refer_image", "url": b64(folder / kit["asset"]), "id": "image_1"}
    # Planche d'angles du produit (facultative) : image de référence image_2, citée par le prompt du kit.
    views = [{"type": "refer_image", "url": b64(folder / name), "id": f"image_{i}"}
             for i, name in enumerate(kit.get("views", [])[:1], 2)]
    sent = ["Le prompt du kit (anglais)", "L’image du produit, sur fond blanc",
            "Le plan vidéo source, sans audio (via un lien temporaire à usage unique)"]
    if views:
        sent.insert(2, "La planche d’angles du produit")
    # Image guide : l'image de référence importée (première image avec le produit en place) ou, à défaut, la maquette
    # mesurée par SceneLine. Elle fixe la taille, la position et le rendu attendus.
    guide = kit.get("guide")
    if guide and (folder / guide["file"]).is_file():
        views.append({"type": "refer_image", "url": b64(folder / guide["file"]), "id": guide["id"]})
        sent.insert(len(sent) - 1, "L’image de référence du placement" if guide["kind"] == "reference"
                    else "La maquette du placement (taille et position mesurées)")
    contents = [{"type": "prompt", "text": prompt}, asset, *views,
                {"type": "base_video", "url": public_base.rstrip("/") + f"/pub/{token}/plan.mp4", "id": "video_1"}]
    low, high = spec["seconds"]
    seconds = min(high, max(low, round(kit["seconds"])))
    if model == "kling-4.0":
        settings = {"resolution": "1080p", "aspect_ratio": "adaptive", "duration": seconds, "audio": "original"}
    else:
        settings = {"multi_shot": False, "audio": "off", "resolution": "1080p", "duration": seconds, "aspect_ratio": "16:9"}
    options = {"external_task_id": f"sceneline-{proposal_id}-r{revision['n']}-{secrets.token_hex(3)}",
               "watermark_info": {"enabled": False}}
    return {"contents": contents, "settings": settings, "options": options}, sent, kit


# --------------------------------------------------------------------------- suivi d'une génération

def _store(folder):
    return read(folder, "generations.json", {"generations": {}})


def get_generation(folder, proposal_id):
    record = _store(folder)["generations"].get(proposal_id)
    if not record:
        return {"state": "idle"}
    if record["state"] in ACTIVE and (folder.name, proposal_id) not in _RUNNING:
        record = dict(record, state="error", resumable=bool(record.get("task_id")),
                      message="Le suivi a été interrompu (serveur relancé). " +
                              ("La génération a peut-être abouti chez Kling : reprenez le suivi." if record.get("task_id") else "Relancez la génération."))
    return record


def _save(folder, proposal_id, **changes):
    with LOCK:
        store = _store(folder)
        record = store["generations"].setdefault(proposal_id, {})
        record.update(changes, updated_at=now())
        replace_json(folder / "generations.json", store)
        return dict(record)


def start(folder, proposal_id, model, mode, public_base, consent):
    if not consent:
        raise KlingError("Cochez l’autorisation d’envoi à Kling pour ce placement.")
    if not _KEY["value"]:
        raise KlingError("Connectez d’abord votre clé d’API Kling.", 409)
    if get_generation(folder, proposal_id)["state"] in ACTIVE:
        raise KlingError("Une génération est déjà en cours pour ce placement.", 409)
    public_base = (public_base or "").strip() or platform_url()
    token = secrets.token_hex(16)
    payload, sent, kit = build_request(folder, proposal_id, model, mode, public_base, token)   # valide avant d'envoyer
    if token:
        _TOKENS[token] = (folder, kit["clip"])
    record = _save(folder, proposal_id, state="submitting", model=model, mode=mode, sent=sent, task_id=None,
                   message="Envoi à Kling…", started_at=now(), consent_at=now(), render=None, resumable=False,
                   seconds=payload["settings"]["duration"])
    _RUNNING.add((folder.name, proposal_id))
    threading.Thread(target=_run, args=(folder, proposal_id, model, payload, token, None), daemon=True).start()
    return record


def resume(folder, proposal_id):
    record = get_generation(folder, proposal_id)
    if record["state"] != "error" or not record.get("task_id"):
        raise KlingError("Aucune génération à reprendre.", 409)
    if not _KEY["value"]:
        raise KlingError("Reconnectez d’abord votre clé d’API Kling.", 409)
    _save(folder, proposal_id, state="processing", message="Reprise du suivi chez Kling…", resumable=False)
    _RUNNING.add((folder.name, proposal_id))
    threading.Thread(target=_run, args=(folder, proposal_id, record["model"], None, None, record["task_id"]), daemon=True).start()
    return get_generation(folder, proposal_id)


def _run(folder, proposal_id, model, payload, token, task_id):
    try:
        if not task_id:
            code, answer = api("POST", f"/omni-video/{model}", payload, timeout=180)
            if code != 200 or answer.get("code") != 0:
                raise KlingError("Kling a refusé la demande : " + clean(answer.get("message") or f"HTTP {code}"))
            task_id = answer["data"]["id"]
            _save(folder, proposal_id, state="processing", task_id=task_id, message="Génération en cours chez Kling…")
        deadline = time.time() + TIMEOUT_S
        started = time.time()
        while True:
            code, answer = api("GET", f"/tasks?task_ids={task_id}", timeout=60)
            task = (answer.get("data") or [{}])[0] if code == 200 else {}
            state = task.get("status")
            if state == "failed":
                raise KlingError("La génération a échoué chez Kling : " + clean(task.get("message") or "motif non précisé"), final=True)
            if state == "succeeded":
                break
            if time.time() > deadline:
                raise KlingError("Kling met trop de temps : le suivi est arrêté. Vous pouvez le reprendre.")
            _save(folder, proposal_id, state="processing", message=f"Génération en cours chez Kling ({int(time.time() - started)} s)…")
            time.sleep(POLL_S)
        url = next((o.get("url") for o in task.get("outputs") or [] if o.get("type") == "video" and o.get("url")), None)
        if not url or urlparse(url).scheme != "https" and not BASE.startswith("http://127."):
            raise KlingError("Kling n’a renvoyé aucune vidéo exploitable.")
        _save(folder, proposal_id, state="downloading", message="Téléchargement de la vidéo…")
        with urlopen(Request(url, headers={"User-Agent": "SceneLine"}), timeout=300) as response:
            data = response.read(render.MAX_UPLOAD + 1)
        if not data or len(data) > render.MAX_UPLOAD:
            raise KlingError("La vidéo reçue est vide ou trop lourde.")
        _save(folder, proposal_id, state="integrating", message="Intégration dans la vidéo d’origine…")
        label = MODELS[model]["label"]
        record = render.import_external(folder, proposal_id, data, ".mp4", f"Kling AI via l’API ({label})",
                                        f"Tâche Kling {task_id}, envoyée depuis le kit SceneLine.")
        _save(folder, proposal_id, state="done", message="Vidéo intégrée.", render={"warnings": record["warnings"]}, finished_at=now())
    except KlingError as error:
        _save(folder, proposal_id, state="error", message=clean(error), resumable=bool(task_id) and not error.final)
    except render.RenderError as error:
        _save(folder, proposal_id, state="error", message="Vidéo reçue mais non intégrée : " + clean(error), resumable=False)
    except Exception as error:   # jamais de trace brute vers l'interface
        _save(folder, proposal_id, state="error", message="Erreur inattendue : " + clean(error)[:200], resumable=bool(task_id))
    finally:
        _RUNNING.discard((folder.name, proposal_id))
        if token:
            _TOKENS.pop(token, None)


def public_clip(token):
    """(dossier, nom du plan) servi par le lien temporaire, ou None."""
    return _TOKENS.get(token)
