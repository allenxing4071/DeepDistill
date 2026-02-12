"""
导出标题生成测试：验证中文短标题提取逻辑
覆盖各种 AI 分析结果场景下的标题生成
"""

import pytest

from deepdistill.export.google_docs import GoogleDocsExporter


class TestGenerateShortTitle:
    """中文短标题生成测试"""

    def _make_task(self, summary="", key_points=None, keywords=None,
                   filename="test.txt", source_url=""):
        """构造测试用 task 字典"""
        return {
            "filename": filename,
            "source_url": source_url,
            "result": {
                "ai_result": {
                    "summary": summary,
                    "key_points": key_points or [],
                    "keywords": keywords or [],
                },
            },
        }

    def test_chinese_summary(self):
        """中文 summary 应提取前 ≤8 字"""
        task = self._make_task(summary="加密货币市场近期波动剧烈")
        title = GoogleDocsExporter._generate_short_title(task)
        assert len(title) <= 8
        assert "加密货币" in title

    def test_summary_with_prefix_removal(self):
        """应去除"本文介绍了"等套话"""
        task = self._make_task(summary="本文介绍了区块链技术的核心原理和应用场景")
        title = GoogleDocsExporter._generate_short_title(task)
        assert not title.startswith("本文")
        assert len(title) <= 8

    def test_summary_with_english_prefix(self):
        """英文前缀应被跳过，提取中文部分"""
        task = self._make_task(
            summary="本文探讨了Ethereum钱包在跨链交易体验和账户安全方面的改进方向"
        )
        title = GoogleDocsExporter._generate_short_title(task)
        assert len(title) <= 8
        # 应包含中文，不应以英文开头
        import re
        assert re.search(r'[\u4e00-\u9fff]', title), f"标题应包含中文: {title}"

    def test_summary_truncate_at_virtual_word(self):
        """应在虚词（和/与/的）处优先截断"""
        task = self._make_task(summary="以太坊钱包安全与隐私保护的最佳实践")
        title = GoogleDocsExporter._generate_short_title(task)
        assert len(title) <= 8
        # "以太坊钱包安全" 在 "与" 处截断 = 6 字
        assert "以太坊" in title

    def test_key_points_fallback(self):
        """summary 为空时应从 key_points 提取"""
        task = self._make_task(
            summary="",
            key_points=["跨链交易需要统一地址格式", "钱包安全需多重签名"],
        )
        title = GoogleDocsExporter._generate_short_title(task)
        assert len(title) <= 8
        assert len(title) >= 2

    def test_chinese_keywords_fallback(self):
        """summary 和 key_points 都为空时，从中文 keywords 提取"""
        task = self._make_task(
            summary="",
            key_points=[],
            keywords=["区块链", "智能合约", "DeFi"],
        )
        title = GoogleDocsExporter._generate_short_title(task)
        assert title == "区块链"

    def test_english_keywords_skip(self):
        """纯英文 keywords 应被跳过"""
        task = self._make_task(
            summary="",
            key_points=[],
            keywords=["Ethereum", "blockchain", "DeFi"],
        )
        title = GoogleDocsExporter._generate_short_title(task)
        # 应 fallback 到文件名或"未命名文档"
        assert len(title) >= 2

    def test_empty_ai_result(self):
        """AI 结果完全为空时应返回兜底值"""
        task = self._make_task(summary="", key_points=[], keywords=[])
        title = GoogleDocsExporter._generate_short_title(task)
        assert title == "未命名文档" or len(title) >= 2

    def test_chinese_filename(self):
        """中文文件名应被使用"""
        task = self._make_task(
            summary="", key_points=[], keywords=[],
            filename="深度学习入门教程.pdf",
        )
        title = GoogleDocsExporter._generate_short_title(task)
        assert "深度学习" in title

    def test_hash_filename_fallback(self):
        """哈希值文件名应被跳过"""
        task = self._make_task(
            summary="", key_points=[], keywords=[],
            filename="d72b17233b6cb527f7.html",
        )
        title = GoogleDocsExporter._generate_short_title(task)
        assert title == "未命名文档"

    def test_title_max_length(self):
        """标题不应超过 8 字"""
        task = self._make_task(
            summary="这是一个非常非常非常长的摘要文本用来测试截断功能是否正常工作"
        )
        title = GoogleDocsExporter._generate_short_title(task)
        assert len(title) <= 8


class TestAutoCategorize:
    """自动分类测试"""

    def _make_task(self, summary="", keywords=None):
        return {
            "result": {
                "ai_result": {
                    "summary": summary,
                    "keywords": keywords or [],
                },
            },
        }

    def test_tech_category(self):
        """技术相关内容应分类到技术文档"""
        task = self._make_task(
            summary="Docker 容器化部署微服务架构",
            keywords=["Docker", "微服务", "架构"],
        )
        category = GoogleDocsExporter._auto_categorize(task)
        assert category == "技术文档"

    def test_market_category(self):
        """市场相关内容应分类到市场分析"""
        task = self._make_task(
            summary="比特币价格突破新高，市场情绪乐观",
            keywords=["比特币", "市场", "价格"],
        )
        category = GoogleDocsExporter._auto_categorize(task)
        assert category == "市场分析"

    def test_learning_category(self):
        """学习相关内容应分类到学习笔记"""
        task = self._make_task(
            summary="Python 入门教程，从零开始学习编程",
            keywords=["教程", "学习", "Python"],
        )
        category = GoogleDocsExporter._auto_categorize(task)
        assert category in ("学习笔记", "技术文档")  # 两者都合理

    def test_default_category(self):
        """无法匹配时应返回"其他" """
        task = self._make_task(
            summary="今天天气很好，适合出去散步",
            keywords=["天气", "散步"],
        )
        category = GoogleDocsExporter._auto_categorize(task)
        assert category == "其他"

    def test_empty_result(self):
        """空结果应返回"其他" """
        task = self._make_task(summary="", keywords=[])
        category = GoogleDocsExporter._auto_categorize(task)
        assert category == "其他"

    def test_all_categories_valid(self):
        """返回的分类必须在 CATEGORIES 中"""
        test_cases = [
            ("Docker 部署", ["Docker"]),
            ("比特币交易", ["比特币"]),
            ("学习笔记", ["教程"]),
            ("投诉举报", ["投诉"]),
            ("会议纪要", ["会议"]),
            ("UI 设计", ["设计"]),
            ("法律法规", ["法律"]),
            ("随便什么", ["随便"]),
        ]
        for summary, keywords in test_cases:
            task = self._make_task(summary=summary, keywords=keywords)
            category = GoogleDocsExporter._auto_categorize(task)
            assert category in GoogleDocsExporter.CATEGORIES, \
                f"分类 '{category}' 不在 CATEGORIES 中"
