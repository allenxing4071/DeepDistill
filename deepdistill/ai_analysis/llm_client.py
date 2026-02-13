"""
LLM 客户端封装
支持 Ollama（本地）/ DeepSeek / Qwen API（兼容 OpenAI 接口格式）。
调用优先级：Ollama 本地 -> DeepSeek API -> Qwen API，自动 fallback。
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("deepdistill.llm")

# 提供商配置（Ollama 兼容 OpenAI 接口格式，无需 API Key）
_PROVIDERS = {
    "ollama": {
        "base_url": "http://host.docker.internal:11434/v1",
        "default_model": "qwen3:8b",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "default_model": "deepseek-chat",
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-max",
    },
}


def _get_api_key(provider: str) -> str:
    """获取指定 provider 的 API Key（Ollama 不需要）"""
    from ..config import cfg

    if provider == "ollama":
        return "ollama"  # Ollama 不需要真实 Key，但 OpenAI 客户端要求非空
    elif provider == "deepseek":
        return cfg.DEEPSEEK_API_KEY
    elif provider == "qwen":
        return cfg.QWEN_API_KEY
    return ""


def _call_single_provider(
    prompt: str,
    system_prompt: str,
    provider: str,
    model: str | None,
    max_tokens: int,
    temperature: float,
    timeout: float,
    max_retries: int = 3,
) -> tuple[str, dict]:
    """
    调用单个 LLM provider，带指数退避重试。
    返回 (content, usage_dict)，usage_dict 含 prompt_tokens/completion_tokens/total_tokens。
    """
    import time
    from openai import OpenAI

    if provider not in _PROVIDERS:
        raise ValueError(f"不支持的 LLM 提供商: {provider}")

    api_key = _get_api_key(provider)
    if not api_key:
        raise ValueError(f"{provider} API Key 未配置，请在 .env 中设置")

    provider_config = _PROVIDERS[provider]
    base_url = provider_config["base_url"]
    use_model = model or provider_config["default_model"]

    logger.info(f"调用 LLM: {provider}/{use_model} (输入: {len(prompt)} 字符)")

    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=timeout,
    )

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    last_error = None
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=use_model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )

            result = response.choices[0].message.content or ""
            usage = {}
            if getattr(response, "usage", None):
                u = response.usage
                usage = {
                    "prompt_tokens": getattr(u, "prompt_tokens", 0) or 0,
                    "completion_tokens": getattr(u, "completion_tokens", 0) or 0,
                    "total_tokens": getattr(u, "total_tokens", 0) or 0,
                }
            logger.info(f"LLM 响应 ({provider}/{use_model}): {len(result)} 字符")
            return result, usage

        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                wait = 2 ** attempt  # 1s, 2s, 4s 指数退避
                logger.warning(f"LLM {provider} 第 {attempt + 1} 次调用失败: {e}，{wait}s 后重试")
                time.sleep(wait)
            else:
                logger.error(f"LLM {provider} 第 {attempt + 1} 次调用失败（已达重试上限）: {e}")

    raise last_error


def call_llm(
    prompt: str,
    system_prompt: str = "",
    provider: str | None = None,
    model: str | None = None,
    max_tokens: int = 4096,
    temperature: float = 0.3,
    timeout: float | None = None,
) -> tuple[str, dict]:
    """
    调用 LLM API，返回 (文本响应, usage_dict)。
    usage_dict 含 prompt_tokens/completion_tokens/total_tokens（部分 provider 可能无）。
    支持 Ollama（本地）/ DeepSeek / Qwen，自动 fallback。
    """
    from ..config import cfg

    if timeout is None:
        primary = provider or cfg.AI_PROVIDER
        timeout = 120.0 if primary == "ollama" else 60.0

    if provider:
        return _call_single_provider(
            prompt, system_prompt, provider, model, max_tokens, temperature, timeout
        )

    providers_chain = [cfg.AI_PROVIDER] + cfg.AI_FALLBACK_PROVIDERS
    seen: set[str] = set()
    unique_chain = []
    for p in providers_chain:
        if p not in seen:
            seen.add(p)
            unique_chain.append(p)

    last_error = None
    for i, prov in enumerate(unique_chain):
        try:
            use_model = model if i == 0 else None
            use_timeout = 120.0 if prov == "ollama" else 60.0
            return _call_single_provider(
                prompt, system_prompt, prov, use_model, max_tokens, temperature, use_timeout
            )
        except Exception as e:
            last_error = e
            if i < len(unique_chain) - 1:
                logger.warning("LLM %s 调用失败: %s，fallback 到 %s", prov, e, unique_chain[i + 1])
            else:
                logger.error("LLM %s 调用失败: %s，已无可用 fallback", prov, e)

    raise RuntimeError(f"所有 LLM provider 均调用失败，最后错误: {last_error}")
