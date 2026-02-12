"""
DeepDistill 配置管理
从 .env + YAML 配置文件读取所有配置，提供统一访问入口。
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
CONFIG_DIR = PROJECT_ROOT / "config"
DEFAULT_CONFIG_PATH = CONFIG_DIR / "default.yaml"

# 加载 .env
_env_path = PROJECT_ROOT / ".env"
if _env_path.exists():
    load_dotenv(dotenv_path=_env_path)


def _load_yaml_config() -> dict:
    """加载 YAML 配置文件"""
    if DEFAULT_CONFIG_PATH.exists():
        with open(DEFAULT_CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


class Config:
    """应用配置（.env 环境变量 + YAML 文件配置）"""

    # ── LLM API（可选，本地模型优先） ──
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    QWEN_API_KEY: str = os.getenv("QWEN_API_KEY", "")

    # ── 模型缓存路径 ──
    MODEL_CACHE_DIR: Path = Path(
        os.getenv("MODEL_CACHE_DIR", str(Path.home() / ".cache" / "deepdistill"))
    )

    # ── 日志级别 ──
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # ── 数据路径 ──
    DATA_DIR: Path = DATA_DIR
    OUTPUT_DIR: Path = DATA_DIR / "output"

    # ── YAML 配置（模型选择、处理参数等） ──
    _yaml: dict = _load_yaml_config()

    # ASR 配置
    ASR_MODEL: str = _yaml.get("asr", {}).get("model", "base")
    ASR_LANGUAGE: str | None = _yaml.get("asr", {}).get("language", None)
    ASR_DEVICE: str = _yaml.get("asr", {}).get("device", "auto")

    # OCR 配置
    OCR_ENGINE: str = _yaml.get("ocr", {}).get("engine", "easyocr")
    OCR_LANGUAGES: list[str] = _yaml.get("ocr", {}).get("languages", ["ch_sim", "en"])

    # AI 分析配置
    AI_PROVIDER: str = _yaml.get("ai", {}).get("provider", "deepseek")
    AI_MODEL: str = _yaml.get("ai", {}).get("model", "deepseek-chat")
    AI_LOCAL_THRESHOLD: int = _yaml.get("ai", {}).get("local_threshold", 2000)

    # 视频分析配置
    VIDEO_ANALYSIS_LEVEL: str = _yaml.get("video_analysis", {}).get("level", "off")

    # 输出配置
    OUTPUT_FORMAT: str = _yaml.get("output", {}).get("format", "markdown")

    # ── 服务端口 ──
    API_PORT: int = int(os.getenv("PORT", "8006"))
    FRONTEND_PORT: int = int(os.getenv("FRONTEND_PORT", "3006"))

    @classmethod
    def validate(cls) -> list[str]:
        """验证配置，返回警告列表（非致命）"""
        warnings = []
        if not cls.DEEPSEEK_API_KEY and not cls.QWEN_API_KEY:
            warnings.append("未配置 LLM API Key，仅可使用本地模型")
        return warnings

    @classmethod
    def ensure_dirs(cls):
        """确保数据目录存在"""
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        cls.MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def get_device(cls) -> str:
        """检测最佳可用设备：mps > cuda > cpu"""
        if cls.ASR_DEVICE != "auto":
            return cls.ASR_DEVICE
        try:
            import torch
            if torch.backends.mps.is_available():
                return "mps"
            if torch.cuda.is_available():
                return "cuda"
        except ImportError:
            pass
        return "cpu"

    @classmethod
    def to_dict(cls) -> dict:
        """导出当前配置为字典（脱敏）"""
        return {
            "asr": {"model": cls.ASR_MODEL, "language": cls.ASR_LANGUAGE, "device": cls.get_device()},
            "ocr": {"engine": cls.OCR_ENGINE, "languages": cls.OCR_LANGUAGES},
            "ai": {
                "provider": cls.AI_PROVIDER,
                "model": cls.AI_MODEL,
                "has_api_key": bool(cls.DEEPSEEK_API_KEY or cls.QWEN_API_KEY),
            },
            "video_analysis": {"level": cls.VIDEO_ANALYSIS_LEVEL},
            "output": {"format": cls.OUTPUT_FORMAT},
            "paths": {
                "data": str(cls.DATA_DIR),
                "output": str(cls.OUTPUT_DIR),
                "model_cache": str(cls.MODEL_CACHE_DIR),
            },
        }


# 全局配置单例
cfg = Config()
