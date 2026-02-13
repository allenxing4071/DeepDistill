"""
DeepDistill 主管线编排
协调 6 层处理流程：输入 → 内容处理 → 视频/图片风格分析 → AI 提炼 → 融合输出 → 知识管理

核心设计：
- 每一层的输出是下一层的输入，层间通过 PipelineResult 传递
- 插件化：每个处理器实现统一接口，可独立替换
- 渐进增强：MVP 只需 Layer 1-2-4-5
- intent 参数控制处理路径：content（提取内容）/ style（分析风格）
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

    # Layer 3: 视频分析（可选，intent=style 时启用）
    video_analysis: dict | None = None

    # Layer 3b: 图片风格分析（可选，intent=style 且 image 类型时启用）
    image_style: dict | None = None

    # Layer 4: AI 提炼结果
    ai_result: dict | None = None

    # Layer 5: 输出路径
    output_path: str = ""

    # Layer 5.5: 视觉素材
    visual_assets: dict | None = None

    # 处理意图与文档类型（用于模板与导出样式细分）
    intent: str = "content"
    doc_type: str = "doc"  # "doc" | "skill" | "both"

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
            "raw_text": self.extracted_text or "",
            "extracted_text": self.extracted_text or "",
            "has_video_analysis": self.video_analysis is not None,
            "video_analysis": self.video_analysis,
            "image_style": self.image_style,
            "ai_result": self.ai_result,
            "visual_assets": self.visual_assets,
            "output_path": self.output_path,
            "intent": self.intent,
            "doc_type": getattr(self, "doc_type", "doc"),
            "processing_time_sec": self.processing_time_sec,
            "created_at": self.created_at,
            "errors": self.errors,
        }


class Pipeline:
    """主管线：协调各层处理器，根据 intent 走不同路径"""

    # 各层进度区间定义（百分比）
    PROGRESS_STEPS = {
        "identify":  {"start": 5,  "end": 10,  "label": "识别文件格式"},
        "extract":   {"start": 10, "end": 35,  "label": "提取文本内容"},
        "style":     {"start": 35, "end": 55,  "label": "分析风格特征"},
        "ai":        {"start": 55, "end": 80,  "label": "AI 结构化提炼"},
        "output":    {"start": 80, "end": 90,  "label": "生成输出文件"},
        "visual":    {"start": 90, "end": 95,  "label": "生成视觉素材"},
        "done":      {"start": 95, "end": 100, "label": "处理完成"},
    }

    def __init__(
        self,
        output_dir: Path | None = None,
        output_format: str | None = None,
        intent: str = "content",
        doc_type: str = "doc",
        progress_callback: Optional[callable] = None,
    ):
        self.output_dir = output_dir or cfg.OUTPUT_DIR
        self.output_format = output_format or cfg.OUTPUT_FORMAT
        self.intent = intent  # "content" | "style"
        self.doc_type = doc_type  # "doc" | "skill" | "both"（用于模板与导出样式细分）
        self._progress_cb = progress_callback  # 进度回调：(percent, step_label) -> None
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _report_progress(self, step: str, sub_progress: float = 0.0):
        """报告进度。sub_progress 为当前步骤内的完成比例 0.0~1.0"""
        if not self._progress_cb:
            return
        info = self.PROGRESS_STEPS.get(step)
        if not info:
            return
        span = info["end"] - info["start"]
        pct = int(info["start"] + span * min(sub_progress, 1.0))
        try:
            self._progress_cb(pct, info["label"])
        except Exception:
            pass  # 回调失败不影响管线

    def process(self, file_path: Path) -> ProcessingResult | None:
        """处理单个文件，根据 intent 走不同路径"""
        import time
        start = time.time()

        logger.info(f"🔄 开始处理: {file_path.name} (intent={self.intent})")

        # Layer 1: 输入层 — 格式识别
        self._report_progress("identify", 0.0)
        source_type = self._identify_type(file_path)
        if not source_type:
            logger.warning(f"⚠️  不支持的格式: {file_path.suffix}")
            return None
        self._report_progress("identify", 1.0)

        result = ProcessingResult(
            source_path=str(file_path),
            source_type=source_type,
            filename=file_path.name,
            intent=self.intent,
            doc_type=getattr(self, "doc_type", "doc"),
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        # Layer 2: 内容处理层 — 文本提取（两条路径都需要）
        self._report_progress("extract", 0.0)
        try:
            result.extracted_text = self._extract_content(file_path, source_type)
            logger.info(f"  📝 提取文本: {len(result.extracted_text)} 字符")
        except Exception as e:
            logger.error(f"  ❌ 文本提取失败: {e}")
            result.errors.append(f"文本提取失败: {e}")
        self._report_progress("extract", 1.0)

        # Layer 3: 风格分析（仅 intent=style 时执行）
        if self.intent == "style":
            self._report_progress("style", 0.0)
            # 视频风格分析
            if source_type == "video" and cfg.VIDEO_ANALYSIS_LEVEL != "off":
                try:
                    result.video_analysis = self._analyze_video(file_path)
                    logger.info(f"  🎬 视频风格分析完成")
                except Exception as e:
                    logger.error(f"  ❌ 视频风格分析失败: {e}")
                    result.errors.append(f"视频风格分析失败: {e}")

            # 图片风格分析
            if source_type == "image":
                try:
                    result.image_style = self._analyze_image_style(file_path)
                    logger.info(f"  🎨 图片风格分析完成")
                except Exception as e:
                    logger.error(f"  ❌ 图片风格分析失败: {e}")
                    result.errors.append(f"图片风格分析失败: {e}")
            self._report_progress("style", 1.0)
        else:
            # 跳过风格分析，直接推进进度
            self._report_progress("style", 1.0)

        # Layer 4: AI 分析层 — 结构化提炼
        self._report_progress("ai", 0.0)
        if result.extracted_text or result.video_analysis or result.image_style:
            try:
                result.ai_result = self._ai_analyze(
                    result.extracted_text,
                    result.video_analysis,
                    result.image_style,
                )
                logger.info(f"  🧠 AI 提炼完成")
            except Exception as e:
                logger.error(f"  ❌ AI 提炼失败: {e}")
                result.errors.append(f"AI 提炼失败: {e}")
        self._report_progress("ai", 1.0)

        # Layer 5: 融合输出层
        self._report_progress("output", 0.0)
        try:
            result.output_path = self._generate_output(result)
            logger.info(f"  📄 输出: {result.output_path}")
        except Exception as e:
            logger.error(f"  ❌ 输出生成失败: {e}")
            result.errors.append(f"输出生成失败: {e}")
        self._report_progress("output", 1.0)

        # Layer 5.5: 视觉素材生成（已移除 — Stable Diffusion 不再集成）
        self._report_progress("visual", 1.0)

        result.processing_time_sec = round(time.time() - start, 2)
        self._report_progress("done", 1.0)
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

    def _analyze_image_style(self, file_path: Path) -> dict:
        """Layer 3b: 图片风格分析"""
        from .processing.image_style import analyze_image_style
        return analyze_image_style(file_path)

    def _ai_analyze(
        self,
        text: str,
        video_analysis: dict | None = None,
        image_style: dict | None = None,
    ) -> dict:
        """Layer 4: AI 结构化提炼。仅两模板：summarize / style_analysis；Skill 文档用 summarize+hint。"""
        from .ai_analysis.extractor import extract_knowledge, resolve_prompt_template
        template_name = resolve_prompt_template(self.intent, getattr(self, "doc_type", "doc"))
        doc_type = getattr(self, "doc_type", "doc")
        hint = None
        if self.intent == "content" and doc_type in ("skill", "both"):
            hint = "本输出将用于 Skill 文档，请尽量补充 rules（规则/约束）、steps（实践步骤，每项含 step_number, title, summary）及 related（关联知识）。"
        style_context = video_analysis
        if image_style:
            style_context = image_style if not video_analysis else {
                **video_analysis, "image_style": image_style
            }
        return extract_knowledge(text, style_context, template_name=template_name, hint=hint)

    def _generate_output(self, result: ProcessingResult) -> str:
        """Layer 5: 生成输出文件"""
        from .fusion import generate_output
        return generate_output(result, self.output_dir, self.output_format)

    def _generate_visuals(self, result: ProcessingResult) -> dict:
        """Layer 5.5: 生成视觉素材（prompt + 可选图片）"""
        from .fusion.visual_generator import generate_visual_assets
        visual_dir = self.output_dir / "visuals"
        return generate_visual_assets(
            ai_result=result.ai_result,
            video_analysis=result.video_analysis,
            output_dir=visual_dir,
        )
