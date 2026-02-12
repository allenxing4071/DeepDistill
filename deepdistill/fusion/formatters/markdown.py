"""
Markdown 格式化输出器
将处理结果输出为可读的 Markdown 文件。
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("deepdistill.formatter.markdown")


def format_markdown(result, output_dir: Path) -> str:
    """将 ProcessingResult 格式化为 Markdown 文件"""
    output_dir.mkdir(parents=True, exist_ok=True)

    # 生成文件名（去掉原扩展名，加 .md）
    stem = Path(result.filename).stem
    output_path = output_dir / f"{stem}_distilled.md"

    lines = []

    # 标题
    lines.append(f"# {stem}")
    lines.append("")
    lines.append(f"> 来源: `{result.filename}` | 类型: {result.source_type} | 处理耗时: {result.processing_time_sec}s")
    lines.append("")

    # AI 提炼结果
    ai = result.ai_result
    if ai:
        # 摘要
        if ai.get("summary"):
            lines.append("## 摘要")
            lines.append("")
            lines.append(ai["summary"])
            lines.append("")

        # 核心观点
        if ai.get("key_points"):
            lines.append("## 核心观点")
            lines.append("")
            for point in ai["key_points"]:
                lines.append(f"- {point}")
            lines.append("")

        # 关键词
        if ai.get("keywords"):
            lines.append("## 关键词")
            lines.append("")
            tags = " ".join([f"`{kw}`" for kw in ai["keywords"]])
            lines.append(tags)
            lines.append("")

        # 内容结构
        structure = ai.get("structure")
        if structure:
            lines.append("## 内容结构")
            lines.append("")
            if structure.get("type"):
                lines.append(f"**类型**: {structure['type']}")
                lines.append("")
            for section in structure.get("sections", []):
                lines.append(f"### {section.get('heading', '未命名')}")
                lines.append("")
                lines.append(section.get("content", ""))
                lines.append("")

    # 原始文本（折叠）
    if result.extracted_text:
        lines.append("---")
        lines.append("")
        lines.append("<details>")
        lines.append("<summary>📝 原始提取文本</summary>")
        lines.append("")
        # 限制长度
        text = result.extracted_text
        if len(text) > 5000:
            text = text[:5000] + f"\n\n... (共 {len(result.extracted_text)} 字符，已截断)"
        lines.append(text)
        lines.append("")
        lines.append("</details>")
        lines.append("")

    # 错误信息
    if result.errors:
        lines.append("---")
        lines.append("")
        lines.append("## ⚠️ 处理警告")
        lines.append("")
        for err in result.errors:
            lines.append(f"- {err}")
        lines.append("")

    # 写入文件
    content = "\n".join(lines)
    output_path.write_text(content, encoding="utf-8")

    logger.info(f"Markdown 输出: {output_path}")
    return str(output_path)
