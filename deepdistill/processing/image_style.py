"""
图片风格分析模块
当 intent=style 且文件类型为 image 时，分析图片的视觉/设计风格。
分析维度：色彩（主色调/色温/饱和度）、光影（亮度/对比度）、构图（三分法/对称性）、视觉复杂度。
纯 OpenCV + NumPy 实现，不依赖 GPU 模型。
"""

from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger("deepdistill.processing.image_style")


def analyze_image_style(file_path: Path) -> dict:
    """
    分析单张图片的视觉/设计风格。

    Returns:
        {
            "color_palette": {"dominant_colors": [...], "color_temperature": str, "saturation_level": str},
            "lighting": {"brightness_level": str, "contrast_level": str, "lighting_style": str},
            "composition": {"rule_of_thirds_score": float, "symmetry_score": float, "visual_center": str},
            "complexity": {"edge_density": float, "level": str},
            "dimensions": {"width": int, "height": int, "aspect_ratio": str},
            "summary": str,
        }
    """
    img = cv2.imread(str(file_path))
    if img is None:
        return {"summary": "无法读取图片", "error": True}

    h, w = img.shape[:2]

    # ── 色彩分析 ──
    color_palette = _analyze_colors(img)

    # ── 光影分析 ──
    lighting = _analyze_lighting(img)

    # ── 构图分析 ──
    composition = _analyze_composition(img)

    # ── 视觉复杂度 ──
    complexity = _analyze_complexity(img)

    # ── 尺寸信息 ──
    aspect = _get_aspect_ratio(w, h)
    dimensions = {"width": w, "height": h, "aspect_ratio": aspect}

    # ── 总结 ──
    summary = _generate_summary(color_palette, lighting, composition, complexity)

    return {
        "color_palette": color_palette,
        "lighting": lighting,
        "composition": composition,
        "complexity": complexity,
        "dimensions": dimensions,
        "summary": summary,
    }


def _analyze_colors(img: np.ndarray) -> dict:
    """分析图片色彩风格"""
    # 缩小图片加速处理
    small = cv2.resize(img, (64, 64))
    pixels = small.reshape(-1, 3).astype(np.float32)

    # K-Means 提取主色调
    k = 5
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    _, labels, centers = cv2.kmeans(pixels, k, None, criteria, 3, cv2.KMEANS_RANDOM_CENTERS)

    # 按出现频率排序
    counts = np.bincount(labels.flatten())
    sorted_idx = np.argsort(-counts)

    dominant_colors = []
    for idx in sorted_idx:
        bgr = centers[idx].astype(int).tolist()
        dominant_colors.append([bgr[2], bgr[1], bgr[0]])  # BGR -> RGB

    # 色温判断
    avg_color = np.mean(pixels, axis=0)  # BGR
    b, _g, r = avg_color
    if r > b + 20:
        temperature = "暖色调"
    elif b > r + 20:
        temperature = "冷色调"
    else:
        temperature = "中性色调"

    # 饱和度
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    avg_sat = float(np.mean(hsv[:, :, 1]))
    if avg_sat > 120:
        sat_level = "高饱和"
    elif avg_sat > 60:
        sat_level = "中等饱和"
    else:
        sat_level = "低饱和/灰调"

    return {
        "dominant_colors": dominant_colors[:5],
        "color_temperature": temperature,
        "saturation_level": sat_level,
    }


def _analyze_lighting(img: np.ndarray) -> dict:
    """分析光影特征"""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    v = hsv[:, :, 2]

    avg_brightness = float(np.mean(v))
    avg_contrast = float(np.std(v))

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
    elif avg_contrast > 70 and avg_brightness > 150:
        style = "强烈明暗对比"
    elif avg_brightness > 150 and avg_contrast < 40:
        style = "柔和均匀"
    else:
        style = "自然光影"

    return {
        "brightness_level": brightness_level,
        "contrast_level": contrast_level,
        "lighting_style": style,
    }


def _analyze_composition(img: np.ndarray) -> dict:
    """分析构图特征"""
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 三分法评分：检测关键内容是否在三分线交叉点附近
    thirds_score = _rule_of_thirds_score(gray)

    # 对称性评分
    symmetry_score = _symmetry_score(gray)

    # 视觉重心
    visual_center = _visual_center(gray, h, w)

    return {
        "rule_of_thirds_score": round(thirds_score, 3),
        "symmetry_score": round(symmetry_score, 3),
        "visual_center": visual_center,
    }


