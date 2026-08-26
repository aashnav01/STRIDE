import csv
import cv2
import mediapipe as mp
import os


MODEL_PATH = os.path.join(
    os.path.dirname(__file__),
    "models",
    "pose_landmarker.task"
)


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


def extract_pose(video_path, output_csv=None):

    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        raise ValueError(
            f"Could not open video: {video_path}"
        )

    fps = cap.get(cv2.CAP_PROP_FPS)

    if fps <= 0:
        fps = 30.0

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

    # Open CSV before processing so frames are written immediately.
    csv_file = None
    writer = None

    if output_csv:
        csv_file = open(
            output_csv,
            "w",
            newline="",
            encoding="utf-8"
        )

        writer = csv.DictWriter(
            csv_file,
            fieldnames=fieldnames
        )

        writer.writeheader()

    frames_processed = 0
    frames_detected = 0

    options = mp.tasks.vision.PoseLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(
            model_asset_path=MODEL_PATH
        ),
        running_mode=mp.tasks.vision.RunningMode.VIDEO,
        num_poses=1
    )

    try:

        with mp.tasks.vision.PoseLandmarker.create_from_options(
            options
        ) as landmarker:

            while True:

                success, frame = cap.read()

                if not success:
                    break

                if frames_processed % 10 == 0:
                    print(
                        f"Processing frame {frames_processed}...",
                        flush=True
                    )

                rgb = cv2.cvtColor(
                    frame,
                    cv2.COLOR_BGR2RGB
                )

                image = mp.Image(
                    image_format=mp.ImageFormat.SRGB,
                    data=rgb
                )

                timestamp_ms = int(
                    (frames_processed / fps) * 1000
                )

                result = landmarker.detect_for_video(
                    image,
                    timestamp_ms
                )

                row = {
                    "frame": frames_processed,
                    "detected": 0
                }

                if result.pose_landmarks:

                    pose = result.pose_landmarks[0]

                    if result.pose_world_landmarks:
                        world = result.pose_world_landmarks[0]
                    else:
                        world = None

                    row["detected"] = 1
                    frames_detected += 1

                    for joint in JOINTS:

                        index = MP_INDEX[joint]

                        lm = pose[index]

                        row[f"{joint}_x"] = lm.x
                        row[f"{joint}_y"] = lm.y
                        row[f"{joint}_v"] = lm.visibility

                        if world:
                            w = world[index]

                            row[f"w_{joint}_x"] = w.x
                            row[f"w_{joint}_y"] = w.y
                            row[f"w_{joint}_z"] = w.z

                if writer:
                    writer.writerow(row)

                frames_processed += 1

    finally:

        cap.release()

        if csv_file:
            csv_file.close()

    print(
        f"CSV written: {output_csv}",
        flush=True
    )

    print(
        f"Frames processed: {frames_processed}",
        flush=True
    )

    print(
        f"Frames detected: {frames_detected}",
        flush=True
    )

    # Return only lightweight information.
    return {
        "frames_processed": frames_processed,
        "frames_detected": frames_detected
    }