"""
输入层测试：文件格式识别与路由
验证所有支持的文件格式能被正确识别和分类
"""

import pytest
from pathlib import Path

from deepdistill.ingestion.router import identify_file_type, get_supported_extensions


class TestFileTypeIdentification:
    """文件类型识别测试"""

    @pytest.mark.parametrize("filename,expected", [
        # 视频
        ("video.mp4", "video"),
        ("video.mov", "video"),
        ("video.avi", "video"),
        ("video.mkv", "video"),
        ("video.webm", "video"),
        ("video.flv", "video"),
        # 音频
        ("audio.mp3", "audio"),
        ("audio.wav", "audio"),
        ("audio.m4a", "audio"),
        ("audio.flac", "audio"),
        ("audio.ogg", "audio"),
        ("audio.aac", "audio"),
        # 文档
        ("doc.pdf", "document"),
        ("doc.docx", "document"),
        ("doc.doc", "document"),
        ("doc.pptx", "document"),
        ("doc.ppt", "document"),
        ("doc.xlsx", "document"),
        ("doc.xls", "document"),
        ("doc.txt", "document"),
        ("doc.md", "document"),
        # 图片
        ("img.jpg", "image"),
        ("img.jpeg", "image"),
        ("img.png", "image"),
        ("img.bmp", "image"),
        ("img.tiff", "image"),
        ("img.webp", "image"),
        ("img.gif", "image"),
        # 网页
        ("page.html", "webpage"),
        ("page.htm", "webpage"),
    ])
    def test_supported_formats(self, filename: str, expected: str):
        """所有支持的格式应被正确识别"""
        result = identify_file_type(Path(filename))
        assert result == expected, f"{filename} 应识别为 {expected}，实际为 {result}"

    @pytest.mark.parametrize("filename", [
        "file.xyz", "file.exe", "file.zip", "file.tar.gz", "file",
    ])
    def test_unsupported_formats(self, filename: str):
        """不支持的格式应返回 None"""
        result = identify_file_type(Path(filename))
        assert result is None, f"{filename} 应返回 None，实际为 {result}"

    def test_case_insensitive(self):
        """扩展名应不区分大小写"""
        # identify_file_type 使用 .lower()，应能处理大写
        result = identify_file_type(Path("VIDEO.MP4"))
        assert result == "video"

    def test_get_supported_extensions(self):
        """应返回所有支持的扩展名列表"""
        extensions = get_supported_extensions()
        assert isinstance(extensions, list)
        assert len(extensions) > 20  # 至少 20+ 种格式
        assert ".mp4" in extensions
        assert ".pdf" in extensions
        assert ".jpg" in extensions
        # 应已排序
        assert extensions == sorted(extensions)
