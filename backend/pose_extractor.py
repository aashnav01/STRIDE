import cv2
import mediapipe as mp
import os


MODEL_PATH = os.path.join(
    os.path.dirname(__file__),
    "models",
    "pose_landmarker.task"
)


BaseOptions = mp.tasks.BaseOptions
PoseLandmarker = mp.tasks.vision.PoseLandmarker
PoseLandmarkerOptions = mp.tasks.vision.PoseLandmarkerOptions
RunningMode = mp.tasks.vision.RunningMode


def extract_pose(video_path):
    """
    Extract pose landmarks from a video.

    Returns:
        list: Pose landmarks for each frame.
    """

    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        raise ValueError("Could not open the video.")

    all_frames = []

    options = PoseLandmarkerOptions(
        base_options=BaseOptions(
            model_asset_path=MODEL_PATH
        ),
        running_mode=RunningMode.VIDEO,
        num_poses=1
    )

    with PoseLandmarker.create_from_options(options) as landmarker:

        fps = cap.get(cv2.CAP_PROP_FPS)

        if fps <= 0:
            fps = 30

        frame_index = 0

        while True:

            success, frame = cap.read()

            if not success:
                break

            # Convert BGR to RGB
            rgb_frame = cv2.cvtColor(
                frame,
                cv2.COLOR_BGR2RGB
            )

            # Convert OpenCV image to MediaPipe image
            mp_image = mp.Image(
                image_format=mp.ImageFormat.SRGB,
                data=rgb_frame
            )

            timestamp_ms = int(
                (frame_index / fps) * 1000
            )

            result = landmarker.detect_for_video(
                mp_image,
                timestamp_ms
            )

            frame_landmarks = []

            if result.pose_landmarks:

                for landmark in result.pose_landmarks[0]:

                    frame_landmarks.append({
                        "x": landmark.x,
                        "y": landmark.y,
                        "z": landmark.z,
                        "visibility": landmark.visibility
                    })

            all_frames.append(frame_landmarks)

            frame_index += 1

    cap.release()

    return all_frames