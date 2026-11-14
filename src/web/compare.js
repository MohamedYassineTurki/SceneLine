// Étape 3 · kit de génération. Étape 4 · intégration du résultat et comparaison.
// Utilise get, node, time, upper, S, go de app.js.
(() => {
  let job = null;
  let selected = null;
  let mode = "original";
  const video = get("cmp-video");
  const baseUrl = () => "/api/jobs/" + job + "/files/";
  const ms = (value) => time(value);
  const when = (iso) => new Date(iso).toLocaleString("fr-FR", {dateStyle: "medium", timeStyle: "short"});

  async function call(path, options) {
    const response = await fetch("/api/jobs/" + job + path, options);
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw Error(body.message || "Requête impossible.");
    return body;
  }

  const approvedKit = (proposal, data) => {
    const kit = data.kits[proposal.id];
    return kit && kit.revision === proposal.approved_revision ? kit : null;
  };
  const head = (proposal, extra) => {
    const row = node("div", null, "head");
    const left = node("div");
    left.append(node("h3", proposal.product_name));
    const sub = node("p", ms(proposal.latest.start_ms) + " – " + ms(proposal.latest.end_ms) + " · " + upper(proposal.latest.surface) + " · révision " + proposal.approved_revision, "muted");
    left.append(sub);
    row.append(left);
    if (extra) row.append(extra);
    return row;
  };
  const io = (input, output) => {
    const line = node("p", null, "flow-line");
    line.append(node("span", input), node("i", null, "flow-arrow"), node("span", output));
    return line;
  };

  /* ---------------------------------------------------------------- étape 3 : kit */

  function copyButton(getText) {
    const button = node("button", "Copier", "btn quiet small");
    button.type = "button";
    button.onclick = async () => {
      const text = getText();
      try { await navigator.clipboard.writeText(text); button.textContent = "Copié"; }
      catch { button.textContent = "Sélectionnez le texte"; }
      setTimeout(() => { button.textContent = "Copier"; }, 1800);
    };
    return button;
  }

  /* Contenu du kit : commun aux deux façons de produire la vidéo. */
  function kitMedia(kit) {
    const base = baseUrl();
    const row = node("div", null, "media-row");
    const fig = (child, caption) => { const f = node("figure"); f.append(child, node("figcaption", caption)); return f; };
    const clip = node("video"); clip.src = base + kit.clip; clip.controls = true; clip.preload = "metadata"; clip.muted = true;
    const img = (src, alt, cls) => { const i = node("img", null, cls); i.src = base + src; i.alt = alt; i.loading = "lazy"; return i; };
    row.append(fig(clip, "Scène · " + kit.seconds + " s, sans audio"), fig(img(kit.frames.debut, "Première image"), "Première image"),
      fig(img(kit.frames.fin, "Dernière image"), "Dernière image"), fig(img(kit.asset, "Asset produit", "asset"), "Asset du produit"));
    return row;
  }

  const section = (...children) => { const s = node("section", null, "nsec"); s.append(...children); return s; };

  /* Option manuelle : prompt à copier, kit à télécharger, import à l'étape 4. */
  function manualPanel(kit, proposal) {
    const box = node("div", null, "numpanel");
    box.setAttribute("role", "group"); box.setAttribute("aria-label", "Génération manuelle");
    const panel = node("div", null, "prompt-panel");
    const bar = node("div", null, "panel-bar");
    const texts = {en: kit.prompt_en, fr: kit.prompt_fr, neg: kit.negative_en};
    const area = node("textarea"); area.readOnly = true; area.value = texts.en; area.setAttribute("aria-label", "Prompt");
    const tabs = node("div", null, "segmented"); tabs.setAttribute("role", "radiogroup");
    const name = "pt-" + proposal.id;
    for (const [value, label] of [["en", "Anglais"], ["fr", "Français"], ["neg", "Prompt négatif"]]) {
      const l = node("label"); const input = node("input"); input.type = "radio"; input.name = name; input.value = value; input.checked = value === "en";
      input.onchange = () => { area.value = texts[value]; area.rows = value === "neg" ? 4 : 12; };
      l.append(input, node("span", label)); tabs.append(l);
    }
    area.rows = 12;
    const copy = node("button", "Copier", "btn secondary");
    copy.type = "button";
    copy.onclick = async () => {
      try { await navigator.clipboard.writeText(area.value); copy.textContent = "Copié"; }
      catch { copy.textContent = "Sélectionnez le texte"; }
      setTimeout(() => { copy.textContent = "Copier"; }, 1800);
    };
    bar.append(tabs, copy);
    panel.append(bar, area, node("p", "Prompt rédigé à partir de trois images du plan (" + kit.description_model + "), empreinte " + kit.prompt_sha + ". Les outils comprennent en général mieux l’anglais.", "muted"));

    const settings = node("details", null, "disclosure flat");
    settings.append(node("summary", "Réglages conseillés"));
    const list = node("ul", null, "settings");
    for (const line of kit.settings) list.append(node("li", line));
    const inner = node("div", null, "disclosure-body"); inner.append(list); settings.append(inner);

    const zip = node("a", "Télécharger le kit (ZIP)", "btn primary"); zip.href = baseUrl() + kit.zip; zip.download = kit.zip;
    const foot = node("div", null, "row-between");
    foot.append(node("p", "Quand la vidéo est prête, importez-la à l’étape 4 : SceneLine la replace dans la vidéo d’origine.", "ink-note"), zip);
    box.append(section(panel), section(settings), section(foot));
    return box;
  }

  /* ---------------------------------------------------------------- option automatique : API de Kling AI */

  const gen = {};       // choix de l'interface conservés d'un affichage à l'autre (jamais la clé d'API)
  const timers = {};
  const genState = (id) => gen[id] || (gen[id] = {choice: "auto", model: "kling-4.0", mode: "video", base: "", consent: false});
  async function provider(path, options) {
    const response = await fetch("/api/providers/kling" + path, options);
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw Error(body.message || "Requête impossible.");
    return body;
  }
  const jsonBody = (method, body) => ({method, headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
  const ACTIVE = ["submitting", "processing", "downloading", "integrating"];
  const PHASES = [["submitting", "Envoi à Kling"], ["processing", "Génération chez Kling"], ["downloading", "Téléchargement de la vidéo"], ["integrating", "Intégration dans la vidéo d’origine"]];
  const alertBox = (title, text) => { const a = node("div", null, "alert"); a.setAttribute("role", "alert"); a.append(node("b", title + " "), document.createTextNode(text)); return a; };

  function autoPanel(proposal, kit) {
    const state = genState(proposal.id);
    clearTimeout(timers[proposal.id]);
    const box = node("div", null, "numpanel");
    box.setAttribute("role", "group"); box.setAttribute("aria-label", "Génération automatique avec Kling AI");
    const connection = node("section", null, "nsec"), options = node("section", null, "nsec"),
      sending = node("section", null, "nsec"), run = node("section", null, "nsec");
    box.append(connection, options, sending, run);
    let account = {connected: false};
    let generation = {state: "idle"};
    const active = () => ACTIVE.includes(generation.state);
    const heading = (text) => node("h4", text, "nh");

    const paintConnection = () => {
      connection.replaceChildren(heading("1 · Votre compte Kling AI"));
      if (account.connected) {
        const row = node("div", null, "gen-row");
        const off = node("button", "Déconnecter", "link"); off.type = "button";
        off.onclick = async () => { account = await provider("/key", {method: "DELETE"}); paint(); window.toast("Compte Kling AI déconnecté. La clé a été oubliée."); };
        row.append(node("span", "Connecté à Kling AI", "chip accent live"), node("span", "clé se terminant par " + account.hint, "muted"), off);
        connection.append(row);
        return;
      }
      const form = node("form", null, "field");
      const label = node("label", "Clé d’API Kling"); label.htmlFor = "kkey-" + proposal.id;
      const line = node("div", null, "gen-connect");
      const input = node("input"); input.type = "password"; input.id = "kkey-" + proposal.id; input.autocomplete = "off"; input.spellcheck = false; input.required = true;
      input.setAttribute("aria-describedby", "key-help-" + proposal.id);
      const submit = node("button", "Vérifier et connecter", "btn secondary"); submit.type = "submit";
      const message = node("p", null, "status");
      line.append(input, submit);
      form.onsubmit = async (event) => {
        event.preventDefault();
        submit.disabled = true; submit.classList.add("busy"); submit.textContent = "Vérification…"; message.className = "status"; message.textContent = "";
        try {
          account = await provider("/key", jsonBody("POST", {api_key: input.value}));
          input.value = "";
          paint();
          window.toast(account.verified ? "Compte Kling AI connecté." : "Clé enregistrée. Kling ne l’a pas confirmée : elle sera testée à la première génération.");
        } catch (error) {
          message.className = "status error"; message.textContent = error.message;
          submit.disabled = false; submit.classList.remove("busy"); submit.textContent = "Vérifier et connecter"; input.focus();
        }
      };
      const help = node("p", "Créez la clé dans la console développeur de Kling AI. Elle reste dans la mémoire de SceneLine tant que le programme tourne : elle n’est jamais enregistrée sur le disque et n’est envoyée qu’à Kling.", "muted");
      help.id = "key-help-" + proposal.id;
      form.append(label, line, message, help);
      connection.append(form);
    };

    const paintOptions = () => {
      options.replaceChildren(heading("2 · Réglages"));
      const model = node("label", null, "field"); model.append(node("span", "Modèle"));
      const select = node("select");
      for (const [value, text] of Object.entries(account.models || {"kling-4.0": "Kling 4.0"})) {
        const option = node("option", value === "kling-4.0" ? text + " (recommandé)" : text); option.value = value; select.append(option);
      }
      select.value = state.model;
      select.onchange = () => { state.model = select.value; };
      model.append(select);
      options.append(model);
      const f = node("label", null, "field"); f.append(node("span", "Adresse publique de SceneLine (https)"));
      const input = node("input"); input.type = "text"; input.placeholder = "Ex. https://mon-tunnel.example.org"; input.value = state.base; input.spellcheck = false; input.inputMode = "url";
      input.oninput = () => { state.base = input.value.trim(); updateButton(); };
      f.append(input, node("span", "Kling ne télécharge un plan que depuis une adresse publique. Lancez un tunnel (ngrok, Cloudflare Tunnel…) vers http://localhost:8002 et collez son adresse https. Tant que le tunnel est ouvert, SceneLine ne répond qu’à un lien aléatoire qui ne sert que ce plan, et seulement pendant la génération.", "muted"));
      options.append(f);
    };

    let button, why;
    const reason = () => !account.connected ? "Connectez d’abord votre compte Kling AI."
      : !state.consent ? "Cochez l’autorisation d’envoi pour continuer."
      : !/^https:\/\/[^\s/]+/.test(state.base) ? "Indiquez l’adresse publique (https) de SceneLine." : "";
    const updateButton = () => {
      if (!button) return;
      const text = reason();
      button.disabled = Boolean(text) || active();
      why.textContent = text;
    };
    const launch = async () => {
      button.disabled = true;
      try {
        generation = await call("/proposals/" + proposal.id + "/generate", jsonBody("POST", {model: state.model, mode: state.mode, public_base: state.base, consent: state.consent}));
        paintRun(); paintSending(); poll();
      } catch (error) { generation = {state: "error", message: error.message}; paintRun(); paintSending(); }
    };
    const paintSending = () => {
      sending.replaceChildren(heading("3 · Ce qui sera envoyé à Kling"));
      const list = node("ul", null, "sendlist"); list.setAttribute("aria-label", "Éléments envoyés à Kling");
      for (const line of ["Le prompt du kit, en anglais", "L’image du produit, sur fond blanc",
        "Le plan vidéo, sans audio, par un lien temporaire"]) list.append(node("li", line));
      sending.append(list, node("p", "Chaque génération consomme des crédits de votre compte Kling. Le plan montre des visages : Kling les traite selon ses propres conditions.", "ink-note"));
      const consent = node("label", null, "check-row");
      const check = node("input"); check.type = "checkbox"; check.checked = state.consent; check.disabled = active();
      check.onchange = () => { state.consent = check.checked; updateButton(); };
      const text = node("span", "J’autorise l’envoi de ces éléments à Kling AI pour ce placement.");
      text.append(node("span", "Angles Droits et Données · rien ne part sans cette autorisation", "cap"));
      consent.append(check, text);
      sending.append(consent);
      if (generation.state === "idle") {
        const row = node("div", null, "gen-row");
        button = node("button", "Générer avec Kling et intégrer", "btn primary"); button.type = "button"; button.onclick = launch;
        why = node("p", null, "status"); why.setAttribute("role", "status");
        row.append(button, why);
        sending.append(row);
        updateButton();
      } else { button = null; }
    };

    const paintRun = () => {
      run.replaceChildren();
      run.hidden = generation.state === "idle";
      if (generation.state === "idle") return;
      run.append(heading("4 · Suivi"));
      const at = PHASES.findIndex(([key]) => key === generation.state);
      if (active() || generation.state === "done" || generation.task_id) {
        const list = node("ol", null, "progress-list"); list.setAttribute("aria-label", "Étapes du suivi");
        PHASES.forEach(([, label], i) => list.append(node("li", label, generation.state === "done" || (at >= 0 && i < at) || (at < 0 && i < 2 && generation.task_id) ? "done" : i === at ? "active" : "")));
        run.append(list);
      }
      if (active() && generation.message) { const live = node("p", generation.message, "muted"); live.setAttribute("role", "status"); live.setAttribute("aria-live", "polite"); run.append(live); }
      if (generation.state === "done") {
        const banner = node("div", null, "state-banner approved");
        banner.setAttribute("role", "status");
        const next = node("button", "Voir la comparaison", "btn primary"); next.type = "button";
        next.onclick = () => { go(4); setTimeout(() => get("cmp-player").scrollIntoView({block: "start", behavior: "smooth"}), 300); };
        banner.append(node("span", "Vidéo générée par Kling et intégrée", "lead"), next);
        run.append(banner);
        const first = ((generation.render && generation.render.warnings) || [])[0];
        if (first) run.append(node("p", first, "badge uncertain"));
        const again = node("button", "Générer à nouveau", "link"); again.type = "button";
        again.onclick = () => { generation = {state: "idle"}; paintRun(); paintSending(); };
        run.append(again);
      }
      if (generation.state === "error") {
        const message = generation.message || "La génération a échoué.";
        const cut = message.match(/^(Le suivi a été interrompu[^.]*\.)\s*(.*)$/);
        const alert = cut ? alertBox(cut[1], cut[2]) : alertBox("Erreur :", message);
        const act = node("button", generation.resumable ? "Reprendre le suivi chez Kling" : "Relancer la génération", "btn primary"); act.type = "button";
        act.onclick = generation.resumable
          ? async () => { try { generation = await call("/proposals/" + proposal.id + "/generation/resume", {method: "POST"}); paintRun(); paintSending(); poll(); } catch (error) { generation = {state: "error", message: error.message}; paintRun(); } }
          : () => { generation = {state: "idle"}; paintRun(); paintSending(); updateButton(); };
        alert.append(act);
        run.append(alert);
      }
    };

    const paint = () => { paintConnection(); paintOptions(); paintSending(); paintRun(); };
    const poll = () => {
      clearTimeout(timers[proposal.id]);
      timers[proposal.id] = setTimeout(async () => {
        try { generation = await call("/proposals/" + proposal.id + "/generation"); } catch { return; }
        if (generation.state === "done") { await window.reloadProject(); return; }
        paintRun(); paintSending();
        if (active()) poll();
      }, 2500);
    };
    (async () => {
      try { [account, generation] = await Promise.all([provider(""), call("/proposals/" + proposal.id + "/generation")]); } catch { /* panneau affiché déconnecté */ }
      paint();
      if (active()) poll();
    })();
    paint();
    return box;
  }

  function optionCards(proposal, show) {
    const state = genState(proposal.id);
    const wrap = node("div", null, "option-cards"); wrap.setAttribute("role", "radiogroup"); wrap.setAttribute("aria-label", "Comment produire la vidéo");
    for (const [value, title, text, tag, tagClass] of [
      ["auto", "Automatique avec Kling AI", "Connectez votre clé d’API : SceneLine envoie le plan, le produit et le prompt, récupère la vidéo et l’intègre à votre place.", "Automatisé", "chip accent"],
      ["manual", "Manuelle, avec l’outil de votre choix", "Copiez le prompt ou téléchargez le kit, générez la vidéo dans Google Flow, Kling, Runway…, puis importez-la à l’étape 4.", "Sans clé d’API", "chip out"]]) {
      const label = node("label", null, "option-card");
      const input = node("input"); input.type = "radio"; input.name = "gen-" + proposal.id; input.value = value; input.checked = state.choice === value;
      input.onchange = () => { state.choice = value; show(); if (lastData) step3Gate(lastData); };
      const top = node("span", null, "oc-top"); top.append(node("span", tag, tagClass), node("span", null, "oc-ck"));
      label.append(input, top, node("span", title, "oc-title"), node("span", text, "oc-text"));
      wrap.append(label);
    }
    return wrap;
  }

  let lastData = null;
  const STEP3_WHY = "Générez d’abord la vidéo avec Kling, ou choisissez la méthode manuelle et préparez le kit.";
  // « Continuer · Intégration » : une vidéo est déjà intégrée, ou le kit est prêt pour la méthode manuelle.
  function step3Gate(data) {
    const button = get("go-integration"), note = get("step3-why");
    const ok = data.proposals.filter(p => p.status === "approuvee").some(p => {
      const record = data.renders[p.id];
      return (record && record.revision === p.approved_revision) || (approvedKit(p, data) && genState(p.id).choice === "manual");
    });
    button.disabled = !ok;
    button.title = ok ? "" : STEP3_WHY;
    note.textContent = ok ? "" : STEP3_WHY;
  }

  function kitCard(proposal, data) {
    const kit = approvedKit(proposal, data);
    const card = node("article", null, "step-card");
    const build = node("button", kit ? "Régénérer le kit" : "Préparer le kit de génération", kit ? "link" : "btn primary");
    build.type = "button";
    const message = node("p", null, "status");
    build.onclick = async () => {
      build.disabled = true; message.classList.remove("error");
      message.textContent = "Préparation en cours : découpe du plan, images et description (environ 15 s)…";
      try { await call("/proposals/" + proposal.id + "/kit", {method: "POST"}); await window.reloadProject(); }
      catch (error) { message.textContent = error.message; message.classList.add("error"); build.disabled = false; }
    };
    card.append(head(proposal, kit ? null : build),
      io("Placement approuvé et plan source", "Scène + asset + prompt, prêts pour la génération"));
    const stale = data.kits[proposal.id] && !kit;
    if (stale) card.append(node("p", "Le kit existant correspond à la révision " + data.kits[proposal.id].revision + ". Préparez-en un nouveau.", "badge uncertain"));
    else if (!kit) card.append(node("p", "Le kit n’existe pas encore. Il contient le clip source, la première et la dernière image, l’asset du produit et le prompt.", "muted"));
    card.append(message);
    if (kit) {
      const place = node("div", null, "gen-choice");
      const show = () => place.replaceChildren(genState(proposal.id).choice === "auto" ? autoPanel(proposal, kit) : manualPanel(kit, proposal));
      const content = node("div", null, "stack-sm");
      content.append(node("h3", "Contenu du kit", "sub-title"), kitMedia(kit));
      const choose = node("div", null, "stack-sm");
      choose.append(node("h3", "Comment produire la vidéo ?"), optionCards(proposal, show));
      card.append(content, node("hr", null, "hr"), choose, place, build);
      show();
    }
    return card;
  }

  /* ---------------------------------------------------------------- étape 4 : intégration */

  function integrationCard(proposal, data) {
    const record = data.renders[proposal.id];
    const current = record && record.revision === proposal.approved_revision;
    const kit = approvedKit(proposal, data);
    const card = node("article", null, "step-card");
    const status = node("span", current ? "Résultat intégré" : "En attente du résultat", "chip " + (current ? "ok" : "warn"));
    card.append(head(proposal, status),
      io("La vidéo produite par l’outil de génération", "Extrait avec l’original et son audio, plus la comparaison"));
    if (!kit && !current) {
      const hint = node("p", null, "note-line");
      hint.append(document.createTextNode("Conseil : préparez d’abord le kit à l’étape 3. "));
      const back = node("button", "Aller au kit", "link"); back.type = "button"; back.onclick = () => go(3);
      hint.append(back); card.append(hint);
    }
    if (current) {
      for (const warning of record.warnings) card.append(node("p", warning, "badge uncertain"));
      if (record.kit) card.append(node("p", "Lié au kit du " + when(record.kit.created_at) + " (empreinte du prompt " + record.kit.prompt_sha + ").", "note-line"));
      const actions = node("div", null, "decide");
      const open = node("button", "Voir la comparaison", "btn secondary small"); open.type = "button";
      open.onclick = () => { select(proposal.id, data); get("cmp-player").scrollIntoView({block: "start", behavior: "smooth"}); };
      actions.append(open);
      card.append(actions);
      const options = node("details", null, "disclosure");
      options.append(node("summary", "Options de l’extrait"));
      const inner = node("div", null, "disclosure-body");
      const lead = node("select"); lead.title = "Contexte conservé avant le placement";
      lead.append(...[["0", "L’extrait commence dès la première image du placement"], ["3000", "L’extrait garde 3 s d’original avant le placement"]]
        .map(([value, text]) => { const o = node("option", text); o.value = value; o.selected = value === String(record.provenance.lead_ms || 0); return o; }));
      const redo = node("button", "Réassembler l’extrait", "btn quiet small"); redo.type = "button";
      redo.onclick = async () => {
        redo.disabled = true;
        try {
          await call("/proposals/" + proposal.id + "/reassemble", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({lead_ms: Number(lead.value)})});
          selected = proposal.id; await window.reloadProject();
        } catch (error) { inner.append(node("p", error.message, "badge reject")); }
        redo.disabled = false;
      };
      inner.append(lead, redo); options.append(inner);
      card.append(options);
    } else if (record) {
      card.append(node("p", "Un résultat existe pour la révision " + record.revision + ". Importez-en un pour la révision " + proposal.approved_revision + ".", "badge uncertain"));
    }

    const form = node("form", null, "import-grid");
    const tool = node("input"); tool.placeholder = "Outil utilisé, par exemple Google Flow"; tool.maxLength = 120; tool.required = true; tool.setAttribute("aria-label", "Outil de génération utilisé");
    const note = node("input"); note.placeholder = "Note : modèle, nombre d’essais (facultatif)"; note.maxLength = 300; note.setAttribute("aria-label", "Note de provenance");
    const fit = node("select"); fit.setAttribute("aria-label", "Cadrage si le format diffère de la source");
    fit.append(...[["contain", "Cadrage : tout le plan, avec bandes noires"], ["cover-center", "Cadrage : remplir l’image, recadrage centré"], ["cover", "Cadrage : remplir l’image, recadrage vers le bas"]]
      .map(([value, text]) => { const o = node("option", text); o.value = value; return o; }));
    const drop = node("label", null, "dropzone compact");
    const dropLabel = node("strong", "Choisir la vidéo produite (MP4, MOV, WebM)");
    const file = node("input"); file.type = "file"; file.accept = "video/mp4,video/quicktime,video/webm,.mkv"; file.required = true;
    file.onchange = () => { dropLabel.textContent = file.files[0] ? file.files[0].name : "Choisir la vidéo produite (MP4, MOV, WebM)"; drop.classList.toggle("has-file", Boolean(file.files[0])); };
    drop.append(dropLabel, file);
    const submit = node("button", current ? "Remplacer le résultat" : "Intégrer le résultat", "btn primary");
    const message = node("p", null, "status");
    const foot = node("div", null, "form-foot"); foot.append(message, submit);
    form.append(tool, note, fit, drop, foot);
    form.onsubmit = async (event) => {
      event.preventDefault();
      submit.disabled = true; message.classList.remove("error");
      message.textContent = "Assemblage en cours (quelques secondes)…";
      const body = new FormData();
      body.set("video", file.files[0]); body.set("tool", tool.value); body.set("note", note.value);
      body.set("fit", fit.value.startsWith("cover") ? "cover" : "contain"); body.set("anchor", fit.value === "cover-center" ? "0.5" : "0.7");
      try {
        await call("/proposals/" + proposal.id + "/external", {method: "POST", body});
        selected = proposal.id; await window.reloadProject();
        get("cmp-player").scrollIntoView({block: "start", behavior: "smooth"});
      } catch (error) { message.textContent = error.message; message.classList.add("error"); }
      submit.disabled = false;
    };
    if (current) {
      const replace = node("details", null, "disclosure");
      replace.append(node("summary", "Remplacer par un autre résultat"));
      const inner = node("div", null, "disclosure-body"); inner.append(form); replace.append(inner);
      card.append(replace);
    } else card.append(form);
    return card;
  }

  /* ---------------------------------------------------------------- comparaison */

  function setMode(next, data, keepTime = true) {
    const record = data.renders[selected];
    if (!record) return;
    const time0 = keepTime ? video.currentTime : 0;
    const playing = !video.paused;
    mode = next;
    const wanted = baseUrl() + (mode === "edited" ? record.edited : record.original);
    if (!video.src.endsWith(wanted)) {
      video.src = wanted;
      video.addEventListener("loadedmetadata", () => {
        video.currentTime = Math.min(time0, video.duration || time0);
        if (playing) video.play().catch(() => {});
      }, {once: true});
    }
    for (const input of document.querySelectorAll("input[name=cmp-mode]")) input.checked = input.value === mode;
    paintTimeline(data);
  }

  function paintTimeline(data) {
    const record = data.renders[selected];
    const track = get("cmp-track");
    track.replaceChildren();
    const span = record.excerpt.end_ms - record.excerpt.start_ms;
    const caption = get("cmp-caption");
    if (mode === "original") {
      caption.textContent = "Version originale : aucune modification. L’intervalle approuvé est " + ms(record.source_interval.start_ms) + " – " + ms(record.source_interval.end_ms) + " dans la vidéo source.";
      get("cmp-now").hidden = true;
      return;
    }
    const marker = node("button", null, "marker");
    marker.type = "button";
    marker.style.left = record.marker.start_ms / span * 100 + "%";
    marker.style.width = (record.marker.end_ms - record.marker.start_ms) / span * 100 + "%";
    const text = "Placement virtuel : " + record.product_name + ", de " + ms(record.marker.start_ms) + " à " + ms(record.marker.end_ms) + " dans l’extrait";
    marker.setAttribute("aria-label", text + ". Entrée pour y aller.");
    marker.title = text;
    marker.onclick = () => { video.currentTime = record.marker.start_ms / 1000; video.play().catch(() => {}); };
    track.append(marker, node("span", null, "playhead"));
    caption.textContent = "Repère jaune : " + text + ". Intervalle source " + ms(record.source_interval.start_ms) + " – " + ms(record.source_interval.end_ms) + ".";
  }

  function fiche(data) {
    const record = data.renders[selected];
    const row = (key, value, wide) => { const p = node("p", null, wide ? "wide" : ""); p.append(node("b", key), document.createTextNode(value)); return p; };
    get("cmp-fiche").replaceChildren(
      row("Produit", record.product_name + " · " + (data.labels.modes[record.mode] || record.mode)),
      row("Support", upper(record.surface)),
      row("Intervalle dans la vidéo source", ms(record.source_interval.start_ms) + " – " + ms(record.source_interval.end_ms)),
      row("Révision approuvée", record.revision + " · empreinte " + record.revision_digest),
      row("Approuvée par", record.approved_by + " · " + when(record.approved_at)),
      row("Audio", record.audio),
      row("Provenance de l’image", data.external_label + " : " + record.provenance.tool + (record.provenance.note ? " (" + record.provenance.note + ")" : "") + ". Non produit par SceneLine.", true),
      row("Vidéo originale", "Conservée, non modifiée"));
  }

  function select(id, data) {
    selected = id;
    get("cmp-player").hidden = false;
    fiche(data);
    setMode(mode, data, false);
    get("cmp-select").value = id;
    get("cmp-log").href = "/api/jobs/" + job + "/modifications.json";
  }

  function render(data, id) {
    job = id;
    lastData = data;
    const approved = data.proposals.filter(p => p.status === "approuvee");
    const kitList = get("kit-list");
    kitList.replaceChildren(...approved.map(p => kitCard(p, data)));
    if (!approved.length) kitList.append(node("p", "Approuvez un placement à l’étape 2 pour préparer son kit.", "empty"));
    step3Gate(data);
    const list = get("integrate-list");
    list.replaceChildren(...approved.map(p => integrationCard(p, data)));
    if (!approved.length) list.append(node("p", "Approuvez un placement à l’étape 2 pour pouvoir intégrer un résultat.", "empty"));

    const ready = Object.keys(data.renders);
    const picker = get("cmp-select");
    picker.replaceChildren(...ready.map(pid => {
      const option = node("option", data.renders[pid].product_name + " · " + ms(data.renders[pid].source_interval.start_ms));
      option.value = pid;
      return option;
    }));
    get("cmp-player").hidden = !ready.length;
    if (ready.length) {
      if (!selected || !data.renders[selected]) selected = ready[0];
      picker.value = selected;
      picker.onchange = () => { mode = "original"; select(picker.value, data); };
      for (const input of document.querySelectorAll("input[name=cmp-mode]")) input.onchange = () => setMode(input.value, data);
      select(selected, data);
      video.ontimeupdate = () => {
        const record = data.renders[selected];
        if (!record) return;
        const span = record.excerpt.end_ms - record.excerpt.start_ms;
        const playhead = get("cmp-track").querySelector(".playhead");
        if (playhead) playhead.style.left = video.currentTime * 1000 / span * 100 + "%";
        const inside = mode === "edited" && video.currentTime * 1000 >= record.marker.start_ms && video.currentTime * 1000 <= record.marker.end_ms;
        get("cmp-now").hidden = !inside;
        get("cmp-now").textContent = "Placement virtuel · " + record.product_name;
      };
    }
  }

  window.renderCompare = render;
})();
