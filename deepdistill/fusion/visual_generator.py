"""
视觉素材生成器
基于蒸馏结果（文字 + 风格向量）生成图片/视觉素材。

实现策略：
1. 从 AI 分析结果 + 风格向量生成详细的图片描述 prompt
2. 调用 LLM 优化 prompt（适配 Stable Diffusion / DALL-E 等）
3. 如果有本地 Stable Diffusion 或云端 API，直接生成图片
4. 否则输出优化后的 prompt 供用户手动生成

支持的生成后端：
- Ollama 多模态模型（本地）
- OpenAI DALL-E API（云端）
- Stable Diffusion WebUI API（本地/远程）
- 纯 prompt 输出（无生成后端时）
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("deepdistill.fusion.visual")


def generate_visual_assets(
    ai_result: dict,
    video_analysis: dict | None = None,
    output_dir: Path | None = None,
    max_images: int = 3,
) -> dict:
    """
    基于蒸馏结果生成视觉素材（或生成 prompt）。

    Args:
        ai_result: AI 分析结果
        video_analysis: 视频分析结果（含风格向量）
        output_dir: 输出目录
        max_images: 最大生成图片数

    Returns:
        {
            "prompts": [{"title": str, "prompt": str, "negative_prompt": str, "style_tags": [str]}],
            "generated_images": [str],  # 生成的图片路径（如有）
            "style_description": str,   # 风格描述
        }
    """
    # 提取风格信息
    style_info = _extract_style_info(video_analysis)

    # 从分析结果生成图片 prompt
    prompts = _generate_prompts(ai_result, style_info, max_images)

    # 尝试生成图片
    generated_images = []
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        generated_images = _try_generate_images(prompts, output_dir)

    return {
        "prompts": prompts,
        "generated_images": generated_images,
        "style_description": style_info.get("description", ""),
    }


def _extract_style_info(video_analysis: dict | None) -> dict:
    """从视频分析结果中提取风格信息"""
    if not video_analysis:
        return {"description": "", "tags": [], "vector": []}

    style = video_analysis.get("style", {})
    if not style:
        return {"description": "", "tags": [], "vector": []}

    tags = []
    color = style.get("color_palette", {})
    if color:
        if color.get("color_temperature"):
            tags.append(color["color_temperature"])
        if color.get("saturation_level"):
            tags.append(color["saturation_level"])

    lighting = style.get("lighting", {})
    if lighting:
        if lighting.get("lighting_style"):
            tags.append(lighting["lighting_style"])

    rhythm = style.get("rhythm", {})
    if rhythm and rhythm.get("pace"):
        tags.append(rhythm["pace"])

    return {
        "description": style.get("summary", ""),
        "tags": tags,
        "vector": style.get("style_vector", []),
        "dominant_colors": color.get("dominant_colors", []),
    }


def _generate_prompts(ai_result: dict, style_info: dict, max_images: int) -> list[dict]:
    """从分析结果生成图片描述 prompt"""
    prompts = []

    summary = ai_result.get("summary", "")
    keywords = ai_result.get("keywords", [])
    key_points = ai_result.get("key_points", [])
    sections = ai_result.get("structure", {}).get("sections", [])

    # 风格标签
    style_tags = style_info.get("tags", [])
    style_desc = style_info.get("description", "")

    # Prompt 1: 基于核心摘要的封面图
    if summary:
        prompt_text = _build_image_prompt(
            subject=summary[:100],
            style_tags=style_tags,
            style_desc=style_desc,
            purpose="封面图/缩略图",
        )
        prompts.append({
            "title": "封面图",
            "prompt": prompt_text,
            "negative_prompt": "text, watermark, logo, blurry, low quality, distorted",
            "style_tags": style_tags,
        })

    # Prompt 2-N: 基于核心要点的配图
    for i, point in enumerate(key_points[:max_images - 1]):
        prompt_text = _build_image_prompt(
            subject=point,
            style_tags=style_tags,
            style_desc=style_desc,
            purpose=f"要点配图 #{i + 1}",
        )
        prompts.append({
            "title": f"要点 {i + 1}: {point[:30]}...",
            "prompt": prompt_text,
            "negative_prompt": "text, watermark, logo, blurry, low quality, distorted",
            "style_tags": style_tags,
        })

    return prompts[:max_images]


def _build_image_prompt(
    subject: str,
    style_tags: list[str],
    style_desc: str,
    purpose: str,
) -> str:
    """构建适配 Stable Diffusion / DALL-E 的图片生成 prompt"""
    parts = []

    # 主题
    parts.append(f"A professional illustration about: {subject}")

    # 用途
    parts.append(f"Purpose: {purpose}")

    # 风格
    if style_desc:
        parts.append(f"Visual style: {style_desc}")

    if style_tags:
        parts.append(f"Style attributes: {', '.join(style_tags)}")

    # 通用质量标签
    parts.append("high quality, detailed, professional, clean composition")

    return ". ".join(parts)


def _try_generate_images(prompts: list[dict], output_dir: Path) -> list[str]:
    """
    尝试调用可用的图片生成后端。
    优先级：Stable Diffusion WebUI > DALL-E API > 跳过
    """
    # 尝试 Stable Diffusion WebUI（本地）
    images = _try_sd_webui(prompts, output_dir)
    if images:
        return images

    # 尝试 DALL-E API
    images = _try_dalle(prompts, output_dir)
    if images:
        return images

    # 无可用后端，仅输出 prompt
    logger.info("无可用图片生成后端，仅输出 prompt 描述")
    return []


def _try_sd_webui(prompts: list[dict], output_dir: Path) -> list[str]:
    """尝试调用本地 Stable Diffusion WebUI API"""
    try:
        import httpx

        # 检查 SD WebUI 是否可用（默认端口 7860）
        response = httpx.get("http://host.docker.internal:7860/sdapi/v1/options", timeout=3)
        if response.status_code != 200:
            return []

        images = []
        for i, prompt_info in enumerate(prompts):
            payload = {
                "prompt": prompt_info["prompt"],
                "negative_prompt": prompt_info.get("negative_prompt", ""),
                "steps": 20,
                "width": 768,
                "height": 512,
                "cfg_scale": 7,
                "sampler_name": "DPM++ 2M Karras",
            }

            resp = httpx.post(
                "http://host.docker.internal:7860/sdapi/v1/txt2img",
                json=payload,
                timeout=120,
            )

            if resp.status_code == 200:
                import base64
                data = resp.json()
                for j, img_b64 in enumerate(data.get("images", [])):
                    img_path = output_dir / f"visual_{i + 1}_{j + 1}.png"
                    img_path.write_bytes(base64.b64decode(img_b64))
                    images.append(str(img_path))
                    logger.info(f"SD WebUI 生成图片: {img_path}")

        return images

    except Exception as e:
        logger.debug(f"SD WebUI 不可用: {e}")
        return []


def _try_dalle(prompts: list[dict], output_dir: Path) -> list[str]:
    """尝试调用 OpenAI DALL-E API"""
    try:
        from ..config import cfg

        # 需要 OpenAI API Key（复用 DeepSeek 的 key 不行，需要真正的 OpenAI key）
        import os
        openai_key = os.getenv("OPENAI_API_KEY", "")
        if not openai_key:
            return []

        from openai import OpenAI
        client = OpenAI(api_key=openai_key)

        images = []
        for i, prompt_info in enumerate(prompts):
            response = client.images.generate(
                model="dall-e-3",
                prompt=prompt_info["prompt"],
                size="1024x1024",
                quality="standard",
                n=1,
            )

            if response.data:
                import httpx
                img_url = response.data[0].url
                img_resp = httpx.get(img_url, timeout=30)
                if img_resp.status_code == 200:
                    img_path = output_dir / f"visual_{i + 1}.png"
                    img_path.write_bytes(img_resp.content)
                    images.append(str(img_path))
                    logger.info(f"DALL-E 生成图片: {img_path}")

        return images

    except Exception as e:
        logger.debug(f"DALL-E 不可用: {e}")
        return []
