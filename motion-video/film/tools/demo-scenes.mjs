// Contenu des quatre étapes de la démo. Temps en secondes, locaux à chaque scène.
// Le rythme vient de la voix off : T[id].S[k] = début de la phrase k (0 = « Étape n : … », 1 à 3 = les trois légendes),
// T[id].D[k] = sa durée, T[id].dur = durée de la scène. Calculé par build-demo.mjs à partir de assets/vo/<id>-<k>.wav.
// Les valeurs affichées sont celles du vrai projet de démo (voir SOURCES.md) : rien n'est inventé.
const TK = `<svg viewBox="0 0 20 20"><path d="M4 10.5l4 4 8-9" fill="none" stroke="#fff" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
const chk = (id) => `<span class="chk" id="${id}"><span class="tick">${TK}</span></span>`;

// Positions du curseur : coordonnées de l'image (1920 × 1080).
const cursorPath = (id, pts) => pts.map(([t, x, y, click]) =>
  `tl.to("#${id}-cur", { x: ${x}, y: ${y}, duration: 0.45, ease: "power2.inOut" }, ${t});` +
  (click ? `\n        tl.to("#${id}-cur", { scale: 0.82, duration: 0.08, yoyo: true, repeat: 1 }, ${t + 0.45});` : "")
).join("\n        ");

export function scenes(T) {
const f = (x) => Math.round(x * 100) / 100;
// ───────────────────────── 1 · Analyse ─────────────────────────
const SEG = [["r", 1.2], ["r", 3.4], ["g", 12.6], ["g", 15.4], ["g", 15.8], ["a", 3.4], ["a", 17.6], ["g", 10.8], ["g", 8.2], ["r", 4.6], ["r", 7.0]];
const MKS = [4, 12.5, 16.5, 21.5, 25.5, 28, 32, 74.5, 77];
const s4a = {
  id: "s4a", file: "s4a-analyse.html", step: 1, duration: T.s4a.dur,
  lit: ["droits", "donnees", "cultures", "planete"],
  cursor: true,
  css: `
