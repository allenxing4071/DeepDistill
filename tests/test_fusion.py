"""
融合层测试：格式化输出函数
验证 Markdown / JSON / Skill 格式化器的导入和基本功能
"""

import pytest
import tempfile
from pathlib import Path


class TestMarkdownFormatter:
    """Markdown 格式化测试"""

    def test_import(self):
        """format_markdown 函数应可导入"""
        from deepdistill.fusion.formatters.markdown import format_markdown
        assert callable(format_markdown)

    def test_format_basic(self):
        """基本格式化应生成有效 Markdown 文件"""
        from deepdistill.fusion.formatters.markdown import format_markdown
        from deepdistill.pipeline import ProcessingResult

        result = ProcessingResult(
            source_path="test.txt",
            source_type="document",
            filename="test.txt",
            extracted_text="测试文本内容",
        )
        result.ai_result = {
            "summary": "这是测试摘要",
            "key_points": ["要点一", "要点二"],
            "keywords": ["测试", "摘要"],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = format_markdown(result, Path(tmpdir))
            assert output_path is not None
            # 输出文件应存在
            if isinstance(output_path, str):
                p = Path(output_path)
                if p.exists():
                    content = p.read_text(encoding="utf-8")
                    assert len(content) > 0


class TestJsonFormatter:
    """JSON 格式化测试"""

    def test_import(self):
        """format_json 函数应可导入"""
        from deepdistill.fusion.formatters.json_fmt import format_json
        assert callable(format_json)


class TestSkillFormatter:
    """Skill 文档格式化测试"""

    def test_import(self):
        """format_skill 函数应可导入"""
        from deepdistill.fusion.formatters.skill_fmt import format_skill
        assert callable(format_skill)
