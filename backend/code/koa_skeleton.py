"""
koa_skeleton.py — MediaPipe-33 -> NTU-25 skeletons for pretrained GCNs.

Why remap instead of retraining the graph
-----------------------------------------
Every NTU-pretrained checkpoint (ST-GCN++, CTR-GCN, MS-G3D) is welded to the
25-joint NTU RGB+D topology. With 80 subjects there is no prospect of training a
graph net from scratch, so the pretrained weights are the only thing that makes
the deep branch viable — which means the data must come to the graph, not the
other way round.

Twelve NTU joints map directly from MediaPipe. Four spine/neck joints are
synthesised from midpoints, which is what they anatomically are. The nine
hand/thumb/tip joints have no gait content and are filled from their parent so
the tensor shape is right without inventing motion; they are listed in
SYNTHETIC_JOINTS so you can mask them if you prefer.

Output is (C=3, T, V=25, M=1) float32 — the layout PYSKL and MS-G3D expect.
"""

from __future__ import annotations

import numpy as np

# NTU RGB+D joint order (0-indexed), and the standard parent list.
NTU_JOINT_NAMES = [
    "SpineBase", "SpineMid", "Neck", "Head", "ShoulderLeft", "ElbowLeft",
    "WristLeft", "HandLeft", "HandTipLeft", "ThumbLeft", "ShoulderRight",
    "ElbowRight", "WristRight", "HandRight", "HandTipRight", "ThumbRight",
    "HipLeft", "KneeLeft", "AnkleLeft", "FootLeft", "HipRight", "KneeRight",
    "AnkleRight", "FootRight", "SpineShoulder",
]
NTU_PARENTS = [0, 0, 24, 2, 24, 4, 5, 6, 7, 6, 24, 10, 11, 12, 13, 12,
               0, 16, 17, 18, 0, 20, 21, 22, 1]
NUM_JOINTS = 25
CENTER_JOINT = 0

# MediaPipe landmark index -> NTU slot, where a direct equivalent exists.
MP = {
    "nose": 0, "left_shoulder": 11, "right_shoulder": 12, "left_elbow": 13,
    "right_elbow": 14, "left_wrist": 15, "right_wrist": 16, "left_pinky": 17,
    "right_pinky": 18, "left_index": 19, "right_index": 20, "left_thumb": 21,
    "right_thumb": 22, "left_hip": 23, "right_hip": 24, "left_knee": 25,
    "right_knee": 26, "left_ankle": 27, "right_ankle": 28, "left_heel": 29,
    "right_heel": 30, "left_foot_index": 31, "right_foot_index": 32,
}

DIRECT = {
    "ShoulderLeft": "left_shoulder", "ShoulderRight": "right_shoulder",
    "ElbowLeft": "left_elbow", "ElbowRight": "right_elbow",
    "WristLeft": "left_wrist", "WristRight": "right_wrist",
    "HipLeft": "left_hip", "HipRight": "right_hip",
    "KneeLeft": "left_knee", "KneeRight": "right_knee",
    "AnkleLeft": "left_ankle", "AnkleRight": "right_ankle",
    "FootLeft": "left_foot_index", "FootRight": "right_foot_index",
}

# Filled from a parent joint — no independent motion. Mask these if you want
# the graph to ignore them entirely.
SYNTHETIC_JOINTS = ["HandLeft", "HandTipLeft", "ThumbLeft",
                    "HandRight", "HandTipRight", "ThumbRight"]

NTU_IDX = {n: i for i, n in enumerate(NTU_JOINT_NAMES)}


