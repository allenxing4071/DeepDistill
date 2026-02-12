"""
拍摄手法分析
分析视频的构图、景别、镜头运动类型。
基于 OpenCV 光流 + 帧特征分析，不依赖重型 GPU 模型。
"""

from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger("deepdistill.video_analysis.cinematography")


def analyze_cinematography(file_path: Path, scenes: list[dict]) -> dict:
    """
    分析视频的拍摄手法。

    Returns:
        {
            "shot_types": [{"scene_id", "shot_type", "confidence"}],
            "camera_movements": [{"scene_id", "movement_type", "intensity"}],
            "composition": [{"scene_id", "rule_of_thirds_score", "symmetry_score", "dominant_region"}],
            "summary": "整体拍摄风格描述"
        }
    """
    cap = cv2.VideoCapture(str(file_path))
    if not cap.isOpened():
        return {"shot_types": [], "camera_movements": [], "composition": [], "summary": "无法打开视频"}

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    shot_types = []
    camera_movements = []
    compositions = []

    for scene in scenes:
        mid_frame = (scene["start_frame"] + scene["end_frame"]) // 2

        # --- 景别分析 ---
        cap.set(cv2.CAP_PROP_POS_FRAMES, mid_frame)
        ret, frame = cap.read()
        if not ret:
            continue

        shot_type, shot_conf = _classify_shot_type(frame)
        shot_types.append({
            "scene_id": scene["scene_id"],
            "shot_type": shot_type,
            "confidence": round(shot_conf, 3),
        })

        # --- 构图分析 ---
        comp = _analyze_composition(frame)
        comp["scene_id"] = scene["scene_id"]
        compositions.append(comp)

        # --- 镜头运动分析 ---
        movement = _analyze_camera_movement(cap, scene, fps)
        movement["scene_id"] = scene["scene_id"]
        camera_movements.append(movement)

    cap.release()

    # 生成整体描述
    summary = _generate_summary(shot_types, camera_movements, compositions)

    return {
        "shot_types": shot_types,
        "camera_movements": camera_movements,
        "composition": compositions,
        "summary": summary,
    }


def _classify_shot_type(frame: np.ndarray) -> tuple[str, float]:
    """
    景别分类：远景/全景/中景/近景/特写。
    基于人脸占比和边缘分布推断。
    """
    h, w = frame.shape[:2]
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # 人脸检测
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    faces = face_cascade.detectMultiScale(gray, 1.1, 4)

    if len(faces) > 0:
        # 最大人脸的面积占比
        max_face = max(faces, key=lambda f: f[2] * f[3])
        face_ratio = (max_face[2] * max_face[3]) / (w * h)

        if face_ratio > 0.15:
            return "特写", 0.85
        elif face_ratio > 0.05:
            return "近景", 0.80
        elif face_ratio > 0.01:
            return "中景", 0.75
        else:
            return "全景", 0.70
    else:
        # 无人脸：基于边缘密度和纹理判断
        edges = cv2.Canny(gray, 50, 150)
        edge_density = float(np.mean(edges > 0))

        if edge_density < 0.05:
            return "远景", 0.65
        elif edge_density < 0.10:
            return "全景", 0.60
        else:
            return "中景", 0.55


