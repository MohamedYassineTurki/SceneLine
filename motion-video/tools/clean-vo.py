# Retire le souffle parasite que Gemini TTS ajoute au début et à la fin de chaque fichier
# (environ 0,2 s de bruit blanc presque à pleine puissance), puis ajoute un fondu court.
# Usage : .venv/Scripts/python.exe -I motion-video/tools/clean-vo.py fichier.wav [...]   (réécrit les fichiers)
import subprocess, sys
import numpy as np

SR = 24000
HOP = 240  # 10 ms


def flat_rms(w):
    s = np.abs(np.fft.rfft(w * np.hanning(len(w)))) + 1e-9
    return np.exp(np.log(s).mean()) / s.mean(), np.sqrt((w ** 2).mean())


def is_noise(w):
    fl, r = flat_rms(w)
    return fl > 0.55 and r > 10 ** (-30 / 20)


for f in sys.argv[1:]:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", f, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"], capture_output=True).stdout
    a = np.frombuffer(raw, np.float32).copy()
    # fin : on remonte tant que les fenêtres sont du bruit blanc ou du silence
    end = len(a)
    while end - 2 * HOP > 0:
        w = a[end - 2 * HOP:end]
        fl, r = flat_rms(w)
        if is_noise(w) or r < 10 ** (-45 / 20):
            end -= HOP
        else:
            break
    # début : idem
    start = 0
    while start + 2 * HOP < end:
        w = a[start:start + 2 * HOP]
        fl, r = flat_rms(w)
        if is_noise(w) or r < 10 ** (-45 / 20):
            start += HOP
        else:
            break
    start = max(0, start - HOP)
    a = a[start:end]
    fi, fo = int(0.01 * SR), int(0.04 * SR)
    a[:fi] *= np.linspace(0, 1, fi)
    a[-fo:] *= np.linspace(1, 0, fo)
    a = np.concatenate([a, np.zeros(int(0.15 * SR), np.float32)])  # petite respiration
    pcm = (np.clip(a, -1, 1) * 32767).astype("<i2").tobytes()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "s16le", "-ar", str(SR), "-ac", "1", "-i", "-", f], input=pcm, check=True)
    print(f"{f.replace(chr(92), '/').split('/')[-1]}: coupé {start / SR:.2f} s au début, {(len(raw) // 4 - end) / SR:.2f} s à la fin -> {len(a) / SR:.2f} s")
