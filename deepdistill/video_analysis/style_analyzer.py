"""
风格特征分析
分析视频的色彩风格、光影特征、节奏/剪辑速度、视觉冲击力。
纯 OpenCV + NumPy 实现，不依赖 GPU 模型。
"""

from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger("deepdistill.video_analysis.style")


def analyze_style(file_path: Path, scenes: list[dict]) -> dict:
    """
    分析视频的整体视觉风格。

    Returns:
        {
            "color_palette": {"dominant_colors": [...], "color_temperature": str, "saturation_level": str},
            "lighting": {"brightness_level": str, "contrast_level": str, "lighting_style": str},
            "rhythm": {"avg_scene_duration": float, "pace": str, "scene_count": int},
            "visual_impact": {"score": float, "description": str},
            "style_vector": [float, ...],  # 用于下游生成的风格向量
            "summary": str,
        }
    """
    cap = cv2.VideoCapture(str(file_path))
    if not cap.isOpened():
        return {"summary": "无法打开视频"}

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # 采样帧（均匀采样 + 场景关键帧）
    sample_frames = _get_sample_frames(scenes, total_frames, max_samples=20)

    all_colors = []
    all_brightness = []
    all_contrast = []
    all_saturation = []
    all_edge_density = []

    for frame_idx in sample_frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            continue

        # 色彩分析
        colors = _extract_dominant_colors(frame, k=3)
        all_colors.extend(colors)

        # 光影分析
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(hsv)

        all_brightness.append(float(np.mean(v)))
        all_contrast.append(float(np.std(v)))
        all_saturation.append(float(np.mean(s)))

        # 视觉复杂度
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        all_edge_density.append(float(np.mean(edges > 0)))

    cap.release()

    # --- 色彩分析 ---
    color_palette = _analyze_color_palette(all_colors, all_saturation)

    # --- 光影分析 ---
    lighting = _analyze_lighting(all_brightness, all_contrast)

    # --- 节奏分析 ---
    rhythm = _analyze_rhythm(scenes, total_frames, fps)

    # --- 视觉冲击力 ---
    visual_impact = _calculate_visual_impact(
        all_contrast, all_saturation, all_edge_density, rhythm
    )

    # --- 风格向量（12 维，用于下游生成） ---
    style_vector = _compute_style_vector(
        all_brightness, all_contrast, all_saturation, all_edge_density, rhythm
    )

    # --- 总结 ---
    summary = _generate_style_summary(color_palette, lighting, rhythm, visual_impact)

    return {
        "color_palette": color_palette,
        "lighting": lighting,
        "rhythm": rhythm,
        "visual_impact": visual_impact,
        "style_vector": style_vector,
        "summary": summary,
    }


