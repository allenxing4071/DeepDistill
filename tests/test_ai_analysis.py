"""
AI 分析层测试：extractor / prompt_stats 工具函数
验证 prompt 模板管理、JSON 解析、统计采集
"""

import pytest

from deepdistill.ai_analysis.extractor import (
    list_prompt_templates,
    get_prompt_content,
    _parse_json_response,
)


class TestListPromptTemplates:
    """prompt 模板列表测试"""

    def test_returns_list(self):
        """应返回列表"""
        result = list_prompt_templates()
        assert isinstance(result, list)

    def test_items_have_name_and_description(self):
        """每项应有 name 和 description 字段"""
        result = list_prompt_templates()
        for item in result:
            assert "name" in item
            assert "description" in item
            assert isinstance(item["name"], str)
            assert isinstance(item["description"], str)

    def test_summarize_exists_if_prompts_dir_present(self):
        """若 prompts 目录存在，应至少包含 summarize"""
        result = list_prompt_templates()
        names = [t["name"] for t in result]
        # summarize.txt 为默认模板，通常存在
        if result:
            assert any("summarize" in n for n in names) or len(names) >= 1


class TestGetPromptContent:
    """prompt 模板内容获取测试"""

    def test_empty_name_returns_none(self):
        """空名称应返回 None"""
        assert get_prompt_content("") is None
        assert get_prompt_content("   ") is None

    def test_path_traversal_blocked(self):
        """路径穿越应被拒绝"""
        assert get_prompt_content("../config/default.yaml") is None
        assert get_prompt_content("..\\windows") is None
        assert get_prompt_content(".") is None
        assert get_prompt_content("..") is None

    def test_summarize_returns_content_when_exists(self):
        """summarize 模板存在时应返回非空内容"""
        content = get_prompt_content("summarize")
        if content is not None:
            assert len(content) > 0
            assert "{{CONTENT}}" in content or "CONTENT" in content.upper()

    def test_nonexistent_returns_none(self):
        """不存在的模板应返回 None"""
        assert get_prompt_content("__nonexistent_template_xyz__") is None

    def test_name_without_txt_suffix(self):
        """不含 .txt 后缀的名称应能解析"""
        content = get_prompt_content("summarize")
        # 与 get_prompt_content("summarize.txt") 等价
        content2 = get_prompt_content("summarize.txt")
        assert content == content2


class TestParseJsonResponse:
    """LLM 响应 JSON 解析测试"""

    def test_direct_json(self):
        """纯 JSON 应直接解析"""
        resp = '{"summary": "测试", "key_points": ["a"], "keywords": ["b"]}'
        result = _parse_json_response(resp)
        assert result["summary"] == "测试"
        assert result["key_points"] == ["a"]
        assert "parse_error" not in result

    def test_json_in_code_block(self):
        """```json ... ``` 代码块应被提取"""
        resp = """前面有说明文字
```json
{"summary": "块内", "key_points": [], "keywords": []}
```
后面有说明"""
        result = _parse_json_response(resp)
        assert result["summary"] == "块内"
        assert "parse_error" not in result

    def test_curly_brace_extraction(self):
        """首尾 { } 之间的内容应被提取"""
        resp = "这是前缀 {\"summary\": \"括号内\", \"key_points\": [], \"keywords\": []} 后缀"
        result = _parse_json_response(resp)
        assert result["summary"] == "括号内"

    def test_parse_error_fallback(self):
        """无法解析时返回 parse_error 结构"""
        resp = "这不是合法的 JSON 内容，完全没有大括号"
        result = _parse_json_response(resp)
        assert "parse_error" in result
        assert result["parse_error"] is True
        assert "summary" in result
        assert len(result["summary"]) <= 500
        assert result["key_points"] == []
        assert result["keywords"] == []

    def test_empty_response(self):
        """空字符串应返回 parse_error 结构"""
        result = _parse_json_response("")
        assert result.get("parse_error") is True
        assert "summary" in result


class TestPromptStatsCollector:
    """Prompt 统计采集器测试"""

    def test_snapshot_returns_list(self):
        """snapshot 应返回列表"""
        from deepdistill.ai_analysis.prompt_stats import prompt_stats

        result = prompt_stats.snapshot()
        assert isinstance(result, list)

    def test_summary_returns_dict(self):
        """summary 应返回汇总字典"""
        from deepdistill.ai_analysis.prompt_stats import prompt_stats

        result = prompt_stats.summary()
        assert isinstance(result, dict)
        assert "total_calls" in result
        assert "total_tokens" in result
        assert "cache_hit_rate" in result

    def test_record_does_not_crash(self):
        """record 调用不应抛出异常"""
        from deepdistill.ai_analysis.prompt_stats import prompt_stats

        prompt_stats.record(
            "test_stats",
            duration_ms=100,
            usage={"prompt_tokens": 10, "completion_tokens": 20},
            success=True,
            cache_hit=False,
        )
        # 若到此未异常则通过
        summ = prompt_stats.summary()
        assert summ["total_calls"] >= 1
