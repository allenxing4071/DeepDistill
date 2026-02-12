"""
AI 结构化提炼器
将提取的文本通过 LLM 分析，输出结构化的知识摘要。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("deepdistill.extractor")

# Prompt 模板目录
PROMPTS_DIR = Path(__file__).parent / "prompts"


def extract_knowledge(text: str, video_analysis: dict | None = None) -> dict:
    """
    对提取的文本进行 AI 结构化提炼。
    返回：摘要、关键词、核心观点、结构分析。
    """
    from .llm_client import call_llm

    # 加载 prompt 模板
    prompt_template = _load_prompt("summarize.txt")

    # 构建 prompt
    user_prompt = prompt_template.replace("{{CONTENT}}", text[:8000])  # 限制输入长度

    if video_analysis and video_analysis.get("scenes"):
        video_desc = json.dumps(video_analysis, ensure_ascii=False, indent=2)
        user_prompt += f"\n\n## 视频视觉分析结果\n{video_desc}"

    # 调用 LLM
    system_prompt = (
        "你是一个专业的内容分析助手。请严格按照 JSON 格式输出分析结果，"
        "不要输出任何其他内容。确保 JSON 格式正确。"
    )

    response = call_llm(
        prompt=user_prompt,
        system_prompt=system_prompt,
        temperature=0.2,
    )

    # 解析 JSON 响应
    result = _parse_json_response(response)
    return result


def _load_prompt(filename: str) -> str:
    """加载 prompt 模板文件"""
    prompt_path = PROMPTS_DIR / filename
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")

    # 默认 prompt（模板文件不存在时使用）
    return _DEFAULT_SUMMARIZE_PROMPT


def _parse_json_response(response: str) -> dict:
    """从 LLM 响应中解析 JSON"""
    # 尝试直接解析
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass

    # 尝试提取 ```json ... ``` 代码块
    if "```json" in response:
        start = response.index("```json") + 7
        end = response.index("```", start)
        try:
            return json.loads(response[start:end].strip())
        except (json.JSONDecodeError, ValueError):
            pass

    # 尝试提取 { ... } 块
    try:
        start = response.index("{")
        end = response.rindex("}") + 1
        return json.loads(response[start:end])
    except (ValueError, json.JSONDecodeError):
        pass

    # 解析失败，返回原始文本
    logger.warning("JSON 解析失败，返回原始文本")
    return {
        "summary": response[:500],
        "key_points": [],
        "keywords": [],
        "parse_error": True,
    }


# 默认提炼 prompt
_DEFAULT_SUMMARIZE_PROMPT = """请分析以下内容，输出 JSON 格式的结构化结果。

## 要求
1. summary: 200 字以内的核心摘要
2. key_points: 3-7 条核心观点（每条一句话）
3. keywords: 5-10 个关键词/标签
4. structure: 内容的结构分析
   - type: 内容类型（教程/分析/叙事/演讲/对话/其他）
   - sections: 主要章节/段落列表

## 输出格式（严格 JSON）
```json
{
  "summary": "...",
  "key_points": ["...", "..."],
  "keywords": ["...", "..."],
  "structure": {
    "type": "...",
    "sections": [
      {"heading": "...", "content": "..."}
    ]
  }
}
```

## 待分析内容
{{CONTENT}}
"""
