"""
koa_glossary.py — every feature name in one plain-English sentence.

Why this file exists
--------------------
An explainable model that reports `asym_knee_rom_ratio = -0.31` has explained
nothing to the person who has to act on it. The EBM surrogate is only worth
building if its output reads like a clinical note, so the glossary is part of
the model, not documentation: it ships inside the deployment bundle and the
frontend renders from it.

Each entry gives:
  label      short human name, for a chart axis or a table row
  sentence   one line a physiotherapist could read aloud
  unit       degrees / degrees per second / steps per minute / ratio / index
  high_means what a HIGH value indicates clinically
  low_means  what a LOW value indicates clinically
"""
from __future__ import annotations

import re

JOINT = {
    "knee":  ("knee bend", "how far the knee flexes and straightens"),
    "hip":   ("hip swing", "how far the thigh swings forward and back"),
    "ankle": ("ankle angle", "how far the foot pivots at the ankle"),
    "trunk": ("trunk lean", "how far the upper body tips away from upright"),
}
SIDE = {"L": "left", "R": "right", "both": "both legs averaged",
        "left": "left", "right": "right"}

STAT = {
    "mean":     ("average", "the average angle held through the walk"),
    "min":      ("straightest point", "the most extended the joint gets"),
    "max":      ("most bent point", "the most flexed the joint gets"),
    "rom":      ("range of movement", "the total sweep from straightest to most bent"),
    "std":      ("steadiness", "how much the angle varies from stride to stride"),
    "iqr":      ("middle spread", "the spread of the middle half of the angles"),
    "cv":       ("relative variability", "variation measured relative to the average"),
    "p05":      ("low end", "the angle at the bottom 5% of the walk"),
    "p95":      ("high end", "the angle at the top 5% of the walk"),
    "vel_mean": ("average speed of movement", "how quickly the joint angle changes on average"),
    "vel_max":  ("fastest movement", "the quickest the joint angle changes"),
    "acc_mean": ("average smoothness", "how sharply the joint changes direction on average"),
    "acc_max":  ("sharpest change", "the sharpest direction change in the joint"),
}

# What a high value means, per (joint, stat). Only the clinically meaningful
# ones are spelled out; the rest fall back to a neutral phrasing.
DIRECTION = {
    ("knee", "rom"):  ("a freely moving knee", "a stiff knee — the classic OA sign"),
    ("knee", "max"):  ("the knee flexes fully in swing", "the knee never fully bends"),
    ("knee", "min"):  ("the knee never fully straightens — flexion contracture",
                       "the knee straightens normally"),
    ("hip", "rom"):   ("a long, free stride", "a shortened, guarded stride"),
    ("trunk", "mean"): ("the person leans, often to unload a painful knee",
                        "an upright, unguarded posture"),
    ("trunk", "std"): ("an unsteady upper body", "a steady upper body"),
}

SPECIAL = {
    "asym_knee_rom": dict(
        label="Knee range difference, left vs right",
        sentence="How differently the two knees move. Healthy walking is close "
                 "to symmetric; one-sided OA is not.",
        unit="degrees", high_means="one knee is doing much less work than the other",
        low_means="both knees move alike"),
    "asym_knee_rom_ratio": dict(
        label="Knee range ratio (worse / better)",
        sentence="The worse knee's range divided by the better knee's. 1.0 is "
                 "perfectly symmetric; lower means one knee is far stiffer.",
        unit="ratio", high_means="both knees move alike",
        low_means="one knee is markedly stiffer than the other"),
    "asym_knee_rom_worse": dict(
        label="Worse knee's range of movement",
        sentence="The range of the more affected knee — the single number a "
                 "clinician would look at first.",
        unit="degrees", high_means="even the worse knee moves freely",
        low_means="the worse knee is stiff"),
    "asym_knee_rom_better": dict(
        label="Better knee's range of movement",
        sentence="The range of the less affected knee. If this is also reduced, "
                 "the problem is likely bilateral.",
        unit="degrees", high_means="the better knee is unaffected",
        low_means="both knees are stiff — bilateral disease"),
    "asym_knee_corr": dict(
        label="Left-right knee coordination",
        sentence="How closely the two knee-angle traces mirror each other "
                 "through the walk.",
        unit="correlation", high_means="the legs move in a coordinated pattern",
        low_means="the legs have fallen out of step with each other"),
    "rhy_cadence_spm": dict(
        label="Cadence",
        sentence="Steps taken per minute.",
        unit="steps/min", high_means="a brisk, regular step rate",
        low_means="a slow step rate — strongly linked to walking speed, so read "
                  "it alongside the speed control"),
    "rhy_step_len_norm": dict(
        label="Step length, scaled to leg length",
        sentence="How far each step reaches, divided by the person's leg length "
                 "so tall and short people compare fairly.",
        unit="ratio", high_means="a long, confident step",
        low_means="a short, guarded step"),
    "rhy_ankle_sep_amp": dict(
        label="Stride width of the ankle swing",
        sentence="How far apart the ankles get at the widest point of each stride.",
        unit="normalised", high_means="a full stride", low_means="a shuffling stride"),
    "rhy_spectral_sharpness": dict(
        label="Rhythm regularity",
        sentence="How clean and repeating the walking rhythm is. A metronomic "
                 "walk has a sharp peak; a hesitant one is smeared.",
        unit="index", high_means="a regular, metronomic rhythm",
        low_means="an irregular, hesitant rhythm"),
    "var_ankle_sep_sampen": dict(
        label="Stride predictability",
        sentence="Sample entropy of the stride pattern — low means each stride "
                 "closely repeats the last, high means the pattern wanders.",
        unit="index", high_means="strides vary unpredictably",
        low_means="strides repeat closely"),
    "dur_walk_seconds": dict(
        label="Time taken to cross",
        sentence="How long the walk took. CARRIES THE SPEED CONFOUND — excluded "
                 "from every headline model and kept only as a control.",
        unit="seconds", high_means="a slow walk", low_means="a quick walk"),
    "dur_walk_frames": dict(
        label="Clip length in frames",
        sentence="The same thing as the time taken, in frames. CONTROL ONLY.",
        unit="frames", high_means="a long clip", low_means="a short clip"),
}

