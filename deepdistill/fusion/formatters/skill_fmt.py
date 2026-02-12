"""
Skill 文档格式化输出器
将处理结果输出为可交互/可复用的结构化 Skill 文档（Markdown 变体）。
Skill 文档特点：
- 标准化的元数据头部
- 知识点分层（概念/原理/实践/经验）
- 可复用的代码片段和操作步骤
- 关联标签系统
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("deepdistill.formatter.skill")


def format_skill(result, output_dir: Path) -> str:
    """将 ProcessingResult 格式化为 Skill 文档"""
    output_dir.mkdir(parents=True, exist_ok=True)

    stem = Path(result.filename).stem
    output_path = output_dir / f"{stem}_skill.md"

    lines = []
    ai = result.ai_result or {}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # ── 元数据头部（YAML Front Matter） ──
    lines.append("---")
    lines.append(f"title: \"{stem}\"")
    lines.append(f"source: \"{result.filename}\"")
    lines.append(f"source_type: \"{result.source_type}\"")
    lines.append(f"created: \"{now}\"")

    keywords = ai.get("keywords", [])
    if keywords:
        tags_str = ", ".join(f'"{kw}"' for kw in keywords[:10])
        lines.append(f"tags: [{tags_str}]")

    content_type = ai.get("structure", {}).get("type", "未分类")
    lines.append(f"category: \"{content_type}\"")
    lines.append(f"processing_time: {result.processing_time_sec}s")
    lines.append("---")
    lines.append("")

    # ── 标题 ──
    lines.append(f"# {stem}")
    lines.append("")

    # ── 核心摘要（一句话概括） ──
    summary = ai.get("summary", "")
    if summary:
        lines.append("> **核心摘要**: " + summary)
        lines.append("")

    # ── 关键词标签 ──
    if keywords:
        tags = " ".join(f"`#{kw}`" for kw in keywords)
        lines.append(f"**标签**: {tags}")
        lines.append("")

    # ── 知识要点 ──
    key_points = ai.get("key_points", [])
    if key_points:
        lines.append("## 知识要点")
        lines.append("")
        for i, point in enumerate(key_points, 1):
            lines.append(f"{i}. {point}")
        lines.append("")

    # ── 内容结构（分层知识） ──
    structure = ai.get("structure", {})
    sections = structure.get("sections", [])
    if sections:
        lines.append("## 详细内容")
        lines.append("")
        for section in sections:
            heading = section.get("heading", "未命名")
            content = section.get("content", "")
            lines.append(f"### {heading}")
            lines.append("")
            lines.append(content)
            lines.append("")

    # ── 视频分析（如有） ──
    if result.video_analysis and result.source_type == "video":
        va = result.video_analysis
        lines.append("## 视频分析")
        lines.append("")

        # 场景信息
        scenes = va.get("scenes", [])
        if scenes:
            lines.append(f"**场景数**: {len(scenes)}")
            lines.append("")
            lines.append("| 场景 | 时间范围 | 时长 |")
            lines.append("|------|----------|------|")
            for s in scenes[:20]:  # 最多显示 20 个
                lines.append(f"| #{s['scene_id']} | {s['start_time']}s - {s['end_time']}s | {s['duration']}s |")
            lines.append("")

        # 风格信息
        style = va.get("style", {})
        if style and style.get("summary"):
            lines.append(f"**视觉风格**: {style['summary']}")
            lines.append("")

            color = style.get("color_palette", {})
            if color:
                lines.append(f"- 色温: {color.get('color_temperature', '未知')}")
                lines.append(f"- 饱和度: {color.get('saturation_level', '未知')}")

            lighting = style.get("lighting", {})
            if lighting:
                lines.append(f"- 光影: {lighting.get('lighting_style', '未知')}")

            rhythm = style.get("rhythm", {})
            if rhythm:
                lines.append(f"- 节奏: {rhythm.get('pace', '未知')} (平均 {rhythm.get('avg_scene_duration_sec', 0)}s/场景)")

            lines.append("")

        # 拍摄手法
        cinema = va.get("cinematography", {})
        if cinema and cinema.get("summary"):
            lines.append(f"**拍摄手法**: {cinema['summary']}")
            lines.append("")

        # 转场
        transitions = va.get("transitions", [])
        if transitions:
            trans_types = {}
            for t in transitions:
                tt = t.get("transition_type", "未知")
                trans_types[tt] = trans_types.get(tt, 0) + 1
            trans_desc = "、".join(f"{t}({c}次)" for t, c in trans_types.items())
            lines.append(f"**转场类型**: {trans_desc}")
            lines.append("")

    # ── 实践指南（可操作的建议） ──
    lines.append("## 实践指南")
    lines.append("")
    lines.append("### 如何使用这份知识")
    lines.append("")
    if content_type == "教程":
        lines.append("1. 按照知识要点中的步骤逐步实践")
        lines.append("2. 参考详细内容中的具体操作说明")
        lines.append("3. 遇到问题时回顾相关章节")
    elif content_type == "分析":
        lines.append("1. 理解核心摘要中的主要结论")
        lines.append("2. 深入阅读各分析维度的详细内容")
        lines.append("3. 将分析结论应用到实际决策中")
    else:
        lines.append("1. 快速浏览核心摘要了解主旨")
        lines.append("2. 根据关键词标签关联相关知识")
        lines.append("3. 深入阅读感兴趣的章节")
    lines.append("")

    # ── 关联知识 ──
    lines.append("### 关联知识")
    lines.append("")
    if keywords:
        for kw in keywords[:5]:
            lines.append(f"- 搜索: `{kw}` 查找相关内容")
    lines.append("")

    # ── 元信息 ──
    lines.append("---")
    lines.append("")
    lines.append("## 元信息")
    lines.append("")
    lines.append(f"- **来源文件**: `{result.filename}`")
    lines.append(f"- **文件类型**: {result.source_type}")
    lines.append(f"- **处理耗时**: {result.processing_time_sec}s")
    lines.append(f"- **提取文本长度**: {len(result.extracted_text)} 字符")
    lines.append(f"- **生成时间**: {now}")
    lines.append("")

    # 写入文件
    content = "\n".join(lines)
    output_path.write_text(content, encoding="utf-8")

    logger.info(f"Skill 文档输出: {output_path}")
    return str(output_path)
