"""
镜头切割 / 分镜分析
使用 PySceneDetect 检测视频中的场景切换点，提取关键帧。
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger("deepdistill.video_analysis.scene")


def detect_scenes(file_path: Path, threshold: float = 30.0) -> list[dict]:
    """
    检测视频中的场景切换。

    Args:
        file_path: 视频文件路径
        threshold: 场景切换阈值（ContentDetector 默认 27.0，适当提高减少误检）

    Returns:
        场景列表，每个场景包含：
        - scene_id: 场景编号
        - start_time: 开始时间（秒）
        - end_time: 结束时间（秒）
        - duration: 持续时间（秒）
        - start_frame: 开始帧号
        - end_frame: 结束帧号
        - keyframe_path: 关键帧图片路径（可选）
    """
    try:
        from scenedetect import open_video, SceneManager
        from scenedetect.detectors import ContentDetector
    except ImportError:
        logger.warning("PySceneDetect 未安装，使用 OpenCV 简易检测")
        return _fallback_detect_scenes(file_path, threshold)

    video = open_video(str(file_path))
    scene_manager = SceneManager()
    scene_manager.add_detector(ContentDetector(threshold=threshold))

    # 执行检测
    scene_manager.detect_scenes(video)
    scene_list = scene_manager.get_scene_list()

    scenes = []
    for i, (start, end) in enumerate(scene_list):
        start_sec = start.get_seconds()
        end_sec = end.get_seconds()
        scenes.append({
            "scene_id": i + 1,
            "start_time": round(start_sec, 2),
            "end_time": round(end_sec, 2),
            "duration": round(end_sec - start_sec, 2),
            "start_frame": start.get_frames(),
            "end_frame": end.get_frames(),
        })

    # 如果没检测到场景切换，把整个视频当一个场景
    if not scenes:
        cap = cv2.VideoCapture(str(file_path))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()
        duration = total_frames / fps
        scenes.append({
            "scene_id": 1,
            "start_time": 0.0,
            "end_time": round(duration, 2),
            "duration": round(duration, 2),
            "start_frame": 0,
            "end_frame": total_frames,
        })

    return scenes


def _fallback_detect_scenes(file_path: Path, threshold: float = 30.0) -> list[dict]:
    """
    OpenCV 简易场景检测（PySceneDetect 不可用时的 fallback）。
    基于帧间差异检测场景切换。
    """
    cap = cv2.VideoCapture(str(file_path))
    if not cap.isOpened():
        logger.error(f"无法打开视频: {file_path}")
        return []

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    scenes = []
    prev_frame = None
    scene_start_frame = 0
    scene_id = 1

    # 每隔几帧采样（加速处理）
    sample_interval = max(1, int(fps / 5))
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % sample_interval == 0:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.resize(gray, (160, 90))  # 缩小加速

            if prev_frame is not None:
                diff = np.mean(np.abs(gray.astype(float) - prev_frame.astype(float)))
                if diff > threshold:
                    # 场景切换
                    scenes.append({
                        "scene_id": scene_id,
                        "start_time": round(scene_start_frame / fps, 2),
                        "end_time": round(frame_idx / fps, 2),
                        "duration": round((frame_idx - scene_start_frame) / fps, 2),
                        "start_frame": scene_start_frame,
                        "end_frame": frame_idx,
                    })
                    scene_id += 1
                    scene_start_frame = frame_idx

            prev_frame = gray

        frame_idx += 1

    # 最后一个场景
    if scene_start_frame < total_frames:
        scenes.append({
            "scene_id": scene_id,
            "start_time": round(scene_start_frame / fps, 2),
            "end_time": round(total_frames / fps, 2),
            "duration": round((total_frames - scene_start_frame) / fps, 2),
            "start_frame": scene_start_frame,
            "end_frame": total_frames,
        })

    cap.release()
    return scenes


def extract_keyframes(file_path: Path, scenes: list[dict], output_dir: Path | None = None) -> list[str]:
    """
    从每个场景中提取关键帧（中间帧）。
    返回关键帧图片路径列表。
    注意：如果 output_dir 为 None，会创建临时目录，调用方需负责清理。
    """
    if output_dir is None:
        # 使用项目 data 目录下的子目录，而非系统临时目录，便于统一清理
        from ..config import cfg
        output_dir = cfg.DATA_DIR / "output" / "keyframes" / f"kf_{file_path.stem}"
    output_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(file_path))
    keyframe_paths = []

    for scene in scenes:
        mid_frame = (scene["start_frame"] + scene["end_frame"]) // 2
        cap.set(cv2.CAP_PROP_POS_FRAMES, mid_frame)
        ret, frame = cap.read()
        if ret:
            path = output_dir / f"scene_{scene['scene_id']:03d}.jpg"
            cv2.imwrite(str(path), frame)
            keyframe_paths.append(str(path))

    cap.release()
    return keyframe_paths
