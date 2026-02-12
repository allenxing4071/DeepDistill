"""
管线核心测试：ProcessingResult 数据结构与序列化
验证管线结果的创建、序列化、字段完整性
"""

import pytest
from datetime import datetime, timezone

from deepdistill.pipeline import ProcessingResult


class TestProcessingResult:
    """ProcessingResult 数据结构测试"""

    def test_create_minimal(self):
        """最小参数创建"""
        result = ProcessingResult(
            source_path="test.txt",
            source_type="document",
            filename="test.txt",
        )
        assert result.source_path == "test.txt"
        assert result.source_type == "document"
        assert result.filename == "test.txt"
        assert result.extracted_text == ""
        assert result.video_analysis is None
        assert result.image_style is None

    def test_create_with_text(self):
        """带提取文本创建"""
        result = ProcessingResult(
            source_path="article.pdf",
            source_type="document",
            filename="article.pdf",
            extracted_text="这是提取的文本内容",
        )
        assert result.extracted_text == "这是提取的文本内容"

    def test_to_dict(self):
        """序列化为字典"""
        result = ProcessingResult(
            source_path="video.mp4",
            source_type="video",
            filename="video.mp4",
            extracted_text="视频转录文本",
        )
        d = result.to_dict()
        assert isinstance(d, dict)
        assert d["source_path"] == "video.mp4"
        assert d["source_type"] == "video"
        assert d["filename"] == "video.mp4"
        assert d["raw_text"] == "视频转录文本"
        assert d["extracted_text"] == "视频转录文本"
        assert "created_at" in d

    def test_to_dict_preserves_full_text(self):
        """to_dict 应保留完整文本（API 层负责截断）"""
        long_text = "测试" * 10000  # 20000 字符
        result = ProcessingResult(
            source_path="big.txt",
            source_type="document",
            filename="big.txt",
            extracted_text=long_text,
        )
        d = result.to_dict()
        assert len(d["raw_text"]) == 20000
        assert len(d["extracted_text"]) == 20000

    def test_to_dict_with_ai_result(self):
        """带 AI 分析结果的序列化"""
        result = ProcessingResult(
            source_path="doc.pdf",
            source_type="document",
            filename="doc.pdf",
            extracted_text="文本",
        )
        result.ai_result = {
            "summary": "这是摘要",
            "key_points": ["要点1", "要点2"],
            "keywords": ["关键词1", "关键词2"],
        }
        d = result.to_dict()
        assert d["ai_result"]["summary"] == "这是摘要"
        assert len(d["ai_result"]["key_points"]) == 2

    def test_to_dict_with_video_analysis(self):
        """带视频分析结果的序列化"""
        result = ProcessingResult(
            source_path="clip.mp4",
            source_type="video",
            filename="clip.mp4",
            extracted_text="视频文本",
            video_analysis={"scenes": [{"start": 0, "end": 5}]},
        )
        d = result.to_dict()
        assert d["has_video_analysis"] is True
        assert d["video_analysis"]["scenes"][0]["start"] == 0
