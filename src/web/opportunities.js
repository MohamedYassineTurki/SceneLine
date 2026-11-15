// Étape 1 · parcours « Recherche d'opportunités » : rapport pour un créateur sans sponsor.
// Réutilise les fonctions globales déclarées par app.js (get, node, time, upper, thumb, seekButton,
// riskPill, guardBlock, go) : ce fichier n'ajoute aucune logique de score, de région ni de navigation.
(() => {
  const filesBase = (job) => "/api/jobs/" + job + "/files/";
  const plain = (list) => list.map(name => name.replace(/_/g, " ")).join(", ");

  function kpi(label, value) {
    const box = node("div", null, "kpi");
    box.append(node("b", String(value), "kpi-value"), node("span", label, "kpi-label"));
    return box;
  }

  function advertiserBlock(item) {
    const box = node("div", null, "advertiser-block");
    box.append(node("p", "Annonceurs inscrits compatibles :", "surface-title"));
    if (item.advertiser_matches.length) {
      for (const match of item.advertiser_matches) {
        const row = node("div", null, "advertiser-match");
        const head = node("div", null, "blocked-head");
        head.append(node("b", match.name), node("span", match.provenance, "chip warn"));
        row.append(head, node("p", match.why));
        if (match.budget) row.append(node("p", "Budget déclaré : " + match.budget, "facts"));
        box.append(row);
      }
    } else {
      box.append(node("p", "Aucun annonceur inscrit ne correspond pour l’instant.", "muted"));
    }
    box.append(node("p", "Types de partenaires à démarcher :", "surface-title"));
    const list = node("ul", null, "axbody");
    (item.advertiser_fallback.length ? item.advertiser_fallback
      : ["Aucune catégorie compatible relevée pour cet emplacement."]).forEach(text => list.append(node("li", text)));
    box.append(list);
    return box;
  }

  function opportunityRow(item, jobBase) {
    const row = node("article", null, "place keep");
    row.append(thumb(jobBase + item.reference_frame, "Image de l’intervalle du plan " + item.shot_id, item, "N° " + item.rank));
    const body = node("div", null, "place-body");
    const line = node("div", null, "place-line");
    line.append(seekButton(time(item.start_ms) + " – " + time(item.end_ms), item.start_ms), riskPill(item.guard));
    line.append(node("span", item.overall_score + "/10", "score-text"));
    body.append(line, node("h3", upper(item.surface)), node("p", item.reason, "reason"));
    body.append(node("p", "Scène : " + item.scene_summary + " · " + item.scene_location + " · " + item.scene_period, "facts"));
    if (item.compatible_categories?.length) body.append(node("p", "Catégories compatibles : " + plain(item.compatible_categories)));
    if (item.avoid_categories?.length) body.append(node("p", "À éviter : " + plain(item.avoid_categories)));
    body.append(guardBlock(item.guard), advertiserBlock(item));
    row.append(body);
    return row;
  }

  function renderReport(job, data) {
    const jobBase = filesBase(job);
    const ind = data.indicators;
    get("opp-kpis").replaceChildren(
      kpi("Emplacements potentiels", ind.potential_locations),
      kpi("Catégories compatibles", ind.compatible_categories),
      kpi("Durée totale à l’écran", ind.total_screen_time_text),
      kpi("Déconseillés par le Guard", ind.guard_discouraged));
    const list = get("opp-list");
    list.replaceChildren(...data.opportunities.map(item => opportunityRow(item, jobBase)));
    if (!data.opportunities.length) list.append(node("p", "Aucun emplacement retenu pour l’instant. C’est un résultat valide : rien n’est imposé à l’œuvre.", "empty"));
    get("opp-tips").replaceChildren(...data.monetization_tips.map(text => node("li", text)));
    get("opp-disclaimer").textContent = data.disclaimer;
    get("opp-directory-notice").textContent = data.directory_notice;
    get("opp-pdf").href = "/api/jobs/" + job + "/opportunity-report.pdf";
  }

  // Appelée depuis showResults() dans app.js, uniquement quand le parcours choisi à l'import est
  // « Recherche d'opportunités ». Le parcours habituel (#candidates, #guard-section) n'est pas touché
  // sinon : cette fonction ne fait rien de plus que les masquer pendant que ce rapport est affiché.
  window.renderOpportunityReport = (job, result) => {
    const seeking = result.parcours === "recherche_opportunites";
    get("opportunity-report").hidden = !seeking;
    get("candidates-block").hidden = seeking;
    if (!seeking) return;
    get("guard-section").hidden = true;
    fetch("/api/jobs/" + job + "/opportunity-report", {cache: "no-store"})
      .then(response => response.json())
      .then(data => renderReport(job, data))
      .catch(() => get("opp-list").replaceChildren(node("p", "Rapport indisponible pour l’instant.", "empty")));
  };

  get("opp-integrate").onclick = () => go(2);
})();