#s4a-app .crow { margin-top: 18px; display: flex; gap: 18px; align-items: flex-start; padding: 18px 22px; border: 1px solid #e3e3e8; border-radius: 14px; font-size: 22px; line-height: 1.4; }
#s4a-app .crow .cap { display: block; margin-top: 4px; font-size: 18px; color: #0066cc; font-weight: 500; }
#s4a-hl { margin-top: 34px; font-size: 36px; font-weight: 600; line-height: 1.25; letter-spacing: -0.02em; }
#s4a-map { margin-top: 26px; }
#s4a-mks { position: relative; height: 34px; }
.s4a-mk { position: absolute; top: 0; width: 22px; height: 28px; border-radius: 4px; background: #ffcc00; border: 2px solid #8a5100; box-sizing: border-box; }
#s4a-bar { display: flex; gap: 4px; height: 26px; margin-top: 6px; }
#s4a-bar div { height: 100%; border-radius: 4px; transform-origin: left center; }
#s4a-bar .g { background: #23873f; } #s4a-bar .a { background: #d17f00; } #s4a-bar .r { background: #b81d22; }
#s4a-ticks { display: flex; justify-content: space-between; margin-top: 8px; font-size: 18px; color: #6e6e73; }
#s4a-leg { display: flex; gap: 26px; margin-top: 18px; font-size: 19px; color: #1d1d1f; }
#s4a-leg span { display: inline-flex; align-items: center; gap: 8px; }
#s4a-leg i { display: inline-block; width: 16px; height: 16px; border-radius: 3px; }
#s4a-met { margin-top: 16px; font-size: 19px; color: #5b5b61; }`,
  app: `
            <h1>Analyser la vidéo</h1>
            <div class="lede"><b style="color:#0058b0">Exemple de test</b> · série française, épisode « BALTRINGUE #1 »</div>
            <div class="crow">${chk("s4a-c1")}<span>Je suis autorisé(e) à traiter et modifier cette vidéo (droits d’auteur, droit à l’image et à la voix).<span class="cap">Angle Droits</span></span></div>
            <div class="crow">${chk("s4a-c2")}<span>J’accepte l’envoi d’images échantillonnées et du dialogue voisin à Google Gemini.<span class="cap">Angle Données · le calcul des plans et la transcription restent locaux</span></span></div>
            <p id="s4a-hl">SceneLine a compris 11 scènes dans 48 plans. Il propose 9 placements et protège 4 scènes.</p>
            <div id="s4a-map">
              <div id="s4a-mks">${MKS.map((p, i) => `<div class="s4a-mk" id="s4a-mk${i}" style="left:${p}%"></div>`).join("")}</div>
              <div id="s4a-bar">${SEG.map(([c, w], i) => `<div class="${c}" id="s4a-sg${i}" style="width:${w}%"></div>`).join("")}</div>
              <div id="s4a-ticks"><span>00:00</span><span>04:38</span></div>
              <div id="s4a-leg"><span><i style="background:#b81d22"></i>Scène protégée (4)</span><span><i style="background:#d17f00"></i>À vérifier (2)</span><span><i style="background:#23873f"></i>Sans risque relevé (5)</span><span><i style="background:#ffcc00;border:2px solid #8a5100;box-sizing:border-box"></i>Placement proposé (9)</span></div>
              <div id="s4a-met">Plans et transcription : calcul local · Gemini : 57 appels · 381 images envoyées</div>
            </div>`,
  callouts: [[T.s4a.S[1], "Chaque scène et chaque plan compris"], [T.s4a.S[2], "Génériques et moments sensibles protégés"], [T.s4a.S[3], "Plans et dialogue analysés en local"]],
  js: `
        tl.set("#s4a-cur", { x: 700, y: 900 }, 0);
        ${cursorPath("s4a", [[0.05, 200, 375, true], [0.55, 200, 520, true]])}
        tl.to("#s4a-c1 .tick", { opacity: 1, duration: 0.1 }, 0.5);
        tl.to("#s4a-c2 .tick", { opacity: 1, duration: 0.1 }, 1.0);
        tl.to("#s4a-cur", { opacity: 0, duration: 0.3 }, 1.3);
        tl.fromTo("#s4a-hl", { opacity: 0, y: 14 }, { opacity: 1, y: 0, duration: 0.5, ease: E }, ${f(T.s4a.S[1])});
        tl.fromTo("#s4a-bar div", { scaleX: 0 }, { scaleX: 1, duration: 0.3, ease: "power2.out", stagger: 0.13 }, ${f(T.s4a.S[1] + 0.2)});
        tl.fromTo(["#s4a-ticks", "#s4a-leg"], { opacity: 0 }, { opacity: 1, duration: 0.4 }, ${f(T.s4a.S[2])});
        tl.to(["#s4a-sg0", "#s4a-sg1", "#s4a-sg9", "#s4a-sg10"], { scaleY: 1.5, duration: 0.18, yoyo: true, repeat: 1 }, ${f(T.s4a.S[2] + 0.4)});
        tl.fromTo(".s4a-mk", { opacity: 0, y: -14, scale: 0.6 }, { opacity: 1, y: 0, scale: 1, duration: 0.3, ease: "back.out(2.4)", stagger: 0.09 }, ${f(T.s4a.S[2] + 1.0)});
        tl.fromTo("#s4a-met", { opacity: 0 }, { opacity: 1, duration: 0.4 }, ${f(T.s4a.S[3])});`,
};

