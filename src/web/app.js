// SceneLine · noyau de l'interface : aides, navigation par étapes et étape 1 (analyse).
const get = (id) => document.getElementById(id);

function node(tag, value, className) {
  const element = document.createElement(tag);
  if (value !== undefined && value !== null && value !== "") element.textContent = value;
  if (className) element.className = className;
  return element;
}

function time(ms) {
  const seconds = Math.floor(ms / 1000);
  return [Math.floor(seconds / 60), seconds % 60].map(n => String(n).padStart(2, "0")).join(":");
}

const upper = (text) => text ? text.charAt(0).toUpperCase() + text.slice(1) : text;

// État partagé : projet courant, étape affichée, données chargées par les autres scripts.
const S = {job: null, step: 1, analysisDone: false, project: null, wanted: null};
window.S = S;

const player = get("player");

function seekButton(label, ms) {
  const button = node("button", label, "time");
  button.type = "button";
  button.onclick = () => {
    const holder = player.closest("details");
    if (holder) holder.open = true;
    player.currentTime = ms / 1000;
    player.scrollIntoView({block: "center", behavior: "smooth"});
  };
  return button;
}

/* ------------------------------------------------------------------ navigation par étapes */

const approvedProposals = () => (S.project?.proposals || []).filter(p => p.status === "approuvee");
const hasKit = () => approvedProposals().some(p => S.project.kits?.[p.id]?.revision === p.approved_revision);
const hasRender = () => approvedProposals().some(p => S.project.renders?.[p.id]?.revision === p.approved_revision);

function unlocked(step) {
  if (step <= 1) return true;           // l'étape 1 et la page Éthique 360 (0) sont toujours ouvertes
  if (step === 2) return S.analysisDone;
  return approvedProposals().length > 0;
}

const lockReason = (step) => step === 2 ? "Terminez d’abord l’analyse de la vidéo." : "Approuvez d’abord un placement.";

function toast(message) {
  const box = get("toast");
  box.textContent = message;
  box.classList.add("on");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => box.classList.remove("on"), 2800);
}
window.toast = toast;

function isDone(step) {
  return [null, S.analysisDone, approvedProposals().length > 0, hasKit(), hasRender()][step];
}

function refreshStepper() {
  document.querySelectorAll(".step-pill").forEach(pill => {
    const step = Number(pill.dataset.step);
    if (step === S.step) pill.setAttribute("aria-current", "step"); else pill.removeAttribute("aria-current");
    pill.disabled = !unlocked(step);
    pill.title = unlocked(step) ? "" : lockReason(step);
    pill.classList.toggle("done", isDone(step) && step !== S.step);
  });
  document.querySelectorAll("[data-needs]").forEach(button => {
    const step = Number(button.dataset.needs);
    button.disabled = !unlocked(step);
    button.title = unlocked(step) ? "" : lockReason(step);
  });
  const ethics = get("lk-eth");
  if (S.step === 0) ethics.setAttribute("aria-current", "page"); else ethics.removeAttribute("aria-current");
  if (S.wanted && unlocked(S.wanted)) { const wanted = S.wanted; S.wanted = null; go(wanted); }
}

// Change d'étape (0 = page Éthique 360). `target` : identifiant d'un élément vers lequel défiler.
function go(step, target) {
  if (!unlocked(step)) { toast(lockReason(step)); return; }
  if (step > 0) S.prev = step;
  S.step = step;
  document.querySelectorAll(".stage").forEach(stage => stage.classList.toggle("active", Number(stage.dataset.step) === step));
  const hash = step === 0 ? "#ethique-360" + (target && target.startsWith("ax-") ? "/" + target.slice(3) : "") : "#etape-" + step;
  history.replaceState(null, "", location.pathname + location.search + hash);
  refreshStepper();
  if (step > 1 && window.reloadProject) window.reloadProject();   // toujours l'état du projet le plus récent
  const heading = document.querySelector("#stage-" + step + " h1");
  if (heading) heading.focus({preventScroll: true});
  const element = target && document.getElementById(target);
  if (element) requestAnimationFrame(() => element.scrollIntoView({behavior: "smooth", block: "start"}));
  else window.scrollTo({top: 0, behavior: "smooth"});
}

window.go = go;
window.refreshAnalysis = () => S.job && poll(S.job);
window.refreshStepper = refreshStepper;
window.setProject = (data) => { S.project = data; refreshStepper(); };

