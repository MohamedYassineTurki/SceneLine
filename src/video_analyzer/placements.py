"""Find visually stable, low-texture regions across the frames of each shot."""

import cv2
import numpy as np


def find_placements(source, shots):
    video = cv2.VideoCapture(str(source))
    if not video.isOpened():
        raise ValueError("Impossible de lire la vidéo pour détecter les emplacements.")
    candidates = []
    try:
        for shot in shots:
            start = shot["start_ms"] + 250
            end = shot["end_ms"] - 250
            if end - start < 2500:
                continue
            frames = []
            for time in range(start, end + 1, 500):
                video.set(cv2.CAP_PROP_POS_MSEC, time)
                ok, frame = video.read()
                if not ok:
                    break
                frame = cv2.resize(frame, (320, 180), interpolation=cv2.INTER_AREA)
                frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
            if len(frames) < 6:
                continue
            pixels = np.stack(frames).astype(np.float32)
            motion = np.abs(np.diff(pixels, axis=0))
            edges = np.stack([cv2.Canny(frame, 45, 110) > 0 for frame in frames])
            # A nearly uniform image gives insufficient evidence of an in-scene surface.
            if np.mean(edges) < 0.035:
                continue
            regions = []
            for x in [16, 40, 64, 208, 232, 256]:
                for y in range(18, 127, 18):
                    patch = (slice(y, y + 36), slice(x, x + 48))
                    edge_fraction = float(edges[:, patch[0], patch[1]].mean())
                    max_change = float(motion[:, patch[0], patch[1]].mean(axis=(1, 2)).max())
                    contrast = float(pixels[:, patch[0], patch[1]].std(axis=(1, 2)).mean())
                    if edge_fraction > 0.12 or max_change > 9 or contrast < 4:
                        continue
                    score = max_change / 9 + edge_fraction / 0.12
                    regions.append((score, x, y, max_change, edge_fraction))
            if not regions:
                continue
            score, x, y, max_change, edge_fraction = min(regions)
            candidates.append({
                "shot_id": shot["id"],
                "start_ms": start,
                "end_ms": start + 500 * (len(frames) - 1),
                "reference_frame": shot["frame"],
                "region": {"x": x / 320, "y": y / 180, "width": 48 / 320, "height": 36 / 180},
                "type": "flat_graphic_candidate",
                "evidence": {
                    "sampled_frames": len(frames),
                    "max_mean_pixel_change": round(max_change, 2),
                    "edge_fraction": round(edge_fraction, 3),
                },
                "visual_rank_cost": round(score, 3),
                "review_required": ["surface réelle", "contexte narratif et culturel", "occultation entre les images échantillonnées"],
            })
    finally:
        video.release()
    return sorted(candidates, key=lambda candidate: candidate["visual_rank_cost"])
