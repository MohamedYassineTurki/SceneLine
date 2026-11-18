"""SceneLine · aperçu édité et relevé des modifications (F06, F07).

Pour la première soumission, l'image modifiée vient d'un OUTIL EXTERNE, jamais de SceneLine.
SceneLine fait trois choses :
  1. exporter le plan source d'une proposition approuvée, avec un descriptif pour l'outil externe ;
  2. importer le plan édité et l'assembler dans un extrait : l'original avant, le plan édité sur
     l'intervalle approuvé, l'original après, avec l'AUDIO SOURCE conservé ;
  3. produire un relevé des modifications qui accompagne la version éditée.

Seule la révision approuvée d'une proposition peut recevoir un aperçu.
L'original n'est jamais modifié.
"""

import json
import re
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from product_matcher.catalog import load_catalog
from producer_review.decisions import decision_for, digest, read
from video_analyzer.review import replace_json

LOCK = threading.RLock()
CONTEXT_MS = 1000          # original conservé APRÈS le plan édité
LEAD_MS = 1000             # original conservé AVANT le plan édité : le spectateur voit la scène, puis le placement
MATCH_MIN = 0.70           # ressemblance minimale entre la vidéo importée et le plan d'origine
MATCH_MARGIN = 0.05        # un autre placement qui ressemble nettement plus : la vidéo n'est pas pour celui-ci
EXTERNAL_LABEL = "Aperçu illustratif réalisé avec un outil externe"
VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".mkv"}
MAX_UPLOAD = 200 * 1024 * 1024


class RenderError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
        capture_output=True, text=True, timeout=60)
    if out.returncode:
        raise RenderError("Fichier vidéo illisible.")
    data = json.loads(out.stdout)
    video = next((s for s in data["streams"] if s["codec_type"] == "video"), None)
    if not video:
        raise RenderError("Le fichier ne contient aucune piste vidéo.")
    duration = float(data["format"].get("duration") or video.get("duration") or 0)
    return {"width": int(video["width"]), "height": int(video["height"]), "duration": duration,
            "has_audio": any(s["codec_type"] == "audio" for s in data["streams"])}


def ffmpeg(*args, timeout=300):
    result = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", *args],
                            capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RenderError("Échec du traitement vidéo : " + result.stderr.strip()[-300:], 500)


def clock(ms):
    seconds = int(ms // 1000)
    return f"{seconds // 60:02}:{seconds % 60:02}"


def approved_revision(folder, proposal_id):
    """Dernière révision approuvée d'une proposition, ou erreur."""
    store = read(folder, "proposals.json", {"proposals": {}})
    proposal = store["proposals"].get(proposal_id)
    if not proposal:
        raise RenderError("Proposition introuvable.", 404)
    decisions = read(folder, "decisions.json", {"decisions": []})["decisions"]
    approved = [r for r in proposal["revisions"]
                if (decision_for(decisions, proposal_id, r["n"]) or {}).get("action") == "accepter"]
    if not approved:
        raise RenderError("Seule une révision approuvée peut recevoir un aperçu.", 409)
    revision = approved[-1]
    return proposal, revision, decision_for(decisions, proposal_id, revision["n"])


def product_of(folder, revision):
    return next((p for p in load_catalog(folder)["products"] if p["id"] == revision["product_id"]), None)


def bar_crop(path, target_ratio):
    """Détecte des bandes noires incrustées par l'outil externe (ex. 16:9 autour d'un plan large).

    Retourne un filtre crop si la zone utile a le format de la source, sinon None."""
    result = subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "info", "-i", str(path), "-vf", "cropdetect=limit=24:round=2:reset=0",
         "-frames:v", "60", "-f", "null", "-"], capture_output=True, text=True, timeout=90)
    crops = re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", result.stderr)
    if not crops:
        return None
    w, h, x, y = map(int, crops[-1])
    info = probe(path)
    if (w, h) == (info["width"], info["height"]) or h <= 0:
        return None
    return f"crop={w}:{h}:{x}:{y}" if abs(w / h - target_ratio) / target_ratio < 0.08 else None


