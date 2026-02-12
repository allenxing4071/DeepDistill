"""
Layer 2: 内容处理层 — ASR / OCR / 文档提取
根据文件类型分发到对应的处理器，统一返回提取的文本。
"""

from __future__ import annotations

from pathlib import Path


def extract_text(file_path: Path, source_type: str) -> str:
    """
    统一文本提取入口。
    根据 source_type 分发到对应处理器。
    """
    if source_type in ("video", "audio"):
        from .asr import transcribe
        return transcribe(file_path)
    elif source_type == "image":
        from .ocr import extract_text_from_image
        return extract_text_from_image(file_path)
    elif source_type == "document":
        from .document import extract_text_from_document
        return extract_text_from_document(file_path)
    elif source_type == "webpage":
        from .document import extract_text_from_html
        return extract_text_from_html(file_path)
    else:
        raise ValueError(f"不支持的文件类型: {source_type}")
