"""Assemble les images enregistrées par record_demo.py en MP4 (et GIF) de démonstration.

Les longues attentes (analyse Gemini, appariement) sont accélérées, et un badge l'indique à l'écran :
rien n'est coupé ni simulé. Le reste est en temps réel.

Usage : .venv/Scripts/python scripts/build_demo_video.py output/demo-recording docs/media/demo.mp4 [--gif docs/media/demo.gif]
"""
import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FONT = ROOT / "motion-video/film/assets/fonts"
FAST = [("analysis-start", "analysis-done", "Analyse réelle en cours"), ("match-start", "match-done", "Appariement réel en cours")]
TYPING = ("add-products", "match-start", "Saisie du catalogue", 2.0)  # saisie à la main, simplement accélérée
JOIN = "Étapes 3 et 4 · même épisode, plan généré par Kling AI puis intégré"
LEAD, TAIL, TARGET = 2.5, 1.5, 7.0  # secondes en temps réel au début et à la fin de chaque attente ; durée visée de l'attente


def font():
    for name in ("Inter-SemiBold.ttf", "Inter-Medium.ttf", "Inter-Regular.ttf"):
        if (FONT / name).is_file():
            return FONT / name
    found = sorted(FONT.glob("*.ttf")) + sorted(FONT.glob("*.otf"))
    return found[0] if found else Path("C:/Windows/Fonts/segoeui.ttf")


def esc(path):
    return str(path).replace("\\", "/").replace(":", "\\:")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("frames")
    ap.add_argument("out")
    ap.add_argument("--gif")
    ap.add_argument("--extra", nargs="*", default=[], help="autres dossiers enregistrés, ajoutés à la suite")
    a = ap.parse_args()

    segments, badges, t_out = [], [], 0.0
    titles = []
    for index, folder in enumerate([Path(a.frames), *map(Path, a.extra)]):
        data = json.loads((folder / "timeline.json").read_text(encoding="utf-8"))
        frames, marks = data["frames"], {label: ts for ts, label in data["markers"]}
        if index and "step3" in marks:   # un enregistrement ajouté commence à l'étape 3
            frames = [f for f in frames if f[0] >= marks["step3"] - 0.3]
            titles.append((t_out, t_out + 4.5))
        windows = []
        if TYPING[0] in marks and TYPING[1] in marks:
            windows.append((marks[TYPING[0]], marks[TYPING[1]] - 0.5, TYPING[3], TYPING[2]))
        for start, end, text in FAST:
            if start in marks and end in marks and marks[end] - marks[start] > LEAD + TAIL + TARGET:
                a0, a1 = marks[start] + LEAD, marks[end] - TAIL
                windows.append((a0, a1, max(1.0, (a1 - a0) / TARGET), text))
        for i, (ts, name) in enumerate(frames):
            nxt = frames[i + 1][0] if i + 1 < len(frames) else ts + 1.5
            dur = max(nxt - ts, 0.001)
            speed = next((w[2] for w in windows if w[0] <= ts < w[1]), 1.0)
            segments.append((folder / name, dur / speed))
            for w in windows:
                if w[0] <= ts < w[1] and (not badges or badges[-1][3] != w):
                    badges.append([t_out, t_out, f"{w[3]} · accélérée ×{round(w[2])}", w])
            if badges and badges[-1][3][0] <= ts < badges[-1][3][1]:
                badges[-1][1] = t_out + dur / speed
            t_out += dur / speed

    concat = Path(a.frames) / "concat.txt"
    with concat.open("w", encoding="utf-8") as f:
        for path, dur in segments:
            f.write(f"file '{path.resolve().as_posix()}'\nduration {dur:.4f}\n")
        f.write(f"file '{segments[-1][0].resolve().as_posix()}'\n")

    draws = []
    for start, end, text, _ in badges:
        safe = text.replace(":", "\\:").replace("'", "’")
        draws.append(f"drawtext=fontfile='{esc(font())}':text='{safe}':fontsize=26:fontcolor=white:"
                     f"box=1:boxcolor=0x1d1d1f@0.86:boxborderw=16:x=w-tw-40:y=h-th-40:enable='between(t,{start:.2f},{end:.2f})'")
    for start, end in titles:
        draws.append(f"drawtext=fontfile='{esc(font())}':text='{JOIN}':fontsize=28:fontcolor=0x1d1d1f:"
                     f"box=1:boxcolor=0xffcc00@0.95:boxborderw=18:x=(w-tw)/2:y=h-th-48:enable='between(t,{start:.2f},{end:.2f})'")
    vf = ",".join(["fps=30", "format=yuv420p", *draws])
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-vf", vf,
                    "-c:v", "libx264", "-preset", "slow", "-crf", "24", "-movflags", "+faststart", str(out)], check=True)
    print(out, f"{t_out:.1f} s", f"{out.stat().st_size / 1e6:.1f} Mo")

    if a.gif:
        gif = Path(a.gif)
        pal = Path(a.frames) / "palette.png"
        scale = "setpts=PTS/1.6,fps=10,scale=960:-1:flags=lanczos"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(out), "-vf", scale + ",palettegen=max_colors=128:stats_mode=diff", str(pal)], check=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(out), "-i", str(pal), "-lavfi",
                        scale + "[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle", str(gif)], check=True)
        print(gif, f"{gif.stat().st_size / 1e6:.1f} Mo")


if __name__ == "__main__":
    main()
