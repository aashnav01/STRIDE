import csv
import cv2
import mediapipe as mp
import os


MODEL_PATH = os.path.join(
    os.path.dirname(__file__),
    "models",
    "pose_landmarker.task"
)


# The model was trained at 25 fps. Cadence, velocity and duration features
# scale with fps, so a 30/60 fps phone clip must be resampled or the numbers
# come out wrong. See BUILD_SPEC.md §8.
TARGET_FPS = 25.0

# Hard ceiling on frames handed to MediaPipe.
#
# The model samples 3 windows of 48 frames — roughly 144 frames of signal —
# yet extraction previously ran over EVERY frame of the clip. A two-minute
# video is ~3000 frames and took minutes of pose detection to produce a
# score that needed a fraction of it, which is what made long uploads time
# out.
#
# The ceiling is memory, not time. Measured on Render's 512 MB free
# instance: 300 frames completes in ~55s, 750 frames gets OOM-killed
# mid-request (the KOA model holds ~242 MB and MediaPipe's heavy pose
# runtime adds ~170 MB on top). 400 frames is 16 seconds of walking at
# 25 fps — still nearly three times the ~144 frames the model samples —
# and stays well inside the envelope that has actually been tested.
MAX_ANALYSIS_FRAMES = 400


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


# Knee visibility values, indexed into the pose landmark list.
_KNEE_INDICES = (MP_INDEX["left_knee"], MP_INDEX["right_knee"])


def extract_pose(video_path, output_csv=None):
    """Run MediaPipe on a video, write a landmark CSV at 25 fps, and return
    quality stats the API layer uses to gate bad captures."""

    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        raise ValueError(
            f"Could not open video: {video_path}"
        )

    src_fps = cap.get(cv2.CAP_PROP_FPS)

    if not src_fps or src_fps <= 0:
        src_fps = 30.0

    # Which source-frame indices we want to keep to approximate 25 fps.
    # We walk the video sequentially and pick a frame when its timestamp
    # passes the next target tick.
    frame_interval = src_fps / TARGET_FPS

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

    frames_processed = 0     # frames actually written to the CSV (post-resample)
    frames_detected = 0      # of those, how many had a pose
    src_frames_read = 0      # frames read from the source video
    knee_vis_sum = 0.0
    knee_vis_count = 0

    next_target_index = 0.0

    options = mp.tasks.vision.PoseLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(
            model_asset_path=MODEL_PATH
        ),
        running_mode=mp.tasks.vision.RunningMode.VIDEO,
        num_poses=1
    )

    truncated = False

    try:

        with mp.tasks.vision.PoseLandmarker.create_from_options(
            options
        ) as landmarker:

            while True:

                if frames_processed >= MAX_ANALYSIS_FRAMES:
                    # enough signal for every window the model needs
                    truncated = True
                    print(
                        f"Reached the {MAX_ANALYSIS_FRAMES}-frame analysis cap; "
                        "ignoring the rest of the clip"
                    )
                    break

                success, frame = cap.read()

                if not success:
                    break

                # ------------------------------------------------
                # Resample to TARGET_FPS by skipping source frames.
                # If the video is slower than 25 fps we just take
                # every frame (no interpolation — we can't invent
                # frames from nothing).
                # ------------------------------------------------

                if src_frames_read < next_target_index and src_fps > TARGET_FPS:
                    src_frames_read += 1
                    continue

                next_target_index += frame_interval
                src_frames_read += 1

                if frames_processed % 10 == 0:
                    print(
                        f"Processing frame {frames_processed}...",
                        flush=True
                    )

                # ------------------------------------------------
                # Reduce frame resolution before MediaPipe
                # ------------------------------------------------

                height, width = frame.shape[:2]

                MAX_WIDTH = 640

                if width > MAX_WIDTH:

                    scale = MAX_WIDTH / width

                    new_width = MAX_WIDTH
                    new_height = int(height * scale)

                    frame = cv2.resize(
                        frame,
                        (new_width, new_height),
                        interpolation=cv2.INTER_AREA
                    )

                # ------------------------------------------------
                # OpenCV BGR -> RGB
                # ------------------------------------------------

                rgb = cv2.cvtColor(
                    frame,
                    cv2.COLOR_BGR2RGB
                )

                image = mp.Image(
                    image_format=mp.ImageFormat.SRGB,
                    data=rgb
                )

                # Timestamp uses the resampled clock so the model sees a
                # monotonically increasing series at ~40 ms per step.
                timestamp_ms = int(
                    (frames_processed / TARGET_FPS) * 1000
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

                    for k in _KNEE_INDICES:
                        knee_vis_sum += float(pose[k].visibility)
                        knee_vis_count += 1

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

    duration_s = frames_processed / TARGET_FPS if frames_processed else 0.0

    detection_rate = (
        frames_detected / frames_processed if frames_processed else 0.0
    )

    mean_knee_visibility = (
        knee_vis_sum / knee_vis_count if knee_vis_count else 0.0
    )

    print(
        f"CSV written: {output_csv}",
        flush=True
    )

    print(
        f"Source fps: {src_fps:.1f} -> resampled to {TARGET_FPS:.0f} fps",
        flush=True
    )

    print(
        f"Frames processed: {frames_processed}",
        flush=True
    )

    print(
        f"Frames detected: {frames_detected} "
        f"(rate {detection_rate:.2f})",
        flush=True
    )

    print(
        f"Mean knee visibility: {mean_knee_visibility:.2f}",
        flush=True
    )

    return {
        "frames_processed": frames_processed,
        "frames_detected": frames_detected,
        "duration_s": round(duration_s, 2),
        "detection_rate": round(detection_rate, 3),
        "mean_knee_visibility": round(mean_knee_visibility, 3),
        "source_fps": round(src_fps, 2),
        "target_fps": TARGET_FPS,
        "truncated": truncated,
        "max_analysis_frames": MAX_ANALYSIS_FRAMES,
    }
