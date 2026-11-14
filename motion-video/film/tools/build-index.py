# Génère index.html : scènes, voix off et effets sonores.  Usage : python tools/build-index.py
# Les temps des voix et des sons sont locaux à chaque scène ; le script calcule les temps globaux.
import json, subprocess

# Les quatre étapes de la démo suivent leur voix off : durées, voix et sons viennent de tools/demo-timing.json (build-demo.mjs).
DEMO = json.load(open("tools/demo-timing.json", encoding="utf-8"))

K = 1 / 1.10  # le constat (s2) et la promesse (s5) sont accélérés de 10 % ; l'interview et l'idée gardent leur vitesse
SCALED = {"s2", "s5"}
SCENES = [  # id, fichier, durée
    ("s1", "s1-interview", 43.9),
    ("s2", "s2-constat", round(28.0 * K, 2)),
    ("s3", "s3-idee", 11.4),
    ("s4a", "s4a-analyse", DEMO["s4a"]["duration"]),
    ("s4b", "s4b-produits", DEMO["s4b"]["duration"]),
    ("s4c", "s4c-generation", DEMO["s4c"]["duration"]),
    ("s4d", "s4d-integration", DEMO["s4d"]["duration"]),
    ("s5", "s5-promesse", round(10 * K, 2)),
]
# Voix off Gemini TTS (voix Puck), fichiers assets/vo/<id>.wav : (scène, temps local)
VO = {"l01": ("s2", 0.6), "l01b": ("s2", 7.2), "l02": ("s2", 12.2), "l02b": ("s2", 23.0), "l03": ("s3", 0.3), "l04": ("s3", 6.3),
      "l09": ("s5", 0.3)}
for sid, d in DEMO.items():
    VO.update({k: (sid, lt) for k, lt in d["vo"]})
V = {"swish": .3, "swell": .3, "bloop": .3, "tap": .35, "tick": .25, "chime": .3, "deny": .3}
SFX = {  # temps locaux ; un « swish » seulement aux changements de scène, et des sons d'interface discrets
    "s1": [],
    "s2": [("swish", 0.0), ("bloop", 13.2), ("bloop", 15.5), ("bloop", 17.7), ("deny", 20.2), ("swish", 22.6)],
    "s3": [("swell", -0.4), ("chime", 0.8)] + [("bloop", 6.9 + i * 0.4) for i in range(6)],
    "s5": [("swish", -0.2), ("bloop", 0.35), ("bloop", 1.95), ("bloop", 3.4), ("swell", 4.6), ("chime", 6.25)],
}

SFX.update({sid: [tuple(e) for e in d["sfx"]] for sid, d in DEMO.items()})

loc = lambda s, lt: lt * K if s in SCALED else lt

start, t = {}, 0.0
for i, f, d in SCENES:
    start[i] = t
    t += d
total = t
r = lambda x: round(x, 3)
dur = lambda p: float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p], capture_output=True, text=True).stdout)

hosts = "\n".join(f'      <div id="{i}" data-composition-id="{i}" data-composition-src="compositions/{f}.html" data-start="{r(start[i])}" data-duration="{r(d)}" data-track-index="0" data-width="1920" data-height="1080"></div>' for i, f, d in SCENES)
vos = "\n".join(f'      <audio id="vo-{k}" src="assets/vo/{k}.wav" data-start="{r(start[s] + loc(s, lt))}" data-duration="{r(dur(f"assets/vo/{k}.wav"))}" data-track-index="1" data-volume="1"></audio>' for k, (s, lt) in VO.items())
events = sorted((start[s] + loc(s, lt), k) for s, lst in SFX.items() for k, lt in lst)
sf = "\n".join(f'      <audio id="sfx-{n:02d}-{k}" src="assets/sfx/{k}.wav" data-start="{r(gt)}" data-duration="{r(dur(f"assets/sfx/{k}.wav"))}" data-track-index="{2 + n % 2}" data-volume="{V[k]}"></audio>' for n, (gt, k) in enumerate(events))

html = f'''<!doctype html>
<html lang="fr">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1920, height=1080" />
    <title>SceneLine · vidéo de présentation</title>
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.15.0/dist/gsap.min.js"></script>
    <style>
      @font-face {{ font-family: 'Inter'; font-style: normal; font-weight: 400 600; font-display: block; src: url('assets/fonts/inter-latin.woff2') format('woff2'); }}
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ margin: 0; width: 1920px; height: 1080px; overflow: hidden; background: #f5f5f7; }}
      #root {{ position: relative; width: 100%; height: 100%; font-family: 'Inter', sans-serif; background: #f5f5f7; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{r(total)}" data-width="1920" data-height="1080">
      <!-- Généré par tools/build-index.py. Scènes : voir ../SCRIPT.md ; les scènes s4* viennent de tools/build-demo.mjs. -->
{hosts}

      <!-- Voix off française : Gemini TTS, voix Puck (texte : ../vo/lines.json) -->
{vos}

      <!-- Effets sonores synthétisés localement (FFmpeg), pas de musique -->
{sf}
    </div>
    <script>
      const tl = gsap.timeline({{ paused: true }});
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
'''
open("index.html", "w", encoding="utf-8").write(html)
print("durée totale", r(total), "s")
for k, (s, lt) in VO.items():
    d = dur(f"assets/vo/{k}.wav")
    end = scene_end = None
    sd = dict((i, d2) for i, _, d2 in SCENES)[s]
    if loc(s, lt) + d > sd:
        print(f"  attention : {k} dépasse la scène {s} ({loc(s, lt) + d:.2f} s > {sd} s)")
