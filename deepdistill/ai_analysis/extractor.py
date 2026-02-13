"""
AI 结构化提炼器
将提取的文本通过 LLM 分析，输出结构化的知识摘要。
仅保留两个模板，避免为模板而增加模板：
- summarize：所有内容提炼（教程/新闻/问答/会议/长文/Skill 等），输出统一 JSON，按内容类型酌情填可选字段；Skill 文档时通过 hint 要求补全 rules/steps/related。
- style_analysis：分析风格（视觉/设计），intent=style 时使用。
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


def resolve_prompt_template(intent: str, doc_type: str) -> str:
    """
    按处理意图解析模板名。只保留两个模板：内容用 summarize，风格用 style_analysis。
    content+skill 也用 summarize，通过 hint 要求补全 rules/steps/related。
    """
    from ..config import cfg
    default_content = getattr(cfg, "AI_PROMPT_TEMPLATE", None) or "summarize"
    if (intent or "content") == "style":
        return "style_analysis"
    return default_content


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


def _is_likely_verification_or_empty_page(text: str) -> bool:
    """判断是否为验证页/错误页/无正文页，避免对这类内容做无意义摘要。"""
    if not text or len(text.strip()) < 200:
        return True
    lower = text.strip().lower()
    verification_phrases = (
        "enable javascript", "请启用 javascript", "javascript",
        "robot verification", "人机验证", "验证失败", "请刷新",
        "captcha", "cloudflare", "access denied", "checking your browser",
    )
    # 内容很短且包含典型验证/错误提示 → 视为无效页
    if len(text) < 800:
        for p in verification_phrases:
            if p in lower:
                return True
    return False


def extract_knowledge(
    text: str,
    video_analysis: dict | None = None,
    template_name: str | None = None,
    hint: str | None = None,
) -> dict:
    """
    对提取的文本进行 AI 结构化提炼。
    模板仅两个：summarize（内容）、style_analysis（风格）。content+skill 用 summarize 并传 hint 要求补全 rules/steps/related。
    """
    import time

    from ..config import cfg
    from .llm_client import call_llm
    from .prompt_stats import prompt_stats

    # 预检：验证页/无正文页直接返回「抓取失败」，不调用 LLM，避免产出低质量摘要
    if _is_likely_verification_or_empty_page(text):
        logger.info("检测到验证页或无效正文，跳过 LLM 分析，返回抓取失败结构")
        return {
            "summary": "未能获取有效页面内容，源站可能要求验证或需执行 JavaScript，当前抓取未得到正文。",
            "key_points": ["源站可能为动态加载或需人机验证，建议使用浏览器打开该 URL 查看"],
            "keywords": ["抓取失败", "需验证", "动态页面"],
            "structure": {"type": "fetch_failed", "sections": []},
        }

    if not template_name:
        template_name = getattr(cfg, "AI_PROMPT_TEMPLATE", None) or "summarize"
    prompt_template = _load_prompt(template_name)

    user_prompt = prompt_template.replace("{{CONTENT}}", text[:8000])
    if hint:
        user_prompt = user_prompt.rstrip() + "\n\n" + hint.strip()

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