def brief_text(folder, proposal, revision):
    product = product_of(folder, revision) or {"name": revision["product_id"], "description": ""}
    region = revision.get("region")
    where = where_en = ""
    if region:
        box = [round(region[k] * 100) for k in ("x", "y", "width", "height")]
        where = (f" Zone approximative (en % de l'image) : gauche {box[0]} %, haut {box[1]} %, "
                 f"largeur {box[2]} %, hauteur {box[3]} %.")
        where_en = f" Approximate area (% of the frame): left {box[0]}, top {box[1]}, width {box[2]}, height {box[3]}."
    size = f" Le produit apparaît à {round(revision['scale'] * 100)} % de sa taille de référence." \
        if revision["scale"] != 1 else ""
    fr = (f"Plan : {clock(revision['start_ms'])}–{clock(revision['end_ms'])} de la vidéo source.\n"
          f"Produit : {product['name']} — {product['description']}\n"
          f"Support : {revision['surface']}.{where}{size}\n"
          "Consigne : ajouter ce produit sur ce support, de façon discrète, avec la même lumière, la même "
          "perspective et une ombre de contact crédible. Ne modifier ni les personnages, ni le décor, ni le "
          "mouvement de caméra, ni la durée, ni la résolution. Aucun texte ni logo supplémentaire. Le produit "
          "doit rester fixe sur son support pendant tout le plan et être masqué quand une personne passe devant.")
    en = (f"Edit this video shot: add a small, unobtrusive {product['name']} ({product['description']}) on "
          f"{revision['surface']}.{where_en} "
          "Match the lighting, perspective and add a believable contact shadow. Do not change the people, the "
          "set, the camera motion, the duration or the resolution. No extra text or logos. The product must "
          "stay fixed on the surface for the whole shot and be hidden when someone passes in front of it.")
    return fr, en


