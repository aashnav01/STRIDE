"""
koa_deploy.py — one function for the frontend.

    from koa_deploy import KOAScreener
    s = KOAScreener("koa_deployable")
    result = s.score_landmarks("walk.csv")

`result` is JSON-serialisable and contains everything a UI needs:

    {
      "risk": 0.78,                      # 0-1, subject level
      "band": "elevated",                # low / borderline / elevated
      "stage": {                         # the graded answer the brief asks for
        "grade": "moderate",
        "probabilities": {"early": 0.18, "moderate": 0.61, "severe": 0.21},
        "expected_grade": 1.03,          # continuous, good for a progress bar
        "confidence": "within one grade 98.7% of the time in validation"
      },
      "confidence": "moderate",
      "n_windows": 3,
      "measurements": [                  # what was measured, in plain English
        {"label": "Knee bend (left) — range of movement",
         "value": 44.2, "unit": "degrees", "cohort_median": 62.1,
         "reading": "a stiff knee — the classic OA sign"}
      ],
      "reasons": [ "..." ],              # ranked sentences from the surrogate
      "caveats": [ "..." ]               # always shown; never hide these
    }

Input is a MediaPipe landmark CSV in the same format the training data used —
one row per frame, `w_<joint>_<xyz>`, `<joint>_<xy>`, `<joint>_v`, `detected`.
`score_video()` will produce that from an MP4 if mediapipe is installed.
"""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np

import koa_features as KF
import koa_glossary as GL

BANDS = ((0.35, "low"), (0.65, "borderline"), (1.01, "elevated"))


