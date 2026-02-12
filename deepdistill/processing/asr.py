"""
ASR 处理器：视频/音频 → 文本
使用 ffmpeg 提取音轨 + faster-whisper 转录。

依赖：pip install deepdistill[asr]
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

logger = logging.getLogger("deepdistill.asr")


def transcribe(file_path: Path) -> str:
    """
    将视频/音频文件转录为文本。
    1. ffmpeg 提取音轨 → WAV 16kHz mono
    2. faster-whisper 转录
    3. 合并所有片段为完整文本
    """
    from ..config import cfg

    # 提取音轨
    wav_path = _extract_audio(file_path)

    try:
        # 加载 whisper 模型
        from faster_whisper import WhisperModel

        device = cfg.get_device()
        # faster-whisper 在 MPS 上暂不支持，fallback 到 CPU
        compute_type = "float16" if device == "cuda" else "int8"
        if device == "mps":
            device = "cpu"
            logger.info("faster-whisper 暂不支持 MPS，使用 CPU")

        logger.info(f"加载 Whisper 模型: {cfg.ASR_MODEL} (设备: {device})")
        model = WhisperModel(
            cfg.ASR_MODEL,
            device=device,
            compute_type=compute_type,
            download_root=str(cfg.MODEL_CACHE_DIR),
        )

        # 转录
        logger.info(f"开始转录: {file_path.name}")
        segments, info = model.transcribe(
            str(wav_path),
            language=cfg.ASR_LANGUAGE,
            beam_size=5,
            vad_filter=True,
        )

        logger.info(f"检测语言: {info.language} (概率: {info.language_probability:.2f})")

        # 合并片段
        texts = []
        for segment in segments:
            texts.append(segment.text.strip())

        full_text = "\n".join(texts)
        logger.info(f"转录完成: {len(full_text)} 字符")
        return full_text

    finally:
        # 清理临时文件
        if wav_path.exists() and wav_path != file_path:
            wav_path.unlink()


def _extract_audio(file_path: Path) -> Path:
    """使用 ffmpeg 提取音轨为 WAV 16kHz mono"""
    import subprocess

    # 如果已经是音频格式，直接返回
    if file_path.suffix.lower() in (".wav",):
        return file_path

    # 创建临时 WAV 文件
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    wav_path = Path(tmp.name)

    logger.info(f"提取音轨: {file_path.name} → WAV")
    cmd = [
        "ffmpeg", "-i", str(file_path),
        "-ar", "16000",      # 采样率 16kHz
        "-ac", "1",          # 单声道
        "-c:a", "pcm_s16le", # PCM 16-bit
        "-y",                # 覆盖
        str(wav_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg 提取音轨失败: {result.stderr[:500]}")

    return wav_path
