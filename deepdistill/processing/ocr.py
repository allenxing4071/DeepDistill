"""
OCR 处理器：图片 → 文本
使用 EasyOCR 或 PaddleOCR 提取图片中的文字。

依赖：pip install deepdistill[ocr]
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("deepdistill.ocr")


def extract_text_from_image(file_path: Path) -> str:
    """
    从图片中提取文字。
    默认使用 EasyOCR，支持中英文混合识别。
    """
    from ..config import cfg

    engine = cfg.OCR_ENGINE.lower()

    if engine == "easyocr":
        return _easyocr_extract(file_path, cfg.OCR_LANGUAGES)
    elif engine == "paddleocr":
        return _paddleocr_extract(file_path)
    else:
        raise ValueError(f"不支持的 OCR 引擎: {engine}")


def _easyocr_extract(file_path: Path, languages: list[str]) -> str:
    """使用 EasyOCR 提取文字"""
    import easyocr

    logger.info(f"EasyOCR 识别: {file_path.name} (语言: {languages})")
    reader = easyocr.Reader(languages, gpu=_has_gpu())

    results = reader.readtext(str(file_path))

    # 按位置排序（从上到下，从左到右）
    results.sort(key=lambda r: (r[0][0][1], r[0][0][0]))

    # 合并文本
    texts = [text for _, text, conf in results if conf > 0.3]
    full_text = "\n".join(texts)

    logger.info(f"OCR 完成: {len(texts)} 个文本块, {len(full_text)} 字符")
    return full_text


def _paddleocr_extract(file_path: Path) -> str:
    """使用 PaddleOCR 提取文字"""
    from paddleocr import PaddleOCR

    logger.info(f"PaddleOCR 识别: {file_path.name}")
    ocr = PaddleOCR(use_angle_cls=True, lang="ch")

    result = ocr.ocr(str(file_path), cls=True)

    texts = []
    if result and result[0]:
        for line in result[0]:
            text = line[1][0]
            conf = line[1][1]
            if conf > 0.3:
                texts.append(text)

    full_text = "\n".join(texts)
    logger.info(f"OCR 完成: {len(texts)} 行, {len(full_text)} 字符")
    return full_text


def _has_gpu() -> bool:
    """检测是否有可用 GPU"""
    try:
        import torch
        return torch.cuda.is_available() or torch.backends.mps.is_available()
    except ImportError:
        return False
