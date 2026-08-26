"""
koa_features.py — gait features for knee-OA screening from MediaPipe landmarks.

Design decisions, and why
-------------------------
* **World coordinates for angles.** MediaPipe's world landmarks are metric and
  hip-centred, so a joint angle computed from them is invariant to where the
  person stands in frame and how far they are from the camera. Image coordinates
  are not.
* **Sagittal only.** Markerless capture is reliable in the sagittal plane
  (ICC 0.93) and poor in frontal/transverse (0.50/0.34) — West China J Biomech
  validation. Every headline feature here is a sagittal quantity.
* **Fixed-length windows.** Healthy subjects cross this dataset's walkway in a
  median 2.4 s and KOA subjects in 7.1 s, which alone gives AUC 0.982. Windows
  of identical length remove that shortcut so the model must use kinematics.
  Duration is still computed, but kept in its own group so it can be included
  or excluded deliberately.
* **Cadence from the spectrum, not from event detection.** Heel-strike detection
  on noisy markerless data is brittle; the dominant frequency of the ankle
  separation signal is not.

Feature groups (see FEATURE_GROUPS): each name is prefixed so you can select or
ablate a whole group by prefix.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

import numpy as np

# --------------------------------------------------------------------------
# landmark plumbing
# --------------------------------------------------------------------------

JOINTS = [
    "left_shoulder", "right_shoulder", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle",
    "left_heel", "right_heel", "left_foot_index", "right_foot_index",
]

VIS_MIN = 0.30        # below this a landmark is treated as missing
MAX_GAP = 5           # frames; longer gaps are left as NaN rather than invented


def load_sequence(csv_path: str | Path) -> dict | None:
    """Read one landmark CSV into arrays. Returns None if unusable.

    Returns dict with:
      frame  (N,)          original frame index of each detected row
      world  (N, J, 3)     metric coords, hip-centred
      img    (N, J, 2)     normalised image coords
      vis    (N, J)        visibility
    """
    path = Path(csv_path)
    if not path.exists():
        return None

    frames, world, img, vis = [], [], [], []
    with path.open() as fh:
        for row in csv.DictReader(fh):
            if row.get("detected") != "1":
                continue
            try:
                w = [[float(row[f"w_{j}_{c}"]) for c in "xyz"] for j in JOINTS]
                p = [[float(row[f"{j}_x"]), float(row[f"{j}_y"])] for j in JOINTS]
                v = [float(row[f"{j}_v"]) for j in JOINTS]
            except (KeyError, TypeError, ValueError):
                continue
            frames.append(int(row["frame"]))
            world.append(w)
            img.append(p)
            vis.append(v)

    if len(frames) < 10:
        return None

    return {
        "frame": np.asarray(frames, dtype=int),
        "world": np.asarray(world, dtype=np.float32),
        "img": np.asarray(img, dtype=np.float32),
        "vis": np.asarray(vis, dtype=np.float32),
    }


IDX = {j: i for i, j in enumerate(JOINTS)}


def _angle(a, b, c):
    """Interior angle at b, in degrees. Vectorised over the leading axis."""
    v1, v2 = a - b, c - b
    n1 = np.linalg.norm(v1, axis=-1)
    n2 = np.linalg.norm(v2, axis=-1)
    denom = np.maximum(n1 * n2, 1e-8)
    cos = np.clip(np.sum(v1 * v2, axis=-1) / denom, -1.0, 1.0)
    return np.degrees(np.arccos(cos))


def _interp_nans(x: np.ndarray, max_gap: int = MAX_GAP) -> np.ndarray:
    """Linear-interpolate NaN runs up to max_gap; leave longer runs as NaN."""
    x = x.astype(np.float64).copy()
    n = len(x)
    isn = np.isnan(x)
    if not isn.any() or isn.all():
        return x
    idx = np.arange(n)
    good = ~isn
    # find runs of NaN
    starts = np.where(isn & ~np.r_[False, isn[:-1]])[0]
    ends = np.where(isn & ~np.r_[isn[1:], False])[0]
    filled = np.interp(idx, idx[good], x[good])
    for s, e in zip(starts, ends):
        if (e - s + 1) <= max_gap and s > 0 and e < n - 1:
            x[s:e + 1] = filled[s:e + 1]
    return x


def build_signals(seq: dict) -> dict:
    """Per-frame biomechanical signals. Low-visibility joints become NaN."""
    W, V, P = seq["world"], seq["vis"], seq["img"]

    def w(j):
        a = W[:, IDX[j], :].copy()
        a[V[:, IDX[j]] < VIS_MIN] = np.nan
        return a

    sig = {}

    # --- knee flexion: interior angle hip-knee-ankle.
    # 180 deg = fully extended, so flexion = 180 - angle.
    for side in ("left", "right"):
        knee = 180.0 - _angle(w(f"{side}_hip"), w(f"{side}_knee"), w(f"{side}_ankle"))
        sig[f"knee_{side}"] = _interp_nans(knee)

        # --- hip flexion: shoulder-hip-knee
        hip = 180.0 - _angle(w(f"{side}_shoulder"), w(f"{side}_hip"), w(f"{side}_knee"))
        sig[f"hip_{side}"] = _interp_nans(hip)

        # --- ankle: knee-ankle-foot_index
        ank = _angle(w(f"{side}_knee"), w(f"{side}_ankle"), w(f"{side}_foot_index"))
        sig[f"ankle_{side}"] = _interp_nans(ank)

    # --- trunk lean: angle of the shoulder-midpoint-to-hip-midpoint axis
    #     away from vertical, in the world frame.
    sh = (w("left_shoulder") + w("right_shoulder")) / 2.0
    hp = (w("left_hip") + w("right_hip")) / 2.0
    axis = sh - hp
    vert = np.zeros_like(axis); vert[:, 1] = -1.0        # world y points down
    nrm = np.maximum(np.linalg.norm(axis, axis=-1), 1e-8)
    cos = np.clip(np.sum(axis * vert, axis=-1) / nrm, -1.0, 1.0)
    sig["trunk_lean"] = _interp_nans(np.degrees(np.arccos(cos)))

    # --- direction of travel, from the hip midpoint in IMAGE space
    hip_img = (P[:, IDX["left_hip"], :] + P[:, IDX["right_hip"], :]) / 2.0
    sig["_hip_img_x"] = hip_img[:, 0]
    drift = hip_img[-1, 0] - hip_img[0, 0]
    sig["_direction"] = 1.0 if drift >= 0 else -1.0

    # --- ankle separation along the travel axis: the cadence carrier.
    #     Signed so it oscillates about zero once per step.
    la = P[:, IDX["left_ankle"], 0]
    ra = P[:, IDX["right_ankle"], 0]
    sig["ankle_sep"] = _interp_nans((la - ra) * sig["_direction"])

    # --- leg length, for normalising spatial measures
    # median over both legs, so one badly-tracked side can't wipe it out
    legs = []
    for side in ("left", "right"):
        fem = np.linalg.norm(w(f"{side}_hip") - w(f"{side}_knee"), axis=-1)
        tib = np.linalg.norm(w(f"{side}_knee") - w(f"{side}_ankle"), axis=-1)
        legs.append(fem + tib)
    allleg = np.concatenate(legs)
    allleg = allleg[np.isfinite(allleg)]
    med = float(np.median(allleg)) if allleg.size else 0.0
    sig["_leg_len"] = med if 0.3 < med < 1.5 else 0.8   # fall back to a plausible adult leg

    return sig


# --------------------------------------------------------------------------
# feature computation
# --------------------------------------------------------------------------

def _stats(x: np.ndarray, prefix: str) -> dict:
    """Distribution + derivative summary of one signal."""
    x = np.asarray(x, dtype=np.float64)
    x = x[np.isfinite(x)]
    out = {}
    if len(x) < 5:
        for k in ("mean", "std", "min", "max", "rom", "p05", "p95", "iqr",
                  "vel_mean", "vel_max", "acc_mean", "acc_max", "cv"):
            out[f"{prefix}_{k}"] = np.nan
        return out
    d1, d2 = np.diff(x), np.diff(x, 2)
    out[f"{prefix}_mean"] = float(np.mean(x))
    out[f"{prefix}_std"] = float(np.std(x))
    out[f"{prefix}_min"] = float(np.min(x))
    out[f"{prefix}_max"] = float(np.max(x))
    out[f"{prefix}_rom"] = float(np.max(x) - np.min(x))
    out[f"{prefix}_p05"] = float(np.percentile(x, 5))
    out[f"{prefix}_p95"] = float(np.percentile(x, 95))
    out[f"{prefix}_iqr"] = float(np.percentile(x, 75) - np.percentile(x, 25))
    out[f"{prefix}_vel_mean"] = float(np.mean(np.abs(d1)))
    out[f"{prefix}_vel_max"] = float(np.max(np.abs(d1)))
    out[f"{prefix}_acc_mean"] = float(np.mean(np.abs(d2))) if len(d2) else np.nan
    out[f"{prefix}_acc_max"] = float(np.max(np.abs(d2))) if len(d2) else np.nan
    out[f"{prefix}_cv"] = float(np.std(x) / max(abs(np.mean(x)), 1e-6))
    return out


def _sample_entropy(x, m=2, r_factor=0.2):
    """Regularity of the signal. Lower = more repeatable gait."""
    x = np.asarray(x, dtype=np.float64)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 30:
        return np.nan
    if n > 300:                        # subsample: O(n^2)
        x = x[np.linspace(0, n - 1, 300).astype(int)]
        n = 300
    r = r_factor * np.std(x)
    if r <= 0:
        return np.nan

    def _count(mm):
        tmpl = np.lib.stride_tricks.sliding_window_view(x, mm)
        d = np.abs(tmpl[:, None, :] - tmpl[None, :, :]).max(axis=2)
        np.fill_diagonal(d, np.inf)
        return float((d <= r).sum())

    a, b = _count(m + 1), _count(m)
    if a == 0 or b == 0:
        return np.nan
    return float(-math.log(a / b))


def _dominant_freq(x, fps):
    """Step frequency from the ankle-separation spectrum.

    Robust where discrete heel-strike detection is not. Returns
    (steps_per_min, spectral_peak_sharpness).
    """
    x = np.asarray(x, dtype=np.float64)
    x = x[np.isfinite(x)]
    if len(x) < 24:
        return np.nan, np.nan
    x = x - x.mean()
    x = x * np.hanning(len(x))
    n = 1 << int(np.ceil(np.log2(len(x) * 4)))
    spec = np.abs(np.fft.rfft(x, n=n))
    freq = np.fft.rfftfreq(n, d=1.0 / fps)
    band = (freq >= 0.3) & (freq <= 3.0)       # plausible step rates
    if not band.any():
        return np.nan, np.nan
    s, f = spec[band], freq[band]
    k = int(np.argmax(s))
    peak_f = float(f[k])
    sharpness = float(s[k] / max(np.mean(s), 1e-9))
    return peak_f * 60.0, sharpness


def _asym(a: float, b: float) -> float:
    """Symmetry index, percent. 0 = symmetric."""
    if not (np.isfinite(a) and np.isfinite(b)):
        return np.nan
    denom = max(abs(a) + abs(b), 1e-6) / 2.0
    return float(abs(a - b) / denom * 100.0)


def window_features(sig: dict, fps: float = 25.0, sl: slice | None = None) -> dict:
    """All features for one window of one walk."""
    if sl is None:
        sl = slice(None)

    def g(k):
        return np.asarray(sig[k], dtype=np.float64)[sl]

    f: dict = {}

    # ---- kinematic distributions, per side and averaged -------------------
    for joint in ("knee", "hip", "ankle"):
        L, R = g(f"{joint}_left"), g(f"{joint}_right")
        f.update(_stats(L, f"kin_{joint}_L"))
        f.update(_stats(R, f"kin_{joint}_R"))
        both = np.concatenate([L, R])
        f.update(_stats(both, f"kin_{joint}_both"))

    f.update(_stats(g("trunk_lean"), "kin_trunk"))

    # ---- asymmetry --------------------------------------------------------
    for joint in ("knee", "hip", "ankle"):
        L, R = g(f"{joint}_left"), g(f"{joint}_right")
        Lf, Rf = L[np.isfinite(L)], R[np.isfinite(R)]
        if len(Lf) > 4 and len(Rf) > 4:
            f[f"asym_{joint}_rom"] = _asym(Lf.max() - Lf.min(), Rf.max() - Rf.min())
            f[f"asym_{joint}_mean"] = _asym(Lf.mean(), Rf.mean())
            f[f"asym_{joint}_max"] = _asym(Lf.max(), Rf.max())
            f[f"asym_{joint}_min"] = _asym(Lf.min(), Rf.min())
            n = min(len(L), len(R))
            m = np.isfinite(L[:n]) & np.isfinite(R[:n])
            f[f"asym_{joint}_corr"] = (float(np.corrcoef(L[:n][m], R[:n][m])[0, 1])
                                       if m.sum() > 8 else np.nan)
        else:
            for k in ("rom", "mean", "max", "min", "corr"):
                f[f"asym_{joint}_{k}"] = np.nan

    # worse-vs-better leg: which side is more affected is unknown a priori,
    # so order by ROM rather than by anatomical side.
    kL, kR = g("knee_left"), g("knee_right")
    kL, kR = kL[np.isfinite(kL)], kR[np.isfinite(kR)]
    if len(kL) > 4 and len(kR) > 4:
        romL, romR = kL.max() - kL.min(), kR.max() - kR.min()
        f["asym_knee_rom_worse"] = float(min(romL, romR))
        f["asym_knee_rom_better"] = float(max(romL, romR))
        f["asym_knee_rom_ratio"] = float(min(romL, romR) / max(max(romL, romR), 1e-6))
    else:
        f["asym_knee_rom_worse"] = f["asym_knee_rom_better"] = np.nan
        f["asym_knee_rom_ratio"] = np.nan

    # ---- rhythm -----------------------------------------------------------
    cad, sharp = _dominant_freq(g("ankle_sep"), fps)
    f["rhy_cadence_spm"] = cad
    f["rhy_spectral_sharpness"] = sharp
    sep = g("ankle_sep")
    sepf = sep[np.isfinite(sep)]
    f["rhy_ankle_sep_amp"] = float(np.percentile(sepf, 95) - np.percentile(sepf, 5)) \
        if len(sepf) > 5 else np.nan
    leg = sig.get("_leg_len", 0.8) or 0.8
    f["rhy_step_len_norm"] = (f["rhy_ankle_sep_amp"] / leg
                              if np.isfinite(f["rhy_ankle_sep_amp"]) else np.nan)

    # ---- variability / regularity ----------------------------------------
    f["var_knee_L_sampen"] = _sample_entropy(g("knee_left"))
    f["var_knee_R_sampen"] = _sample_entropy(g("knee_right"))
    f["var_ankle_sep_sampen"] = _sample_entropy(g("ankle_sep"))

    return f


# Group prefixes, so a whole family can be ablated by name.
FEATURE_GROUPS = {
    "kin": "sagittal joint-angle distributions",
    "asym": "left-right asymmetry",
    "rhy": "cadence and step length",
    "var": "gait variability / regularity",
    "dur": "walk duration (the confound — excluded by default)",
}


def duration_features(sig: dict, fps: float = 25.0) -> dict:
    """Kept apart from everything else, on purpose.

    Walk duration alone reaches AUC 0.982 on this dataset, and 8 m in the
    healthy median of 2.4 s implies 3.3 m/s, which is running. The separation
    is therefore substantially an artefact of how clips were recorded. Include
    these only to quantify the shortcut, never in the headline model.
    """
    n = len(np.asarray(sig["knee_left"]))
    return {
        "dur_walk_seconds": n / fps,
        "dur_walk_frames": float(n),
    }


ALL_33 = [
    "nose","left_eye_inner","left_eye","left_eye_outer","right_eye_inner",
    "right_eye","right_eye_outer","left_ear","right_ear","mouth_left",
    "mouth_right","left_shoulder","right_shoulder","left_elbow","right_elbow",
    "left_wrist","right_wrist","left_pinky","right_pinky","left_index",
    "right_index","left_thumb","right_thumb","left_hip","right_hip",
    "left_knee","right_knee","left_ankle","right_ankle","left_heel",
    "right_heel","left_foot_index","right_foot_index",
]


def load_sequence_full(csv_path):
    """All 33 world landmarks, for the GCN branch. Returns None if unusable."""
    path = Path(csv_path)
    if not path.exists():
        return None
    w33, v33 = [], []
    with path.open() as fh:
        for row in csv.DictReader(fh):
            if row.get("detected") != "1":
                continue
            try:
                w33.append([[float(row[f"w_{j}_{c}"]) for c in "xyz"] for j in ALL_33])
                v33.append([float(row[f"{j}_v"]) for j in ALL_33])
            except (KeyError, TypeError, ValueError):
                continue
    if len(w33) < 10:
        return None
    return {"world33": np.asarray(w33, dtype=np.float32),
            "vis33": np.asarray(v33, dtype=np.float32)}
