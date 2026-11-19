// Étape 2 · catalogue, appariement et décisions du producteur. Utilise get, node, time, upper, seekButton, S de app.js.
(() => {
  let job = null;
  let labels = {categories: {}, modes: {}};
  let timer = null;
  const reviewer = get("reviewer");
  reviewer.value = localStorage.getItem("sceneline-reviewer") || "";
  reviewer.addEventListener("change", () => localStorage.setItem("sceneline-reviewer", reviewer.value.trim()));

  const actionText = {accepter: "Acceptée", refuser: "Refusée", ajuster: "Ajustement demandé", reviser: "Nouvelle révision"};
  const verdictText = {propose: "Convenable", insuffisant: "Score insuffisant", restriction: "Restriction du produit",
    risque_eleve: "Écarté par le Cultural Integrity Guard"};
  const base = () => "/api/jobs/" + job + "/files/";
  const when = (iso) => new Date(iso).toLocaleString("fr-FR", {dateStyle: "medium", timeStyle: "short"});

  async function api(path, options) {
    const response = await fetch("/api/jobs/" + job + path, {cache: "no-store", ...options});
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw Error(body.message || "Requête impossible.");
    return body;
  }
  const json = (method, body) => ({method, headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});

  function fill(select, entries) {
    select.replaceChildren(...Object.entries(entries).map(([value, text]) => {
      const option = node("option", text);
      option.value = value;
      return option;
    }));
  }

  function chipChoices(container, entries, name, selected = []) {
    container.replaceChildren(...Object.entries(entries).map(([value, text]) => {
      const label = node("label");
      const input = node("input");
      input.type = "checkbox"; input.name = name; input.value = value; input.checked = selected.includes(value);
      label.append(input, node("span", text));
      return label;
    }));
  }

  /* ---------------------------------------------------------------- catalogue */

  function productCard(product) {
    const attrs = product.effective;
    const card = node("article", null, "product");
    const pic = node("div", null, "pic");
    const image = node("img");
    image.src = base() + (product.asset || product.image); image.alt = "Visuel de " + product.name; image.loading = "lazy";
    pic.append(image);
    const tags = node("div", null, "tags");
    tags.append(node("span", labels.categories[attrs.category], "chip accent"), node("span", attrs.size_class, "chip"));
    if (attrs.origin) tags.append(node("span", attrs.origin, "chip"));
    if (product.provenance.startsWith("FICTIF")) tags.append(node("span", "Fictif", "chip warn"));
    card.append(pic, node("h4", product.name), tags);
    const details = node("details");
    details.append(node("summary", product.analysis ? "Détails" : "Détails (analyse à l’appariement)"));
    if (product.analysis) {
      details.append(node("p", "Apparence · " + product.analysis.appearance));
      if (product.analysis.uncertainties.length) details.append(node("p", "Incertitudes · " + product.analysis.uncertainties.join(" ; ")));
    }
    details.append(node("p", "Modes · " + attrs.modes.map(m => labels.modes[m]).join(", ")));
    if (attrs.markets?.length) details.append(node("p", "Marchés visés · " + attrs.markets.join(", ")));
    if (attrs.flags.length) details.append(node("p", "Sujets sensibles · " + attrs.flags.join(", ")));
    if (attrs.exclusions) details.append(node("p", "Restrictions · " + attrs.exclusions));
    for (const warning of attrs.warnings) details.append(node("p", warning, "badge uncertain"));
    details.append(node("p", "Provenance du visuel · " + product.provenance));
    const edit = node("button", "Corriger les attributs", "link");
    edit.type = "button";
    edit.onclick = () => { edit.hidden = true; details.append(correctionForm(product)); };
    details.append(edit);
    card.append(details, viewsBlock(product));
    return card;
  }

  // Planche d'angles (facultative) : un prompt pour un outil d'image, puis l'import d'une seule photo.
  // Elle accompagne le visuel principal jusqu'à l'outil vidéo, qui rend mieux la forme selon l'angle de la caméra.
  function viewsBlock(product) {
    const view = (product.views || [])[0];
    const box = node("details", null, "views");
    box.append(node("summary", "Autres angles · facultatif" + (view ? " · photo importée" : "")));
    box.append(node("p", "Pour une intégration plus naturelle : donnez ce prompt et le visuel du produit à un outil d’image (ChatGPT, Gemini…), puis importez la photo obtenue. Sans elle, SceneLine utilise le visuel principal.", "muted"));
    let lang = "en";
    const text = node("textarea", null, "views-prompt");
    text.readOnly = true; text.rows = 7; text.value = product.views_prompt[lang];
    text.setAttribute("aria-label", "Prompt pour générer les angles de " + product.name);
    const bar = node("div", null, "views-bar");
    const copy = node("button", "Copier le prompt", "btn secondary small"); copy.type = "button";
    copy.onclick = async () => {
      try { await navigator.clipboard.writeText(text.value); } catch { text.select(); document.execCommand("copy"); }
      window.toast?.("Prompt copié.");
    };
    const swap = node("button", "Version française", "link"); swap.type = "button";
    swap.onclick = () => { lang = lang === "en" ? "fr" : "en"; text.value = product.views_prompt[lang];
      swap.textContent = lang === "en" ? "Version française" : "English version"; };
    bar.append(copy, swap);
    box.append(text, bar);

    if (view) {
      const item = node("figure", null, "view");
      const img = node("img"); img.src = base() + view.image; img.alt = "Planche d’angles de " + product.name; img.loading = "lazy";
      const remove = node("button", "Retirer", "link"); remove.type = "button";
      remove.onclick = async () => { await api("/products/" + product.id + "/views/0", {method: "DELETE"}); await load(); };
      item.append(img, remove);
      box.append(item);
    }
    const input = node("input"); input.type = "file"; input.accept = ".png,.jpg,.jpeg,.webp"; input.hidden = true;
    const pick = node("button", view ? "Remplacer la photo" : "Importer la photo", "btn secondary small"); pick.type = "button";
    const status = node("p", null, "status");
    pick.onclick = () => input.click();
    input.onchange = async () => {
      if (!input.files[0]) return;
      const body = new FormData();
      body.append("image", input.files[0]);
      pick.disabled = true; status.className = "status"; status.textContent = "Import…";
      try { await api("/products/" + product.id + "/views", {method: "POST", body}); await load(); }
      catch (error) { status.className = "status error"; status.textContent = error.message; pick.disabled = false; }
    };
    box.append(input, pick, status);
    return box;
  }

  function correctionForm(product) {
    const attrs = product.effective;
    const box = node("form", null, "edit-form");
    const category = node("select"); fill(category, labels.categories); category.value = attrs.category;
    const size = node("select"); fill(size, {petit: "Petit", moyen: "Moyen", grand: "Grand"}); size.value = attrs.size_class;
    const era = node("select"); fill(era, {intemporel: "Époque : intemporel", contemporain_seulement: "Époque : contemporain seulement"});
    era.value = attrs.era_constraint;
    const modes = node("div", null, "chips-check"); chipChoices(modes, labels.modes, "modes", attrs.modes);
    const exclusions = node("input"); exclusions.value = attrs.exclusions; exclusions.placeholder = "Restrictions d’usage";
    const save = node("button", "Enregistrer", "btn secondary small");
    box.append(category, size, era, modes, exclusions, save);
    box.onsubmit = async (event) => {
      event.preventDefault();
      try {
        await api("/products/" + product.id, json("PATCH", {category: category.value, size_class: size.value,
          era_constraint: era.value, exclusions: exclusions.value,
          modes: [...modes.querySelectorAll("input:checked")].map(i => i.value)}));
        await load();
      } catch (error) { get("match-status").textContent = error.message; get("match-status").classList.add("error"); }
    };
    return box;
  }

  /* ---------------------------------------------------------------- propositions */

  function meter(label, value) {
    const wrap = node("div", null, "meter");
    const bar = node("i"); const fillBar = node("b"); fillBar.style.width = value * 10 + "%"; bar.append(fillBar);
    wrap.append(node("span", label), bar, node("b", value + "/10"));
    return wrap;
  }

  function adjustForm(proposal, data, action, send) {
    const form = node("form", null, "adjust");
    const type = node("select"); fill(type, {decaler: "Décaler l’intervalle", intervalle: "Définir l’intervalle exact",
      reduire: "Réduire la taille du visuel", changer_produit: "Changer de produit", autre: "Autre demande"});
    const shift = node("input"); shift.type = "number"; shift.step = "0.5"; shift.value = "1"; shift.title = "Décalage en secondes (négatif pour reculer)";
    const scale = node("input"); scale.type = "number"; scale.min = "30"; scale.max = "95"; scale.value = "70"; scale.title = "Nouvelle taille, en % de la taille actuelle";
    const product = node("select");
    fill(product, Object.fromEntries(data.catalog.filter(p => p.id !== proposal.latest.product_id).map(p => [p.id, p.name])));
    const range = node("div"); range.style.cssText = "display:grid;gap:8px";
    const from = node("input"); from.type = "number"; from.step = "0.01"; from.value = (proposal.latest.start_ms / 1000).toFixed(2); from.title = "Début, en secondes dans la vidéo source";
    const to = node("input"); to.type = "number"; to.step = "0.01"; to.value = (proposal.latest.end_ms / 1000).toFixed(2); to.title = "Fin, en secondes dans la vidéo source";
    range.append(node("small", "Début et fin en secondes dans la vidéo source, à l’intérieur du plan"), from, to);
    const comment = node("input"); comment.placeholder = action === "reviser" ? "Motif de la modification" : "Commentaire (facultatif)"; comment.maxLength = 500;
    const go = node("button", action === "reviser" ? "Créer la nouvelle révision" : "Envoyer la demande", "btn primary small");
    const fields = {decaler: shift, intervalle: range, reduire: scale, changer_produit: product};
    const sync = () => Object.entries(fields).forEach(([key, input]) => { input.hidden = key !== type.value; });
    type.onchange = sync; sync();
    form.append(type, shift, range, scale, product, comment, go);
    form.onsubmit = (event) => {
      event.preventDefault();
      send(action, {type: type.value, shift_ms: Math.round(shift.value * 1000), scale: scale.value / 100,
        product_id: product.value, start_s: from.value, end_s: to.value}, comment.value);
    };
    return form;
  }

  function renderProposal(proposal, data) {
    const latest = proposal.latest;
    const card = node("article", null, "proposal");
    const frame = node("div", null, "frame");
    const image = node("img"); image.src = base() + latest.reference_frame; image.alt = "Surface proposée"; image.loading = "lazy";
    frame.append(image);
    if (latest.region) {
      const region = node("span", null, "region"); region.setAttribute("aria-hidden", "true");
      for (const [property, key] of [["left", "x"], ["top", "y"], ["width", "width"], ["height", "height"]]) region.style[property] = latest.region[key] * 100 + "%";
      frame.append(region);
    }
    if (latest.score) frame.append(node("span", latest.score.overall + "/10", "score"));

    const body = node("div", null, "proposal-body");
    const head = node("div", null, "headline");
    head.append(node("h3", proposal.product_name), node("span", labels.modes[latest.mode] || latest.mode, "chip accent"));
    if (proposal.latest.n > 1) head.append(node("span", "Révision " + latest.n, "chip"));
    body.append(head);
    const score = latest.score;
    body.append(node("p", score ? score.justification : "Produit choisi par le réviseur : non évalué par l’IA.", "why"));
    const place = node("p");
    place.append(seekButton(time(latest.start_ms) + " – " + time(latest.end_ms), latest.start_ms), document.createTextNode("  " + upper(latest.surface)));
    body.append(place);
    if (score) {
      const meters = node("div", null, "meters");
      meters.append(meter("Cohérence", score.narrative_coherence), meter("Discrétion", score.discretion), meter("Faisabilité", score.visual_feasibility));
      body.append(meters);
      if (score.cultural_flag) body.append(node("p", "Point culturel à valider · " + score.cultural_flag, "badge uncertain"));
      if (score.checks.length) body.append(node("p", "À vérifier · " + score.checks.join(" ; ")));
    }
    if (proposal.guard) body.append(guardBlock(proposal.guard));
    const blocked = proposal.alternatives.filter(a => a.verdict === "risque_eleve");
    if (blocked.length) {
      const place = data.context && data.context.location && data.context.location !== "Inconnu" ? data.context.location : null;
      const box = node("div", null, "blocked");
      box.append(node("p", blocked.length > 1 ? "Produits écartés par le Guard" : "Produit écarté par le Guard", "blocked-title"),
        node("p", blocked.length > 1
          ? "SceneLine ne les propose pas pour ce placement, car ils ne correspondent pas à la culture de la scène. Le réalisateur peut en décider autrement."
          : "SceneLine ne le propose pas pour ce placement, car il ne correspond pas à la culture de la scène. Le réalisateur peut en décider autrement.", "blocked-lede"));
      for (const item of blocked) {
        const product = data.catalog.find(p => p.id === item.product_id);
        const attrs = product ? product.effective : {};
        const row = node("div", null, "blocked-item");
        const top = node("div", null, "blocked-top");
        if (product) {
          const pic = node("div", null, "blocked-pic");
          const img = node("img"); img.src = base() + (product.asset || product.image); img.alt = ""; pic.append(img);
          top.append(pic);
        }
        const info = node("div", null, "blocked-info");
        const head = node("div", null, "blocked-head");
        head.append(node("b", item.name), riskPill({level: "eleve", label: "Risque élevé"}));
        info.append(head);
        const geographic = /L.action se passe/.test(item.guard_summary || "");
        const markets = (attrs.markets && attrs.markets.length ? attrs.markets : attrs.origin ? [attrs.origin] : []).join(", ");
        if (geographic && place && markets) {
          const cmp = node("div", null, "blocked-cmp");
          const side = (label, value) => { const cell = node("div"); cell.append(node("span", label), node("b", value)); return cell; };
          cmp.append(side("Lieu de l’action", place), node("span", "ne correspond pas à", "blocked-vs"), side("Marché visé par " + item.name, markets));
          info.append(cmp);
        }
        top.append(info);
        row.append(top, node("p", item.guard_summary));
        box.append(row);
      }
      body.append(box);
    }
    if (latest.scale !== 1) body.append(node("p", "Taille du visuel · " + Math.round(latest.scale * 100) + " %"));
    if (latest.outside_verified_window) body.append(node("p", "Intervalle modifié hors de la fenêtre vérifiée : à contrôler sur la vidéo.", "badge uncertain"));
    const req = latest.adjustment_request;
    if (req && req.requested_shift_ms !== undefined && req.requested_shift_ms !== req.applied_shift_ms) {
      body.append(node("p", "Décalage demandé " + req.requested_shift_ms / 1000 + " s, appliqué " + req.applied_shift_ms / 1000 + " s (limite du plan).", "badge uncertain"));
    }

    // ----- décision
    const zone = node("div", null, "decide");
    const message = node("p", null, "status error");
    const slot = node("div", null, "decide-note");
    const send = async (action, adjustment, comment) => {
      if (!reviewer.value.trim()) { message.textContent = "Indiquez d’abord votre nom, en haut de la liste."; reviewer.focus(); return; }
      message.textContent = "";
      try {
        await api("/proposals/" + proposal.id + "/decision", json("POST", {action, reviewer: reviewer.value.trim(), comment: comment || "", adjustment, revision: latest.n}));
        await load();
      } catch (error) { message.textContent = error.message; }
    };
    if (proposal.status === "en_attente") {
      const accept = node("button", "Accepter", "btn primary small"); accept.onclick = () => send("accepter");
      const refuse = node("button", "Refuser", "btn quiet small");
      const adjust = node("button", "Ajuster…", "btn secondary small");
      refuse.onclick = () => {
        const box = node("div", null, "adjust"); const reason = node("input"); reason.placeholder = "Motif (facultatif)";
        const confirm = node("button", "Confirmer le refus", "btn danger small"); confirm.onclick = () => send("refuser", null, reason.value);
        box.append(reason, confirm); slot.replaceChildren(box);
      };
      adjust.onclick = () => slot.replaceChildren(adjustForm(proposal, data, "ajuster", send));
      zone.append(accept, refuse, adjust);
    } else {
      const last = proposal.history.filter(h => h.action !== "reviser").slice(-1)[0];
      const banner = node("div", null, "state-banner " + (proposal.status === "approuvee" ? "approved" : proposal.status === "refusee" ? "refused" : "pending"));
      banner.append(document.createTextNode(proposal.status === "approuvee" ? "Approuvé" : proposal.status === "refusee" ? "Refusé" : "Ajustement demandé"));
      if (last) banner.append(node("span", "par " + last.reviewer + " · " + when(last.at)));
      zone.append(banner);
      if (proposal.status === "approuvee" || proposal.status === "refusee") {
        const revise = node("button", "Proposer une modification", "link");
        revise.onclick = () => slot.replaceChildren(adjustForm(proposal, data, "reviser", send));
        zone.append(revise);
      }
    }
    body.append(zone, slot, message);
    if (proposal.approved_revision && proposal.approved_revision !== latest.n) {
      body.append(node("p", "La révision " + proposal.approved_revision + " reste approuvée. Cette nouvelle révision doit être décidée à son tour.", "note-line"));
    }

    // ----- détails
    const details = node("details", null, "disclosure");
    details.append(node("summary", "Détails, origine et historique"));
    const inner = node("div", null, "disclosure-body trace");
    const origin = proposal.source;
    inner.append(node("h5", "Origine : analyse de la vidéo, placement n° " + (origin.rank || "—") + " (plan " + origin.shot_id + ")"));
    const where = node("p");
    where.append(seekButton(time(origin.start_ms) + " – " + time(origin.end_ms), origin.start_ms),
      document.createTextNode("  score " + origin.overall_score + "/10, vérifié sur 6 images"));
    inner.append(where,
      node("p", "Scène " + origin.scene.id + " (" + time(origin.scene.start_ms) + " – " + time(origin.scene.end_ms) + ") · " + origin.scene.summary),
      node("p", "Lieu · " + origin.scene.location + " · Époque · " + origin.scene.period + " · Ton · " + origin.scene.tone),
      node("p", "Pourquoi cette surface · " + origin.reason),
      node("p", "Raccord · " + (origin.alignment || "non évalué")),
      node("p", "Catégories compatibles · " + (origin.compatible_categories.join(", ") || "—") + " · À éviter · " + (origin.avoid_categories.join(", ") || "—")));
    if (origin.trimmed) inner.append(node("p", "Début ou fin recalés pour éviter un titre ou une coupe (fenêtre analysée " + time(origin.trimmed.from_ms) + " – " + time(origin.trimmed.to_ms) + ")."));
    if (latest.start_ms !== origin.start_ms || latest.end_ms !== origin.end_ms) inner.append(node("p", "Intervalle modifié depuis l’analyse : " + time(latest.start_ms) + " – " + time(latest.end_ms) + ".", "badge uncertain"));
    const others = proposal.alternatives.filter(a => a.product_id !== latest.product_id);
    if (others.length) {
      inner.append(node("h5", "Autres produits évalués"));
      for (const item of others) inner.append(node("p", item.name + " · " + item.overall + "/10 · " + verdictText[item.verdict] + " · " + item.justification));
    }
    if (proposal.history.length) {
      inner.append(node("h5", "Historique"));
      for (const entry of proposal.history) inner.append(node("p", "Révision " + entry.revision + " · " + actionText[entry.action] + " · " + entry.reviewer + " · " + when(entry.at) + (entry.comment ? " · « " + entry.comment + " »" : "")));
    }
    details.append(inner);
    body.append(details);
    card.append(frame, body);
    return card;
  }

  /* ---------------------------------------------------------------- affichage */

  function renderContext(context) {
    const bar = get("context-bar");
    bar.hidden = false;
    const show = (value) => !value || value === "Inconnu" ? "non déclaré" : value;
    const c = context || {};
    get("context-text").replaceChildren(node("b", "Contexte de l’œuvre"),
      document.createTextNode("  Lieu : " + show(c.location) + " · Époque : " + show(c.period) + " · Intention : " + show(c.intention)));
    const form = get("context-form");
    if (form.hidden) for (const key of ["location", "period", "intention"]) form.elements[key].value = c[key] && c[key] !== "Inconnu" ? c[key] : "";
  }

  function render(data) {
    labels = data.labels;
    window.setProject(data);
    renderContext(data.context);
    get("matching").hidden = false;
    fill(get("pf-category"), labels.categories);
    chipChoices(get("pf-modes"), labels.modes, "modes", ["objet_pose"]);
    get("catalog").replaceChildren(...data.catalog.map(p => productCard(p)));
    if (!data.catalog.length) get("catalog").append(node("p", "Aucun produit pour l’instant. Chargez le catalogue d’exemple ou ajoutez un produit.", "empty"));
    get("demo-products").hidden = data.catalog.length > 0;
    const state = data.status;
    const matchStatus = get("match-status");
    matchStatus.classList.toggle("error", state.state === "error");
    const run = get("run-match");
    if (state.state === "running") {
      matchStatus.textContent = (state.step === "produits" ? "Analyse des produits" : "Appariement") + " · " + state.done + " sur " + state.total;
      run.disabled = true; run.textContent = "Appariement en cours…";
      clearTimeout(timer); timer = setTimeout(load, 2000);
    } else {
      run.disabled = !data.catalog.length;
      run.textContent = state.state === "complete" ? "Relancer l’appariement" : "Lancer l’appariement";
      matchStatus.textContent = state.state === "error" ? state.message : state.state === "complete" ? "Appariement terminé." : "";
    }
    const showProposals = state.state === "complete" || data.proposals.length > 0 || state.state === "running";
    get("proposals-card").hidden = !showProposals;
    const list = get("proposals");
    list.replaceChildren(...data.proposals.map(p => renderProposal(p, data)));
    if (state.state === "complete" && !data.proposals.length) list.append(node("p", "Aucun placement convenable pour ce catalogue. C’est un résultat valide.", "empty"));
    get("unmatched").replaceChildren(...data.unmatched.map(item => {
      const row = node("div", null, "list-item");
      row.append(seekButton(time(item.start_ms) + " – " + time(item.end_ms), item.start_ms), node("p", upper(item.surface) + " · " + item.reason));
      return row;
    }));
    get("exclusions").replaceChildren(...data.exclusions.sort((a, b) => a.start_ms - b.start_ms).map(item => {
      const row = node("div", null, "list-item");
      row.append(node("span", time(item.start_ms), "time"), node("p", item.product_name + " · " + item.reason));
      return row;
    }));
    if (!data.exclusions.length) get("exclusions").append(node("p", "Aucune paire écartée.", "empty"));
    get("journal").replaceChildren(...data.decisions.map(d => {
      const row = node("div", null, "list-item");
      row.append(node("span", when(d.at), "muted"), node("p", d.proposal_id + " · révision " + d.revision + " · " + actionText[d.action] + " · " + d.reviewer + " · empreinte " + d.revision_digest));
      return row;
    }));
    if (!data.decisions.length) get("journal").append(node("p", "Aucune décision enregistrée.", "empty"));
    if (window.renderCompare) window.renderCompare(data, job);
  }

  async function load() {
    if (!job) return;
    try { render(await api("/project")); } catch (error) { get("match-status").textContent = error.message; }
  }

  window.loadProject = (id) => { job = id; load(); };
  window.reloadProject = () => load();
  window.hideProject = () => { job = null; clearTimeout(timer); get("matching").hidden = true; };

  const status = (text, bad) => { get("match-status").textContent = text; get("match-status").classList.toggle("error", Boolean(bad)); };
  get("demo-products").onclick = async () => {
    try { await api("/products/demo", {method: "POST"}); await load(); } catch (error) { status(error.message, true); }
  };
  get("run-match").onclick = async () => {
    try { await api("/match", {method: "POST"}); await load(); } catch (error) { status(error.message, true); }
  };
  const contextForm = get("context-form");
  get("edit-context").onclick = () => { contextForm.hidden = !contextForm.hidden; };
  get("cancel-context").onclick = () => { contextForm.hidden = true; };
  contextForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const body = Object.fromEntries(["location", "period", "intention"].map(key => [key, contextForm.elements[key].value]));
    try {
      await api("/context", json("PATCH", body));
      contextForm.hidden = true;
      await load();
      if (window.refreshAnalysis) window.refreshAnalysis();
    } catch (error) { status(error.message, true); }
  });
  const productForm = get("product-form");
  get("toggle-add").onclick = () => { productForm.hidden = !productForm.hidden; if (!productForm.hidden) productForm.scrollIntoView({block: "nearest", behavior: "smooth"}); };
  get("cancel-add").onclick = () => { productForm.hidden = true; productForm.reset(); get("pf-file").textContent = "Choisir le visuel (PNG, JPG, WebP)"; };
  get("pf-image").addEventListener("change", () => {
    const file = get("pf-image").files[0];
    get("pf-file").textContent = file ? file.name : "Choisir le visuel (PNG, JPG, WebP)";
    get("pf-image").closest(".dropzone").classList.toggle("has-file", Boolean(file));
  });
  productForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await api("/products", {method: "POST", body: new FormData(productForm)});
      productForm.reset(); productForm.hidden = true; await load();
    } catch (error) { status(error.message, true); }
  });
})();
