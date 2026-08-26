
import csv
import cv2
import mediapipe as mp
import os


MODEL_PATH = os.path.join(
    os.path.dirname(__file__),
    "models",
    "pose_landmarker.task"
)


# --------------------------------------------------
# MediaPipe landmark indices
# --------------------------------------------------

JOINTS = [
    "left_shoulder",
    "right_shoulder",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
    "left_heel",
    "right_heel",
    "left_foot_index",
    "right_foot_index",
]


MP_INDEX = {
    "left_shoulder": 11,
    "right_shoulder": 12,
    "left_hip": 23,
    "right_hip": 24,
    "left_knee": 25,
    "right_knee": 26,
    "left_ankle": 27,
    "right_ankle": 28,
    "left_heel": 29,
    "right_heel": 30,
    "left_foot_index": 31,
    "right_foot_index": 32,
}


# --------------------------------------------------
# Pose extraction
# --------------------------------------------------

def extract_pose(video_path, output_csv=None):
    """
    Extract MediaPipe pose landmarks from a video.

    If output_csv is provided, the landmarks are also
    saved in CSV format for the KOA model.

    Returns:
        list of frame landmarks
    """

    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        raise ValueError(
            f"Could not open video: {video_path}"
        )

    fps = cap.get(cv2.CAP_PROP_FPS)

    if fps <= 0:
        fps = 30.0

    all_frames = []

    options = mp.tasks.vision.PoseLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(
            model_asset_path=MODEL_PATH
        ),
        running_mode=mp.tasks.vision.RunningMode.VIDEO,
        num_poses=1
    )

    with mp.tasks.vision.PoseLandmarker.create_from_options(
        options
    ) as landmarker:

        frame_index = 0

        while True:

            success, frame = cap.read()

            if not success:
                break

            # Show progress every 10 frames
            if frame_index % 10 == 0:
                print(
                    f"Processing frame {frame_index}...",
                    flush=True
                )

            # OpenCV BGR -> RGB
            rgb = cv2.cvtColor(
                frame,
                cv2.COLOR_BGR2RGB
            )

            # Convert to MediaPipe image
            image = mp.Image(
                image_format=mp.ImageFormat.SRGB,
                data=rgb
            )

            # MediaPipe VIDEO mode requires increasing timestamps
            timestamp_ms = int(
                (frame_index / fps) * 1000
            )

            result = landmarker.detect_for_video(
                image,
                timestamp_ms
            )

            frame_data = []

            # --------------------------------------------------
            # Pose landmarks
            # --------------------------------------------------

            if result.pose_landmarks:

                pose = result.pose_landmarks[0]

                # World landmarks are available with this model
                if result.pose_world_landmarks:
                    world = result.pose_world_landmarks[0]
                else:
                    world = None

                for i in range(33):

                    lm = pose[i]

                    item = {
                        "x": lm.x,
                        "y": lm.y,
                        "z": lm.z,
                        "visibility": lm.visibility
                    }

                    if world:
                        w = world[i]

                        item["wx"] = w.x
                        item["wy"] = w.y
                        item["wz"] = w.z

                    frame_data.append(item)

            all_frames.append(frame_data)

            frame_index += 1

    cap.release()

    # --------------------------------------------------
    # Save CSV
    # --------------------------------------------------

    if output_csv:

        fieldnames = [
            "frame",
            "detected"
        ]

        for joint in JOINTS:

            fieldnames += [
                f"w_{joint}_x",
                f"w_{joint}_y",
                f"w_{joint}_z",
                f"{joint}_x",
                f"{joint}_y",
                f"{joint}_v"
            ]

        with open(
            output_csv,
            "w",
            newline="",
            encoding="utf-8"
        ) as f:

            writer = csv.DictWriter(
                f,
                fieldnames=fieldnames
            )

            writer.writeheader()

            for frame_number, landmarks in enumerate(
                all_frames
            ):

                row = {
                    "frame": frame_number,
                    "detected": int(bool(landmarks))
                }

                if landmarks:

                    for joint in JOINTS:

                        index = MP_INDEX[joint]

                        lm = landmarks[index]

                        row[
                            f"w_{joint}_x"
                        ] = lm.get("wx", "")

                        row[
                            f"w_{joint}_y"
                        ] = lm.get("wy", "")

                        row[
                            f"w_{joint}_z"
                        ] = lm.get("wz", "")

                        row[
                            f"{joint}_x"
                        ] = lm["x"]

                        row[
                            f"{joint}_y"
                        ] = lm["y"]

                        row[
                            f"{joint}_v"
                        ] = lm["visibility"]

                writer.writerow(row)

        print(
            f"CSV written: {output_csv}",
            flush=True
        )

        print(
            f"Frames processed: {len(all_frames)}",
            flush=True
        )

    return all_frames