document.querySelectorAll(".step-pill").forEach(pill => pill.addEventListener("click", () => go(Number(pill.dataset.step))));
document.addEventListener("click", (event) => {
  const target = event.target.closest("[data-go]");
  if (target && !target.disabled) go(Number(target.dataset.go));
});

/* ------------------------------------------------------------------ étape 1 : envoi */

const form = get("upload");
const videoInput = get("video");
const status = get("status");
const resume = get("resume");
let activeJob;

videoInput.addEventListener("change", () => {
  const file = videoInput.files[0];
  get("filename").textContent = file ? file.name : "Choisir une vidéo";
  videoInput.closest(".dropzone").classList.toggle("has-file", Boolean(file));
  status.textContent = file ? "Prêt. Cochez les deux autorisations pour lancer l’analyse." : "Choisissez une vidéo pour commencer.";
});

document.querySelectorAll("input[data-for]").forEach(box => box.addEventListener("change", () => {
  const input = get(box.dataset.for);
  input.disabled = box.checked;
  if (box.checked) input.value = "";
}));

function view(name) {
  get("upload").hidden = name !== "upload";
  get("progress-card").hidden = name !== "progress";
  get("results").hidden = name !== "results";
}

function updateSteps(stage, state, done, total) {
  document.querySelectorAll("#steps li").forEach((step, index) => {
    step.classList.toggle("done", index + 1 < stage);
    step.classList.toggle("active", state === "running" && index + 1 === stage);
  });
  let part = Math.max(stage - 1, 0);
  if (stage === 5 && total) part += Math.min(done / total, 1);
  get("progress-bar").style.width = Math.max(4, Math.min(100, part / 6 * 100)) + "%";
}

function setBusy(busy) {
  get("submit").disabled = busy;
}

/* ------------------------------------------------------------------ garde d'intégrité culturelle */

function riskPill(guard) {
  const pill = node("span", null, "risk " + guard.level);
  pill.append(node("i"), document.createTextNode(guard.label));
  return pill;
}

// Verdict du Guard : alerte éventuelle, justification, puis le détail des cinq critères.
function guardBlock(guard) {
  const box = node("section", null, "guard");
  box.setAttribute("aria-label", "Cultural Integrity Guard");
  const head = node("div", null, "guard-head");
  head.append(node("span", "Cultural Integrity Guard", "guard-name"), riskPill(guard));
  box.append(head);
  if (guard.alert) {
    const alert = node("p", null, "guard-alert");
    alert.append(node("b", guard.alert.title + ". "), document.createTextNode(guard.alert.text));
    box.append(alert);
  }
  box.append(node("p", guard.summary, "guard-summary"));
  const details = node("details", null, "guard-details");
  details.append(node("summary", "Les cinq critères"));
  for (const dimension of guard.dimensions) {
    const row = node("div", null, "guard-row " + dimension.level);
    row.append(node("i"), node("b", dimension.label), node("span", dimension.text));
    details.append(row);
  }
  box.append(details);
  return box;
}
window.guardBlock = guardBlock;
window.riskPill = riskPill;
let currentGuard = {scenes: {}, opportunities: {}};

/* ------------------------------------------------------------------ étape 1 : résultats */

function regionOf(item, frame) {
  if (!item.region) return;
  const region = node("span", null, "region");
  region.setAttribute("aria-hidden", "true");
  for (const [property, key] of [["left", "x"], ["top", "y"], ["width", "width"], ["height", "height"]]) {
    region.style[property] = item.region[key] * 100 + "%";
  }
  frame.append(region);
}

function thumb(src, alt, item, badge) {
  const frame = node("div", null, "thumb");
  const image = node("img"); image.src = src; image.alt = alt; image.loading = "lazy";
  frame.append(image);
  if (item) regionOf(item, frame);
  if (badge) frame.append(node("span", badge, "thumb-badge"));
  return frame;
}

