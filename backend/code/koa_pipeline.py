"""
koa_pipeline.py — dataset assembly, the locked hold-out split, and evaluation.

The hold-out contract
---------------------
20% of SUBJECTS are split off once, by seed, stratified on class and severity,
and written to holdout_split.json. Nothing in development may read them. The
split is on subjects, never on videos or windows: the same person's two
sequences must never straddle the wall.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

import koa_features as KF

FPS = 25.0            # 50 fps source extracted at stride 2
WINDOW = 48           # frames (~1.9 s) — fits inside the 10th-percentile walk
WINDOWS_PER_VIDEO = 3 # fixed count per video — see build_windows()
MIN_FRAMES = 30       # shorter than this and there is no usable gait

NAME_RE = re.compile(
    r"^(?P<subject>\d{1,4})_(?P<cls>KOA|PD|NM)_(?P<seq>\d{1,2})"
    r"(?:_(?P<sev>EL|ML|MD|SV))?$", re.IGNORECASE)
SEV = {"el": "early", "ml": "early", "md": "moderate", "sv": "severe"}


def parse_rel(rel: str) -> dict | None:
    m = NAME_RE.match(Path(rel).stem.replace(".MOV", ""))
    if not m:
        return None
    cls = m.group("cls").upper()
    sev = SEV.get((m.group("sev") or "").lower(), "")
    num = int(m.group("subject"))
    return {
        "subject_id": f"{cls}_{sev.upper()[:2] or ''}_{num:03d}".replace("__", "_"),
        "cls": cls,
        "severity": sev,
        "seq": m.group("seq").lstrip("0"),
        "direction": {"1": "l2r", "2": "r2l"}.get(m.group("seq").lstrip("0"), ""),
    }


# --------------------------------------------------------------------------
# dataset
# --------------------------------------------------------------------------

def build_windows(landmarks_dir: str | Path, keep_classes=("KOA", "NM"),
                  window=WINDOW, windows_per_video=3, verbose=True) -> pd.DataFrame:
    """One row per window: features + labels + provenance."""
    root = Path(landmarks_dir)
    csvs = sorted(root.rglob("*.csv"))
    if verbose:
        print(f"{len(csvs)} landmark CSVs under {root}")

    rows, skipped = [], Counter()
    for p in csvs:
        rel = str(p.relative_to(root))
        meta = parse_rel(rel)
        if meta is None:
            skipped["unparsed"] += 1
            continue
        if meta["cls"] not in keep_classes:
            skipped["other_class"] += 1
            continue

        seq = KF.load_sequence(p)
        if seq is None:
            skipped["unreadable"] += 1
            continue

        sig = KF.build_signals(seq)
        n = len(sig["knee_left"])
        if n < MIN_FRAMES:
            skipped["too_short"] += 1
            continue

        dur = KF.duration_features(sig, FPS)

        # FIXED number of windows per video, evenly spaced.
        #
        # Sliding at a fixed hop looks natural but silently reintroduces the
        # confound: KOA walks are ~3x longer, so they yield ~3x more windows,
        # and window COUNT encodes duration even though window LENGTH doesn't.
        # Measured: 694 KOA vs 79 NM windows at hop=24, an 8.8:1 ratio against
        # a true subject ratio of 1.7:1. Taking the same count from every video
        # removes it and makes subject-level averaging fair.
        #
        # Cadence measured *inside* a fixed window is still legitimate
        # physiology — slow walking is a real OA sign. Total clip length is
        # not; it is an artefact of how these clips were recorded.
        if n >= window:
            last = n - window
            starts = ([0] if windows_per_video == 1 else
                      np.unique(np.linspace(0, last, windows_per_video)
                                .round().astype(int)).tolist())
        else:
            starts = [0]
        for wi, s in enumerate(starts):
            sl = slice(s, min(s + window, n))
            feats = KF.window_features(sig, fps=FPS, sl=sl)
            rows.append({
                "relpath": rel,
                "subject_id": meta["subject_id"],
                "cls": meta["cls"],
                "severity": meta["severity"],
                "direction": meta["direction"],
                "window_index": wi,
                "window_frames": sl.stop - sl.start,
                "n_windows_this_video": len(starts),
                "is_short": int((sl.stop - sl.start) < window),
                "y": int(meta["cls"] == "KOA"),
                **feats, **dur,
            })

    df = pd.DataFrame(rows)
    if verbose:
        print(f"windows: {len(df)}  videos: {df.relpath.nunique()}  "
              f"subjects: {df.subject_id.nunique()}")
        if skipped:
            print("skipped:", dict(skipped))
    return df


def feature_columns(df: pd.DataFrame, groups=("kin", "asym", "rhy", "var")) -> list[str]:
    """Feature names in the requested groups. 'dur' is opt-in by design."""
    return [c for c in df.columns if c.split("_")[0] in groups]


# --------------------------------------------------------------------------
# the locked hold-out
# --------------------------------------------------------------------------

def make_holdout(df: pd.DataFrame, test_frac=0.20, seed=20260822,
                 path="holdout_split.json", verbose=True) -> dict:
    """Split SUBJECTS, stratified on class+severity. Write once, never peek.

    If the file already exists it is loaded rather than regenerated — so the
    hold-out cannot silently change when you re-run with a different seed.
    """
    p = Path(path)
    if p.exists():
        split = json.loads(p.read_text())
        if verbose:
            print(f"loaded existing hold-out from {p} "
                  f"({len(split['test_subjects'])} test subjects) — not regenerated")
        return split

    subj = (df.groupby("subject_id")
              .agg(cls=("cls", "first"), severity=("severity", "first"))
              .reset_index())
    subj["stratum"] = subj.cls + "_" + subj.severity.replace("", "none")

    rng = np.random.default_rng(seed)
    test = []
    for stratum, grp in subj.groupby("stratum"):
        ids = grp.subject_id.to_numpy()
        rng.shuffle(ids)
        k = max(1, int(round(len(ids) * test_frac)))
        test.extend(ids[:k].tolist())

    test = sorted(test)
    train = sorted(set(subj.subject_id) - set(test))
    split = {
        "seed": seed, "test_frac": test_frac,
        "train_subjects": train, "test_subjects": test,
        "note": ("Subject-level hold-out, stratified on class+severity. "
                 "Never used for model selection, feature selection, "
                 "threshold choice or hyperparameters."),
    }
    p.write_text(json.dumps(split, indent=2))

    if verbose:
        print(f"wrote {p}")
        print(f"  train subjects: {len(train)}   test subjects: {len(test)}")
        for name, ids in (("train", train), ("test", test)):
            c = Counter(subj.set_index('subject_id').loc[ids, 'stratum'])
            print(f"  {name}: {dict(sorted(c.items()))}")
    return split


def apply_split(df: pd.DataFrame, split: dict):
    tr = df[df.subject_id.isin(split["train_subjects"])].reset_index(drop=True)
    te = df[df.subject_id.isin(split["test_subjects"])].reset_index(drop=True)
    assert not set(tr.subject_id) & set(te.subject_id), "subject leak across the wall"
    return tr, te


# --------------------------------------------------------------------------
# evaluation
# --------------------------------------------------------------------------

def to_subject(prob: np.ndarray, y: np.ndarray, groups: np.ndarray):
    """Average window probabilities within a subject. Screening decides on a
    person, not on a two-second clip."""
    order = sorted(set(groups))
    p = np.array([prob[groups == g].mean() for g in order])
    yy = np.array([y[groups == g][0] for g in order])
    return p, yy, np.array(order)


def metrics(y, p, thr=0.5) -> dict:
    from sklearn.metrics import (roc_auc_score, accuracy_score, f1_score,
                                 confusion_matrix, average_precision_score)
    yhat = (p >= thr).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, yhat, labels=[0, 1]).ravel()
    return {
        "auc": float(roc_auc_score(y, p)) if len(set(y)) > 1 else np.nan,
        "ap": float(average_precision_score(y, p)) if len(set(y)) > 1 else np.nan,
        "acc": float(accuracy_score(y, yhat)),
        "f1": float(f1_score(y, yhat, zero_division=0)),
        "sensitivity": float(tp / max(tp + fn, 1)),
        "specificity": float(tn / max(tn + fp, 1)),
        "n": int(len(y)), "tp": int(tp), "fp": int(fp), "tn": int(tn), "fn": int(fn),
    }


def cv_evaluate(df: pd.DataFrame, feat_cols: list[str], model_fn,
                n_splits=5, seeds=(42, 123, 2024), verbose=True) -> dict:
    """Subject-wise stratified group CV, repeated over seeds.

    Returns per-seed subject-level metrics and the pooled OOF predictions of
    the first seed (used downstream as the EBM teacher).
    """
    from sklearn.model_selection import StratifiedGroupKFold

    X = df[feat_cols].to_numpy(dtype=np.float64)
    y = df["y"].to_numpy()
    g = df["subject_id"].to_numpy()

    per_seed, oof_first = [], None
    for si, seed in enumerate(seeds):
        oof = np.full(len(df), np.nan)
        cv = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
        for tr, te in cv.split(X, y, groups=g):
            assert not set(g[tr]) & set(g[te])
            oof[te] = model_fn(X[tr], y[tr], X[te], seed)
        sp, sy, _ = to_subject(oof, y, g)
        m = metrics(sy, sp)
        m["seed"] = seed
        per_seed.append(m)
        if si == 0:
            oof_first = oof
        if verbose:
            print(f"  seed {seed}: AUC {m['auc']:.3f}  acc {m['acc']:.3f}  "
                  f"sens {m['sensitivity']:.3f}  spec {m['specificity']:.3f}")

    agg = {k: (float(np.mean([m[k] for m in per_seed])),
               float(np.std([m[k] for m in per_seed])))
           for k in ("auc", "acc", "sensitivity", "specificity", "f1")}
    if verbose:
        print(f"  → AUC {agg['auc'][0]:.3f} ± {agg['auc'][1]:.3f} | "
              f"acc {agg['acc'][0]:.3f} ± {agg['acc'][1]:.3f}")
    return {"per_seed": per_seed, "agg": agg, "oof": oof_first}


# --------------------------------------------------------------------------
# models
# --------------------------------------------------------------------------

def make_gbm(n_estimators=400, max_depth=3, lr=0.03):
    """Gradient-boosted trees with median imputation and class balancing.

    max_depth 3 and heavy regularisation on purpose: 80 subjects is small and
    deep trees will memorise individuals.
    """
    def fit_predict(Xtr, ytr, Xte, seed):
        from sklearn.ensemble import HistGradientBoostingClassifier
        from sklearn.impute import SimpleImputer
        from sklearn.pipeline import make_pipeline
        from sklearn.utils.class_weight import compute_sample_weight

        imp = SimpleImputer(strategy="median")
        Xtr_i, Xte_i = imp.fit_transform(Xtr), imp.transform(Xte)
        clf = HistGradientBoostingClassifier(
            max_iter=n_estimators, max_depth=max_depth, learning_rate=lr,
            l2_regularization=1.0, min_samples_leaf=20,
            early_stopping=False, random_state=seed)
        clf.fit(Xtr_i, ytr,
                sample_weight=compute_sample_weight("balanced", ytr))
        return clf.predict_proba(Xte_i)[:, 1]
    return fit_predict


def make_logistic():
    """Linear baseline — if trees don't beat this, the signal is simple."""
    def fit_predict(Xtr, ytr, Xte, seed):
        from sklearn.impute import SimpleImputer
        from sklearn.preprocessing import StandardScaler
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import make_pipeline
        pipe = make_pipeline(
            SimpleImputer(strategy="median"), StandardScaler(),
            LogisticRegression(max_iter=2000, C=0.1, class_weight="balanced",
                               random_state=seed))
        pipe.fit(Xtr, ytr)
        return pipe.predict_proba(Xte)[:, 1]
    return fit_predict
