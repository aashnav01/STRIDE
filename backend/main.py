from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import os
import uuid
import sys

# Make backend/code importable
CODE_DIR = os.path.join(os.path.dirname(__file__), "code")
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from pose_extractor import extract_pose
from koa_deploy import KOAScreener


app = FastAPI(
    title="KOA Risk & Severity Prediction API",
    description="API for gait-based KOA risk screening",
    version="1.0.0"
)


# --------------------------------------------------
# CORS
# --------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------
# Paths
# --------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MODEL_DIR = os.path.join(BASE_DIR, "models")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")

os.makedirs(UPLOAD_DIR, exist_ok=True)


# --------------------------------------------------
# Load actual KOA model
# --------------------------------------------------

print("Loading KOA model...")

try:
    screener = KOAScreener(
        MODEL_DIR,
        use_graph=False
    )

    print("✅ KOA Model loaded successfully!")
    print(f"✅ Features: {len(screener.features)}")
    print(f"✅ Window: {screener.window}")
    print(f"✅ Windows/video: {screener.windows_per_video}")

except Exception as e:
    screener = None
    print(f"❌ KOA model loading failed: {e}")


# --------------------------------------------------
# Endpoints
# --------------------------------------------------

@app.get("/")
def root():
    return {
        "message": "KOA Prediction API is running!"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "model_loaded": screener is not None
    }


# --------------------------------------------------
# Video analysis
# --------------------------------------------------

@app.post("/extract-pose")
async def extract_pose_from_video(
    video: UploadFile = File(...)
):

    video_id = str(uuid.uuid4())

    extension = os.path.splitext(
        video.filename or ""
    )[1]

    video_path = os.path.join(
        UPLOAD_DIR,
        f"{video_id}{extension}"
    )

    csv_path = os.path.join(
        UPLOAD_DIR,
        f"{video_id}.csv"
    )

    try:

        print(f"📥 Received video: {video.filename}")

        # ------------------------------------------
        # Save uploaded video
        # ------------------------------------------

        content = await video.read()

        with open(video_path, "wb") as f:
            f.write(content)

        print("✅ Video saved")
        print("🧍 Extracting pose landmarks...")

        # ------------------------------------------
        # MediaPipe pose extraction
        # ------------------------------------------

        landmarks = extract_pose(
            video_path,
            csv_path
        )

        detected = sum(
            bool(frame)
            for frame in landmarks
        )

        print(
            f"✅ Pose extraction complete: "
            f"{len(landmarks)} frames, "
            f"{detected} detected"
        )

        # ------------------------------------------
        # KOA prediction
        # ------------------------------------------

        if screener is None:
            raise RuntimeError(
                "KOA model is not loaded."
            )

        print("🧠 Running KOA model...")

        result = screener.score_landmarks(
            csv_path
        )

        print("✅ Prediction complete")
        print(result)

        # ------------------------------------------
        # Return result to React
        # ------------------------------------------

        return {
            "success": True,
            "filename": video.filename,
            "frames_processed": len(landmarks),
            "frames_detected": detected,
            "prediction": result
        }

    except Exception as e:

        print(f"❌ Analysis error: {e}")

        return {
            "success": False,
            "error": str(e)
        }

    finally:

        # ------------------------------------------
        # Cleanup temporary files
        # ------------------------------------------

        if os.path.exists(video_path):
            os.remove(video_path)

        if os.path.exists(csv_path):
            os.remove(csv_path)