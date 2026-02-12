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
) -> str:
    """调用单个 LLM provider，带指数退避重试（网络抖动/临时故障），失败时抛出异常"""
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
            logger.info(f"LLM 响应 ({provider}/{use_model}): {len(result)} 字符")
            return result

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
) -> str:
    """
    调用 LLM API，返回文本响应。
    支持 Ollama（本地）/ DeepSeek / Qwen，自动 fallback。

    fallback 逻辑：
    - 若指定了 provider，仅调用该 provider（不 fallback）
    - 若未指定，按 cfg.AI_PROVIDER -> cfg.AI_FALLBACK_PROVIDERS 顺序尝试
    """
    from ..config import cfg

    # 确定超时（Ollama 本地推理较慢，默认 120s；云端 60s）
    if timeout is None:
        primary = provider or cfg.AI_PROVIDER
        timeout = 120.0 if primary == "ollama" else 60.0

    # 若明确指定了 provider，直接调用（不 fallback）
    if provider:
        return _call_single_provider(
            prompt, system_prompt, provider, model, max_tokens, temperature, timeout
        )

    # 构建 fallback 链：主 provider + fallback providers
    providers_chain = [cfg.AI_PROVIDER] + cfg.AI_FALLBACK_PROVIDERS
    # 去重并保持顺序
    seen = set()
    unique_chain = []
    for p in providers_chain:
        if p not in seen:
            seen.add(p)
            unique_chain.append(p)

    last_error = None
    for i, prov in enumerate(unique_chain):
        try:
            # fallback 时使用对应 provider 的默认模型，而非主 provider 的模型
            use_model = model if i == 0 else None
            use_timeout = 120.0 if prov == "ollama" else 60.0
            return _call_single_provider(
                prompt, system_prompt, prov, use_model, max_tokens, temperature, use_timeout
            )
        except Exception as e:
            last_error = e
            if i < len(unique_chain) - 1:
                next_prov = unique_chain[i + 1]
                logger.warning(f"LLM {prov} 调用失败: {e}，fallback 到 {next_prov}")
            else:
                logger.error(f"LLM {prov} 调用失败: {e}，已无可用 fallback")

    raise RuntimeError(f"所有 LLM provider 均调用失败，最后错误: {last_error}")
