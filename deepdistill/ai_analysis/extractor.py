"""
AI 结构化提炼器
将提取的文本通过 LLM 分析，输出结构化的知识摘要。
Prompt 模板从 prompts/ 目录加载，模板名由配置 ai.prompt_template 指定（可与 KKline 一样按需扩展）。
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger("deepdistill.extractor")

# Prompt 模板目录（与 KKline 一致：.txt 文件，名不含后缀）
PROMPTS_DIR = Path(__file__).parent / "prompts"


def list_prompt_templates() -> list[dict]:
    """
    列出 prompts 目录下所有 .txt 模板（供设置页/API 使用）。
    返回: [{"name": "summarize", "description": "首行注释或空"}]
    """
    if not PROMPTS_DIR.exists():
        return []
    result = []
    for p in sorted(PROMPTS_DIR.glob("*.txt")):
        name = p.stem
        desc = ""
        try:
            first_line = p.read_text(encoding="utf-8").split("\n")[0].strip()
            # 兼容 # 用途：xxx 或 # 用途: xxx
            if first_line.startswith("#"):
                m = re.match(r"#\s*用途[：:]\s*(.+)", first_line)
                if m:
                    desc = m.group(1).strip()
                else:
                    desc = first_line.lstrip("# ").strip()[:80]
        except Exception:
            pass
        result.append({"name": name, "description": desc})
    return result


def get_prompt_content(name: str) -> Optional[str]:
    """
    获取指定名称的 prompt 模板内容（名称不含 .txt）。
    若不存在或路径非法（目录穿越）返回 None。
    """
    name = name.strip()
    if not name:
        return None
    # 禁止路径穿越，只允许文件名
    if "/" in name or "\\" in name or name in (".", ".."):
        return None
    if not name.endswith(".txt"):
        name = name + ".txt"
    path = (PROMPTS_DIR / name).resolve()
    try:
        # 必须位于 PROMPTS_DIR 下且为直接子文件（禁止目录穿越）
        if path.parent != PROMPTS_DIR.resolve() or not path.exists() or not path.is_file():
            return None
    except (ValueError, OSError):
        return None
    return path.read_text(encoding="utf-8")


def extract_knowledge(text: str, video_analysis: dict | None = None) -> dict:
    """
    对提取的文本进行 AI 结构化提炼。
    使用配置中的 ai.prompt_template 指定模板（默认 summarize）。
    每次调用后上报 prompt_stats 供监控页展示。
    返回：摘要、关键词、核心观点、结构分析。
    """
    import time

    from ..config import cfg
    from .llm_client import call_llm
    from .prompt_stats import prompt_stats

    template_name = getattr(cfg, "AI_PROMPT_TEMPLATE", None) or "summarize"
    prompt_template = _load_prompt(template_name)

    user_prompt = prompt_template.replace("{{CONTENT}}", text[:8000])

    if video_analysis and video_analysis.get("scenes"):
        video_desc = json.dumps(video_analysis, ensure_ascii=False, indent=2)
        user_prompt += f"\n\n## 视频视觉分析结果\n{video_desc}"

    system_prompt = (
        "你是一个专业的内容分析助手。请严格按照 JSON 格式输出分析结果，"
        "不要输出任何其他内容。确保 JSON 格式正确。"
    )

    t0 = time.perf_counter()
    try:
        response, usage = call_llm(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.2,
        )
        duration_ms = int((time.perf_counter() - t0) * 1000)
        prompt_stats.record(
            template_name,
            duration_ms=duration_ms,
            usage=usage,
            success=True,
            cache_hit=False,
        )
        result = _parse_json_response(response)
        return result
    except Exception as e:
        duration_ms = int((time.perf_counter() - t0) * 1000)
        prompt_stats.record(
            template_name,
            duration_ms=duration_ms,
            usage={},
            success=False,
            error=str(e)[:200],
            cache_hit=False,
        )
        raise


def _load_prompt(name: str) -> str:
    """加载 prompt 模板：name 为模板名（不含 .txt），如 summarize。"""
    name = (name or "summarize").strip()
    if not name.endswith(".txt"):
        name = name + ".txt"
    prompt_path = PROMPTS_DIR / name
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
