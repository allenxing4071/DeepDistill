"""
Layer 3: 视频增强分析层
对视频进行多维度分析：镜头切割、场景识别、动作识别、拍摄手法、风格特征、转场检测。
分析级别由 config.yaml 的 video_analysis.level 控制：off / basic / standard / full。
"""

from __future__ import annotations

import logging
from pathlib import Path

from ..config import cfg

logger = logging.getLogger("deepdistill.video_analysis")


def analyze_video(file_path: Path) -> dict:
    """
    视频增强分析入口。
    根据 VIDEO_ANALYSIS_LEVEL 决定分析深度：
    - basic: 仅镜头切割 + 基础风格
    - standard: + 场景识别 + 动作识别
    - full: + 拍摄手法 + 转场检测
    """
    level = cfg.VIDEO_ANALYSIS_LEVEL
    logger.info(f"视频分析开始: {file_path.name} (级别: {level})")

    result = {
        "scenes": [],
        "objects": [],
        "actions": [],
        "cinematography": {},
        "style": {},
        "transitions": [],
        "analysis_level": level,
    }

    # basic 级别：镜头切割 + 基础风格
    if level in ("basic", "standard", "full"):
        try:
            from .scene_detector import detect_scenes
            result["scenes"] = detect_scenes(file_path)
            logger.info(f"  镜头切割: {len(result['scenes'])} 个场景")
        except Exception as e:
            logger.warning(f"  镜头切割失败: {e}")

        try:
            from .style_analyzer import analyze_style
            result["style"] = analyze_style(file_path, result["scenes"])
            logger.info(f"  风格分析完成")
        except Exception as e:
            logger.warning(f"  风格分析失败: {e}")

    # standard 级别：+ 场景识别 + 动作识别
    if level in ("standard", "full"):
        try:
            from .object_detector import detect_objects
            result["objects"] = detect_objects(file_path, result["scenes"])
            logger.info(f"  场景识别: {len(result['objects'])} 个关键帧分析")
        except Exception as e:
            logger.warning(f"  场景识别失败: {e}")

        try:
            from .action_detector import detect_actions
            result["actions"] = detect_actions(file_path, result["scenes"])
            logger.info(f"  动作识别: {len(result['actions'])} 个动作")
        except Exception as e:
            logger.warning(f"  动作识别失败: {e}")

    # full 级别：+ 拍摄手法 + 转场检测
    if level == "full":
        try:
            from .cinematography import analyze_cinematography
            result["cinematography"] = analyze_cinematography(file_path, result["scenes"])
            logger.info(f"  拍摄手法分析完成")
        except Exception as e:
            logger.warning(f"  拍摄手法分析失败: {e}")

        try:
            from .transition_detector import detect_transitions
            result["transitions"] = detect_transitions(file_path, result["scenes"])
            logger.info(f"  转场检测: {len(result['transitions'])} 个转场")
        except Exception as e:
            logger.warning(f"  转场检测失败: {e}")

    logger.info(f"视频分析完成: {file_path.name}")
    return result