// Carte de la vidéo : chaque scène colorée selon le Guard, les placements proposés en jaune dessous.
function videoMap(result, kept) {
  const map = get("videomap");
  const total = result.duration_ms || Math.max(...result.shots.map(s => s.end_ms));
  const pct = (ms) => (ms / total * 100) + "%";
  const scenes = node("div", null, "lane scenes-lane");
  for (const scene of result.scenes || []) {
    const verdict = currentGuard.scenes[scene.id] || {level: "faible", label: "", text: ""};
    const seg = node("button", null, "seg " + verdict.level);
    seg.type = "button";
    seg.style.left = pct(scene.start_ms); seg.style.width = pct(scene.end_ms - scene.start_ms);
    const label = "Scène " + scene.id + ", " + time(scene.start_ms) + " – " + time(scene.end_ms) + " : " + (verdict.label || "") +
      (scene.kind === "generique" ? " (titre ou générique)" : ". " + scene.summary);
    seg.title = label; seg.setAttribute("aria-label", label);
    seg.onclick = () => seekTo(scene.start_ms);
    scenes.append(seg);
  }
  const lane = node("div", null, "lane places-lane");
  for (const item of kept) {
    const tick = node("button", null, "tick");
    tick.type = "button";
    tick.style.left = pct(item.start_ms); tick.style.width = pct(item.end_ms - item.start_ms);
    const label = "Placement n° " + item.rank + ", " + time(item.start_ms) + " – " + time(item.end_ms) + " : " + item.surface;
    tick.title = label; tick.setAttribute("aria-label", label);
    tick.onclick = () => seekTo(item.start_ms);
    lane.append(tick);
  }
  const axis = node("div", null, "axis");
  axis.append(node("span", "00:00"), node("span", time(total)));
  map.replaceChildren(scenes, lane, axis);
  const count = (level) => (result.scenes || []).filter(s => (currentGuard.scenes[s.id] || {}).level === level).length;
  const legend = get("videomap-legend");
  const key = (cls, text) => { const item = node("span", null, "key"); item.append(node("i", null, cls), document.createTextNode(text)); return item; };
  legend.replaceChildren(
    key("seg eleve", "Scène protégée, aucun placement (" + count("eleve") + ")"),
    key("seg moyen", "À vérifier par le réalisateur (" + count("moyen") + ")"),
    key("seg faible", "Sans risque relevé (" + count("faible") + ")"),
    key("tick", "Placement proposé (" + kept.length + ")"));
}

function seekTo(ms) {
  const holder = player.closest("details");
  if (holder) holder.open = true;
  player.currentTime = ms / 1000;
  player.scrollIntoView({block: "center", behavior: "smooth"});
}

async function retain(item, button) {
  button.disabled = true;
  try {
    const response = await fetch("/api/jobs/" + S.job + "/opportunities/" + item.key + "/retain", {method: "POST",
      headers: {"Content-Type": "application/json"}, body: JSON.stringify({reviewer: localStorage.getItem("sceneline-reviewer") || ""})});
    const answer = await response.json();
    if (!response.ok) throw Error(answer.message || "Impossible de retenir ce placement.");
    await poll(S.job);
  } catch (error) { button.textContent = error.message; }
}

function surfacePicker(item, base) {
  const box = node("div", null, "surface-picker");
  const reviewer = () => localStorage.getItem("sceneline-reviewer") || "";
  const choose = async (index, button) => {
    button.disabled = true;
    const response = await fetch("/api/jobs/" + S.job + "/opportunities/" + item.key + "/surface", {method: "POST",
      headers: {"Content-Type": "application/json"}, body: JSON.stringify({index, reviewer: reviewer()})});
    const answer = await response.json();
    if (!response.ok) { button.textContent = answer.message || "Échec"; return; }
    await poll(S.job);
  };
  const render = options => {
    box.replaceChildren(node("p", options.length ? "Surfaces trouvées dans ce plan :" : "Aucune autre surface utilisable dans ce plan.", "surface-title"));
    options.forEach((option, index) => {
      const row = node("div", null, "surface-option");
      row.append(thumb(base + item.reference_frame, option.surface, option));
      const text = node("div");
      text.append(node("b", upper(option.surface)), node("span", option.overall_score + "/10", "score-text"), node("p", option.reason));
      row.append(text);
      const current = option.surface === item.surface;
      const button = node("button", current ? "Surface actuelle" : "Choisir", "btn quiet small");
      button.type = "button";
      button.disabled = current;
      button.onclick = () => choose(index, button);
      row.append(button);
      box.append(row);
    });
  };
  const search = node("button", item.surface_options ? "Relancer la recherche de surfaces" : "Chercher d’autres surfaces dans ce plan", "link");
  search.type = "button";
  search.onclick = async () => {
    search.disabled = true;
    search.textContent = "Recherche en cours…";
    const response = await fetch("/api/jobs/" + S.job + "/opportunities/" + item.key + "/surfaces", {method: "POST"});
    const answer = await response.json();
    if (!response.ok) { search.textContent = answer.message || "Recherche impossible"; return; }
    item.surface_options = answer.options;
    render(answer.options);
    search.disabled = false;
    search.textContent = "Relancer la recherche de surfaces";
    box.append(search);
  };
  if (item.surface_options) render(item.surface_options);
  if (item.surface_choice) box.prepend(node("p", "Surface d’origine proposée par SceneLine : " + item.surface_choice.was + ".", "facts"));
  box.append(search);
  return box;
}