def export_source(folder, proposal_id):
    """Découpe le plan approuvé pour l'outil externe et prépare le descriptif."""
    proposal, revision, _ = approved_revision(folder, proposal_id)
    name = f"export-{proposal_id}-r{revision['n']}.mp4"
    ffmpeg("-ss", f"{revision['start_ms'] / 1000:.3f}", "-t", f"{(revision['end_ms'] - revision['start_ms']) / 1000:.3f}",
           "-i", str(folder / "source.mp4"), "-an",   # définition d'origine : Kling exige au moins 700 px sur le petit côté
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-movflags", "+faststart", str(folder / name))
    fr, en = brief_text(folder, proposal, revision)
    product = product_of(folder, revision)
    seconds = (revision["end_ms"] - revision["start_ms"]) / 1000
    warning = (f"Ce plan dure {seconds:.1f} s : plusieurs outils externes se limitent à environ 8 s. "
               "Au besoin, raccourcissez-le avec « Définir l'intervalle exact ».") if seconds > 8.2 else None
    return {"clip": name, "revision": revision["n"], "brief_fr": fr, "brief_en": en, "warning": warning,
            "product_image": product["image"] if product else None,
            "duration_s": round((revision["end_ms"] - revision["start_ms"]) / 1000, 2)}


ALIGN_SIZE = (96, 40)   # images réduites pour comparer le mouvement


def _small(frame, region):
    """Image réduite, centrée en luminosité, sans la zone du produit (seul endroit censé différer)."""
    import cv2
    import numpy as np
    gray = cv2.cvtColor(cv2.resize(frame, ALIGN_SIZE, interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY).astype(np.float32)
    if region:
        w, h = ALIGN_SIZE
        x0, y0 = int(max(0, region["x"] - 0.05) * w), int(max(0, region["y"] - 0.05) * h)
        x1, y1 = int(min(1, region["x"] + region["width"] + 0.05) * w), int(min(1, region["y"] + region["height"] + 0.05) * h)
        gray[y0:y1, x0:x1] = gray.mean()
    return (gray - gray.mean()) / (gray.std() + 1e-3)


def retime(source, edited_path, start_ms, end_ms, region, target):
    """Recale un plan regénéré dont la durée diffère de l'original (un outil peut accélérer une partie du plan).

    Chaque image de l'original (25 i/s) reçoit l'image du plan regénéré qui lui ressemble le plus, hors zone
    du produit, sous contrainte d'ordre (programmation dynamique) : les gestes retombent sur le rythme du
    dialogue d'origine. Retourne l'écart moyen de synchronisation estimé, en secondes."""
    import cv2
    import numpy as np
    src = cv2.VideoCapture(str(source))
    src.set(cv2.CAP_PROP_POS_MSEC, start_ms)
    fps_src = src.get(cv2.CAP_PROP_FPS) or 25
    originals = []
    while src.get(cv2.CAP_PROP_POS_MSEC) < end_ms - 1000 / fps_src / 2:
        ok, frame = src.read()
        if not ok:
            break
        originals.append(_small(frame, region))
    src.release()
    cap = cv2.VideoCapture(str(edited_path))
    fps_edit = cap.get(cv2.CAP_PROP_FPS) or 25
    edits = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        edits.append(_small(frame, region))
    cap.release()
    n, m = len(originals), len(edits)
    if n < 2 or m < 2:
        raise RenderError("Plan importé trop court pour être recalé.")
    A, B = np.stack(originals).reshape(n, -1), np.stack(edits).reshape(m, -1)
    cost = ((A[:, None, :] - B[None, :, :]) ** 2).mean(axis=2)      # n × m
    # Pas attendu (rapport des cadences) ; on pénalise l'écart pour garder un mouvement fluide.
    ratio = m / n                       # images du plan regénéré par image de l'original
    steps = range(0, 4)
    D = np.full((n, m), np.inf)
    back = np.zeros((n, m), dtype=int)
    D[0, :max(1, m // 10)] = cost[0, :max(1, m // 10)]
    for j in range(1, n):
        for s in steps:
            prev = np.full(m, np.inf)
            prev[s:] = D[j - 1, :m - s] if s else D[j - 1]
            cand = prev + cost[j] + 0.15 * abs(s - ratio)
            better = cand < D[j]
            D[j][better] = cand[better]
            back[j][better] = s
    i = int(np.argmin(D[-1, m - max(1, m // 10):])) + m - max(1, m // 10)
    path = [i]
    for j in range(n - 1, 0, -1):
        i -= back[j, i]
        path.append(i)
    path.reverse()
    counts = np.bincount(path, minlength=m)
    cap = cv2.VideoCapture(str(edited_path))
    width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    writer = subprocess.Popen(
        ["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{width}x{height}",
         "-r", f"{fps_src:.3f}", "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "16",
         "-pix_fmt", "yuv420p", str(target)], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    for index in range(m):
        ok, frame = cap.read()
        if not ok:
            break
        for _ in range(counts[index]):
            writer.stdin.write(frame.tobytes())
    cap.release()
    writer.stdin.close()
    if writer.wait(timeout=300):
        raise RenderError("Échec du recalage du plan importé : " + writer.stderr.read().decode("utf-8", "replace")[-300:], 500)
    linear = np.linspace(0, m - 1, n)
    return round(float(np.mean(np.abs(np.array(path) - linear))) / fps_edit, 2)


def assemble(folder, proposal_id, edited_path, tool, note, fit="contain", anchor=0.5, lead_ms=LEAD_MS):
    """Original/édité sur un extrait identique, audio source conservé."""
    proposal, revision, decision = approved_revision(folder, proposal_id)
    source = folder / "source.mp4"
    info = probe(source)
    edited = probe(edited_path)
    retimed = None
    if abs(edited["duration"] - (revision["end_ms"] - revision["start_ms"]) / 1000) > 0.5:
        aligned = edited_path.with_name("aligned-" + edited_path.stem + ".mp4")
        shift = retime(source, edited_path, revision["start_ms"], revision["end_ms"], revision.get("region"), aligned)
        retimed = {"from_s": round(edited["duration"], 2), "shift_s": shift}
        edited_path = aligned
    duration_ms = round(info["duration"] * 1000)
    start, end = revision["start_ms"], revision["end_ms"]
    ex_start = max(0, start - max(0, int(lead_ms)))   # 1 s d'original avant le plan édité, par défaut
    ex_end = min(duration_ms, end + CONTEXT_MS)
    length = (end - start) / 1000
    pre = (start - ex_start) / 1000
    total = (ex_end - ex_start) / 1000
    post_start = pre + length
    W, H = info["width"] - info["width"] % 2, info["height"] - info["height"] % 2
    stem = f"render-{proposal_id}-r{revision['n']}"
    original_name, edited_name = f"{stem}-original.mp4", f"{stem}-edited.mp4"
    common = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
              "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart"]
    ffmpeg("-ss", f"{ex_start / 1000:.3f}", "-t", f"{total:.3f}", "-i", str(source), "-vf", f"fps=25,scale={W}:{H}",
           *common, str(folder / original_name))
    parts, labels = [], []
    chains = [f"[0:v]fps=25,scale={W}:{H},setsar=1,split=3[a][b][c]"]
    if pre > 0.04:
        chains.append(f"[a]trim=0:{pre:.3f},setpts=PTS-STARTPTS[v1]"); labels.append("[v1]")
    else:
        chains.append("[a]nullsink")
    crop = bar_crop(edited_path, W / H)
    cropped = (crop + ",") if crop else ""
    if fit == "cover":   # remplit le cadre de la source, en rognant ce qui dépasse
        fitting = (f"scale={W}:{H}:force_original_aspect_ratio=increase,"
                   f"crop={W}:{H}:(iw-ow)/2:(ih-oh)*{anchor:.2f}")
    else:                # conserve tout le plan, avec des bandes noires si le format diffère
        fitting = f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2"
    chains.append(f"[1:v]{cropped}fps=25,{fitting},"
                  f"setsar=1,tpad=stop_mode=clone:stop_duration={length:.3f},trim=0:{length:.3f},setpts=PTS-STARTPTS[v2]")
    chains.append("[b]nullsink")
    labels.append("[v2]")
    if total - post_start > 0.04:
        chains.append(f"[c]trim={post_start:.3f}:{total:.3f},setpts=PTS-STARTPTS[v3]"); labels.append("[v3]")
    else:
        chains.append("[c]nullsink")
    chains.append("".join(labels) + f"concat=n={len(labels)}:v=1:a=0,format=yuv420p[v]")
    ffmpeg("-ss", f"{ex_start / 1000:.3f}", "-t", f"{total:.3f}", "-i", str(source), "-i", str(edited_path),
           "-filter_complex", ";".join(chains), "-map", "[v]", "-map", "0:a:0?",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "aac", "-b:a", "128k",
           "-movflags", "+faststart", "-shortest", str(folder / edited_name))
    warnings = []
    if retimed:
        edited_path.unlink(missing_ok=True)
        warnings.append(f"Durée du plan importé : {retimed['from_s']:.1f} s pour {length:.1f} s à l'original. "
                        "SceneLine l'a recalé image par image sur le mouvement de l'original (hors zone du produit), "
                        "pour que les gestes suivent le dialogue d'origine.")
    elif abs(edited["duration"] - length) > 0.5:
        warnings.append(f"Durée du plan importé : {edited['duration']:.1f} s ; intervalle approuvé : {length:.1f} s. "
                        "Le plan a été coupé ou prolongé sur sa dernière image.")
    if crop:
        warnings.append("Bandes noires détectées dans le plan importé : elles ont été retirées automatiquement.")
    elif abs(edited["width"] / edited["height"] - W / H) > 0.05:
        warnings.append("Format différent de la source : le plan importé a été recadré pour remplir l'image."
                        if fit == "cover" else
                        "Format différent de la source : le plan importé a été centré avec des bandes noires.")
    warnings.append("Le plan importé est une vidéo regénérée : cadrage, décor et visages peuvent différer de l'original.")
    product = product_of(folder, revision)
    record = {
        "proposal_id": proposal_id, "revision": revision["n"], "revision_digest": digest(revision),
        "product_id": revision["product_id"], "product_name": product["name"] if product else revision["product_id"],
        "mode": revision["mode"], "surface": revision["surface"], "scale": revision["scale"],
        "region": revision.get("region"),
        "source_interval": {"start_ms": start, "end_ms": end},
        "excerpt": {"start_ms": ex_start, "end_ms": ex_end},
        "marker": {"start_ms": start - ex_start, "end_ms": end - ex_start},
        "original": original_name, "edited": edited_name,
        "approved_by": decision["reviewer"], "approved_at": decision["at"],
        "provenance": {"kind": "externe", "label": EXTERNAL_LABEL, "tool": tool, "note": note, "fit": fit, "anchor": anchor, "lead_ms": max(0, int(lead_ms)),
                       "imported_at": now(), "generated_by_sceneline": False},
        "audio": "audio de la source conservé" if info["has_audio"] else "aucune piste audio dans la source",
        "warnings": warnings, "created_at": now(), "retimed": retimed,
    }
    kit = read(folder, "kits.json", {"kits": {}})["kits"].get(proposal_id)
    if kit and kit["revision"] == revision["n"]:
        record["kit"] = {"prompt_sha": kit["prompt_sha"], "created_at": kit["created_at"],
                         "description_model": kit["description_model"], "zip": kit["zip"]}
    with LOCK:
        store = read(folder, "renders.json", {"renders": {}})
        store["renders"][proposal_id] = record
        replace_json(folder / "renders.json", store)
    return record


# --------------------------------------------------------------------------- la vidéo est-elle pour ce plan ?

def _grab(path, seconds):
    cap = cv2.VideoCapture(str(path))
    cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, seconds * 1000))
    ok, frame = cap.read()
    cap.release()
    return frame if ok else None


def _picture(frame):
    """Image sans bandes noires, en niveaux de gris, réduite et normalisée : comparable d'un outil à l'autre."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    rows = np.where(gray.mean(axis=1) > 20)[0]
    cols = np.where(gray.mean(axis=0) > 20)[0]
    if len(rows) > 10 and len(cols) > 10:
        gray = gray[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1]
    small = cv2.GaussianBlur(cv2.resize(gray, (96, 54), interpolation=cv2.INTER_AREA).astype(np.float32), (0, 0), 1.0)
    return (small - small.mean()) / (small.std() + 1e-3)


def match_score(source, start_ms, end_ms, edited):
    """Ressemblance (de -1 à 1) entre la vidéo importée et le plan d'origine, sur cinq instants."""
    cap = cv2.VideoCapture(str(edited))
    duration = cap.get(cv2.CAP_PROP_FRAME_COUNT) / (cap.get(cv2.CAP_PROP_FPS) or 25)
    cap.release()
    length = (end_ms - start_ms) / 1000
    values = []
    for f in (0.1, 0.3, 0.5, 0.7, 0.9):
        frame = _grab(edited, f * duration)
        if frame is None:
            continue
        picture = _picture(frame)
        best = -1.0
        for dt in (-0.4, 0.0, 0.4):
            original = _grab(source, start_ms / 1000 + f * length + dt)
            if original is not None:
                best = max(best, float((picture * _picture(original)).mean()))
        values.append(best)
    return round(float(np.mean(values)), 3) if values else 0.0


def check_match(folder, proposal_id, revision, edited):
    """Refuse une vidéo qui n'est pas celle de ce placement, et dit à quel placement elle correspond."""
    source = folder / "source.mp4"
    own = match_score(source, revision["start_ms"], revision["end_ms"], edited)
    best = None
    for pid in read(folder, "proposals.json", {"proposals": {}})["proposals"]:
        if pid == proposal_id:
            continue
        try:
            _, other, _ = approved_revision(folder, pid)
        except RenderError:      # placement non approuvé : il ne peut pas recevoir de vidéo
            continue
        value = match_score(source, other["start_ms"], other["end_ms"], edited)
        if not best or value > best[0]:
            best = (value, other)
    here = f"{clock(revision['start_ms'])}–{clock(revision['end_ms'])}"
    if best and best[0] > own + MATCH_MARGIN and best[0] >= MATCH_MIN:
        product = product_of(folder, best[1])
        name = product["name"] if product else best[1]["product_id"]
        raise RenderError(f"Cette vidéo correspond au placement {name} {clock(best[1]['start_ms'])}–{clock(best[1]['end_ms'])}, "
                          f"pas à celui-ci ({here}). Importez-la sur le bon placement.", 422)
    if own < MATCH_MIN:
        raise RenderError(f"Cette vidéo ne ressemble pas au plan d'origine ({here}) : vérifiez que c'est la bonne. "
                          "Si l'outil a beaucoup transformé le plan, importez-la quand même.", 422)
    return own


def remove_render(folder, proposal_id):
    """Retire un résultat intégré par erreur : l'extrait, le plan importé et sa ligne du relevé."""
    with LOCK:
        store = read(folder, "renders.json", {"renders": {}})
        record = store["renders"].pop(proposal_id, None)
        if not record:
            raise RenderError("Aucun résultat intégré pour ce placement.", 404)
        replace_json(folder / "renders.json", store)
    for name in (record["original"], record["edited"]):
        (folder / name).unlink(missing_ok=True)
    for stored in folder.glob(f"external-{proposal_id}-r{record['revision']}.*"):
        stored.unlink(missing_ok=True)
    return {"removed": proposal_id}


def import_external(folder, proposal_id, data, extension, tool, note, fit="contain", anchor=0.5, lead_ms=LEAD_MS,
                    force=False):
    tool = (tool or "").strip()[:120]
    if not tool:
        raise RenderError("Indiquez l'outil externe utilisé pour l'aperçu.")
    if extension.lower() not in VIDEO_EXTENSIONS:
        raise RenderError("Format accepté : MP4, MOV, WebM ou MKV.")
    if not data or len(data) > MAX_UPLOAD:
        raise RenderError("Le plan importé doit peser entre 1 octet et 200 Mo.")
    _, revision, _ = approved_revision(folder, proposal_id)
    kit = read(folder, "kits.json", {"kits": {}})["kits"].get(proposal_id)
    if not kit or kit["revision"] != revision["n"] or not kit.get("reference"):
        raise RenderError("Ce placement n'a pas encore de kit avec son image de référence (étape 3) : "
                          "la vidéo à intégrer doit être produite à partir de ce kit.", 409)
    final = folder / f"external-{proposal_id}-r{revision['n']}{extension.lower()}"
    staging = final.with_name("staging-" + final.name)
    staging.write_bytes(data)
    try:
        match = None if force else check_match(folder, proposal_id, revision, staging)
        record = assemble(folder, proposal_id, staging, tool, (note or "").strip()[:300],
                          "cover" if fit == "cover" else "contain", min(1.0, max(0.0, float(anchor))), lead_ms)
        staging.replace(final)          # le plan reçu n'est conservé qu'après validation et assemblage
        if match is not None or force:
            with LOCK:
                store = read(folder, "renders.json", {"renders": {}})
                store["renders"][proposal_id]["match"] = {"score": match, "forced": bool(force)}
                replace_json(folder / "renders.json", store)
            record["match"] = {"score": match, "forced": bool(force)}
        return record
    except subprocess.TimeoutExpired:
        raise RenderError("Le traitement vidéo a dépassé le délai.", 504) from None
    finally:
        staging.unlink(missing_ok=True)


def renders(folder):
    return read(folder, "renders.json", {"renders": {}})["renders"]


def modification_log(folder):
    """Relevé qui accompagne la version éditée, distinct de la signalétique du lecteur."""
    items = []
    for record in renders(folder).values():
        items.append({
            "placement": record["product_name"], "mode": record["mode"], "support": record["surface"],
            "intervalle_source_ms": record["source_interval"], "intervalle_extrait_ms": record["marker"],
            "revision": record["revision"], "empreinte_revision": record["revision_digest"],
            "approuve_par": record["approved_by"], "approuve_le": record["approved_at"],
            "provenance": record["provenance"]["label"], "outil": record["provenance"]["tool"],
            "genere_par_sceneline": False, "kit_de_generation": record.get("kit"),
            "audio": record["audio"], "avertissements": record["warnings"]})
    return {
        "titre": "Relevé des modifications virtuelles",
        "avertissement": "Placements virtuels ajoutés en postproduction après approbation du producteur. "
                         "Ce relevé ne remplace pas les obligations légales de signalement du placement de produit.",
        "version_originale_conservee": True, "modifications": items, "genere_le": now()}


def reassemble(folder, proposal_id, lead_ms):
    """Refait l'extrait avec un autre contexte avant le placement, sans nouvel aperçu externe."""
    _, revision, _ = approved_revision(folder, proposal_id)
    record = renders(folder).get(proposal_id)
    if not record or record["revision"] != revision["n"]:
        raise RenderError("Aucun aperçu importé pour la révision approuvée.", 409)
    stored = next(iter(folder.glob(f"external-{proposal_id}-r{revision['n']}.*")), None)
    if not stored:
        raise RenderError("Le plan importé n'est plus disponible : importez-le à nouveau.", 409)
    try:
        lead = min(10000, max(0, int(lead_ms)))
    except (TypeError, ValueError):
        raise RenderError("Contexte avant le placement invalide.") from None
    prov = record["provenance"]
    match = record.get("match")
    fresh = assemble(folder, proposal_id, stored, prov["tool"], prov["note"], prov.get("fit", "contain"),
                     prov.get("anchor", 0.7), lead)
    if match:
        with LOCK:
            store = read(folder, "renders.json", {"renders": {}})
            store["renders"][proposal_id]["match"] = match
            replace_json(folder / "renders.json", store)
        fresh["match"] = match
    return fresh
