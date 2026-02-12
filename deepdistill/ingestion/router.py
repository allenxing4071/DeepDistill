"""
输入层：文件格式识别与路由
根据文件扩展名和 MIME 类型，将文件分发到对应的处理器。
"""

from __future__ import annotations

from pathlib import Path

# 文件类型映射
_TYPE_MAP: dict[str, str] = {
    # 视频
    ".mp4": "video", ".mov": "video", ".avi": "video",
    ".mkv": "video", ".webm": "video", ".flv": "video",
    # 音频
    ".mp3": "audio", ".wav": "audio", ".m4a": "audio",
    ".flac": "audio", ".ogg": "audio", ".aac": "audio",
    # 文档
    ".pdf": "document", ".docx": "document", ".doc": "document",
    ".pptx": "document", ".ppt": "document",
    ".xlsx": "document", ".xls": "document",
    ".txt": "document", ".md": "document",
    # 图片
    ".jpg": "image", ".jpeg": "image", ".png": "image",
    ".bmp": "image", ".tiff": "image", ".webp": "image",
    ".gif": "image",
    # 网页
    ".html": "webpage", ".htm": "webpage",
}


def identify_file_type(file_path: Path) -> str | None:
    """
    识别文件类型，返回类型字符串。
    返回值：video / audio / document / image / webpage / None（不支持）
    """
    suffix = file_path.suffix.lower()
    return _TYPE_MAP.get(suffix)


def get_supported_extensions() -> list[str]:
    """返回所有支持的文件扩展名"""
    return sorted(_TYPE_MAP.keys())
