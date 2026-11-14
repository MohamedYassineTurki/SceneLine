// Éthique 360 : les six angles du cahier des charges, ce que SceneLine fait réellement, et où le voir.
// Chaque affirmation correspond à un comportement existant du produit ; les limites sont dites telles quelles.
(() => {
  const AXES = [
    ["createurs", "Créateurs"], ["droits", "Droits"], ["donnees", "Données"],
    ["cultures", "Cultures"], ["transparence", "Transparence"], ["planete", "Planète"]];
  const ACTIVE = {1: ["donnees", "droits", "cultures", "planete"], 2: ["createurs", "cultures", "droits", "donnees"],
    3: ["createurs", "droits", "planete"], 4: ["transparence", "createurs", "droits"]};

  // where : [libellé, étape, identifiant de l'élément]
  const DETAIL = {
    createurs: {name: "Les créateurs", q: "Qui garde la main sur l’œuvre et sur les décisions ?", status: "En place",
      does: ["Rien n’est modifié sans l’accord du producteur : Accepter, Refuser, Ajuster…, Retenir ce placement, Choisir une autre surface.",
        "Le producteur exclut des catégories de produits et des intervalles, et déclare le contexte.",
        "Chaque décision est signée, datée et liée à une révision avec empreinte, dans un journal. La vidéo originale n’est jamais modifiée."],
      where: [["Décisions et journal", 2, "proposals-card"], ["Exclusions à l’import", 1, "upload"]],
      limit: "Un outil externe régénère tout le plan : cadrage et décor peuvent changer, d’où l’aperçu illustratif. La validation finale reste humaine."},
    droits: {name: "Les droits", q: "Consentement, droits d’auteur, rémunération.", status: "Limite connue",
      does: ["Deux autorisations obligatoires à l’import : droit de traiter et modifier la vidéo, et envoi à Google Gemini.",
        "Chaque visuel de produit exige une provenance et une licence déclarées.",
        "Le relevé précise qu’il ne remplace pas les obligations légales de signalement du placement de produit."],
      where: [["Autorisations à l’import", 1, "upload"], ["Provenance du visuel", 2, "matching"]],
      limit: "Les visages modifiés par une IA posent une question de droit à l’image pour une vraie production."},
    donnees: {name: "Les données", q: "D’où viennent-elles ? Sont-elles utilisées légalement ?", status: "Limite connue",
      does: ["La détection des plans et la transcription tournent en local ; seules des images échantillonnées et le dialogue voisin partent vers Gemini, avec consentement.",
        "Les fichiers restent dans le dossier du projet.",
        "Chaque visuel de produit porte sa provenance ; les produits fictifs de démonstration sont signalés « Fictif ».",
        "Le modèle utilisé, le nombre d’appels et d’images envoyées sont affichés.",
        "Génération automatique (option) : votre clé d’API Kling reste en mémoire, jamais sur le disque, et n’est envoyée qu’à Kling. Le plan, le produit et le prompt ne partent qu’avec votre autorisation, placement par placement."],
      where: [["Consentement Gemini", 1, "upload"], ["Modèle et appels", 1, "overview-meta"], ["Envoi à Kling", 3, "kit-list"]],
      limit: "L’offre gratuite de Gemini peut servir à améliorer ses modèles : consentement explicite requis. Avec l’option Kling, les images du plan (donc des visages) sont traitées selon les conditions de Kling."},
    cultures: {name: "Cultures et langues", q: "Quelles cultures le modèle met-il en avant, ou efface-t-il ?", status: "Limite connue",
      does: ["Le Cultural Integrity Guard note chaque scène et chaque paire produit-placement (faible, moyen, élevé) selon cinq critères, avec justification.",
        "Une scène à risque élevé ne reçoit aucun placement ; la décision finale reste au réalisateur.",
        "Cohérence géographique : le lieu est déclaré, les produits portent une origine et des marchés visés. La langue parlée ne décide jamais du pays.",
        "Scènes sacrées, sensibles, traditionnelles, titres et génériques protégés."],
      where: [["Scènes protégées", 1, "guard-section"], ["Produit écarté par le Guard", 2, "proposals-card"]],
      limit: "La détection d’une scène sensible repose sur Gemini et peut se tromper : le réalisateur tranche."},
    transparence: {name: "La transparence", q: "Le public sait-il ce qui a été généré par l’IA ?", status: "En place",
      does: ["Dans le lecteur, la version éditée porte l’étiquette « Placement virtuel · [Produit] » pendant toute la durée du placement.",
        "La fiche de la comparaison et le Relevé des modifications indiquent que l’image vient d’un outil externe (« Aperçu illustratif réalisé avec un outil externe »), et listent chaque placement, produit, support, intervalle, empreinte, approbateur, date, outil, audio et avertissements. SceneLine n’a pas généré l’image.",
        "Des repères jaunes montrent où la vidéo a été modifiée."],
      where: [["Comparaison et étiquettes", 4, "cmp-player"], ["Repères sur la frise", 1, "videomap"]],
      limit: "Le relevé ne remplace pas les obligations légales de signalement."},
    planete: {name: "La planète", q: "Quel coût énergétique pour quel bénéfice ?", status: "Limite connue",
      does: ["SceneLine ne génère jamais de vidéo : la génération n’a lieu que dans un outil externe, pour les placements approuvés.",
        "Le travail lourd reste local ; un modèle plus léger traite les appels nombreux ; les résultats sont mis en cache ; un appel par intervalle.",
        "Le nombre d’appels et d’images envoyées est affiché."],
      where: [["Nombre d’appels", 1, "overview-meta"], ["Génération à la demande", 3, "stage-3"]],
      limit: "Aucune mesure d’énergie : le nombre d’appels est un indicateur indirect. Aucun chiffre en kWh ou en CO₂ n’est affiché."}
  };
  const NOPE = [
    "Il ne génère aucune vidéo : la génération se fait dans un outil externe, choisi par le créateur.",
    "Il ne mesure pas l’énergie : le nombre d’appels n’est qu’un indicateur indirect.",
    "Il ne donne pas de conseil juridique : le relevé ne remplace pas les obligations légales de signalement.",
    "Il ne décide pas à la place du créateur : toute modification passe par un accord signé."];

  // Repères d'angles, en haut de chaque étape.
  document.querySelectorAll("nav.axes[data-axes]").forEach(nav => {
    const active = ACTIVE[nav.dataset.axes] || [];
    nav.append(node("b", "Éthique 360"));
    for (const [key, label] of AXES) {
      const on = active.includes(key);
      const link = node("a", label);
      link.href = "#ethique-360/" + key;
      link.title = on ? "Actif à cette étape" : "Non sollicité à cette étape";
      if (on) { link.className = "on"; link.append(node("span", " (actif)", "sr")); }
      nav.append(link);
    }
  });

  // Page des six angles.
  const list = get("ethics-list");
  AXES.forEach(([key], index) => {
    const x = DETAIL[key];
    const row = node("article", null, "axrow");
    row.id = "ax-" + key;
    row.setAttribute("aria-labelledby", "axh-" + key);
    const side = node("div");
    const title = node("div", null, "ax-title");
    const heading = node("h2", x.name); heading.id = "axh-" + key;
    title.append(node("span", String(index + 1), "ax-n"), heading);
    const status = node("div", null, "ax-status");
    status.append(node("span", x.status, "chip " + (x.status === "En place" ? "accent" : "warn")));
    side.append(title, node("p", x.q, "q"), status);

    const body = node("div", null, "axbody");
    const section = (label, content) => { const box = node("div"); box.append(node("h4", label), content); body.append(box); };
    const ul = node("ul"); x.does.forEach(text => ul.append(node("li", text)));
    section("Ce que fait SceneLine", ul);
    const where = node("p");
    x.where.forEach(([text, step, target], i) => {
      if (i) where.append(document.createTextNode(" · "));
      const link = node("a", text + " (étape " + step + ")");
      link.href = "#";
      link.onclick = (event) => { event.preventDefault(); go(step, target); };
      where.append(link);
    });
    section("Où le voir", where);
    section("Risque et limite", node("p", x.limit));
    row.append(side, body);
    list.append(row);
  });
  get("ethics-nope").append(...NOPE.map(text => node("li", text)));

  // Ouverture de la page, éventuellement sur un angle précis.
  window.openEthics = (axis) => {
    document.querySelectorAll(".axrow.target").forEach(row => row.classList.remove("target"));
    const id = AXES.some(([key]) => key === axis) ? "ax-" + axis : null;
    go(0, id);
    if (id) get(id).classList.add("target");
  };
  document.addEventListener("click", (event) => {
    const link = event.target.closest('a[href^="#ethique-360"]');
    if (!link) return;
    event.preventDefault();
    window.openEthics((link.getAttribute("href").split("/")[1] || "").trim());
  });
  get("ethics-back").onclick = () => go(S.prev || 1);

  const start = location.hash.match(/^#ethique-360(?:\/(\w+))?/);
  if (start) window.openEthics(start[1]);
})();
