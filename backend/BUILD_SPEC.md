# Knee OA screener — frontend build spec

Two pieces, split the way Aashna described:

```
   PHONE (browser, no app store)              LAPTOP (Flask + the model)
 ┌──────────────────────────────┐          ┌────────────────────────────────┐
 │ capture.html                 │  POST    │ /api/session                   │
 │  • camera → MediaPipe Tasks  │ ───────► │  stores landmarks              │
 │    Vision (JS, runs on phone)│  JSON    │  scores with koa_deploy        │
 │  • records 33 landmarks/frame│          │  returns risk + stage + reasons│
 │  • no model, no scoring      │ ◄─────── │                                │
 └──────────────────────────────┘  result  │ dashboard.html                 │
                                            │  • session list, full result   │
                                            │  • "Download report" → PDF     │
                                            └────────────────────────────────┘
```

The phone never sees the model. It only produces landmarks. That keeps the
phone side to one static HTML file and means a teammate can build it without
touching Python.

---

## 1. Files to copy out of `koa_results.zip`

Put these in the backend folder. They are the model and everything it needs.

| From the zip | What it is | Needed by |
|---|---|---|
| `deployable/koa_model.joblib` | fused screening model + imputer + surrogate EBM + cohort medians | scoring |
| `deployable/koa_severity.joblib` | ordinal staging model (early/moderate/severe) | staging |
| `deployable/koa_stgcn.pt` | two-stream graph weights | optional, see §6 |
| `deployable/feature_glossary.json` | every feature in plain English | the report |
| `code/koa_deploy.py` | **the only file you call** | everything |
| `code/koa_features.py` | landmark CSV → 155 gait features | imported by koa_deploy |
| `code/koa_glossary.py` | plain-language rendering | imported by koa_deploy |
| `code/koa_skeleton.py` | MediaPipe-33 → NTU-25 | only if using the graph |
| `code/koa_stgcn.py` | the network definition | only if using the graph |

`pip install flask joblib scikit-learn pandas numpy interpret reportlab`
(add `torch` only if you enable the graph stream).

---

## 2. The landmark format — get this exactly right

`koa_deploy` reads a CSV with **one row per frame**. This is the contract
between the phone and the laptop; everything else is negotiable, this is not.

**Columns, in this order:**

```
frame, t_sec, detected,
<name>_x, <name>_y, <name>_z, <name>_v      ← for all 33 landmarks, image space
w_<name>_x, w_<name>_y, w_<name>_z          ← for all 33 landmarks, world space
```

- `frame` — integer, 0-based
- `t_sec` — seconds from the start of the clip
- `detected` — `1` if a pose was found this frame, `0` if not. **On a `0` row,
  leave every landmark cell empty** — do not write zeros, the loader drops
  those rows by design.
- `<name>` — the 33 MediaPipe pose landmark names, in MediaPipe's own order:
  `nose, left_eye_inner, left_eye, left_eye_outer, right_eye_inner, right_eye,
  right_eye_outer, left_ear, right_ear, mouth_left, mouth_right,
  left_shoulder, right_shoulder, left_elbow, right_elbow, left_wrist,
  right_wrist, left_pinky, right_pinky, left_index, right_index, left_thumb,
  right_thumb, left_hip, right_hip, left_knee, right_knee, left_ankle,
  right_ankle, left_heel, right_heel, left_foot_index, right_foot_index`
- `_x _y _z` (unprefixed) — **normalised image coordinates**, MediaPipe's
  `landmarks` output (0–1 across the frame)
- `_v` — visibility, 0–1
- `w_` prefixed — **world landmarks**, MediaPipe's `worldLandmarks` output, in
  metres, hip-centred. These carry the joint angles, so they matter most.

In MediaPipe Tasks Vision JS both arrays come off the same result object:
`result.landmarks[0]` and `result.worldLandmarks[0]`.

**The phone may POST JSON instead of a CSV** — see §4 — but the JSON must
carry the same two arrays per frame, and the backend writes the CSV.

---

## 3. Capture rules the phone UI must enforce

These are not preferences. The model was trained under them, and breaking them
is the fastest way to get a meaningless score.

| Rule | Why | How to enforce in the UI |
|---|---|---|
| **Side-on view (sagittal)** | Markerless pose is reliable side-on (ICC 0.93) and poor front-on (0.50). Every feature is sagittal. | On-screen guide: "stand side-on to the walker". Reject if both hips are visible at similar depth. |
| **Whole body in frame, knees especially** | Knees are the least reliable joint in this data (0.73 mean visibility). | Show a live warning if mean knee visibility over the last second is < 0.5. |
| **Phone still — tripod, wall, or a friend** | Handheld drift shifts the ankle-separation signal. | Warn on large frame-to-frame motion of the hip midpoint. |
| **At least 4 seconds of walking** | Needs ≥ 30 frames after resampling; the model takes three 48-frame windows. | Disable "finish" until ≥ 4 s captured with `detected == 1`. |
| **One direction per clip** | Turning corrupts the cadence signal. | Prompt "walk one way, then stop recording". |
| **Record the frame rate** | Features assume 25 fps. | Put actual fps in the payload; backend resamples. |

Show a live skeleton overlay while recording. It is the single thing that
makes people trust the capture, and it costs nothing — Tasks Vision gives you
the landmarks you are already drawing.

---

## 4. API contract

### `POST /api/session`
Phone → laptop. Body:

```json
{
  "subject_ref": "demo-01",
  "fps": 30.0,
  "captured_at": "2026-08-23T14:20:00Z",
  "device": "Pixel 7a, rear camera",
  "frames": [
    {"t": 0.000, "detected": 1,
     "landmarks":      [[0.51,0.22,-0.4,0.99], ...33 items [x,y,z,visibility]],
     "worldLandmarks": [[0.01,-0.55,0.02], ...33 items [x,y,z]]},
    ...
  ]
}
```