// ───────────────────────── 2 · Produits ─────────────────────────
const s4b = {
  id: "s4b", file: "s4b-produits.html", step: 2, duration: T.s4b.dur,
  lit: ["createurs", "cultures"],
  cursor: true,
  css: `
#s4b-scroll { position: relative; }
#s4b-ctx { margin-top: 22px; padding: 14px 18px; border-radius: 12px; background: #f5f5f7; font-size: 22px; color: #5b5b61; }
#s4b-ctx b { color: #1d1d1f; font-weight: 600; }
#s4b-cat { display: flex; gap: 22px; margin-top: 22px; }
.pc { width: 300px; border: 1px solid #e3e3e8; border-radius: 14px; padding: 14px; }
.pc .im { height: 170px; border-radius: 10px; background: #f5f5f7; display: flex; align-items: center; justify-content: center; }
.pc .im img { max-height: 150px; max-width: 220px; }
.pc b { display: block; margin-top: 12px; font-size: 22px; font-weight: 600; }
.pc span { display: inline-block; margin-top: 8px; margin-right: 6px; font-size: 16px; padding: 3px 10px; border-radius: 999px; background: #ececf0; color: #5b5b61; }
#s4b-h2 { margin-top: 40px; font-size: 32px; font-weight: 600; letter-spacing: -0.02em; }
#s4b-prop { display: flex; gap: 30px; margin-top: 18px; }
#s4b-th { position: relative; flex: none; width: 440px; height: 248px; border-radius: 12px; overflow: hidden; }
#s4b-th img { width: 100%; height: 100%; object-fit: cover; object-position: left center; display: block; }
#s4b-th .rect { position: absolute; left: 34px; top: 112px; width: 80px; height: 104px; border: 3px solid #ffcc00; border-radius: 6px; box-shadow: 0 0 0 2px rgba(0,0,0,.35); }
#s4b-th .score { position: absolute; right: 12px; top: 12px; background: #fff; border-radius: 999px; padding: 4px 12px; font-size: 18px; font-weight: 600; }
#s4b-pr b { font-size: 28px; font-weight: 600; }
#s4b-pr .where { margin-top: 10px; font-size: 20px; color: #5b5b61; }
#s4b-pr .where em { font-style: normal; color: #0066cc; background: #e8f1fb; padding: 3px 10px; border-radius: 6px; font-weight: 600; margin-right: 8px; }
.mt { display: grid; grid-template-columns: 150px 330px 60px; align-items: center; gap: 14px; margin-top: 14px; font-size: 19px; }
.mt .tr { height: 8px; border-radius: 4px; background: #ececf0; overflow: hidden; }
.mt .fl { display: block; height: 100%; background: #1d1d1f; border-radius: 4px; transform-origin: left center; }
#s4b-guard { margin-top: 26px; border: 1.5px solid #1d1d1f; border-radius: 14px; padding: 20px 24px; }
#s4b-guard .gt { font-size: 22px; font-weight: 600; }
#s4b-guard .gl { margin-top: 4px; font-size: 18px; color: #5b5b61; }
#s4b-cmp { display: flex; align-items: center; gap: 18px; margin-top: 16px; }
#s4b-cmp .bi { width: 74px; height: 74px; border-radius: 10px; background: #f5f5f7; display: flex; align-items: center; justify-content: center; }
#s4b-cmp .bi img { max-height: 62px; filter: grayscale(1); opacity: .7; }
#s4b-cmp .nm { font-size: 21px; font-weight: 600; display: flex; flex-direction: column; gap: 6px; width: 180px; }
.bx { border: 1px solid #8a8a93; border-radius: 10px; padding: 10px 16px; min-width: 200px; }
.bx small { display: block; font-size: 15px; color: #5b5b61; }
.bx b { font-size: 22px; font-weight: 600; }
#s4b-ne { width: 120px; text-align: center; font-size: 17px; font-weight: 600; color: #b81d22; line-height: 1.2; }
#s4b-prio { margin-top: 16px; display: flex; gap: 14px; align-items: center; padding: 12px 16px; border-radius: 10px; background: #fff8d6; font-size: 20px; font-weight: 600; color: #1d1d1f; }
#s4b-prio .bar { flex: none; width: 6px; height: 30px; border-radius: 3px; background: #ffcc00; transform-origin: top; }
#s4b-acts { display: flex; gap: 14px; align-items: center; margin-top: 22px; height: 56px; position: relative; }
#s4b-ok { position: absolute; left: 0; top: 0; height: 56px; display: inline-flex; align-items: center; gap: 10px; padding: 0 22px; border-radius: 12px; border: 1px solid #0066cc; background: #e8f1fb; color: #0058b0; font-size: 22px; font-weight: 600; opacity: 0; }
#s4b-ok svg { width: 22px; height: 22px; }`,
  app: `
            <div id="s4b-scroll">
            <h1>Produits et placements</h1>
            <div id="s4b-ctx"><b>Contexte de l’œuvre</b> · Lieu : <b>Paris, France</b> · Époque : contemporaine</div>
            <div id="s4b-cat">
              <div class="pc" id="s4b-boga"><div class="im"><img src="assets/img/boga-cidre.png" alt="" /></div><b>Boga Cidre</b><span>Boisson sans alcool</span><span>Tunisie</span></div>
              <div class="pc" id="s4b-badoit"><div class="im"><img src="assets/img/badoit.png" alt="" /></div><b>Badoit 1 L</b><span>Boisson sans alcool</span><span>France</span></div>
            </div>
            <div id="s4b-h2">Propositions</div>
            <div id="s4b-prop">
              <div id="s4b-th"><img src="assets/img/cuisine-still.jpg" alt="" /><div class="rect" id="s4b-rect"></div><div class="score">7,7/10</div></div>
              <div id="s4b-pr"><b>Badoit 1 L</b>
                <div class="where"><em>00:30 – 00:40</em>Plan de travail en inox</div>
                <div class="mt"><span>Cohérence</span><span class="tr"><span class="fl" style="width:80%"></span></span><b>8/10</b></div>
                <div class="mt"><span>Discrétion</span><span class="tr"><span class="fl" style="width:70%"></span></span><b>7/10</b></div>
                <div class="mt"><span>Faisabilité</span><span class="tr"><span class="fl" style="width:80%"></span></span><b>8/10</b></div>
              </div>
            </div>
            <div id="s4b-guard">
              <div class="gt">Produit écarté par le Cultural Integrity Guard</div>
              <div class="gl">SceneLine ne le propose pas pour ce placement. Le réalisateur peut en décider autrement.</div>
              <div id="s4b-cmp">
                <div class="bi"><img src="assets/img/boga-cidre.png" alt="" /></div>
                <div class="nm">Boga Cidre<span class="pill hi"><span class="sq"></span>Risque élevé</span></div>
                <div class="bx" id="s4b-bx1"><small>Lieu de l’action</small><b>Paris, France</b></div>
                <div id="s4b-ne">ne correspond pas à</div>
                <div class="bx" id="s4b-bx2"><small>Marché visé par Boga Cidre</small><b>Tunisie</b></div>
              </div>
              <div id="s4b-prio"><span class="bar"></span>Priorité à la culture de la scène : seuls les produits qui la respectent sont proposés.</div>
            </div>
            <div id="s4b-acts"><span class="btn" id="s4b-acc">Accepter</span><span class="btn sec">Refuser</span><span class="btn sec">Ajuster…</span>
              <span id="s4b-ok">${TK.replace('stroke="#fff"', 'stroke="#0058b0"')}Approuvé · par Producteur</span></div>
            </div>`,
  callouts: [[T.s4b.S[1], "Le Cultural Integrity Guard vérifie chaque produit."], [T.s4b.S[2], "Boga Cidre écartée : elle ne correspond ni au lieu ni au public de l’œuvre."], [T.s4b.S[3], "La culture de la scène passe en priorité."], [T.s4b.S[4], "Rien n’est modifié sans votre accord."]],
  js: `
        tl.set("#s4b-cur", { x: 900, y: 1100 }, 0);
        tl.fromTo("#s4b-ctx", { opacity: 0, y: 10 }, { opacity: 1, y: 0, duration: 0.4, ease: E }, 0.4);
        tl.fromTo(["#s4b-boga", "#s4b-badoit"], { opacity: 0, y: 30 }, { opacity: 1, y: 0, duration: 0.5, ease: E, stagger: 0.25 }, 0.8);
        tl.to("#s4b-scroll", { y: -372, duration: 0.9, ease: "power3.inOut" }, ${f(T.s4b.S[1] - 0.3)});
        tl.fromTo("#s4b-th", { opacity: 0, scale: 0.97 }, { opacity: 1, scale: 1, duration: 0.5, ease: E }, ${f(T.s4b.S[1] + 0.1)});
        tl.fromTo("#s4b-rect", { opacity: 0, scale: 1.3 }, { opacity: 1, scale: 1, duration: 0.4, ease: "back.out(2)" }, ${f(T.s4b.S[1] + 0.7)});
        tl.fromTo("#s4b-pr", { opacity: 0, x: 20 }, { opacity: 1, x: 0, duration: 0.5, ease: E }, ${f(T.s4b.S[1] + 0.4)});
        tl.fromTo("#s4b-pr .fl", { scaleX: 0 }, { scaleX: 1, duration: 0.6, ease: "power2.out", stagger: 0.15 }, ${f(T.s4b.S[1] + 1.5)});
        tl.fromTo("#s4b-guard", { opacity: 0, y: 20 }, { opacity: 1, y: 0, duration: 0.5, ease: E }, ${f(T.s4b.S[2])});
        tl.fromTo(["#s4b-bx1", "#s4b-ne", "#s4b-bx2"], { opacity: 0, y: 8 }, { opacity: 1, y: 0, duration: 0.35, ease: E, stagger: 0.25 }, ${f(T.s4b.S[2] + 0.4)});
        tl.to("#s4b-bx2", { borderColor: "#b81d22", backgroundColor: "#fdebec", duration: 0.3 }, ${f(T.s4b.S[2] + 3.6)});
        tl.to("#s4b-bx1", { borderColor: "#1d1d1f", duration: 0.3 }, ${f(T.s4b.S[2] + 3.6)});
        tl.to("#s4b-boga", { opacity: 0.45, filter: "grayscale(1)", duration: 0.4 }, ${f(T.s4b.S[2] + 3.6)});
        tl.to("#s4b-ne", { scale: 1.15, duration: 0.15, yoyo: true, repeat: 1 }, ${f(T.s4b.S[2] + 3.6)});
        tl.fromTo("#s4b-prio", { opacity: 0, y: 10 }, { opacity: 1, y: 0, duration: 0.45, ease: E }, ${f(T.s4b.S[3])});
        tl.fromTo("#s4b-prio .bar", { scaleY: 0 }, { scaleY: 1, duration: 0.35, ease: E }, ${f(T.s4b.S[3] + 0.1)});
        tl.to("#s4b-badoit", { borderColor: "#ffcc00", boxShadow: "0 0 0 3px #ffcc00", duration: 0.3 }, ${f(T.s4b.S[3] + 3.0)});
        tl.fromTo("#s4b-acts", { opacity: 0 }, { opacity: 1, duration: 0.3 }, ${f(T.s4b.S[4] - 0.9)});
        ${cursorPath("s4b", [[f(T.s4b.S[4] - 0.45), 250, 942, true]])}
        tl.to("#s4b-acts .btn", { opacity: 0, duration: 0.15 }, ${f(T.s4b.S[4] + 0.1)});
        tl.to("#s4b-ok", { opacity: 1, duration: 0.25 }, ${f(T.s4b.S[4] + 0.1)});
        tl.to("#s4b-cur", { opacity: 0, duration: 0.3 }, ${f(T.s4b.S[4] + 0.7)});`,
};