def _get_sample_frames(scenes: list[dict], total_frames: int, max_samples: int = 20) -> list[int]:
    """获取采样帧列表"""
    frames = set()

    # 场景关键帧
    for scene in scenes:
        mid = (scene["start_frame"] + scene["end_frame"]) // 2
        frames.add(mid)

    # 均匀采样补充
    if total_frames > 0:
        step = max(1, total_frames // max_samples)
        for i in range(0, total_frames, step):
            frames.add(i)

    return sorted(frames)[:max_samples]


def _extract_dominant_colors(frame: np.ndarray, k: int = 3) -> list[list[int]]:
    """使用 K-Means 提取主色调"""
    small = cv2.resize(frame, (64, 64))
    pixels = small.reshape(-1, 3).astype(np.float32)

    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    _, labels, centers = cv2.kmeans(pixels, k, None, criteria, 3, cv2.KMEANS_RANDOM_CENTERS)

    # 按出现频率排序
    counts = np.bincount(labels.flatten())
    sorted_idx = np.argsort(-counts)

    colors = []
    for idx in sorted_idx:
        bgr = centers[idx].astype(int).tolist()
        # BGR -> RGB
        colors.append([bgr[2], bgr[1], bgr[0]])

    return colors


def _analyze_color_palette(all_colors: list, all_saturation: list) -> dict:
    """分析色彩风格"""
    if not all_colors:
        return {"dominant_colors": [], "color_temperature": "未知", "saturation_level": "未知"}

    # 取出现最多的 5 种颜色
    # 简化：取所有采样颜色的聚类中心
    colors_arr = np.array(all_colors, dtype=np.float32)
    if len(colors_arr) > 5:
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
        _, _, centers = cv2.kmeans(colors_arr, 5, None, criteria, 3, cv2.KMEANS_RANDOM_CENTERS)
        dominant = centers.astype(int).tolist()
    else:
        dominant = colors_arr.astype(int).tolist()

    # 色温判断（基于 RGB 平均值）
    avg_color = np.mean(colors_arr, axis=0)
    r, g, b = avg_color
    if r > b + 20:
        temperature = "暖色调"
    elif b > r + 20:
        temperature = "冷色调"
    else:
        temperature = "中性色调"

    # 饱和度级别
    avg_sat = np.mean(all_saturation) if all_saturation else 0
    if avg_sat > 120:
        sat_level = "高饱和"
    elif avg_sat > 60:
        sat_level = "中等饱和"
    else:
        sat_level = "低饱和/灰调"

    return {
        "dominant_colors": dominant[:5],
        "color_temperature": temperature,
        "saturation_level": sat_level,
    }


def _analyze_lighting(all_brightness: list, all_contrast: list) -> dict:
    """分析光影特征"""
    if not all_brightness:
        return {"brightness_level": "未知", "contrast_level": "未知", "lighting_style": "未知"}

    avg_brightness = np.mean(all_brightness)
    avg_contrast = np.mean(all_contrast)
    brightness_std = np.std(all_brightness)

    # 亮度级别
    if avg_brightness > 170:
        brightness_level = "高调/明亮"
    elif avg_brightness > 100:
        brightness_level = "中等亮度"
    else:
        brightness_level = "低调/暗沉"

    # 对比度级别
    if avg_contrast > 70:
        contrast_level = "高对比"
    elif avg_contrast > 40:
        contrast_level = "中等对比"
    else:
        contrast_level = "低对比/柔和"

    # 光影风格
    if avg_contrast > 70 and avg_brightness < 100:
        style = "戏剧性光影"
    elif brightness_std > 30:
        style = "明暗交替"
    elif avg_brightness > 150 and avg_contrast < 40:
        style = "柔和均匀"
    else:
        style = "自然光影"

    return {
        "brightness_level": brightness_level,
        "contrast_level": contrast_level,
        "lighting_style": style,
    }


def _analyze_rhythm(scenes: list[dict], total_frames: int, fps: float) -> dict:
    """分析剪辑节奏"""
    scene_count = len(scenes)
    total_duration = total_frames / fps if fps > 0 else 0

    if scene_count > 0:
        durations = [s["duration"] for s in scenes]
        avg_duration = np.mean(durations)
    else:
        avg_duration = total_duration

    # 节奏判断
    if avg_duration < 2.0:
        pace = "快节奏"
    elif avg_duration < 5.0:
        pace = "中等节奏"
    elif avg_duration < 15.0:
        pace = "慢节奏"
    else:
        pace = "超慢节奏/长镜头"

    return {
        "scene_count": scene_count,
        "total_duration_sec": round(total_duration, 2),
        "avg_scene_duration_sec": round(float(avg_duration), 2),
        "pace": pace,
    }


def _calculate_visual_impact(
    all_contrast: list, all_saturation: list, all_edge_density: list, rhythm: dict
) -> dict:
    """计算视觉冲击力评分（0-1）"""
    if not all_contrast:
        return {"score": 0.0, "description": "无法评估"}

    # 各维度归一化评分
    contrast_score = min(1.0, np.mean(all_contrast) / 80.0)
    saturation_score = min(1.0, np.mean(all_saturation) / 150.0)
    complexity_score = min(1.0, np.mean(all_edge_density) / 0.15)

    # 节奏贡献（快节奏 = 高冲击）
    pace_scores = {"快节奏": 0.9, "中等节奏": 0.6, "慢节奏": 0.3, "超慢节奏/长镜头": 0.2}
    pace_score = pace_scores.get(rhythm.get("pace", ""), 0.5)

    # 加权平均
    score = (contrast_score * 0.3 + saturation_score * 0.2 + complexity_score * 0.2 + pace_score * 0.3)

    if score > 0.7:
        desc = "高视觉冲击力"
    elif score > 0.4:
        desc = "中等视觉冲击力"
    else:
        desc = "低视觉冲击力/平静"

    return {"score": round(score, 3), "description": desc}


def _compute_style_vector(
    all_brightness: list, all_contrast: list, all_saturation: list,
    all_edge_density: list, rhythm: dict
) -> list[float]:
    """
    计算 12 维风格向量，用于下游图片/视频素材生成。
    维度：[亮度均值, 亮度标准差, 对比度均值, 对比度标准差,
           饱和度均值, 饱和度标准差, 边缘密度均值, 边缘密度标准差,
           场景数, 平均场景时长, 总时长, 节奏评分]
    """
    def safe_mean(arr): return float(np.mean(arr)) if arr else 0.0
    def safe_std(arr): return float(np.std(arr)) if arr else 0.0

    pace_map = {"快节奏": 0.9, "中等节奏": 0.6, "慢节奏": 0.3, "超慢节奏/长镜头": 0.1}

    return [
        round(safe_mean(all_brightness) / 255.0, 4),
        round(safe_std(all_brightness) / 128.0, 4),
        round(safe_mean(all_contrast) / 128.0, 4),
        round(safe_std(all_contrast) / 64.0, 4),
        round(safe_mean(all_saturation) / 255.0, 4),
        round(safe_std(all_saturation) / 128.0, 4),
        round(safe_mean(all_edge_density), 4),
        round(safe_std(all_edge_density), 4),
        round(rhythm.get("scene_count", 0) / 100.0, 4),
        round(min(1.0, rhythm.get("avg_scene_duration_sec", 0) / 30.0), 4),
        round(min(1.0, rhythm.get("total_duration_sec", 0) / 600.0), 4),
        round(pace_map.get(rhythm.get("pace", ""), 0.5), 4),
    ]


def _generate_style_summary(color_palette: dict, lighting: dict, rhythm: dict, impact: dict) -> str:
    """生成风格总结"""
    parts = []

    temp = color_palette.get("color_temperature", "")
    sat = color_palette.get("saturation_level", "")
    if temp:
        parts.append(temp)
    if sat:
        parts.append(sat)

    style = lighting.get("lighting_style", "")
    if style:
        parts.append(style)

    pace = rhythm.get("pace", "")
    if pace:
        parts.append(pace)

    desc = impact.get("description", "")
    if desc:
        parts.append(desc)

    return "，".join(parts) + "。" if parts else "风格分析不可用。"
