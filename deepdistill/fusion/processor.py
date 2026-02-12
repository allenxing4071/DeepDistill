"""
融合处理器 — 去重 / 合并 / 补全
对 AI 分析结果进行后处理：去除重复内容、合并相似观点、补全缺失字段。
"""

from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger("deepdistill.fusion.processor")


def process_fusion(ai_result: dict, extracted_text: str, video_analysis: dict | None = None) -> dict:
    """
    对 AI 分析结果进行融合处理。

    步骤：
    1. 去重：移除重复的关键词和要点
    2. 合并：合并相似的要点
    3. 补全：确保所有必要字段存在且有效
    4. 增强：结合视频分析结果丰富内容

    Args:
        ai_result: AI 提炼的原始结果
        extracted_text: 原始提取文本
        video_analysis: 视频分析结果（可选）

    Returns:
        融合处理后的结果
    """
    if not ai_result:
        return _create_empty_result()

    result = dict(ai_result)

    # Step 1: 去重
    result = _deduplicate(result)

    # Step 2: 合并相似要点
    result = _merge_similar_points(result)

    # Step 3: 补全缺失字段
    result = _complete_missing_fields(result, extracted_text)

    # Step 4: 结合视频分析增强
    if video_analysis:
        result = _enhance_with_video(result, video_analysis)

    # Step 5: 质量检查
    result = _quality_check(result)

    return result


def _deduplicate(result: dict) -> dict:
    """去除重复的关键词和要点"""
    # 关键词去重（忽略大小写和空格）
    keywords = result.get("keywords", [])
    if keywords:
        seen = set()
        unique_keywords = []
        for kw in keywords:
            normalized = kw.strip().lower()
            if normalized and normalized not in seen:
                seen.add(normalized)
                unique_keywords.append(kw.strip())
        result["keywords"] = unique_keywords

    # 要点去重（基于文本相似度）
    key_points = result.get("key_points", [])
    if key_points:
        unique_points = []
        for point in key_points:
            point = point.strip()
            if not point:
                continue
            is_dup = False
            for existing in unique_points:
                if _text_similarity(point, existing) > 0.7:
                    is_dup = True
                    break
            if not is_dup:
                unique_points.append(point)
        result["key_points"] = unique_points

    return result


def _merge_similar_points(result: dict) -> dict:
    """合并相似的要点（相似度 0.5-0.7 之间的合并为一条）"""
    key_points = result.get("key_points", [])
    if len(key_points) < 2:
        return result

    merged = []
    used = set()

    for i, point_a in enumerate(key_points):
        if i in used:
            continue

        # 查找可合并的要点
        merge_group = [point_a]
        for j, point_b in enumerate(key_points):
            if j <= i or j in used:
                continue
            sim = _text_similarity(point_a, point_b)
            if 0.4 < sim < 0.7:
                merge_group.append(point_b)
                used.add(j)

        if len(merge_group) > 1:
            # 合并：取最长的作为主体
            merged_point = max(merge_group, key=len)
            merged.append(merged_point)
        else:
            merged.append(point_a)

        used.add(i)

    result["key_points"] = merged
    return result


def _complete_missing_fields(result: dict, extracted_text: str) -> dict:
    """确保所有必要字段存在且有效"""
    # 确保 summary 存在
    if not result.get("summary"):
        # 从文本中截取前 200 字符作为摘要
        result["summary"] = extracted_text[:200].strip() + "..." if len(extracted_text) > 200 else extracted_text.strip()

    # 确保 key_points 存在且非空
    if not result.get("key_points"):
        # 从文本中提取句子作为要点
        sentences = re.split(r'[。！？\n]', extracted_text)
        result["key_points"] = [s.strip() for s in sentences if len(s.strip()) > 10][:5]

    # 确保 keywords 存在且非空
    if not result.get("keywords"):
        result["keywords"] = []

    # 确保 structure 存在
    if not result.get("structure"):
        result["structure"] = {
            "type": "未分类",
            "sections": [],
        }

    # 限制字段长度
    if len(result.get("summary", "")) > 500:
        result["summary"] = result["summary"][:497] + "..."

    if len(result.get("key_points", [])) > 10:
        result["key_points"] = result["key_points"][:10]

    if len(result.get("keywords", [])) > 15:
        result["keywords"] = result["keywords"][:15]

    return result


def _enhance_with_video(result: dict, video_analysis: dict) -> dict:
    """结合视频分析结果丰富内容"""
    # 添加视频风格信息到结构中
    style = video_analysis.get("style", {})
    if style and style.get("summary"):
        if "structure" not in result:
            result["structure"] = {"type": "视频", "sections": []}

        result["structure"].setdefault("sections", []).append({
            "heading": "视觉风格",
            "content": style["summary"],
        })

    # 添加场景信息
    scenes = video_analysis.get("scenes", [])
    if scenes:
        scene_count = len(scenes)
        total_duration = sum(s.get("duration", 0) for s in scenes)
        result["structure"].setdefault("sections", []).append({
            "heading": "视频结构",
            "content": f"共 {scene_count} 个场景，总时长 {round(total_duration, 1)} 秒",
        })

    # 从物体检测结果补充关键词
    objects = video_analysis.get("objects", [])
    if objects:
        existing_keywords = set(kw.lower() for kw in result.get("keywords", []))
        for obj_result in objects:
            for obj in obj_result.get("objects", []):
                label = obj.get("label", "")
                if label and label.lower() not in existing_keywords:
                    result.setdefault("keywords", []).append(label)
                    existing_keywords.add(label.lower())

    # 拍摄手法信息
    cinematography = video_analysis.get("cinematography", {})
    if cinematography and cinematography.get("summary"):
        result["structure"].setdefault("sections", []).append({
            "heading": "拍摄手法",
            "content": cinematography["summary"],
        })

    return result


def _quality_check(result: dict) -> dict:
    """质量检查：确保输出格式规范"""
    # 清理空白要点
    result["key_points"] = [p for p in result.get("key_points", []) if p.strip()]

    # 清理空白关键词
    result["keywords"] = [kw for kw in result.get("keywords", []) if kw.strip()]

    # 确保 sections 中的 heading 和 content 都非空
    if result.get("structure", {}).get("sections"):
        result["structure"]["sections"] = [
            s for s in result["structure"]["sections"]
            if s.get("heading") and s.get("content")
        ]

    return result


def _text_similarity(text_a: str, text_b: str) -> float:
    """
    简易文本相似度（基于字符级 Jaccard 系数）。
    返回 0-1 之间的相似度。
    """
    if not text_a or not text_b:
        return 0.0

    # 使用 2-gram 字符集合
    set_a = set(_ngrams(text_a.lower(), 2))
    set_b = set(_ngrams(text_b.lower(), 2))

    if not set_a or not set_b:
        return 0.0

    intersection = len(set_a & set_b)
    union = len(set_a | set_b)

    return intersection / union if union > 0 else 0.0


def _ngrams(text: str, n: int = 2) -> list[str]:
    """生成 n-gram 列表"""
    # 去除标点和空格
    clean = re.sub(r'[^\w]', '', text)
    return [clean[i:i + n] for i in range(len(clean) - n + 1)]


def _create_empty_result() -> dict:
    """创建空的结果结构"""
    return {
        "summary": "",
        "key_points": [],
        "keywords": [],
        "structure": {
            "type": "未分类",
            "sections": [],
        },
    }