// ───────────────────────── 3 · Génération ─────────────────────────
const s4c = {
  id: "s4c", file: "s4c-generation.html", step: 3, duration: T.s4c.dur,
  lit: ["createurs", "droits", "donnees", "planete"],
  cursor: true,
  css: `
#s4c-scroll { position: relative; }
#s4c-sub { margin-top: 8px; font-size: 22px; color: #5b5b61; }
#s4c-opt { margin-top: 24px; border: 2px solid #0066cc; background: #f3f8fd; border-radius: 14px; padding: 18px 22px; display: flex; justify-content: space-between; align-items: center; }
#s4c-opt b { font-size: 26px; font-weight: 600; }
#s4c-opt small { display: block; margin-top: 4px; font-size: 18px; color: #5b5b61; }
.live { display: inline-flex; align-items: center; gap: 8px; font-size: 19px; font-weight: 600; color: #19732f; background: #e6f4ea; padding: 6px 14px; border-radius: 999px; }
.live i { width: 10px; height: 10px; border-radius: 50%; background: #23873f; }
#s4c-panel { margin-top: 18px; background: #f5f5f7; border-radius: 14px; padding: 22px 24px; }
.sec-t { font-size: 22px; font-weight: 600; }
.send { display: flex; align-items: center; gap: 16px; margin-top: 12px; font-size: 21px; }
.send .ic { width: 84px; height: 52px; border-radius: 8px; background: #fff; border: 1px solid #e3e3e8; overflow: hidden; display: flex; align-items: center; justify-content: center; font-size: 15px; color: #6e6e73; font-weight: 600; }
.send .ic img { width: 100%; height: 100%; object-fit: cover; object-position: left center; }
.send .ic img.p { width: auto; height: 46px; object-fit: contain; }
#s4c-cons { display: flex; gap: 16px; align-items: flex-start; margin-top: 18px; background: #fff; border: 1px solid #8a8a93; border-radius: 12px; padding: 16px 18px; font-size: 21px; }
#s4c-cons small { display: block; margin-top: 4px; font-size: 16px; color: #5b5b61; }
#s4c-go { margin-top: 16px; position: relative; }
#s4c-go .btn { transition: none; }
#s4c-prog { margin-top: 22px; }
.ps { display: flex; align-items: center; gap: 14px; height: 46px; font-size: 22px; color: #8a8a93; }
.ps .c { width: 28px; height: 28px; border-radius: 50%; border: 2px solid #b4b4bb; box-sizing: border-box; position: relative; }
.ps .c .f { position: absolute; inset: -2px; border-radius: 50%; background: #23873f; opacity: 0; display: flex; align-items: center; justify-content: center; }
.ps .c .f svg { width: 18px; height: 18px; }
#s4c-ban { margin-top: 16px; display: flex; justify-content: space-between; align-items: center; padding: 18px 22px; border-radius: 14px; background: #e6f4ea; border: 1px solid #23873f; }
#s4c-ban b { font-size: 24px; font-weight: 600; color: #19732f; }`,
  app: `
            <div id="s4c-scroll">
            <h1>Kit de génération</h1>
            <div id="s4c-sub">Badoit 1 L · 00:30 – 00:40 · Plan de travail en inox · placement approuvé</div>
            <div id="s4c-opt"><div><b>Automatique avec Kling AI</b><small>SceneLine envoie le plan, le produit et le prompt, puis récupère la vidéo.</small></div><span class="live"><i></i>Connecté à Kling AI</span></div>
            <div id="s4c-panel">
              <div class="sec-t">Ce qui sera envoyé à Kling</div>
              <div class="send"><span class="ic">Prompt</span>Le prompt du kit, en anglais</div>
              <div class="send"><span class="ic"><img class="p" src="assets/img/badoit.png" alt="" /></span>L’image du produit, sur fond blanc</div>
              <div class="send"><span class="ic"><img src="assets/img/cuisine-still.jpg" alt="" /></span>Le plan vidéo, sans audio, par un lien temporaire</div>
              <div id="s4c-cons">${chk("s4c-c1")}<span>J’autorise l’envoi de ces éléments à Kling AI pour ce placement.<small>Angles Droits et Données · rien ne part sans cette autorisation</small></span></div>
              <div id="s4c-go"><span class="btn" id="s4c-btn">Générer avec Kling et intégrer</span></div>
              <div id="s4c-prog">
                ${["Envoi à Kling", "Génération chez Kling", "Téléchargement", "Intégration dans la vidéo"].map((t, i) => `<div class="ps" id="s4c-p${i}"><span class="c"><span class="f">${TK}</span></span>${t}</div>`).join("")}
              </div>
              <div id="s4c-ban"><b>✓ Vidéo générée par Kling et intégrée</b><span class="btn sec">Voir la comparaison</span></div>
            </div>
            </div>`,
  callouts: [[T.s4c.S[1], "Rien ne part sans votre autorisation."], [T.s4c.S[2], "Généré directement depuis SceneLine."], [T.s4c.S[3], "Seulement pour les placements approuvés."]],
  js: `
        tl.set("#s4c-cur", { x: 900, y: 1100 }, 0);
        tl.set(["#s4c-prog", "#s4c-ban"], { opacity: 0 }, 0);
        tl.set("#s4c-btn", { backgroundColor: "#a9c4e3" }, 0);
        ${cursorPath("s4c", [[f(T.s4c.S[1] - 0.45), 210, 742, true], [f(T.s4c.S[1] + 0.6), 330, 835, true]])}
        tl.to("#s4c-c1 .tick", { opacity: 1, duration: 0.1 }, ${f(T.s4c.S[1])});
        tl.to("#s4c-btn", { backgroundColor: "#0066cc", duration: 0.2 }, ${f(T.s4c.S[1] + 0.05)});
        tl.to("#s4c-btn", { scale: 0.96, duration: 0.08, yoyo: true, repeat: 1 }, ${f(T.s4c.S[1] + 1.05)});
        tl.to("#s4c-cur", { opacity: 0, duration: 0.3 }, ${f(T.s4c.S[1] + 1.4)});
        tl.to("#s4c-scroll", { y: -300, duration: 0.8, ease: "power3.inOut" }, ${f(T.s4c.S[2] - 0.3)});
        tl.to("#s4c-prog", { opacity: 1, duration: 0.3 }, ${f(T.s4c.S[2])});
        ${JSON.stringify(T.s4c.ticks)}.forEach((t, i) => {
          tl.to("#s4c-p" + i, { color: "#1d1d1f", duration: 0.2 }, t - 0.6);
          tl.fromTo("#s4c-p" + i + " .f", { opacity: 0, scale: 0.5 }, { opacity: 1, scale: 1, duration: 0.25, ease: "back.out(2.5)" }, t);
        });
        tl.fromTo("#s4c-ban", { opacity: 0, y: 14 }, { opacity: 1, y: 0, duration: 0.45, ease: E }, ${f(T.s4c.S[3])});`,
};

