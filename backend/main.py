from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

import os
import sys
import uuid
import time
import gc
from io import BytesIO
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
)
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.units import mm


# ============================================================
# Make backend/code importable
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CODE_DIR = os.path.join(BASE_DIR, "code")

if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)


# ============================================================
# Imports from project
# ============================================================

from pose_extractor import extract_pose
from koa_deploy import KOAScreener
import store


# ============================================================
# FastAPI
# ============================================================

app = FastAPI(
    title="KOA Risk & Severity Prediction API",
    description="Offline gait-based KOA screening API",
    version="1.0.0",
)


# ============================================================
# CORS
# ============================================================

# Origins come from the environment so a redeploy to a new host does not
# need a code change. ALLOWED_ORIGINS is a comma-separated list; local dev
# ports are always permitted.
_DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",      # vite preview, where the service worker runs
]
def _as_origin(value: str) -> str:
    """Render hands over a bare hostname; CORS needs a scheme to match."""
    value = value.strip()
    if not value:
        return ""
    return value if value.startswith(("http://", "https://")) else f"https://{value}"


_env_origins = [
    o for o in (
        _as_origin(v)
        for v in os.environ.get("ALLOWED_ORIGINS", "").split(",")
    ) if o
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_DEV_ORIGINS + _env_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

print("CORS origins:", _DEV_ORIGINS + _env_origins)


# ============================================================
# Paths
# ============================================================

MODEL_DIR = os.path.join(BASE_DIR, "models")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")

os.makedirs(UPLOAD_DIR, exist_ok=True)


# ============================================================
# Load KOA model
# ============================================================

print("=" * 60)
print("Loading KOA model...")
print("=" * 60)

# The KOA model holds ~242 MB. MediaPipe's pose runtime needs roughly
# another 170 MB while extracting, and on a 512 MB instance holding both at
# once is what gets the process OOM-killed mid-request.
#
# So the model is loaded on demand and released once a score is produced:
# pose extraction runs with the model absent, and scoring runs with
# MediaPipe already torn down. Peak becomes max(pose, model) instead of
# their sum. The cost is ~10 s to reload per request, which is a good trade
# against a 502.
#
# Set KEEP_MODEL_LOADED=1 on an instance with real headroom to skip this
# and keep the model resident.
KEEP_MODEL_LOADED = os.environ.get("KEEP_MODEL_LOADED") == "1"

# Quality gate. The model needs three 48-frame windows of usable signal;
# these bound "usable" without rejecting footage the model was trained on.
MIN_DETECTION_RATE = float(os.environ.get("MIN_DETECTION_RATE", "0.5"))
MIN_DETECTED_FRAMES = int(os.environ.get("MIN_DETECTED_FRAMES", "150"))
MIN_KNEE_VISIBILITY = float(os.environ.get("MIN_KNEE_VISIBILITY", "0.4"))

screener = None
_model_ok = None          # None = never tried, True/False = last outcome


def load_screener():
    """Load the model, reusing it if it is already resident."""
    global screener, _model_ok
    if screener is not None:
        return screener
    try:
        t = time.perf_counter()
        screener = KOAScreener(MODEL_DIR, use_graph=False)
        _model_ok = True
        print(
            f"KOA model loaded in {time.perf_counter() - t:.1f}s "
            f"({len(screener.features)} features, window {screener.window}, "
            f"severity {'yes' if screener.severity else 'no'})"
        )
    except Exception as e:
        screener = None
        _model_ok = False
        print("KOA model failed to load:", type(e).__name__, e)
    return screener


def release_screener():
    """Drop the model so pose extraction gets the memory back."""
    global screener
    if KEEP_MODEL_LOADED or screener is None:
        return
    screener = None
    gc.collect()
    print("KOA model released")


# Deliberately NOT loaded at boot. Loading it even once allocates ~242 MB
# that Python never returns to the OS, so it would sit in RSS during pose
# extraction and push the process past a 512 MB limit — which is exactly
# what was happening (peak 478 MB, then OOM-killed mid-request).
#
# Instead: verify the artefacts exist, and load for real only after
# extraction has finished and MediaPipe has torn its buffers down.
_REQUIRED = ("koa_model.joblib", "koa_severity.joblib")
_missing = [f for f in _REQUIRED if not os.path.exists(os.path.join(MODEL_DIR, f))]
if _missing:
    _model_ok = False
    print("KOA model artefacts missing:", _missing)
else:
    _model_ok = True
    print(f"KOA model artefacts present in {MODEL_DIR}; loading deferred")

if KEEP_MODEL_LOADED:
    load_screener()


# ============================================================
# Health check
# ============================================================

# Render's readiness probe uses HEAD, and Starlette does not add HEAD to a
# GET route automatically — an unanswered probe reads as a failed deploy.
@app.api_route("/", methods=["GET", "HEAD"])
def root():
    return {
        "status": "online",
        "service": "KOA Risk & Severity Prediction API",
        "model_loaded": bool(_model_ok),
        "offline": True,
    }


@app.on_event("startup")
def _init_store():
    store.init_db()
    print("Screening store ready")


# ============================================================
# Screening records — offline sync target for the field app
# ============================================================

@app.post("/screenings")
async def create_screening(record: dict):
    """Idempotent on the client-generated id, so a retried sync is safe."""
    if not record.get("id"):
        raise HTTPException(status_code=400, detail="screening id is required")
    try:
        store.upsert(record)
        return {"success": True, "id": record["id"]}
    except Exception as e:
        print("screening store error:", type(e).__name__, e)
        raise HTTPException(status_code=500, detail="Could not store screening")


@app.get("/screenings")
def get_screenings(limit: int = 500):
    return {"screenings": store.list_screenings(limit)}


@app.get("/screenings/summary")
def get_summary():
    return store.summary()


_BOOTED_AT = time.time()


@app.api_route("/health", methods=["GET", "HEAD"])
def health():
    """Diagnostics for a slow or failing deploy.

    `uptime_s` resetting between requests means the process restarted —
    on a memory-limited host that usually means it was OOM-killed mid
    request, which otherwise looks identical to a timeout from the browser.
    """
    info = {
        "status": "healthy" if _model_ok else "model_error",
        # whether the artefacts load, not whether they are resident right now
        "model_loaded": bool(_model_ok),
        "model_resident": screener is not None,
        "uptime_s": round(time.time() - _BOOTED_AT, 1),
    }
    try:
        import resource
        # ru_maxrss is KB on Linux, bytes on macOS
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        info["peak_rss_mb"] = round(peak / 1024, 1)
    except Exception:
        pass
    return info


# ============================================================
# VIDEO ANALYSIS
# ============================================================

@app.post("/extract-pose")
async def extract_pose_endpoint(video: UploadFile = File(...)):

    if _model_ok is False:
        raise HTTPException(
            status_code=500,
            detail="KOA model is not loaded."
        )

    # --------------------------------------------------------
    # Validate file
    # --------------------------------------------------------

    if not video.filename:
        raise HTTPException(
            status_code=400,
            detail="No video file supplied."
        )

    allowed_extensions = (
        ".mp4",
        ".mov",
        ".avi",
        ".mkv",
        ".webm",
    )

    extension = os.path.splitext(video.filename)[1].lower()

    if extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail="Unsupported video format."
        )

    # --------------------------------------------------------
    # Create temporary filenames
    # --------------------------------------------------------

    t0 = time.perf_counter()
    timings = {}

    file_id = str(uuid.uuid4())

    video_path = os.path.join(
        UPLOAD_DIR,
        f"{file_id}{extension}"
    )

    csv_path = os.path.join(
        UPLOAD_DIR,
        f"{file_id}.csv"
    )

    try:

        # ----------------------------------------------------
        # Save uploaded video
        # ----------------------------------------------------

        print()
        print("=" * 60)
        print("NEW VIDEO ANALYSIS")
        print("=" * 60)

        print(f"Video: {video.filename}")

        with open(video_path, "wb") as f:

            while True:

                chunk = await video.read(1024 * 1024)

                if not chunk:
                    break

                f.write(chunk)

        timings["upload_s"] = round(time.perf_counter() - t0, 2)
        print(f"Video saved ({timings['upload_s']}s)")
        t_pose = time.perf_counter()

        # ----------------------------------------------------
        # MediaPipe pose extraction
        # ----------------------------------------------------

        print("Extracting pose landmarks...")

        pose_stats = extract_pose(
            video_path,
            csv_path
        )

        timings["pose_s"] = round(time.perf_counter() - t_pose, 2)

        frames_processed = pose_stats["frames_processed"]
        frames_detected = pose_stats["frames_detected"]

        if frames_processed:
            timings["ms_per_frame"] = round(
                timings["pose_s"] * 1000 / frames_processed, 1
            )
        print(
            f"Pose extraction: {timings['pose_s']}s for {frames_processed} frames"
            f" ({timings.get('ms_per_frame')} ms/frame)"
        )

        print(
           f"Pose extraction complete: "
           f"{frames_processed} frames, "
           f"{frames_detected} detected"
        )

        # ----------------------------------------------------
        # Quality gate — reject clips that will produce a
        # meaningless score. Better to say no than to hand
        # back a confident number from unusable footage.
        # ----------------------------------------------------

        duration_s = pose_stats.get("duration_s", 0.0)
        detection_rate = pose_stats.get("detection_rate", 0.0)
        mean_knee_visibility = pose_stats.get("mean_knee_visibility", 0.0)

        quality_problems = []

        if duration_s < 3.0:
            quality_problems.append(
                f"Clip is only {duration_s:.1f} s long. "
                "Please record at least 4 seconds of walking."
            )

        # A flat percentage is the wrong test. The model samples three
        # 48-frame windows and koa_features drops non-finite values before
        # computing anything, so what matters is how many usable frames
        # exist, not what share of a long clip they represent. An 80% gate
        # rejected a 436-frame clip carrying 322 detected frames — roughly
        # twice what the model consumes — while a short clip at 85% could
        # carry far fewer and pass.
        #
        # So: a low rate floor to catch genuinely unusable footage, plus an
        # absolute floor on detected frames. Both tunable without a deploy.
        if detection_rate < MIN_DETECTION_RATE:
            quality_problems.append(
                f"A pose was detected in only "
                f"{detection_rate * 100:.0f}% of frames. "
                "Please film with the whole body in frame."
            )
        elif frames_detected < MIN_DETECTED_FRAMES:
            quality_problems.append(
                f"Only {frames_detected} frames had a usable pose, and at "
                f"least {MIN_DETECTED_FRAMES} are needed. "
                "Please record a longer clip, or move further from the camera "
                "so the whole body stays in frame."
            )

        if mean_knee_visibility < MIN_KNEE_VISIBILITY:
            quality_problems.append(
                f"Knee visibility averaged "
                f"{mean_knee_visibility:.2f}. "
                "Please film side-on with the knees clearly visible."
            )

        if quality_problems:
            print("Quality gate rejected clip:")
            for problem in quality_problems:
                print(f"  - {problem}")

            raise HTTPException(
                status_code=422,
                detail=" ".join(quality_problems),
            )

        # ----------------------------------------------------
        # KOA prediction
        # ----------------------------------------------------

        t_score = time.perf_counter()
        print("Running KOA model...")

        # pose extraction is done; bring the model in now that MediaPipe has
        # finished with its memory
        if load_screener() is None:
            raise HTTPException(
                status_code=500,
                detail="KOA model could not be loaded."
            )

        result = screener.score_landmarks(
          csv_path
        )

        timings["score_s"] = round(time.perf_counter() - t_score, 2)
        timings["total_s"] = round(time.perf_counter() - t0, 2)
        print(f"KOA prediction complete ({timings['score_s']}s)")
        print(
            "TIMING  upload=%(upload_s)ss  pose=%(pose_s)ss  "
            "score=%(score_s)ss  TOTAL=%(total_s)ss" % timings
        )

        print(
            f"Risk  : {result.get('risk')}"
        )

        print(
            f"Band  : {result.get('band')}"
        )

        if result.get("stage"):
            print(
                f"Stage : {result['stage'].get('grade')}"
            )

        # ----------------------------------------------------
        # Return result to React
        # ----------------------------------------------------

        return {
            "success": True,
            "filename": video.filename,
            "frames_processed": frames_processed,
            "frames_detected": frames_detected,
            "quality": {
                "duration_s": duration_s,
                "detection_rate": detection_rate,
                "mean_knee_visibility": mean_knee_visibility,
                "source_fps": pose_stats.get("source_fps"),
                "target_fps": pose_stats.get("target_fps"),
                # true when the clip was longer than the analysis cap, so the
                # report can say only the first stretch was read
                "truncated": pose_stats.get("truncated", False),
                "max_analysis_frames": pose_stats.get("max_analysis_frames"),
            },
            "csv_available": os.path.exists(csv_path),
            "prediction": result,
            # where the time actually went, so a slow request is diagnosable
            # from the browser without reading server logs
            "timings": timings,
        }

    except HTTPException:
        # 422s from the quality gate should reach the client as-is.
        raise

    except Exception as e:

        print()
        print("ANALYSIS ERROR")
        print(type(e).__name__, e)

        raise HTTPException(
            status_code=500,
            detail=f"Video analysis failed: {str(e)}"
        )

    finally:

        # ----------------------------------------------------
        # Remove temporary files. Render's disk is ephemeral
        # but a busy demo still fills it up between restarts.
        # ----------------------------------------------------

        for path in (video_path, csv_path):
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass

        # give the 242 MB back so the next request's pose extraction has it
        release_screener()