def _rule_of_thirds_score(gray: np.ndarray) -> float:
    """三分法评分（0-1），越高表示内容越集中在三分线附近"""
    h, w = gray.shape
    # 三分线位置
    third_h = [h // 3, 2 * h // 3]
    third_w = [w // 3, 2 * w // 3]

    # 使用边缘检测找到内容区域
    edges = cv2.Canny(gray, 50, 150)

    # 计算三分线区域（±10% 范围）的边缘密度
    margin_h = max(1, h // 10)
    margin_w = max(1, w // 10)

    thirds_region_sum = 0
    total_edge = float(np.sum(edges > 0))
    if total_edge == 0:
        return 0.5

    for th in third_h:
        region = edges[max(0, th - margin_h):min(h, th + margin_h), :]
        thirds_region_sum += float(np.sum(region > 0))

    for tw in third_w:
        region = edges[:, max(0, tw - margin_w):min(w, tw + margin_w)]
        thirds_region_sum += float(np.sum(region > 0))

    score = thirds_region_sum / (total_edge * 2 + 1e-6)
    return min(1.0, score)


def _symmetry_score(gray: np.ndarray) -> float:
    """对称性评分（0-1），越高越对称"""
    _h, w = gray.shape
    half_w = w // 2

    left = gray[:, :half_w].astype(np.float32)
    right = np.flip(gray[:, w - half_w:], axis=1).astype(np.float32)

    # 计算左右差异
    diff = np.abs(left - right)
    score = 1.0 - float(np.mean(diff)) / 255.0
    return max(0.0, score)


def _visual_center(gray: np.ndarray, h: int, w: int) -> str:
    """判断视觉重心位置"""
    # 使用亮度加权质心
    y_coords, x_coords = np.mgrid[0:h, 0:w]
    weights = gray.astype(np.float32)
    total_weight = np.sum(weights) + 1e-6

    cx = float(np.sum(x_coords * weights) / total_weight)
    cy = float(np.sum(y_coords * weights) / total_weight)

    # 归一化到 0-1
    nx = cx / w
    ny = cy / h

    # 判断位置
    v_suffix = _vertical_suffix(ny)
    if 0.35 < nx < 0.65 and 0.35 < ny < 0.65:
        return "居中"
    elif nx < 0.35:
        return "偏左" + v_suffix
    elif nx > 0.65:
        return "偏右" + v_suffix
    elif ny < 0.35:
        return "偏上"
    else:
        return "偏下"


def _vertical_suffix(ny: float) -> str:
    """根据纵向归一化坐标返回方位后缀"""
    if ny < 0.35:
        return "上"
    elif ny > 0.65:
        return "下"
    return ""


def _analyze_complexity(img: np.ndarray) -> dict:
    """分析视觉复杂度"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    edge_density = float(np.mean(edges > 0))

    if edge_density > 0.15:
        level = "高复杂度/细节丰富"
    elif edge_density > 0.08:
        level = "中等复杂度"
    elif edge_density > 0.03:
        level = "简洁"
    else:
        level = "极简/纯色"

    return {
        "edge_density": round(edge_density, 4),
        "level": level,
    }


def _get_aspect_ratio(w: int, h: int) -> str:
    """获取宽高比描述"""
    ratio = w / h if h > 0 else 1
    if abs(ratio - 1.0) < 0.1:
        return "1:1 正方形"
    elif abs(ratio - 16 / 9) < 0.15:
        return "16:9 宽屏"
    elif abs(ratio - 4 / 3) < 0.1:
        return "4:3 标准"
    elif abs(ratio - 9 / 16) < 0.15:
        return "9:16 竖屏"
    elif abs(ratio - 3 / 4) < 0.1:
        return "3:4 竖版"
    elif ratio > 2:
        return "超宽幅"
    elif ratio < 0.5:
        return "超长竖幅"
    else:
        return f"{round(ratio, 2)}:1"


def _generate_summary(
    color_palette: dict, lighting: dict, composition: dict, complexity: dict
) -> str:
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

    # 构图
    thirds = composition.get("rule_of_thirds_score", 0)
    sym = composition.get("symmetry_score", 0)
    if sym > 0.85:
        parts.append("对称构图")
    elif thirds > 0.3:
        parts.append("三分法构图")
    else:
        parts.append("自由构图")

    level = complexity.get("level", "")
    if level:
        parts.append(level)

    return "，".join(parts) + "。" if parts else "风格分析不可用。"