for side in ("L", "R"):
    SPECIAL[f"var_knee_{side}_sampen"] = dict(
        label=f"{SIDE[side].capitalize()} knee stride predictability",
        sentence=f"How repeatable the {SIDE[side]} knee's bending pattern is "
                 "from stride to stride.",
        unit="index", high_means="the knee pattern wanders between strides",
        low_means="the knee repeats the same pattern each stride")

_KIN = re.compile(r"^kin_(knee|hip|ankle)_(L|R|both)_(.+)$")
_KIN_T = re.compile(r"^kin_(trunk)_(.+)$")
_ASYM = re.compile(r"^asym_(knee|hip|ankle)_(.+)$")
_MOT = re.compile(r"^mot_(\d+)$")


def describe(name: str) -> dict:
    """Feature name -> {label, sentence, unit, high_means, low_means}."""
    if name in SPECIAL:
        return dict(SPECIAL[name], feature=name)

    m = _KIN.match(name) or _KIN_T.match(name)
    if m:
        if m.re is _KIN:
            joint, side, stat = m.group(1), m.group(2), m.group(3)
        else:
            joint, side, stat = "trunk", None, m.group(2)
        jl, jd = JOINT[joint]
        sl, sd = STAT.get(stat, (stat.replace("_", " "), "a summary of the signal"))
        where = f" ({SIDE[side]})" if side else ""
        hi, lo = DIRECTION.get((joint, stat),
                               (f"more {jl.split()[-1]}", f"less {jl.split()[-1]}"))
        unit = ("degrees/s" if stat.startswith("vel") else
                "degrees/s²" if stat.startswith("acc") else
                "ratio" if stat == "cv" else "degrees")
        return dict(feature=name,
                    label=f"{jl.capitalize()}{where} — {sl}",
                    sentence=f"{jd.capitalize()}{where}: {sd}.",
                    unit=unit, high_means=hi, low_means=lo)

    m = _ASYM.match(name)
    if m:
        joint, stat = m.group(1), m.group(2)
        jl, jd = JOINT[joint]
        sl, _ = STAT.get(stat, (stat.replace("_", " "), ""))
        return dict(feature=name,
                    label=f"Left-right difference in {jl} — {sl}",
                    sentence=f"How different the two sides are in {jd} ({sl}). "
                             "Healthy walking is close to symmetric.",
                    unit="degrees", high_means="the two sides move differently",
                    low_means="the two sides move alike")

    m = _MOT.match(name)
    if m:
        return dict(feature=name, label=f"Motion magnitude #{m.group(1)}",
                    sentence="Raw amount of body movement — a SPEED CONTROL "
                             "feature, never part of a headline model.",
                    unit="normalised", high_means="faster, larger movement",
                    low_means="slower, smaller movement")

    return dict(feature=name, label=name, sentence=name, unit="",
                high_means="higher", low_means="lower")


def explain_subject(feature_values: dict, contributions: dict, cohort_median: dict,
                    top_k: int = 5) -> list[str]:
    """Turn one subject's EBM contributions into readable sentences.

    contributions: feature -> signed contribution to the risk score.
    """
    ranked = sorted(contributions.items(), key=lambda kv: -abs(kv[1]))[:top_k]
    out = []
    for feat, contrib in ranked:
        d = describe(feat)
        v = feature_values.get(feat)
        med = cohort_median.get(feat)
        direction = d["high_means"] if (v is not None and med is not None and v >= med) \
            else d["low_means"]
        push = "raises" if contrib > 0 else "lowers"
        val = f"{v:.1f}" if isinstance(v, (int, float)) else "n/a"
        ref = f" against a cohort median of {med:.1f}" if isinstance(med, (int, float)) else ""
        out.append(f"{d['label']}: {val} {d['unit']}{ref} — {direction}. "
                   f"This {push} the estimated risk.")
    return out


if __name__ == "__main__":
    for f in ("kin_knee_L_rom", "kin_knee_R_min", "asym_knee_rom_ratio",
              "rhy_cadence_spm", "kin_trunk_mean", "var_knee_L_sampen",
              "kin_hip_both_vel_mean", "dur_walk_seconds"):
        d = describe(f)
        print(f"{f}\n   {d['label']}  [{d['unit']}]\n   {d['sentence']}"
              f"\n   high -> {d['high_means']}\n   low  -> {d['low_means']}\n")