function placeRow(item, base) {
  const labels = {keep: "Proposé", reserve: "En réserve", uncertain: "Incertain", reject: "Écarté"};
  const modes = {affiche_murale: "Affiche murale", signaletique: "Signalétique", objet_pose: "Objet posé", aucun: "Aucun"};
  const row = node("article", null, "place " + item.decision);
  row.append(thumb(base + item.reference_frame, "Image de l’intervalle du plan " + item.shot_id, item, item.rank ? "N° " + item.rank : null));
  const body = node("div", null, "place-body");
  const line = node("div", null, "place-line");
  line.append(seekButton(time(item.start_ms) + " – " + time(item.end_ms), item.start_ms));
  const verdict = currentGuard.opportunities[item.key];
  if (verdict) line.append(riskPill(verdict));
  if (item.decision !== "keep") line.append(node("span", labels[item.decision], "chip " + (item.decision === "reject" ? "bad" : "warn")));
  if (item.retained) line.append(node("span", "Retenu par " + item.retained.by, "chip accent"));
  line.append(node("span", item.overall_score + "/10", "score-text"));
  body.append(line, node("h3", upper(item.surface)), node("p", item.reason, "reason"));
  const facts = node("p", null, "facts");
  facts.textContent = (modes[item.placement_mode] || "—") + " · plan " + item.shot_id + " · " +
    (item.starts_on_cut && item.ends_on_cut ? "de coupe à coupe" : "raccord à vérifier");
  body.append(facts);
  const details = node("details", null, "more");
  details.append(node("summary", item.decision === "keep" ? "Détails et Cultural Integrity Guard" : "Détails"));
  const inner = node("div", null, "more-body");
  if (item.alignment) inner.append(node("p", "Raccord : " + item.alignment));
  const plain = (list) => list.map(name => name.replace(/_/g, " ")).join(", ");
  if (item.compatible_categories?.length) inner.append(node("p", "Catégories compatibles : " + plain(item.compatible_categories)));
  if (item.avoid_categories?.length) inner.append(node("p", "À éviter : " + plain(item.avoid_categories)));
  if (item.decision === "keep" && item.product_example) inner.append(node("p", "Exemple d’objet : " + item.product_example));
  inner.append(node("p", item.decision_note));
  if (verdict && item.decision === "keep") inner.append(guardBlock(verdict));
  if (item.decision !== "reject") inner.append(surfacePicker(item, base));
  details.append(inner);
  body.append(details);
  row.append(body);
  if (item.decision === "reserve" || item.decision === "uncertain") {
    const button = node("button", "Retenir ce placement", "btn secondary small");
    button.type = "button";
    button.onclick = () => retain(item, button);
    row.append(button);
  }
  return row;
}

function guardSceneRow(scene, verdict, base, shotById) {
  const row = node("article", null, "place guard-scene " + verdict.level);
  const shot = shotById[scene.shot_ids[Math.floor(scene.shot_ids.length / 2)]] || shotById[scene.shot_ids[0]];
  if (shot) row.append(thumb(base + shot.frame, "Image de la scène " + scene.id));
  const body = node("div", null, "place-body");
  const line = node("div", null, "place-line");
  line.append(seekButton(time(scene.start_ms) + " – " + time(scene.end_ms), scene.start_ms), riskPill(verdict));
  body.append(line, node("h3", scene.kind === "generique" ? "Titre ou générique" : upper(scene.summary)), node("p", verdict.text, "reason"));
  if (verdict.alert) body.append(node("p", "Alerte : SceneLine ne propose aucun placement dans cette scène.", "guard-alert"));
  row.append(body);
  return row;
}

function sceneItem(scene) {
  const item = node("div", null, "list-item");
  item.append(seekButton(time(scene.start_ms) + " – " + time(scene.end_ms), scene.start_ms));
  const text = node("div");
  text.append(node("p", scene.summary, "main"));
  const verdict = currentGuard.scenes[scene.id];
  const meta = node("p");
  if (verdict) meta.append(riskPill(verdict), document.createTextNode("  "));
  meta.append(document.createTextNode(scene.location + " · " + scene.period + " · " + scene.tone));
  text.append(meta);
  if (scene.protection !== "clear" && scene.protection_reason) text.append(node("p", "Pourquoi : " + scene.protection_reason));
  if (scene.cultural_cues && scene.cultural_cues !== "Aucun indice relevé") text.append(node("p", "Indices culturels : " + scene.cultural_cues));
  item.append(text);
  return item;
}

