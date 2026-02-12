"""
Layer 5: 融合输出层 — 去重/合并/补全 + 格式化输出
先对 AI 结果进行融合处理，再按指定格式输出。
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("deepdistill.fusion")


def generate_output(result, output_dir: Path, output_format: str = "markdown") -> str:
    """
    对处理结果进行融合后处理，然后生成输出文件。
    返回输出文件路径。
    """
    # Step 1: 融合处理（去重/合并/补全/增强）
    if result.ai_result:
        from .processor import process_fusion
        result.ai_result = process_fusion(
            ai_result=result.ai_result,
            extracted_text=result.extracted_text,
            video_analysis=result.video_analysis,
        )

    # Step 2: 格式化输出
    if output_format == "markdown":
        from .formatters.markdown import format_markdown
        return format_markdown(result, output_dir)
    elif output_format == "json":
        from .formatters.json_fmt import format_json
        return format_json(result, output_dir)
    elif output_format == "skill":
        from .formatters.skill_fmt import format_skill
        return format_skill(result, output_dir)
    else:
        raise ValueError(f"不支持的输出格式: {output_format}")
