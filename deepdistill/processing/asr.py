"""
ASR 处理器：视频/音频 → 文本
使用 ffmpeg 提取音轨 + faster-whisper 转录。

超时保护：
- ffmpeg 提取音轨：最大 10 分钟（600 秒）
- Whisper 转录：最大 30 分钟（1800 秒）

依赖：pip install deepdistill[asr]
"""

from __future__ import annotations

import logging
import os
import tempfile
import time
from pathlib import Path

logger = logging.getLogger("deepdistill.asr")

# 超时配置（秒）
FFMPEG_TIMEOUT = int(os.getenv("DEEPDISTILL_FFMPEG_TIMEOUT", "600"))       # 10 分钟
TRANSCRIBE_TIMEOUT = int(os.getenv("DEEPDISTILL_TRANSCRIBE_TIMEOUT", "1800"))  # 30 分钟


def transcribe(file_path: Path) -> str:
    """
    将视频/音频文件转录为文本。
    1. ffmpeg 提取音轨 → WAV 16kHz mono（超时 10 分钟）
    2. faster-whisper 转录（超时 30 分钟）
    3. 合并所有片段为完整文本
    """
    from ..config import cfg

    # 提取音轨（带超时）
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

        # 转录（带超时保护）
        logger.info(f"开始转录: {file_path.name}（超时 {TRANSCRIBE_TIMEOUT}s）")

        full_text = _transcribe_with_model(model, wav_path, cfg, use_vad=True)

        # VAD 过滤后文本为空时，关闭 VAD 重试（音乐/歌唱类视频可能被 VAD 全部过滤）
        if not full_text.strip():
            logger.info("VAD 过滤后无文本，关闭 VAD 重试转录")
            full_text = _transcribe_with_model(model, wav_path, cfg, use_vad=False)

        return full_text

    finally:
        # 清理临时文件
        if wav_path.exists() and wav_path != file_path:
            wav_path.unlink()


def _transcribe_with_model(model, wav_path: Path, cfg, use_vad: bool = True) -> str:
    """使用 Whisper 模型转录音频，带超时保护"""
    segments, info = model.transcribe(
        str(wav_path),
        language=cfg.ASR_LANGUAGE,
        beam_size=5,
        vad_filter=use_vad,
    )

    logger.info(f"检测语言: {info.language} (概率: {info.language_probability:.2f}, VAD={use_vad})")

    # 合并片段（带超时检查）
    texts = []
    start_time = time.monotonic()
    for segment in segments:
        texts.append(segment.text.strip())
        elapsed = time.monotonic() - start_time
        if elapsed > TRANSCRIBE_TIMEOUT:
            logger.warning(f"转录超时（{elapsed:.0f}s > {TRANSCRIBE_TIMEOUT}s），返回已转录部分")
            break

    full_text = "\n".join(texts)
    elapsed = time.monotonic() - start_time
    logger.info(f"转录完成: {len(full_text)} 字符，耗时 {elapsed:.1f}s (VAD={use_vad})")
    return full_text


def _extract_audio(file_path: Path) -> Path:
    """使用 ffmpeg 提取音轨为 WAV 16kHz mono（带超时保护）"""
    import subprocess

    # 如果已经是音频格式，直接返回
    if file_path.suffix.lower() in (".wav",):
        return file_path

    # 创建临时 WAV 文件
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    wav_path = Path(tmp.name)

    logger.info(f"提取音轨: {file_path.name} → WAV（超时 {FFMPEG_TIMEOUT}s）")
    cmd = [
        "ffmpeg", "-i", str(file_path),
        "-ar", "16000",      # 采样率 16kHz
        "-ac", "1",          # 单声道
        "-c:a", "pcm_s16le", # PCM 16-bit
        "-y",                # 覆盖
        str(wav_path),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=FFMPEG_TIMEOUT)
    except subprocess.TimeoutExpired:
        # 清理临时文件
        if wav_path.exists():
            wav_path.unlink()
        raise RuntimeError(f"ffmpeg 提取音轨超时（>{FFMPEG_TIMEOUT}s），视频可能过大")

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg 提取音轨失败: {result.stderr[:500]}")

    return wav_path
