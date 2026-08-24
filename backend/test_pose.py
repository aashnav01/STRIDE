import mediapipe as mp

MODEL_PATH = "models/pose_landmarker.task"

BaseOptions = mp.tasks.BaseOptions
PoseLandmarker = mp.tasks.vision.PoseLandmarker
PoseLandmarkerOptions = mp.tasks.vision.PoseLandmarkerOptions
RunningMode = mp.tasks.vision.RunningMode

options = PoseLandmarkerOptions(
    base_options=BaseOptions(model_asset_path=MODEL_PATH),
    running_mode=RunningMode.IMAGE,
    num_poses=1
)

with PoseLandmarker.create_from_options(options) as landmarker:
    print("Pose Landmarker loaded successfully!")

print("Test completed!")