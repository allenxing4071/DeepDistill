"""
转场 / 特效识别
检测视频中的转场类型（硬切、淡入淡出、溶解、擦除等）。
基于帧间特征变化模式分析，纯 OpenCV 实现。
"""

from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger("deepdistill.video_analysis.transition")


def detect_transitions(file_path: Path, scenes: list[dict]) -> list[dict]:
    """
    检测场景之间的转场类型。

    Args:
        file_path: 视频文件路径
        scenes: 场景列表（来自 scene_detector）

    Returns:
        转场列表：
        - from_scene: 前一个场景 ID
        - to_scene: 后一个场景 ID
        - transition_type: 转场类型
        - duration_sec: 转场持续时间（秒）
        - time_sec: 转场发生时间（秒）
    """
    if len(scenes) < 2:
        return []

    cap = cv2.VideoCapture(str(file_path))
    if not cap.isOpened():
        return []

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    transitions = []

    for i in range(len(scenes) - 1):
        current_scene = scenes[i]
        next_scene = scenes[i + 1]

        # 分析转场区域（当前场景末尾 ~ 下一场景开头）
        transition_start = max(0, current_scene["end_frame"] - int(fps * 1.5))
        transition_end = min(
            int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            next_scene["start_frame"] + int(fps * 1.5)
        )

        transition_info = _analyze_transition_region(
            cap, transition_start, transition_end, fps
        )

        transitions.append({
            "from_scene": current_scene["scene_id"],
            "to_scene": next_scene["scene_id"],
            "transition_type": transition_info["type"],
            "duration_sec": round(transition_info["duration"], 2),
            "time_sec": round(current_scene["end_time"], 2),
            "confidence": round(transition_info["confidence"], 3),
        })

    cap.release()
    return transitions


def _analyze_transition_region(
    cap: cv2.VideoCapture, start_frame: int, end_frame: int, fps: float
) -> dict:
    """
    分析转场区域的帧间变化模式，判断转场类型。

    转场类型判断逻辑：
    - 硬切 (cut): 帧间差异突然跳变
    - 淡入淡出 (fade): 亮度渐变到黑/白再恢复
    - 溶解 (dissolve): 帧间差异缓慢持续变化
    - 擦除 (wipe): 差异区域从一侧向另一侧扩展
    """
    frame_count = end_frame - start_frame
    if frame_count < 3:
        return {"type": "硬切", "duration": 0.0, "confidence": 0.8}

    # 采样帧（每隔几帧取一次）
    sample_interval = max(1, frame_count // 20)
    brightness_values = []
    diff_values = []
    prev_gray = None

    for f in range(start_frame, end_frame, sample_interval):
        cap.set(cv2.CAP_PROP_POS_FRAMES, f)
        ret, frame = cap.read()
        if not ret:
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        small = cv2.resize(gray, (80, 45))

        brightness_values.append(float(np.mean(small)))

        if prev_gray is not None:
            diff = float(np.mean(np.abs(small.astype(float) - prev_gray.astype(float))))
            diff_values.append(diff)

        prev_gray = small

    if not diff_values:
        return {"type": "硬切", "duration": 0.0, "confidence": 0.5}

    # --- 判断转场类型 ---

    max_diff = max(diff_values)
    avg_diff = np.mean(diff_values)
    diff_std = np.std(diff_values)

    # 检查亮度是否经过极低值（淡入淡出特征）
    min_brightness = min(brightness_values) if brightness_values else 128
    max_brightness = max(brightness_values) if brightness_values else 128
    brightness_range = max_brightness - min_brightness

    # 硬切：差异集中在一个点
    high_diff_count = sum(1 for d in diff_values if d > avg_diff * 2)

    if high_diff_count <= 2 and max_diff > 20:
        # 差异突然跳变 = 硬切
        return {"type": "硬切", "duration": 0.0, "confidence": 0.85}

    if min_brightness < 30 and brightness_range > 80:
        # 亮度经过极暗 = 淡入淡出
        duration = frame_count / fps
        return {"type": "淡入淡出", "duration": duration, "confidence": 0.75}

    if diff_std < avg_diff * 0.5 and avg_diff > 5:
        # 差异持续且均匀 = 溶解
        duration = frame_count / fps
        return {"type": "溶解", "duration": duration, "confidence": 0.70}

    # 检查擦除（差异区域是否有方向性）
    wipe_detected = _check_wipe_pattern(cap, start_frame, end_frame, sample_interval)
    if wipe_detected:
        duration = frame_count / fps
        return {"type": "擦除", "duration": duration, "confidence": 0.65}

    # 默认：硬切
    return {"type": "硬切", "duration": 0.0, "confidence": 0.60}


def _check_wipe_pattern(
    cap: cv2.VideoCapture, start_frame: int, end_frame: int, sample_interval: int
) -> bool:
    """
    检查是否存在擦除转场模式。
    擦除特征：差异区域从一侧向另一侧扩展。
    """
    frame_count = end_frame - start_frame
    if frame_count < 6:
        return False

    # 取转场区域的前中后三帧
    frames_to_check = [
        start_frame + frame_count // 4,
        start_frame + frame_count // 2,
        start_frame + 3 * frame_count // 4,
    ]

    # 获取第一帧作为参考
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    ret, ref_frame = cap.read()
    if not ret:
        return False
    ref_gray = cv2.resize(cv2.cvtColor(ref_frame, cv2.COLOR_BGR2GRAY), (80, 45))

    # 检查差异区域的重心是否有方向性移动
    centroids = []
    for f in frames_to_check:
        cap.set(cv2.CAP_PROP_POS_FRAMES, f)
        ret, frame = cap.read()
        if not ret:
            continue

        gray = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (80, 45))
        diff = np.abs(gray.astype(float) - ref_gray.astype(float))

        # 差异区域的重心
        threshold = np.mean(diff) + np.std(diff)
        mask = diff > threshold
        if np.any(mask):
            y_coords, x_coords = np.where(mask)
            cx = float(np.mean(x_coords))
            cy = float(np.mean(y_coords))
            centroids.append((cx, cy))

    if len(centroids) < 2:
        return False

    # 检查重心是否有明显的单方向移动
    dx = centroids[-1][0] - centroids[0][0]
    dy = centroids[-1][1] - centroids[0][1]
    movement = np.sqrt(dx ** 2 + dy ** 2)

    return movement > 15  # 重心移动超过阈值 = 擦除
