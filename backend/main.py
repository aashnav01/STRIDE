from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import os
import uuid

from pose_extractor import extract_pose


app = FastAPI(
    title="Pose Extraction API",
    description="API for extracting human pose landmarks from videos",
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
# Upload directory
# --------------------------------------------------

UPLOAD_DIR = "uploads"

os.makedirs(UPLOAD_DIR, exist_ok=True)


# --------------------------------------------------
# Root endpoint
# --------------------------------------------------

@app.get("/")
def root():
    return {
        "message": "Pose Extraction API is running!"
    }


# --------------------------------------------------
# Health check
# --------------------------------------------------

@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


# --------------------------------------------------
# Pose extraction endpoint
# --------------------------------------------------

@app.post("/extract-pose")
async def extract_pose_from_video(
    video: UploadFile = File(...)
):

    # Generate a unique filename
    file_extension = os.path.splitext(video.filename)[1]

    filename = f"{uuid.uuid4()}{file_extension}"

    file_path = os.path.join(
        UPLOAD_DIR,
        filename
    )

    # Save uploaded video
    with open(file_path, "wb") as buffer:
        content = await video.read()
        buffer.write(content)

    try:

        # Extract pose landmarks
        landmarks = extract_pose(file_path)

        return {
            "success": True,
            "filename": video.filename,
            "frames_processed": len(landmarks),
            "pose_data": landmarks
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }

    finally:

        # Delete uploaded video after processing
        if os.path.exists(file_path):
            os.remove(file_path)