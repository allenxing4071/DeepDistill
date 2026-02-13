"""
配置模块测试：验证配置加载与关键字段
"""

import pytest
from pathlib import Path

from deepdistill.config import cfg, PROJECT_ROOT, DATA_DIR


class TestConfigPaths:
    """路径配置测试"""

    def test_project_root_exists(self):
        """PROJECT_ROOT 应指向项目根目录"""
        assert PROJECT_ROOT.exists()
        assert (PROJECT_ROOT / "deepdistill").exists()
        assert (PROJECT_ROOT / "config").exists()

    def test_data_dir_resolved(self):
        """DATA_DIR 应为有效路径"""
        assert isinstance(DATA_DIR, Path)
        assert DATA_DIR.name == "data"


class TestConfigInstance:
    """配置实例测试"""

    def test_cfg_has_required_attrs(self):
        """cfg 应具备核心配置属性"""
        assert hasattr(cfg, "DEEPSEEK_API_KEY")
        assert hasattr(cfg, "QWEN_API_KEY")
        assert hasattr(cfg, "AI_PROVIDER")
        assert hasattr(cfg, "AI_PROMPT_TEMPLATE")
        assert hasattr(cfg, "DATA_DIR")
        assert hasattr(cfg, "OUTPUT_DIR")

    def test_ai_provider_valid(self):
        """AI_PROVIDER 应为已知值"""
        assert cfg.AI_PROVIDER in ("ollama", "deepseek", "qwen")

    def test_ai_prompt_template_non_empty(self):
        """AI_PROMPT_TEMPLATE 非空"""
        assert isinstance(cfg.AI_PROMPT_TEMPLATE, str)
        assert len(cfg.AI_PROMPT_TEMPLATE) >= 1