function showResults(job, result, complete) {
  const base = "/api/jobs/" + job + "/files/";
  player.src = base + "source.mp4";
  get("download").href = base + (result.pipeline_version ? "sceneline.json" : "analysis.json");
  const items = (result.opportunities || []).filter(item => item.decision);
  const scenes = result.scenes || [];
  const kept = items.filter(item => item.decision === "keep").sort((a, b) => a.rank - b.rank);
  const others = items.filter(item => item.decision !== "keep");
  const metrics = result.metrics || {};
  currentGuard = result.guard || {scenes: {}, opportunities: {}};
  const protectedCount = scenes.filter(scene => (currentGuard.scenes[scene.id] || {}).level === "eleve").length;
  get("overview-text").textContent = "SceneLine a compris " + scenes.length + " scènes dans " + result.shots.length + " plans. " +
    (kept.length ? "Il propose " + kept.length + (kept.length > 1 ? " placements" : " placement") : "Il ne propose aucun placement") +
    " et protège " + protectedCount + (protectedCount > 1 ? " scènes." : " scène.");
  get("overview-meta").textContent = [result.scene_model ? "Scènes : " + result.scene_model : result.review_model,
    metrics.api_calls ? metrics.api_calls + " appels" : null, metrics.frames_sent ? metrics.frames_sent + " images envoyées" : null,
    !complete ? "analyse incomplète" : null,
    result.scene_model && !/3\.5/.test(result.scene_model) ? "modèle de secours : relire les scènes" : null].filter(Boolean).join(" · ");
  videoMap(result, kept);
  const list = get("candidates");
  list.replaceChildren(...kept.map(item => placeRow(item, base)));
  if (complete && !kept.length) list.append(node("p", "Aucun placement approprié dans cette vidéo. C’est un résultat valide : rien n’est imposé à l’œuvre.", "empty"));
  const shotById = Object.fromEntries(result.shots.map(shot => [shot.id, shot]));
  const order = ["eleve", "moyen"];
  const flagged = scenes.filter(scene => currentGuard.scenes[scene.id] && currentGuard.scenes[scene.id].level !== "faible")
    .sort((a, b) => order.indexOf(currentGuard.scenes[a.id].level) - order.indexOf(currentGuard.scenes[b.id].level) || a.start_ms - b.start_ms);
  get("guard-section").hidden = !flagged.length;
  get("guard-scenes").replaceChildren(...flagged.map(scene => guardSceneRow(scene, currentGuard.scenes[scene.id], base, shotById)));
  const rank = {reserve: 0, uncertain: 1, reject: 2};
  get("rejected").replaceChildren(...others.sort((a, b) => rank[a.decision] - rank[b.decision] || b.overall_score - a.overall_score).map(item => placeRow(item, base)));
  get("others-count").textContent = others.length + " intervalles, dont " + others.filter(o => o.decision !== "reject").length + " que vous pouvez retenir";
  get("scenes").replaceChildren(...scenes.map(sceneItem));
  get("scenes-count").textContent = scenes.length + " scènes";
  get("transcript").replaceChildren(...result.transcript.map(line => {
    const paragraph = node("p", null, "line-text");
    paragraph.append(seekButton(time(line.start_ms), line.start_ms), document.createTextNode(line.text));
    return paragraph;
  }));
  if (!result.transcript.length) get("transcript").append(node("p", "Aucun dialogue transcrit.", "empty"));
  get("shots").replaceChildren(...result.shots.map(shot => {
    const button = seekButton(time(shot.start_ms), shot.start_ms);
    button.className = "shot";
    const image = node("img");
    image.src = base + shot.frame; image.alt = "Plan " + shot.id; image.loading = "lazy";
    button.prepend(image);
    return button;
  }));
  if (window.renderOpportunityReport) window.renderOpportunityReport(job, result);
  view("results");
}

/* ------------------------------------------------------------------ étape 1 : suivi de l'analyse */

