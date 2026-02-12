"""
DeepDistill 测试配置
提供共享 fixtures 和测试环境设置
"""

import os
import sys
from pathlib import Path

import pytest

# 确保项目根目录在 Python 路径中
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 设置测试环境变量（避免连接真实服务）
os.environ.setdefault("DEEPSEEK_API_KEY", "test-key-not-real")
os.environ.setdefault("QWEN_API_KEY", "test-key-not-real")
