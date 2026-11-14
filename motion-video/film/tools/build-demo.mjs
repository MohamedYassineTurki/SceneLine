// Génère les quatre scènes de la démo (compositions/s4*.html) avec le même cadre d'application :
// barre SceneLine, étapes, bandeau des six angles « IA éthique 360 », colonne de légendes à droite.
// Usage : node tools/build-demo.mjs
import { writeFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { scenes as makeScenes } from "./demo-scenes.mjs";

// Rythme dicté par la voix off : chaque phrase <id>-<k>.wav démarre quand la précédente se termine (+ GAP).
const GAP = 0.12, LEAD = 0.3, TAIL = 0.5, CLIP = 12.4; // CLIP : durée utile des extraits de la cuisine
const dur = (p) => Number(execFileSync("ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p]).toString());
const r2 = (x) => Math.round(x * 100) / 100;
const T = {};
for (const id of ["s4a", "s4b", "s4c", "s4d"]) {
  const N = id === "s4b" ? 5 : 4;
  const D = [...Array(N).keys()].map((k) => r2(dur(fileURLToPath(new URL(`../assets/vo/${id}-${k}.wav`, import.meta.url)))));
  const S = [];
  let t = LEAD;
  for (const d of D) { S.push(r2(t)); t += d + GAP; }
  const total = r2(t - GAP + TAIL);
  T[id] = { S, D, dur: total, rate: r2(Math.min(1, CLIP / total)) };
}
T.s4c.ticks = [0, 1, 2, 3].map((i) => r2(T.s4c.S[2] + 0.6 + (i * (T.s4c.D[2] - 0.5)) / 4));

// Effets sonores de la démo, posés sur les mêmes repères (temps locaux).
const SFX = {
  s4a: [["swish", -0.2], ["tap", 0.5], ["tap", 1.0], ["tick", T.s4a.S[2] + 1.0], ["tick", T.s4a.S[2] + 1.4]],
  s4b: [["swish", -0.2], ["deny", T.s4b.S[2] + 3.6], ["bloop", T.s4b.S[3] + 0.1], ["tap", T.s4b.S[4]]],
  s4c: [["swish", -0.2], ["tap", T.s4c.S[1]], ["tap", T.s4c.S[1] + 1.05], ...T.s4c.ticks.map((t) => ["tick", t]), ["chime", T.s4c.S[3]]],
  s4d: [["swish", -0.2], ["bloop", T.s4d.S[3] + 0.2]],
};
const timing = {};
for (const id of Object.keys(T)) timing[id] = { duration: T[id].dur, vo: T[id].S.map((s, k) => [`${id}-${k}`, s]), sfx: SFX[id].map(([n, t]) => [n, r2(t)]) };
writeFileSync(new URL("./demo-timing.json", import.meta.url), JSON.stringify(timing, null, 1));
const scenes = makeScenes(T);

const STEPS = ["Analyse", "Produits", "Génération", "Intégration"];
const AXES = [
  ["createurs", "Créateurs"], ["droits", "Droits"], ["donnees", "Données"],
  ["cultures", "Cultures et langues"], ["transparence", "Transparence"], ["planete", "Planète"],
];

const CHROME_CSS = `
@font-face { font-family: 'Inter'; font-style: normal; font-weight: 400 600; font-display: block; src: url('assets/fonts/inter-latin.woff2') format('woff2'); }
#root { position: absolute; inset: 0; background: #f5f5f7; font-family: 'Inter', sans-serif; color: #1d1d1f; overflow: hidden; }
.stage { position: absolute; inset: 0; }
.mk { background-image: linear-gradient(#ffcc00, #ffcc00); background-repeat: no-repeat; background-size: 0% 100%; -webkit-box-decoration-break: clone; box-decoration-break: clone; padding: 0 3px; border-radius: 4px; }
.top { position: absolute; left: 0; right: 0; top: 0; height: 88px; background: #fff; border-bottom: 1px solid #e3e3e8; display: flex; align-items: center; padding: 0 56px; }
.top .logo { display: flex; align-items: center; gap: 12px; font-size: 30px; font-weight: 600; letter-spacing: -0.02em; width: 360px; }
.top .logo svg { width: 40px; height: 40px; }
.steps { flex: 1; display: flex; justify-content: center; }
.steps .rail { display: flex; gap: 6px; background: #ececf0; border-radius: 999px; padding: 6px; }
.step { display: flex; align-items: center; gap: 10px; padding: 10px 24px; border-radius: 999px; font-size: 22px; font-weight: 500; color: #5b5b61; }
.step .num { width: 28px; height: 28px; border-radius: 50%; background: #0066cc; color: #fff; font-size: 15px; font-weight: 600; display: flex; align-items: center; justify-content: center; }

.step .num svg { width: 16px; height: 16px; }
.step.todo .num { background: #fff; color: #6e6e73; border: 1px solid #8a8a93; }
.step.cur { background: #fff; color: #1d1d1f; box-shadow: 0 1px 2px rgba(29,29,31,.12); }
.top .links { width: 360px; text-align: right; font-size: 22px; color: #1d1d1f; }
.axes { position: absolute; left: 0; right: 0; top: 112px; display: flex; justify-content: center; align-items: center; gap: 12px; }
.axes .lbl { font-size: 21px; font-weight: 600; color: #5b5b61; margin-right: 8px; letter-spacing: .04em; text-transform: uppercase; }
.axc { position: relative; display: flex; align-items: center; gap: 10px; padding: 9px 18px; border-radius: 999px; border: 1px solid #e3e3e8; background: #fff; font-size: 22px; font-weight: 500; color: #6e6e73; }
.axc .d { width: 14px; height: 14px; border-radius: 50%; border: 2px solid #b4b4bb; box-sizing: border-box; }
.axc .on { position: absolute; inset: -1px; border-radius: 999px; background: #1d1d1f; display: flex; align-items: center; gap: 10px; padding: 9px 18px; color: #fff; font-size: 22px; font-weight: 500; opacity: 0; }
.axc .on .d { border: 0; background: #ffcc00; }
.app { position: absolute; left: 110px; top: 186px; width: 1150px; height: 860px; background: #fff; border: 1px solid #e3e3e8; border-radius: 20px; box-shadow: 0 1px 2px rgba(29,29,31,.08), 0 18px 50px rgba(29,29,31,.07); padding: 44px 52px; overflow: hidden; }
.app h1 { font-size: 46px; font-weight: 600; letter-spacing: -0.025em; margin: 0; }
.app .lede { margin-top: 10px; font-size: 24px; color: #5b5b61; line-height: 1.4; }
.cos { position: absolute; left: 1320px; top: 250px; width: 520px; }
.stepno { font-size: 22px; font-weight: 600; color: #0066cc; letter-spacing: .06em; text-transform: uppercase; }
.co { position: relative; margin-top: 30px; padding-left: 26px; font-size: 40px; font-weight: 600; line-height: 1.22; letter-spacing: -0.02em; color: #1d1d1f; }
.co::before { content: ""; position: absolute; left: 0; top: 8px; width: 8px; height: 34px; border-radius: 3px; background: #ffcc00; }
.cursor { position: absolute; left: 0; top: 0; width: 34px; height: 34px; z-index: 50; filter: drop-shadow(0 2px 3px rgba(0,0,0,.3)); }
.chk { flex: none; width: 30px; height: 30px; border-radius: 7px; border: 2px solid #8a8a93; background: #fff; position: relative; box-sizing: border-box; }
.chk .tick { position: absolute; inset: -2px; border-radius: 7px; background: #0066cc; display: flex; align-items: center; justify-content: center; opacity: 0; }
.chk .tick svg { width: 20px; height: 20px; }
.btn { display: inline-flex; align-items: center; justify-content: center; height: 56px; padding: 0 28px; border-radius: 12px; font-size: 23px; font-weight: 600; background: #0066cc; color: #fff; }
.btn.sec { background: #fff; color: #1d1d1f; border: 1px solid #8a8a93; }
.pill { display: inline-flex; align-items: center; gap: 8px; padding: 5px 14px; border-radius: 999px; font-size: 19px; font-weight: 600; }
.pill.hi { background: #fdebec; color: #b81d22; } .pill.mid { background: #fdf1dc; color: #8a5100; } .pill.lo { background: #e6f4ea; color: #19732f; }
.pill .sq { width: 11px; height: 11px; border-radius: 2px; background: currentColor; }
`;

const TICK = `<svg viewBox="0 0 20 20"><path d="M4 10.5l4 4 8-9" fill="none" stroke="#fff" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
const CURSOR = `<svg class="cursor" viewBox="0 0 24 24"><path d="M3 2l17 9.5-7.4 1.6L9 21z" fill="#1d1d1f" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>`;

function chrome(id, step) {
  const steps = STEPS.map((s, i) => {
    const n = i + 1, cls = n < step ? "done" : n === step ? "cur" : "done";
    const num = n === step ? `${n}` : TICK.replace('width="20"', "");
    return `<div class="step ${cls}"><span class="num">${num}</span>${s}</div>`;
  }).join("");
  const axes = AXES.map(([k, l]) =>
    `<div class="axc" id="${id}-ax-${k}"><span class="d"></span>${l}<div class="on"><span class="d"></span>${l}</div></div>`).join("");
  return `
          <div class="top">
            <div class="logo"><svg viewBox="0 0 64 64"><rect x="7" y="11" width="50" height="42" rx="9" fill="none" stroke="#1d1d1f" stroke-width="6"/><rect x="31" y="29" width="17" height="14" rx="3" fill="#ffcc00"/></svg>SceneLine</div>
            <div class="steps"><div class="rail">${steps}</div></div>
            <div class="links">Éthique 360</div>
          </div>
          <div class="axes"><span class="lbl">Éthique 360</span>${axes}</div>`;
}

function page(sc) {
  const lit = sc.lit.map(k => `"#${sc.id}-ax-${k} .on"`).join(", ");
  return `<!doctype html>
<html lang="fr">
  <head><meta charset="UTF-8" /></head>
  <body>
    <!-- Généré par tools/build-demo.mjs : modifier tools/demo-scenes.mjs puis relancer. -->
    <template>
      <style>${CHROME_CSS}${sc.css}
      </style>
      <div id="root" data-composition-id="${sc.id}" data-width="1920" data-height="1080">
        <div id="${sc.id}-stage" class="stage">${chrome(sc.id, sc.step)}
          <div class="app" id="${sc.id}-app">${sc.app}
          </div>
          <div class="cos" id="${sc.id}-cos"><div class="stepno">Étape ${sc.step} · ${STEPS[sc.step - 1]}</div>${sc.callouts.map((c, i) => `<p class="co" id="${sc.id}-co${i}">${c[1]}</p>`).join("")}</div>
          ${sc.cursor ? CURSOR.replace('class="cursor"', `class="cursor" id="${sc.id}-cur"`) : ""}
        </div>
      </div>
      <script>
        const tl = gsap.timeline({ paused: true });
        const E = "power3.out";
        const TICK = ${JSON.stringify(TICK)};
        tl.fromTo("#${sc.id}-app", { opacity: 0, y: 24 }, { opacity: 1, y: 0, duration: 0.5, ease: E }, 0.05);
        tl.fromTo("#${sc.id}-cos .stepno", { opacity: 0, y: 10 }, { opacity: 1, y: 0, duration: 0.4, ease: E }, 0.15);
        tl.fromTo([${lit}], { opacity: 0, scale: 0.9 }, { opacity: 1, scale: 1, duration: 0.35, ease: "back.out(2)", stagger: 0.12 }, 0.3);
        ${sc.callouts.map((c, i) => `tl.fromTo("#${sc.id}-co${i}", { opacity: 0, y: 16 }, { opacity: 1, y: 0, duration: 0.45, ease: E }, ${c[0]});` +
          (i > 0 ? `\n        tl.to("#${sc.id}-co${i - 1}", { color: "#8a8a93", duration: 0.3 }, ${c[0]});` : "")).join("\n        ")}
        ${sc.js}
        window.__timelines["${sc.id}"] = tl;
      </script>
    </template>
  </body>
</html>
`;
}

for (const sc of scenes) {
  writeFileSync(new URL(`../compositions/${sc.file}`, import.meta.url), page(sc));
  console.log("écrit", sc.file);
}