def _analyze_composition(frame: np.ndarray) -> dict:
    """
    构图分析：三分法得分、对称性得分、视觉重心区域。
    """
    h, w = frame.shape[:2]
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(float)

    # --- 三分法得分 ---
    # 检查三分线交叉点附近的视觉权重
    thirds_h = [h // 3, 2 * h // 3]
    thirds_w = [w // 3, 2 * w // 3]
    roi_size = min(h, w) // 10

    thirds_score = 0.0
    for th in thirds_h:
        for tw in thirds_w:
            roi = gray[max(0, th - roi_size):th + roi_size, max(0, tw - roi_size):tw + roi_size]
            # 高对比度区域 = 视觉焦点
            if roi.size > 0:
                thirds_score += float(np.std(roi))
    thirds_score = min(1.0, thirds_score / 400.0)

    # --- 对称性得分 ---
    left_half = gray[:, :w // 2]
    right_half = cv2.flip(gray[:, w // 2:], 1)
    # 确保尺寸一致
    min_w = min(left_half.shape[1], right_half.shape[1])
    left_half = left_half[:, :min_w]
    right_half = right_half[:, :min_w]
    symmetry_diff = np.mean(np.abs(left_half - right_half))
    symmetry_score = max(0.0, 1.0 - symmetry_diff / 128.0)

    # --- 视觉重心 ---
    # 将帧分为 3x3 网格，找到最高权重区域
    regions = ["左上", "中上", "右上", "左中", "中心", "右中", "左下", "中下", "右下"]
    block_h, block_w = h // 3, w // 3
    max_weight = 0
    dominant_idx = 4  # 默认中心

    for i in range(3):
        for j in range(3):
            block = gray[i * block_h:(i + 1) * block_h, j * block_w:(j + 1) * block_w]
            weight = float(np.std(block))  # 标准差作为视觉权重
            if weight > max_weight:
                max_weight = weight
                dominant_idx = i * 3 + j

    return {
        "rule_of_thirds_score": round(thirds_score, 3),
        "symmetry_score": round(symmetry_score, 3),
        "dominant_region": regions[dominant_idx],
    }


def _analyze_camera_movement(cap: cv2.VideoCapture, scene: dict, fps: float) -> dict:
    """
    镜头运动分析：基于光流检测推拉摇移。
    采样场景的前中后三个时间点，计算光流方向和强度。
    """
    start_f = scene["start_frame"]
    end_f = scene["end_frame"]
    duration_frames = end_f - start_f

    if duration_frames < 4:
        return {"movement_type": "静止", "intensity": 0.0}

    # 采样 3 对相邻帧
    sample_points = [
        start_f + duration_frames // 4,
        start_f + duration_frames // 2,
        start_f + 3 * duration_frames // 4,
    ]

    all_dx = []
    all_dy = []
    all_mag = []

    for sp in sample_points:
        cap.set(cv2.CAP_PROP_POS_FRAMES, sp)
        ret1, frame1 = cap.read()
        ret2, frame2 = cap.read()
        if not (ret1 and ret2):
            continue

        gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)

        # 缩小加速
        small1 = cv2.resize(gray1, (160, 90))
        small2 = cv2.resize(gray2, (160, 90))

        flow = cv2.calcOpticalFlowFarneback(small1, small2, None, 0.5, 3, 15, 3, 5, 1.2, 0)
        dx = float(np.median(flow[..., 0]))
        dy = float(np.median(flow[..., 1]))
        mag = float(np.sqrt(dx ** 2 + dy ** 2))

        all_dx.append(dx)
        all_dy.append(dy)
        all_mag.append(mag)

    if not all_mag:
        return {"movement_type": "静止", "intensity": 0.0}

    avg_dx = np.mean(all_dx)
    avg_dy = np.mean(all_dy)
    avg_mag = np.mean(all_mag)

    # 判断运动类型
    if avg_mag < 0.5:
        movement_type = "静止"
    elif abs(avg_dx) > abs(avg_dy) * 2:
        movement_type = "横摇" if avg_dx > 0 else "横摇(反向)"
    elif abs(avg_dy) > abs(avg_dx) * 2:
        movement_type = "俯仰" if avg_dy > 0 else "俯仰(上)"
    elif avg_mag > 2.0:
        # 整体缩放 = 推拉
        # 检查光流是否从中心向外扩散（推）或向中心收缩（拉）
        movement_type = "推拉"
    else:
        movement_type = "轻微移动"

    return {
        "movement_type": movement_type,
        "intensity": round(float(avg_mag), 3),
        "direction": {"dx": round(float(avg_dx), 3), "dy": round(float(avg_dy), 3)},
    }


def _generate_summary(shot_types: list, movements: list, compositions: list) -> str:
    """生成整体拍摄风格描述"""
    if not shot_types:
        return "无法分析"

    # 统计景别分布
    type_counts = {}
    for st in shot_types:
        t = st["shot_type"]
        type_counts[t] = type_counts.get(t, 0) + 1
    dominant_shot = max(type_counts, key=type_counts.get)

    # 统计运动类型
    move_counts = {}
    for m in movements:
        mt = m["movement_type"]
        move_counts[mt] = move_counts.get(mt, 0) + 1
    dominant_move = max(move_counts, key=move_counts.get) if move_counts else "未知"

    # 平均构图得分
    avg_thirds = np.mean([c["rule_of_thirds_score"] for c in compositions]) if compositions else 0
    avg_symmetry = np.mean([c["symmetry_score"] for c in compositions]) if compositions else 0

    parts = [f"以{dominant_shot}为主"]
    if dominant_move != "静止":
        parts.append(f"镜头运动以{dominant_move}为主")
    else:
        parts.append("镜头较为稳定")

    if avg_thirds > 0.5:
        parts.append("构图注重三分法")
    if avg_symmetry > 0.7:
        parts.append("画面对称性较强")

    return "，".join(parts) + "。"