class KOAScreener:
    def __init__(self, bundle_dir="koa_deployable", use_graph=True):
        self.dir = Path(bundle_dir)
        b = joblib.load(self.dir / "koa_model.joblib")
        self.__dict__.update({k: b[k] for k in
                              ("handcrafted_model", "imputer", "features",
                               "w_handcrafted", "ebm", "ebm_imputer",
                               "cohort_medians", "ebm_fidelity", "window",
                               "windows_per_video", "fps", "holdout_metrics")})
        self.severity = None
        sev = self.dir / "koa_severity.joblib"
        if sev.exists():
            self.severity = joblib.load(sev)

        self.graph = None
        if use_graph and (self.dir / "koa_stgcn.pt").exists():
            try:
                self._load_graph()
            except Exception as e:
                print(f"graph streams unavailable ({type(e).__name__}) — "
                      "scoring on handcrafted features alone")

    def _load_graph(self):
        import torch
        import koa_skeleton as KS
        from koa_stgcn import STGCN
        sd = torch.load(self.dir / "koa_stgcn.pt", map_location="cpu")
        self.graph = {}
        for name, state in sd.items():
            m = STGCN(in_ch=3)
            m.load_state_dict(state)
            m.eval()
            self.graph[name] = m
        self._KS = KS
        self._torch = torch

    # -- feature side --------------------------------------------------------
    def _windows(self, csv_path):
        seq = KF.load_sequence(csv_path)
        if seq is None:
            raise ValueError("could not read landmarks — is this the right CSV?")
        sig = KF.build_signals(seq)
        n = len(sig["knee_left"])
        w = self.window
        starts = ([0] if n < w else
                  np.unique(np.linspace(0, n - w, self.windows_per_video)
                            .round().astype(int)).tolist())
        rows = []
        for s in starts:
            sl = slice(s, min(s + w, n))
            rows.append({**KF.window_features(sig, fps=self.fps, sl=sl),
                         **KF.duration_features(sig, self.fps)})
        return rows

    def _graph_prob(self, csv_path):
        if self.graph is None:
            return None
        seq = KF.load_sequence_full(csv_path)
        if seq is None:
            return None
        sk = self._KS.center_and_scale(
            self._KS.mediapipe_to_ntu(seq["world33"]))
        n, w = len(sk), self.window
        starts = ([0] if n < w else
                  np.unique(np.linspace(0, n - w, self.windows_per_video)
                            .round().astype(int)).tolist())
        probs = []
        for s in starts:
            c = sk[s:s + w]
            if len(c) < w:
                c = np.pad(c, ((0, w - len(c)), (0, 0), (0, 0)), mode="edge")
            j = self._KS.to_ctvm(c)[None]
            b = self._KS.bone_stream(self._KS.to_ctvm(c))[None]
            with self._torch.no_grad():
                for name, X in (("joint", j), ("bone", b)):
                    if name in self.graph:
                        logits, _ = self.graph[name](
                            self._torch.tensor(X, dtype=self._torch.float32))
                        probs.append(float(
                            self._torch.softmax(logits, 1)[0, 1]))
        return float(np.mean(probs)) if probs else None

    def _stage(self, df):
        """Ordinal staging: cumulative probabilities, differenced.

        The two stagers give P(grade >= moderate) and P(grade >= severe).
        Differencing them yields grade probabilities that respect the ordering
        by construction, which a softmax over three classes does not.
        """
        if self.severity is None:
            return None
        sv = self.severity
        X = sv["imputer"].transform(
            df.reindex(columns=sv["features"]).to_numpy(float))
        cum = np.column_stack([m.predict_proba(X)[:, 1].mean()
                               for m in sv["stagers"]])[0]
        cum = np.maximum.accumulate(cum[::-1])[::-1]
        grades = sv["grades"]
        P = np.empty(len(grades))
        P[0] = 1.0 - cum[0]
        for t in range(1, len(grades) - 1):
            P[t] = cum[t - 1] - cum[t]
        P[-1] = cum[-1]
        P = np.clip(P, 1e-6, None)
        P = P / P.sum()
        return dict(
            grade=grades[int(P.argmax())],
            probabilities={g: round(float(p), 3) for g, p in zip(grades, P)},
            expected_grade=round(float(P @ np.arange(len(grades))), 2),
            confidence=(f"validation: quadratic weighted kappa "
                        f"{sv['qwk']:.2f}, within one grade "
                        f"{sv['adjacent']:.0%}"),
            note=("Staging is defined within diagnosed knee OA. It is the "
                  "measurement this dataset supports best — unlike the "
                  "screening score, it barely moves when walking speed is "
                  "controlled for (kappa "
                  f"{sv['qwk']:.2f} -> {sv['qwk_speed_controlled']:.2f})."))

    # -- public --------------------------------------------------------------
    def score_landmarks(self, csv_path) -> dict:
        rows = self._windows(csv_path)
        import pandas as pd
        df = pd.DataFrame(rows)
        X = self.imputer.transform(df.reindex(columns=self.features)
                                   .to_numpy(float))
        p_hc = float(np.mean(self.handcrafted_model.predict_proba(X)[:, 1]))

        p_gcn = self._graph_prob(csv_path)
        if p_gcn is None:
            risk, mix = p_hc, "handcrafted only (graph streams not loaded)"
        else:
            risk = self.w_handcrafted * p_hc + (1 - self.w_handcrafted) * p_gcn
            mix = (f"{self.w_handcrafted:.0%} joint-angle features / "
                   f"{1-self.w_handcrafted:.0%} two-stream graph network")

        band = next(name for hi, name in BANDS if risk < hi)
        vals = dict(zip(self.features, np.nanmedian(X, axis=0)))

        reasons, measurements = [], []
        if self.ebm is not None:
            xrow = self.ebm_imputer.transform(
                np.array([vals[f] for f in self.features]).reshape(1, -1))
            loc = self.ebm.explain_local(xrow).data(0)
            contrib = dict(zip(loc["names"], loc["scores"]))
            reasons = GL.explain_subject(vals, contrib, self.cohort_medians,
                                         top_k=5)
            for f, _ in sorted(contrib.items(), key=lambda kv: -abs(kv[1]))[:6]:
                d = GL.describe(f)
                v, med = vals.get(f), self.cohort_medians.get(f)
                measurements.append(dict(
                    label=d["label"], value=(None if v is None else round(float(v), 2)),
                    unit=d["unit"],
                    cohort_median=(None if med is None else round(float(med), 2)),
                    reading=(d["high_means"] if (v is not None and med is not None
                                                 and v >= med) else d["low_means"]),
                    explanation=d["sentence"]))

        return dict(
            risk=round(risk, 3), band=band, stage=self._stage(df),
            components=dict(handcrafted=round(p_hc, 3),
                            graph=(None if p_gcn is None else round(p_gcn, 3)),
                            mix=mix),
            n_windows=len(rows),
            surrogate_fidelity=self.ebm_fidelity,
            measurements=measurements, reasons=reasons,
            caveats=[
                "This is a screening aid, not a diagnosis. Knee osteoarthritis "
                "is diagnosed clinically and radiographically.",
                "Walking speed separates the training groups almost perfectly. "
                "The model was trained with that dependence adversarially "
                "reduced, but it cannot be eliminated from this dataset.",
                "Trained on 80 adults recorded with a fixed DSLR in one clinic. "
                "Phone-camera and field performance are untested.",
                "The healthy training group averaged 43.7 years against 56.8 "
                "for patients. Results in that age gap should be read with care.",
            ])

    def score_video(self, mp4_path, out_csv=None) -> dict:
        """Convenience: MP4 -> landmarks -> score. Needs mediapipe installed."""
        import extract_pose
        out_csv = out_csv or (str(mp4_path) + ".csv")
        extract_pose.extract(mp4_path, out_csv)
        return self.score_landmarks(out_csv)


if __name__ == "__main__":
    import sys
    s = KOAScreener(sys.argv[1] if len(sys.argv) > 1 else "koa_deployable")
    if len(sys.argv) > 2:
        print(json.dumps(s.score_landmarks(sys.argv[2]), indent=2))
    else:
        print("loaded. held-out metrics:", s.holdout_metrics)
        print(f"features: {len(s.features)}  surrogate fidelity: {s.ebm_fidelity}")
        print("severity staging:", "loaded" if s.severity else "not built yet")