Response `201`:
```json
{"session_id": "s_20260823_142000_ab12", "frames": 137, "detected": 134,
 "quality": {"detection_rate": 0.978, "mean_knee_visibility": 0.81,
             "duration_s": 4.6, "warnings": []}}
```

Reject with `422` and a readable message if `detection_rate < 0.8`,
`duration_s < 3.0`, or `mean_knee_visibility < 0.4`. **Refusing a bad capture
is a feature** — a confident number from an unusable clip is worse than none.

### `GET /api/session/<id>/score`
Runs the model. Response:

```json
{
  "session_id": "s_...",
  "risk": 0.78,
  "band": "elevated",
  "components": {"handcrafted": 0.81, "graph": 0.73,
                 "mix": "60% joint-angle features / 40% graph network"},
  "stage": {"grade": "moderate",
            "probabilities": {"early": 0.18, "moderate": 0.61, "severe": 0.21},
            "expected_grade": 1.03,
            "confidence": "kappa 0.82, within one grade 100%"},
  "measurements": [
    {"label": "Worse knee's range of movement", "value": 44.2,
     "unit": "degrees", "cohort_median": 62.1,
     "reading": "the worse knee is stiff",
     "explanation": "The range of the more affected knee — the single number a clinician would look at first."}
  ],
  "reasons": ["Worse knee's range of movement: 44.2 degrees against a cohort median of 62.1 — the worse knee is stiff. This raises the estimated risk."],
  "surrogate_fidelity": 0.996,
  "caveats": ["...", "..."]
}
```

Every field above already comes out of `koa_deploy`. Do not invent new ones.

### `GET /api/session/<id>/report.pdf`
Returns the PDF (§5).

### `GET /api/sessions`
List for the dashboard: id, ref, captured_at, risk, band, grade.

---

## 5. The scoring code — this is the whole backend

```python
from koa_deploy import KOAScreener

screener = KOAScreener("deployable")        # load ONCE at startup, not per request

# after writing the phone's frames to <path>.csv in the §2 format:
result = screener.score_landmarks(path)     # returns exactly the JSON in §4
```

That is genuinely it. `KOAScreener` handles windowing, imputation, the fused
score, the ordinal staging and the plain-language reasons. If
`deployable/koa_stgcn.pt` is missing or torch is not installed it falls back to
the handcrafted half automatically and says so in `components.mix`.

Loading takes a few seconds; scoring a clip takes well under a second.

---

## 6. Do you need the graph stream?

| | with `koa_stgcn.pt` + torch | without |
|---|---|---|
| held-out AUC | 0.983 | 0.975 |
| install | needs torch (~800 MB) | pure sklearn |
| latency | ~1 s | ~0.2 s |

**Start without it.** Eight thousandths of AUC is not worth a torch install
on a demo laptop the night before. `KOAScreener(..., use_graph=False)`.

---

## 7. The PDF report

One page. Suggested blocks, in order:

1. **Header** — subject ref, date, "Screening aid — not a diagnosis" in the header itself, not the footer.
2. **Risk** — the number, the band, and a horizontal bar. Use the band colour, not red/green traffic lights.
3. **Stage** — the three grade probabilities as a small stacked bar, plus `expected_grade` on a 0–2 scale. This is the part the brief asks for; give it as much room as the risk.
4. **What was measured** — the `measurements` array as a table: label, this person's value, cohort median, reading. Four to six rows.
5. **Why** — the `reasons` sentences, verbatim, as bullets.
6. **Capture quality** — duration, detection rate, mean knee visibility. A reader should be able to see the clip was usable.
7. **Caveats** — the `caveats` array, verbatim, in full. Do not summarise, shorten, or move them to a second page.

`reportlab` (`SimpleDocTemplate` + `Table` + `Paragraph`) is enough; no HTML-to-PDF service needed.

---

## 8. Things that will bite you

- **`use_graph=True` on a machine without torch** — the constructor catches it and warns, but check `components.graph is not None` before showing a two-bar breakdown in the UI.
- **`detected: 0` rows** — write empty cells, not zeros. Zeros look like a person collapsed at the origin and will produce nonsense angles.
- **World vs image landmarks** — do not swap them. World carries the joint angles; image carries the ankle-separation cadence signal. Both are needed.
- **fps** — the model assumes 25 fps. A 60 fps phone clip must be resampled or the cadence and velocity features are 2.4× off. Do it in the backend, from the `fps` field.
- **HTTPS for the camera** — `getUserMedia` needs a secure context. `localhost` is fine; a bare LAN IP is not. Use `ngrok http 5000` or a self-signed cert, and test it *before* demo day.
- **Never hide the caveats.** They are in the payload for a reason: the age gap between training groups, the walking-speed dependence, and the fact that phone capture is untested. A judge who finds them in your JSON but not on your screen will ask why.

---

## 9. Suggested split for three people

| Person | Owns | Done when |
|---|---|---|
| A | `capture.html` — camera, MediaPipe Tasks Vision, overlay, quality gates, POST | a phone can record a walk and get a `201` with a session id |
| B | Flask app — routes, session storage, `KOAScreener`, the four endpoints | `GET /api/session/<id>/score` returns the §4 JSON for a stored session |
| C | `dashboard.html` + `report.py` — session list, result view, PDF | clicking a session shows the result and downloads a one-page PDF |

A and C can both work against a hard-coded example response before B is
finished — copy one out of `results/` in the zip.