async function poll(job) {
  try {
    const response = await fetch("/api/jobs/" + job, {cache: "no-store"});
    if (!response.ok) throw Error("Impossible de retrouver cette analyse.");
    const data = await response.json();
    if (job !== activeJob) return;
    updateSteps(data.stage, data.state, data.done, data.total);
    if (data.state === "queued" || data.state === "running") {
      view("progress");
      get("progress-title").textContent = data.state === "queued" ? "Analyse en attente" : "Analyse en cours";
      get("progress-sub").textContent = data.stage === 5 ? "Revue des zones · " + data.done + " sur " + data.total + " intervalles" :
        data.stage === 6 ? "Vérification des meilleurs placements" : data.stage === 4 ? "Compréhension des scènes" : "Préparation de la vidéo";
      resume.hidden = true; get("log").hidden = true;
      setTimeout(() => poll(job), 1200);
      return;
    }
    if (data.result) showResults(job, data.result, data.state === "complete");
    if (data.state === "complete") {
      S.analysisDone = true;
      refreshStepper();
      if (window.loadProject) window.loadProject(job);
    } else {
      if (!data.result) view("progress");
      get("progress-title").textContent = "L’analyse s’est arrêtée";
      get("progress-sub").textContent = data.message || "Une erreur est survenue.";
      resume.hidden = data.stage < 4;
      get("log").href = "/api/jobs/" + job + "/files/run.log";
      get("log").hidden = false;
    }
  } catch (error) {
    view(S.job ? "progress" : "upload");
    get("progress-title").textContent = "Projet introuvable";
    get("progress-sub").textContent = error.message;
  }
  setBusy(false);
}

resume.onclick = async () => {
  resume.hidden = true;
  try {
    const response = await fetch("/api/jobs/" + activeJob + "/resume", {method: "POST"});
    if (!response.ok) throw Error("La reprise est indisponible.");
    poll(activeJob);
  } catch (error) {
    get("progress-sub").textContent = error.message;
    resume.hidden = false;
  }
};

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = new FormData(form);
  setBusy(true);
  status.classList.remove("error");
  status.textContent = "Import de la vidéo…";
  try {
    const response = await fetch("/api/jobs", {method: "POST", body: data});
    const result = await response.json();
    if (!response.ok) throw Error(result.message);
    activeJob = S.job = result.id;
    S.analysisDone = false;
    history.replaceState(null, "", "/?analyse=" + activeJob + "#etape-1");
    updateSteps(0, "queued", 0, 0);
    view("progress");
    poll(activeJob);
  } catch (error) {
    status.textContent = error.message;
    status.classList.add("error");
    setBusy(false);
  }
});

/* ------------------------------------------------------------------ typographie française */

// Espaces insécables avant « : ; ! ? » et « % », autour des guillemets et des tirets de plage, après un nombre.
const NBSP = " ";
function typo(root) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {acceptNode: (n) =>
    /^(SCRIPT|STYLE|TEXTAREA|PRE|CODE|INPUT)$/.test(n.parentNode.nodeName) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT});
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  for (const text of nodes) {
    const before = text.nodeValue;
    const after = before.replace(/ ([:;!?»%])/g, NBSP + "$1").replace(/(«) /g, "$1" + NBSP)
      .replace(/(\d) (?=[A-Za-zÀ-ÿ])/g, "$1" + NBSP).replace(/ – /g, NBSP + "–" + NBSP);
    if (after !== before) text.nodeValue = after;
  }
}
let typoQueued = false;
new MutationObserver(() => {
  if (typoQueued) return;
  typoQueued = true;
  requestAnimationFrame(() => { typoQueued = false; typo(document.body); });
}).observe(document.body, {childList: true, subtree: true});

window.addEventListener("hashchange", () => {
  const ethics = location.hash.match(/^#ethique-360(?:\/(\w+))?/);
  if (ethics) { if (window.openEthics) window.openEthics(ethics[1]); return; }
  const step = Number((location.hash.match(/^#etape-(\d)/) || [])[1]);
  if (step && step !== S.step) go(step);
});

/* ------------------------------------------------------------------ démarrage */

const previous = new URLSearchParams(location.search).get("analyse");
const hashStep = Number((location.hash.match(/etape-(\d)/) || [])[1]) || 1;
S.wanted = hashStep > 1 ? hashStep : null;
document.querySelector("#stage-1").classList.add("active");
refreshStepper();
if (previous && /^[a-f0-9]{32}$/.test(previous)) {
  activeJob = S.job = previous;
  view("progress");
  get("progress-title").textContent = "Chargement du projet";
  poll(previous);
} else {
  view("upload");
}