# ============================================================
# PDF REPORT GENERATOR
# ============================================================

@app.post("/generate-report")
async def generate_report(data: dict):

    try:

        prediction = data.get("prediction", {})

        filename = data.get(
            "filename",
            "Walking Video"
        )

        frames_processed = data.get(
            "frames_processed",
            0
        )

        frames_detected = data.get(
            "frames_detected",
            0
        )

        risk = prediction.get(
            "risk",
            0
        )

        band = prediction.get(
            "band",
            "unknown"
        )

        stage = prediction.get(
            "stage"
        )

        measurements = prediction.get(
            "measurements",
            []
        )

        reasons = prediction.get(
            "reasons",
            []
        )

        caveats = prediction.get(
            "caveats",
            []
        )

        # ====================================================
        # PDF buffer
        # ====================================================

        buffer = BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=15 * mm,
            leftMargin=15 * mm,
            topMargin=14 * mm,
            bottomMargin=14 * mm,
        )

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "ReportTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            alignment=TA_LEFT,
            spaceAfter=5,
        )

        subtitle_style = ParagraphStyle(
            "Subtitle",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#555555"),
        )

        section_style = ParagraphStyle(
            "Section",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            spaceBefore=9,
            spaceAfter=5,
        )

        normal_style = ParagraphStyle(
            "NormalReport",
            parent=styles["Normal"],
            fontSize=8.5,
            leading=12,
        )

        small_style = ParagraphStyle(
            "Small",
            parent=styles["Normal"],
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor("#666666"),
        )

        center_small = ParagraphStyle(
            "CenterSmall",
            parent=small_style,
            alignment=TA_CENTER,
        )

        # ====================================================
        # Helpers
        # ====================================================

        def safe(value):
            if value is None:
                return "—"
            return str(value)

        def pct(value):

            try:
                return f"{float(value) * 100:.1f}%"
            except Exception:
                return "—"

        def page_number(canvas, doc):

            canvas.saveState()

            canvas.setFont(
                "Helvetica",
                7
            )

            canvas.setFillColor(
                colors.HexColor("#777777")
            )

            canvas.drawRightString(
                A4[0] - 15 * mm,
                7 * mm,
                f"page {doc.page}"
            )

            canvas.restoreState()

        # ====================================================
        # DOCUMENT CONTENT
        # ====================================================

        story = []

        # ----------------------------------------------------
        # HEADER
        # ----------------------------------------------------

        story.append(
            Paragraph(
                "OSTEOARTHRITIS RISK SCREENING REPORT",
                title_style
            )
        )

        story.append(
            Paragraph(
                "AI-Assisted Gait Analysis",
                subtitle_style
            )
        )

        story.append(Spacer(1, 4))

        metadata = [
            [
                Paragraph(
                    "<b>Test Subject</b>",
                    normal_style
                ),
                safe(filename),
            ],
            [
                Paragraph(
                    "<b>Date & Time</b>",
                    normal_style
                ),
                datetime.now().strftime(
                    "%d %B %Y, %I:%M %p"
                ),
            ],
        ]

        metadata_table = Table(
            metadata,
            colWidths=[
                35 * mm,
                145 * mm,
            ],
        )

        metadata_table.setStyle(
            TableStyle([
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.4,
                    colors.HexColor("#DDDDDD")
                ),
                (
                    "BACKGROUND",
                    (0, 0),
                    (0, -1),
                    colors.HexColor("#F4F5F7")
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE"
                ),
                (
                    "FONTNAME",
                    (0, 0),
                    (-1, -1),
                    "Helvetica"
                ),
                (
                    "FONTSIZE",
                    (0, 0),
                    (-1, -1),
                    8
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    6
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    6
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    5
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    5
                ),
            ])
        )

        story.append(metadata_table)

        story.append(Spacer(1, 4))

        story.append(
            Paragraph(
                "<i>Estimated from a single walking clip. "
                "This report supports screening and referral discussion; "
                "it does not make a clinical diagnosis.</i>",
                small_style
            )
        )

        # ====================================================
        # SCREENING RISK
        # ====================================================

        story.append(
            Paragraph(
                "SCREENING RISK",
                section_style
            )
        )

        risk_percent = pct(risk)

        risk_data = [
            [
                Paragraph(
                    "<b>LOW</b>",
                    center_small
                ),
                Paragraph(
                    "<b>BORDERLINE</b>",
                    center_small
                ),
                Paragraph(
                    "<b>ELEVATED</b>",
                    center_small
                ),
            ],
            [
                Paragraph(
                    "0.00 – 0.34",
                    center_small
                ),
                Paragraph(
                    "0.35 – 0.64",
                    center_small
                ),
                Paragraph(
                    "0.65 – 1.00",
                    center_small
                ),
            ],
        ]

        risk_table = Table(
            risk_data,
            colWidths=[
                60 * mm,
                60 * mm,
                60 * mm,
            ],
            rowHeights=[
                9 * mm,
                7 * mm,
            ],
        )

        band_column = {
            "low": 0,
            "borderline": 1,
            "elevated": 2,
        }.get(
            str(band).lower(),
            0
        )

        risk_table.setStyle(
            TableStyle([
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.HexColor("#BBBBBB")
                ),
                (
                    "BACKGROUND",
                    (band_column, 0),
                    (band_column, 1),
                    colors.HexColor("#DCEEFF")
                ),
                (
                    "FONTNAME",
                    (band_column, 0),
                    (band_column, 0),
                    "Helvetica-Bold"
                ),
                (
                    "ALIGN",
                    (0, 0),
                    (-1, -1),
                    "CENTER"
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE"
                ),
            ])
        )

        story.append(risk_table)

        story.append(Spacer(1, 4))

        story.append(
            Paragraph(
                f"<b>Observed screening score: "
                f"{risk_percent} — {safe(band).upper()}</b>",
                normal_style
            )
        )

        # ====================================================
        # SEVERITY
        # ====================================================

        story.append(
            Paragraph(
                "SEVERITY STAGE",
                section_style
            )
        )

        # Severity staging is defined *within* diagnosed OA, so a "moderate"
        # grade on a low-risk subject reads as a false positive. The UI hides
        # it for the low band; the PDF must agree or the bug just moves here.
        if stage and str(band).lower() != "low":

            grade = safe(
                stage.get("grade")
            )

            expected = safe(
                stage.get("expected_grade")
            )

            confidence = safe(
                stage.get("confidence")
            )

            story.append(
                Paragraph(
                    f"<b>Most likely stage:</b> {grade}<br/>"
                    f"Expected grade: {expected} on a 0–2 scale.<br/>"
                    f"{confidence}",
                    normal_style
                )
            )

            probabilities = stage.get(
                "probabilities",
                {}
            )

            probability_data = [
                [
                    "Early",
                    "Moderate",
                    "Severe",
                ],
                [
                    pct(probabilities.get("early", 0)),
                    pct(probabilities.get("moderate", 0)),
                    pct(probabilities.get("severe", 0)),
                ],
            ]

            probability_table = Table(
                probability_data,
                colWidths=[
                    60 * mm,
                    60 * mm,
                    60 * mm,
                ],
            )

            probability_table.setStyle(
                TableStyle([
                    (
                        "GRID",
                        (0, 0),
                        (-1, -1),
                        0.4,
                        colors.HexColor("#CCCCCC")
                    ),
                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, 0),
                        colors.HexColor("#F4F5F7")
                    ),
                    (
                        "ALIGN",
                        (0, 0),
                        (-1, -1),
                        "CENTER"
                    ),
                    (
                        "FONTNAME",
                        (0, 0),
                        (-1, 0),
                        "Helvetica-Bold"
                    ),
                    (
                        "FONTSIZE",
                        (0, 0),
                        (-1, -1),
                        8
                    ),
                    (
                        "TOPPADDING",
                        (0, 0),
                        (-1, -1),
                        5
                    ),
                    (
                        "BOTTOMPADDING",
                        (0, 0),
                        (-1, -1),
                        5
                    ),
                ])
            )

            story.append(
                Spacer(1, 3)
            )

            story.append(
                probability_table
            )

        elif stage:

            story.append(
                Paragraph(
                    "Severity staging is not reported at this risk level. "
                    "Staging is defined within diagnosed knee OA, so it is "
                    "not meaningful for a low-risk screening result.",
                    normal_style
                )
            )

        else:

            story.append(
                Paragraph(
                    "Severity staging was not available "
                    "for this analysis.",
                    normal_style
                )
            )

        # ====================================================
        # SECTION 1
        # ====================================================

        story.append(
            Paragraph(
                "1. WHAT WAS MEASURED",
                section_style
            )
        )

        measurement_data = [
            [
                "Measurement",
                "This person",
                "Cohort median",
                "Reading",
            ]
        ]

        for m in measurements:

            value = safe(
                m.get("value")
            )

            unit = safe(
                m.get("unit")
            )

            median = safe(
                m.get("cohort_median")
            )

            measurement_data.append([
                safe(m.get("label")),
                f"{value} {unit}",
                f"{median} {unit}",
                safe(m.get("reading")),
            ])

        if len(measurement_data) == 1:

            measurement_data.append([
                "No measurements available",
                "—",
                "—",
                "—",
            ])

        measurement_table = Table(
            measurement_data,
            colWidths=[
                65 * mm,
                35 * mm,
                35 * mm,
                45 * mm,
                ],
            repeatRows=1,
        )

        measurement_table.setStyle(
            TableStyle([
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.4,
                    colors.HexColor("#CCCCCC")
                ),
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#E9EEF5")
                ),
                (
                    "FONTNAME",
                    (0, 0),
                    (-1, 0),
                    "Helvetica-Bold"
                ),
                (
                    "FONTSIZE",
                    (0, 0),
                    (-1, -1),
                    7
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP"
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    4
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    4
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    4
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    4
                ),
            ])
        )

        story.append(
            measurement_table
        )

        # ====================================================
        # SECTION 2
        # ====================================================

        story.append(
            Paragraph(
                "2. WHY THIS SCORE",
                section_style
            )
        )

        if reasons:

            for reason in reasons:

                story.append(
                    Paragraph(
                        f"• {safe(reason)}",
                        normal_style
                    )
                )

                story.append(
                    Spacer(1, 2)
                )

        else:

            story.append(
                Paragraph(
                    "No explanatory factors were returned "
                    "by the model.",
                    normal_style
                )
            )

        fidelity = prediction.get(
            "surrogate_fidelity"
        )

        if fidelity is not None:

            story.append(
                Spacer(1, 3)
            )

            story.append(
                Paragraph(
                    f"<i>Explainability model fidelity: "
                    f"{safe(fidelity)}.</i>",
                    small_style
                )
            )

        # ====================================================
        # SECTION 3
        # ====================================================

        story.append(
            Paragraph(
                "3. CAPTURE QUALITY",
                section_style
            )
        )

        quality = data.get("quality", {})

        duration_s = quality.get("duration_s")
        detection_rate = quality.get("detection_rate")
        mean_knee_visibility = quality.get("mean_knee_visibility")

        clip_length = (
            f"{duration_s:.1f} s"
            if isinstance(duration_s, (int, float))
            else "—"
        )

        detection_cell = (
            f"{frames_detected}/{frames_processed} "
            f"({detection_rate * 100:.0f}%)"
            if isinstance(detection_rate, (int, float))
            else f"{frames_detected}/{frames_processed}"
        )

        knee_vis_cell = (
            f"{mean_knee_visibility:.2f}"
            if isinstance(mean_knee_visibility, (int, float))
            else "—"
        )

        quality_data = [
            [
                "clip length",
                "frames with a pose",
                "knee visibility",
                "windows scored",
                "model",
            ],
            [
                clip_length,
                detection_cell,
                knee_vis_cell,
                safe(prediction.get("n_windows", "—")),
                "KOA screener",
            ],
        ]

        quality_table = Table(
            quality_data,
            colWidths=[
                36 * mm,
                36 * mm,
                36 * mm,
                36 * mm,
                36 * mm,
            ],
        )

        quality_table.setStyle(
            TableStyle([
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.4,
                    colors.HexColor("#CCCCCC")
                ),
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#F4F5F7")
                ),
                (
                    "FONTNAME",
                    (0, 0),
                    (-1, 0),
                    "Helvetica-Bold"
                ),
                (
                    "ALIGN",
                    (0, 0),
                    (-1, -1),
                    "CENTER"
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE"
                ),
                (
                    "FONTSIZE",
                    (0, 0),
                    (-1, -1),
                    6.8
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    5
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    5
                ),
            ])
        )

        story.append(
            quality_table
        )

        # ====================================================
        # SECTION 4
        # ====================================================

        story.append(
            Paragraph(
                "4. LIMITS OF THIS RESULT",
                section_style
            )
        )

        if caveats:

            for caveat in caveats:

                story.append(
                    Paragraph(
                        f"• {safe(caveat)}",
                        normal_style
                    )
                )

                story.append(
                    Spacer(1, 2)
                )

        # ====================================================
        # FOOTER DISCLAIMER
        # ====================================================

        story.append(
            Spacer(1, 6)
        )

        story.append(
            Paragraph(
                "<b>Important:</b> This is an AI-assisted "
                "screening result for research purposes. "
                "It is not a medical diagnosis and should "
                "not replace evaluation by a qualified "
                "healthcare professional.",
                small_style
            )
        )

        # ====================================================
        # BUILD PDF
        # ====================================================

        doc.build(
            story,
            onFirstPage=page_number,
            onLaterPages=page_number,
        )

        pdf = buffer.getvalue()

        buffer.close()

        return Response(
            content=pdf,
            media_type="application/pdf",
            headers={
                "Content-Disposition":
                    'attachment; filename="OA_Screening_Report.pdf"'
            },
        )

    except Exception as e:

        print(
            "PDF generation error:",
            type(e).__name__,
            e
        )

        raise HTTPException(
            status_code=500,
            detail=f"PDF generation failed: {str(e)}"
        )