def mediapipe_to_ntu(world: np.ndarray) -> np.ndarray:
    """(T, 33, 3) MediaPipe world landmarks -> (T, 25, 3) NTU-ordered."""
    T = world.shape[0]
    out = np.zeros((T, NUM_JOINTS, 3), dtype=np.float32)

    for ntu_name, mp_name in DIRECT.items():
        out[:, NTU_IDX[ntu_name]] = world[:, MP[mp_name]]

    hip_mid = (world[:, MP["left_hip"]] + world[:, MP["right_hip"]]) / 2.0
    sh_mid = (world[:, MP["left_shoulder"]] + world[:, MP["right_shoulder"]]) / 2.0

    # Spine chain: NTU's SpineBase/Mid/Shoulder/Neck are anatomically the
    # pelvis centre, the trunk midpoint, the upper-thorax and the neck base.
    out[:, NTU_IDX["SpineBase"]] = hip_mid
    out[:, NTU_IDX["SpineMid"]] = hip_mid + 0.5 * (sh_mid - hip_mid)
    out[:, NTU_IDX["SpineShoulder"]] = sh_mid
    out[:, NTU_IDX["Neck"]] = sh_mid + 0.25 * (world[:, MP["nose"]] - sh_mid)
    out[:, NTU_IDX["Head"]] = world[:, MP["nose"]]

    # Hands/thumbs: no gait content. Hold at the wrist rather than fabricate.
    for side, wrist in (("Left", "left_wrist"), ("Right", "right_wrist")):
        w = world[:, MP[wrist]]
        for j in (f"Hand{side}", f"HandTip{side}", f"Thumb{side}"):
            out[:, NTU_IDX[j]] = w

    return out


def center_and_scale(sk: np.ndarray, normalize_scale: bool = True) -> np.ndarray:
    """Centre on the pelvis and optionally divide by torso length.

    Scale normalisation removes body-size differences between subjects. Keep it
    on: at 80 subjects a graph net will happily learn to recognise individuals
    by their limb proportions, which is memorisation dressed as accuracy.
    """
    sk = sk - sk[:, CENTER_JOINT:CENTER_JOINT + 1, :]
    if normalize_scale:
        torso = np.linalg.norm(
            sk[:, NTU_IDX["SpineShoulder"]] - sk[:, NTU_IDX["SpineBase"]], axis=-1)
        med = float(np.median(torso[np.isfinite(torso) & (torso > 1e-3)])) \
            if np.isfinite(torso).any() else 0.0
        if med > 1e-3:
            sk = sk / med
    return sk.astype(np.float32)


def to_ctvm(sk: np.ndarray) -> np.ndarray:
    """(T, V, 3) -> (3, T, V, 1), the layout PYSKL / MS-G3D expect."""
    return np.ascontiguousarray(sk.transpose(2, 0, 1)[:, :, :, None].astype(np.float32))


def bone_stream(joint_ctvm: np.ndarray) -> np.ndarray:
    """Bone vectors: each joint minus its parent.

    Translation-invariant, and a knee flexion angle *is* a relation between two
    bones — which is why the bone stream tends to beat the joint stream on NTU
    (90.1 vs 89.3 for ST-GCN++) and should matter here too. Note it also
    amplifies independent landmark noise by about sqrt(2); measure, don't assume.
    """
    return joint_ctvm - joint_ctvm[:, :, NTU_PARENTS, :]


def resample_time(sk: np.ndarray, target: int) -> np.ndarray:
    """Linear resample along time to a fixed frame count.

    Resampling destroys duration — which on this dataset is the point. Walk
    length alone reaches AUC ~0.99 and is largely a recording artefact, so a
    fixed frame count denies the network that shortcut.
    """
    T = sk.shape[0]
    if T == target:
        return sk
    src = np.linspace(0, T - 1, T)
    dst = np.linspace(0, T - 1, target)
    out = np.empty((target,) + sk.shape[1:], dtype=np.float32)
    for v in range(sk.shape[1]):
        for c in range(sk.shape[2]):
            out[:, v, c] = np.interp(dst, src, sk[:, v, c])
    return out


def build_ntu_tensor(seq: dict, target_frames: int = 64,
                     normalize_scale: bool = True):
    """From a koa_features.load_sequence() dict to (joint, bone) CTVM tensors.

    load_sequence keeps only the 12 gait joints, so this re-reads the full
    33-landmark world array when present; otherwise pass `world33` directly.
    """
    world = seq["world33"] if "world33" in seq else None
    if world is None:
        raise ValueError("need the full 33-landmark array — use load_sequence_full()")
    sk = mediapipe_to_ntu(world)
    sk = center_and_scale(sk, normalize_scale)
    sk = resample_time(sk, target_frames)
    j = to_ctvm(sk)
    return j, bone_stream(j)
