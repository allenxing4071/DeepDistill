"""
LLM 客户端封装
支持 DeepSeek / Qwen API（兼容 OpenAI 接口格式）。
本地优先：短内容用本地模型，长内容用 API。
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("deepdistill.llm")

# DeepSeek API 基础配置
_PROVIDERS = {
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "default_model": "deepseek-chat",
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-max",
    },
}


def call_llm(
    prompt: str,
    system_prompt: str = "",
    provider: str | None = None,
    model: str | None = None,
    max_tokens: int = 4096,
    temperature: float = 0.3,
) -> str:
    """
    调用 LLM API，返回文本响应。
    兼容 OpenAI 接口格式（DeepSeek / Qwen 均支持）。
    """
    from openai import OpenAI
    from ..config import cfg

    # 确定 provider
    provider = provider or cfg.AI_PROVIDER
    model = model or cfg.AI_MODEL

    # 获取 API Key
    if provider == "deepseek":
        api_key = cfg.DEEPSEEK_API_KEY
    elif provider == "qwen":
        api_key = cfg.QWEN_API_KEY
    else:
        raise ValueError(f"不支持的 LLM 提供商: {provider}")

    if not api_key:
        raise ValueError(f"{provider} API Key 未配置，请在 .env 中设置")

    provider_config = _PROVIDERS[provider]
    base_url = provider_config["base_url"]

    logger.info(f"调用 LLM: {provider}/{model} (输入: {len(prompt)} 字符)")

    client = OpenAI(api_key=api_key, base_url=base_url)

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )

    result = response.choices[0].message.content or ""
    logger.info(f"LLM 响应: {len(result)} 字符")
    return result
