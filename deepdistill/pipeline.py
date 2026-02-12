"""
DeepDistill 主管线编排
协调 6 层处理流程：输入 → 内容处理 → 视频分析 → AI 提炼 → 融合输出 → 知识管理

核心设计：
- 每一层的输出是下一层的输入，层间通过 PipelineResult 传递
- 插件化：每个处理器实现统一接口，可独立替换
- 渐进增强：MVP 只需 Layer 1-2-4-5
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .config import cfg

logger = logging.getLogger("deepdistill.pipeline")


@dataclass
class ProcessingResult:
    """管线处理结果"""
    source_path: str
    source_type: str  # video/audio/image/document/webpage
    filename: str

    # Layer 2: 提取的文本
    extracted_text: str = ""

    # Layer 3: 视频分析（可选）
    video_analysis: dict | None = None

    # Layer 4: AI 提炼结果
    ai_result: dict | None = None

    # Layer 5: 输出路径
    output_path: str = ""

    # 元数据
    processing_time_sec: float = 0.0
    created_at: str = ""
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "source_path": self.source_path,
            "source_type": self.source_type,
            "filename": self.filename,
            "extracted_text_length": len(self.extracted_text),
            "has_video_analysis": self.video_analysis is not None,
            "ai_result": self.ai_result,
            "output_path": self.output_path,
            "processing_time_sec": self.processing_time_sec,
            "created_at": self.created_at,
            "errors": self.errors,
        }


class Pipeline:
    """主管线：协调各层处理器"""

    def __init__(self, output_dir: Path | None = None, output_format: str | None = None):
        self.output_dir = output_dir or cfg.OUTPUT_DIR
        self.output_format = output_format or cfg.OUTPUT_FORMAT
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def process(self, file_path: Path) -> ProcessingResult | None:
        """处理单个文件，返回结果"""
        import time
        start = time.time()

        logger.info(f"🔄 开始处理: {file_path.name}")

        # Layer 1: 输入层 — 格式识别
        source_type = self._identify_type(file_path)
        if not source_type:
            logger.warning(f"⚠️  不支持的格式: {file_path.suffix}")
            return None

        result = ProcessingResult(
            source_path=str(file_path),
            source_type=source_type,
            filename=file_path.name,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        # Layer 2: 内容处理层 — 文本提取
        try:
            result.extracted_text = self._extract_content(file_path, source_type)
            logger.info(f"  📝 提取文本: {len(result.extracted_text)} 字符")
        except Exception as e:
            logger.error(f"  ❌ 文本提取失败: {e}")
            result.errors.append(f"文本提取失败: {e}")

        # Layer 3: 视频增强分析（可选）
        if source_type == "video" and cfg.VIDEO_ANALYSIS_LEVEL != "off":
            try:
                result.video_analysis = self._analyze_video(file_path)
                logger.info(f"  🎬 视频分析完成")
            except Exception as e:
                logger.error(f"  ❌ 视频分析失败: {e}")
                result.errors.append(f"视频分析失败: {e}")

        # Layer 4: AI 分析层 — 结构化提炼
        if result.extracted_text:
            try:
                result.ai_result = self._ai_analyze(result.extracted_text, result.video_analysis)
                logger.info(f"  🧠 AI 提炼完成")
            except Exception as e:
                logger.error(f"  ❌ AI 提炼失败: {e}")
                result.errors.append(f"AI 提炼失败: {e}")

        # Layer 5: 融合输出层
        try:
            result.output_path = self._generate_output(result)
            logger.info(f"  📄 输出: {result.output_path}")
        except Exception as e:
            logger.error(f"  ❌ 输出生成失败: {e}")
            result.errors.append(f"输出生成失败: {e}")

        result.processing_time_sec = round(time.time() - start, 2)
        logger.info(f"✅ 完成: {file_path.name} ({result.processing_time_sec}s)")

        return result

    def _identify_type(self, file_path: Path) -> str | None:
        """Layer 1: 识别文件类型"""
        from .ingestion.router import identify_file_type
        return identify_file_type(file_path)

    def _extract_content(self, file_path: Path, source_type: str) -> str:
        """Layer 2: 提取文本内容"""
        from .processing import extract_text
        return extract_text(file_path, source_type)

    def _analyze_video(self, file_path: Path) -> dict:
        """Layer 3: 视频增强分析"""
        from .video_analysis import analyze_video
        return analyze_video(file_path)

    def _ai_analyze(self, text: str, video_analysis: dict | None = None) -> dict:
        """Layer 4: AI 结构化提炼"""
        from .ai_analysis.extractor import extract_knowledge
        return extract_knowledge(text, video_analysis)

    def _generate_output(self, result: ProcessingResult) -> str:
        """Layer 5: 生成输出文件"""
        from .fusion import generate_output
        return generate_output(result, self.output_dir, self.output_format)
