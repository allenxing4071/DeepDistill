"""
Layer 5: 融合输出层 — 去重/合并/格式化输出
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("deepdistill.fusion")


def generate_output(result, output_dir: Path, output_format: str = "markdown") -> str:
    """
    根据处理结果生成输出文件。
    返回输出文件路径。
    """
    if output_format == "markdown":
        from .formatters.markdown import format_markdown
        return format_markdown(result, output_dir)
    elif output_format == "json":
        from .formatters.json_fmt import format_json
        return format_json(result, output_dir)
    else:
        raise ValueError(f"不支持的输出格式: {output_format}")