// ───────────────────────── 4 · Intégration ─────────────────────────
const s4d = {
  id: "s4d", file: "s4d-integration.html", step: 4, duration: T.s4d.dur,
  lit: ["createurs", "transparence"],
  cursor: false,
  css: `
#s4d-scroll { position: relative; }
#s4d-pl { position: relative; margin-top: 22px; width: 1046px; height: 438px; border-radius: 14px; overflow: hidden; background: #000; }
#s4d-v1, #s4d-v2 { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
#s4d-wipe { position: absolute; inset: 0; }
#s4d-line { position: absolute; top: 0; bottom: 0; left: 0; width: 4px; margin-left: -2px; background: #ffcc00; }
.vl { position: absolute; top: 16px; padding: 6px 14px; border-radius: 8px; font-size: 19px; font-weight: 600; background: rgba(0,0,0,.65); color: #fff; }
#s4d-lo { left: 16px; } #s4d-lk { right: 16px; }
#s4d-tag { position: absolute; left: 16px; bottom: 16px; display: inline-flex; align-items: center; gap: 10px; padding: 8px 16px; border-radius: 8px; background: #ffcc00; color: #1d1d1f; font-size: 21px; font-weight: 600; }
#s4d-tag i { width: 12px; height: 12px; border-radius: 2px; background: #1d1d1f; }
#s4d-fr { margin-top: 22px; }
#s4d-fr .bar { position: relative; height: 18px; border-radius: 9px; background: #ececf0; }
#s4d-fr .m { position: absolute; left: 10.8%; width: 3.6%; top: -6px; bottom: -6px; border-radius: 4px; background: #ffcc00; border: 2px solid #8a5100; box-sizing: border-box; }
#s4d-fr .lb { display: flex; justify-content: space-between; margin-top: 10px; font-size: 18px; color: #6e6e73; }
#s4d-fr .lb b { color: #1d1d1f; font-weight: 600; }
#s4d-rel { margin-top: 24px; border: 1px solid #e3e3e8; border-radius: 14px; padding: 18px 24px; }
#s4d-rel .t { font-size: 23px; font-weight: 600; }
.rr { display: grid; grid-template-columns: 240px 1fr; padding: 11px 0; border-top: 1px solid #ececf0; font-size: 20px; }
.rr:first-of-type { margin-top: 10px; }
.rr span { color: #6e6e73; } .rr b { font-weight: 600; }`,
  app: `
            <div id="s4d-scroll">
            <h1>Intégration</h1>
            <div class="lede">Badoit 1 L · plan 8 · 00:30 – 00:40</div>
            <div id="s4d-pl">
              <video id="s4d-v1" class="clip" src="assets/footage/cuisine-original.mp4" muted playsinline data-start="0" data-duration="${T.s4d.dur}" data-playback-rate="${T.s4d.rate}" data-track-index="1"></video>
              <div id="s4d-wipe"><video id="s4d-v2" class="clip" src="assets/footage/cuisine-badoit-kling.mp4" muted playsinline data-start="0" data-duration="${T.s4d.dur}" data-playback-rate="${T.s4d.rate}" data-track-index="2"></video></div>
              <div id="s4d-line"></div>
              <span class="vl" id="s4d-lo">Original</span><span class="vl" id="s4d-lk">Avec Badoit · Kling</span>
              <span id="s4d-tag"><i></i>Placement virtuel · Badoit 1 L</span>
            </div>
            <div id="s4d-fr"><div class="bar"><div class="m" id="s4d-m"></div></div><div class="lb"><span>00:00</span><span><b>00:30 – 00:40 remplacé</b> · audio d’origine conservé</span><span>04:38</span></div></div>
            <div id="s4d-rel"><div class="t">Relevé des modifications</div>
              <div class="rr"><span>Outil</span><b>Kling AI · édition vidéo</b></div>
              <div class="rr"><span>Approuvé par</span><b>Producteur</b></div>
              <div class="rr"><span>Recalage</span><b>7,0 s → 9,5 s, image par image</b></div>
              <div class="rr"><span>Original</span><b>Conservé, empreintes enregistrées</b></div>
            </div>
            </div>`,
  callouts: [[T.s4d.S[1], "Le résultat est replacé dans la vidéo d’origine, avec son audio."], [T.s4d.S[2], "L’original est conservé."], [T.s4d.S[3], "Le spectateur est informé."]],
  js: `
        tl.fromTo("#s4d-wipe", { clipPath: "inset(0 100% 0 0)" }, { clipPath: "inset(0 0% 0 0)", duration: 1.4, ease: "power2.inOut" }, ${f(T.s4d.S[1] - 0.2)});
        tl.fromTo("#s4d-line", { x: 0, opacity: 1 }, { x: 1046, duration: 1.4, ease: "power2.inOut" }, ${f(T.s4d.S[1] - 0.2)});
        tl.to("#s4d-line", { opacity: 0, duration: 0.2 }, ${f(T.s4d.S[1] + 1.2)});
        tl.set("#s4d-lk", { opacity: 0 }, 0);
        tl.to("#s4d-lo", { opacity: 0, duration: 0.2 }, ${f(T.s4d.S[1] + 0.4)});
        tl.to("#s4d-lk", { opacity: 1, duration: 0.3 }, ${f(T.s4d.S[1] + 1.1)});
        tl.fromTo("#s4d-tag", { opacity: 0, y: 12, scale: 0.9 }, { opacity: 1, y: 0, scale: 1, duration: 0.4, ease: "back.out(2)" }, ${f(T.s4d.S[3] + 0.2)});
        tl.fromTo("#s4d-fr", { opacity: 0 }, { opacity: 1, duration: 0.4 }, ${f(T.s4d.S[1] + 1.6)});
        tl.fromTo("#s4d-m", { scaleY: 0 }, { scaleY: 1, duration: 0.35, ease: "back.out(2.5)" }, ${f(T.s4d.S[1] + 1.9)});
        tl.to("#s4d-scroll", { y: -250, duration: 0.8, ease: "power3.inOut" }, ${f(T.s4d.S[2] - 0.3)});
        tl.fromTo("#s4d-rel", { opacity: 0, y: 16 }, { opacity: 1, y: 0, duration: 0.5, ease: E }, ${f(T.s4d.S[2])});
        tl.fromTo("#s4d-rel .rr", { opacity: 0, x: -12 }, { opacity: 1, x: 0, duration: 0.3, ease: E, stagger: 0.18 }, ${f(T.s4d.S[2] + 0.2)});
        tl.to("#s4d-tag", { scale: 1.08, duration: 0.2, yoyo: true, repeat: 1 }, ${f(T.s4d.S[3] + 1.8)});`,
};

return [s4a, s4b, s4c, s4d];
}
