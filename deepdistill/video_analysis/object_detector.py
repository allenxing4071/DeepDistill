"""
场景 / 物体识别
使用 YOLOv8 对关键帧进行物体检测，识别场景中的主要元素。
当 YOLOv8 不可用时，降级为基于 OpenCV DNN 的简易检测。
"""

from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger("deepdistill.video_analysis.object")


def detect_objects(file_path: Path, scenes: list[dict], conf_threshold: float = 0.4) -> list[dict]:
    """
    对每个场景的关键帧进行物体检测。

    Args:
        file_path: 视频文件路径
        scenes: 场景列表（来自 scene_detector）
        conf_threshold: 置信度阈值

    Returns:
        每个场景的检测结果列表：
        - scene_id: 场景编号
        - objects: 检测到的物体列表 [{label, confidence, bbox}]
        - scene_description: 场景描述
    """
    try:
        from ultralytics import YOLO
        return _yolo_detect(file_path, scenes, conf_threshold)
    except ImportError:
        logger.warning("YOLOv8 (ultralytics) 未安装，使用 OpenCV 简易检测")
        return _opencv_detect(file_path, scenes, conf_threshold)


def _yolo_detect(file_path: Path, scenes: list[dict], conf_threshold: float) -> list[dict]:
    """使用 YOLOv8 进行物体检测"""
    from ultralytics import YOLO

    model = YOLO("yolov8n.pt")  # nano 模型，速度优先
    cap = cv2.VideoCapture(str(file_path))
    results_list = []

    for scene in scenes:
        mid_frame = (scene["start_frame"] + scene["end_frame"]) // 2
        cap.set(cv2.CAP_PROP_POS_FRAMES, mid_frame)
        ret, frame = cap.read()
        if not ret:
            continue

        # YOLOv8 推理
        results = model(frame, verbose=False, conf=conf_threshold)

        objects = []
        for r in results:
            for box in r.boxes:
                cls_id = int(box.cls[0])
                label = model.names[cls_id]
                conf = float(box.conf[0])
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                objects.append({
                    "label": label,
                    "confidence": round(conf, 3),
                    "bbox": [round(x1), round(y1), round(x2), round(y2)],
                })

        # 生成场景描述
        label_counts = {}
        for obj in objects:
            label_counts[obj["label"]] = label_counts.get(obj["label"], 0) + 1

        desc_parts = [f"{count}个{label}" if count > 1 else label for label, count in label_counts.items()]
        description = "、".join(desc_parts[:8]) if desc_parts else "无明显物体"

        results_list.append({
            "scene_id": scene["scene_id"],
            "frame_index": mid_frame,
            "objects": objects,
            "object_count": len(objects),
            "scene_description": description,
        })

    cap.release()
    return results_list


def _opencv_detect(file_path: Path, scenes: list[dict], conf_threshold: float) -> list[dict]:
    """
    OpenCV 简易检测（YOLOv8 不可用时的 fallback）。
    基于颜色直方图和边缘特征描述场景。
    """
    cap = cv2.VideoCapture(str(file_path))
    results_list = []

    for scene in scenes:
        mid_frame = (scene["start_frame"] + scene["end_frame"]) // 2
        cap.set(cv2.CAP_PROP_POS_FRAMES, mid_frame)
        ret, frame = cap.read()
        if not ret:
            continue

        # 基于颜色分布判断场景类型
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(hsv)

        # 亮度分析
        mean_brightness = float(np.mean(v))
        # 饱和度分析
        mean_saturation = float(np.mean(s))
        # 边缘密度（复杂度指标）
        edges = cv2.Canny(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), 50, 150)
        edge_density = float(np.mean(edges > 0))

        # 简易场景分类
        if mean_brightness < 60:
            scene_type = "暗场景/夜景"
        elif mean_brightness > 200:
            scene_type = "高亮/过曝场景"
        elif mean_saturation < 40:
            scene_type = "低饱和度/灰调场景"
        elif edge_density > 0.15:
            scene_type = "复杂场景/多细节"
        else:
            scene_type = "一般场景"

        results_list.append({
            "scene_id": scene["scene_id"],
            "frame_index": mid_frame,
            "objects": [],
            "object_count": 0,
            "scene_description": scene_type,
            "features": {
                "brightness": round(mean_brightness, 1),
                "saturation": round(mean_saturation, 1),
                "edge_density": round(edge_density, 4),
            },
        })

    cap.release()
    return results_list
