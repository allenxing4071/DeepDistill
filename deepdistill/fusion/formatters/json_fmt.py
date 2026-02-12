"""
JSON 格式化输出器
将处理结果输出为结构化 JSON 文件。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger("deepdistill.formatter.json")


def format_json(result, output_dir: Path) -> str:
    """将 ProcessingResult 格式化为 JSON 文件"""
    output_dir.mkdir(parents=True, exist_ok=True)

    stem = Path(result.filename).stem
    output_path = output_dir / f"{stem}_distilled.json"

    data = {
        "source": {
            "filename": result.filename,
            "type": result.source_type,
            "path": result.source_path,
        },
        "extracted_text": result.extracted_text,
        "ai_analysis": result.ai_result,
        "video_analysis": result.video_analysis,
        "metadata": {
            "processing_time_sec": result.processing_time_sec,
            "created_at": result.created_at,
            "errors": result.errors,
        },
    }

    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    logger.info(f"JSON 输出: {output_path}")
    return str(output_path)
