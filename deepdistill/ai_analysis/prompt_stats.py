"""
Prompt 调用统计采集器
记录每个 prompt 的调用频率、Token 消耗、耗时、缓存命中率等指标，
与 KKline 一致：内存采集 + JSON 文件定期持久化。
"""

from __future__ import annotations

import json
import threading
import time
from collections import deque
from pathlib import Path

from ..config import cfg
from .extractor import PROMPTS_DIR, list_prompt_templates

logger = __import__("logging").getLogger("deepdistill.prompt_stats")

# 持久化文件路径
STATS_FILE = cfg.DATA_DIR / "prompt_stats.json"

# 成本估算定价（美元/百万 Token，按 DeepSeek 计，Ollama 免费不计入）
PRICE_INPUT_PER_M = 0.27
PRICE_OUTPUT_PER_M = 1.10


class _CallRecord:
    """单次调用记录"""
    __slots__ = ("ts", "duration_ms", "prompt_tokens", "completion_tokens",
                 "total_tokens", "success", "error", "cache_hit")

    def __init__(self, ts: float, duration_ms: int, prompt_tokens: int,
                 completion_tokens: int, total_tokens: int,
                 success: bool, error: str | None, cache_hit: bool):
        self.ts = ts
        self.duration_ms = duration_ms
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens
        self.success = success
        self.error = error
        self.cache_hit = cache_hit

    def to_dict(self) -> dict:
        return {
            "ts": self.ts,
            "duration_ms": self.duration_ms,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "success": self.success,
            "error": self.error,
            "cache_hit": self.cache_hit,
        }


class _PromptNode:
    """单个 prompt 的统计节点"""

    def __init__(self, name: str, label: str = "", stage: str = "提炼", icon: str = "📄"):
        self.name = name
        self.label = label or name
        self.stage = stage
        self.icon = icon
        self._records: deque[_CallRecord] = deque(maxlen=500)
        self.total_calls: int = 0
        self.total_cache_hits: int = 0
        self.total_prompt_tokens: int = 0
        self.total_completion_tokens: int = 0
        self.total_tokens: int = 0
        self.total_duration_ms: int = 0
        self.error_count: int = 0
        self.last_error: str | None = None
        self.last_error_ts: float | None = None

    def record(self, duration_ms: int, usage: dict, success: bool,
               error: str | None, cache_hit: bool):
        """记录一次调用"""
        now = time.time()
        pt = usage.get("prompt_tokens", 0)
        ct = usage.get("completion_tokens", 0)
        tt = usage.get("total_tokens", 0) or (pt + ct)

        rec = _CallRecord(
            ts=now, duration_ms=duration_ms,
            prompt_tokens=pt, completion_tokens=ct, total_tokens=tt,
            success=success, error=error, cache_hit=cache_hit,
        )
        self._records.append(rec)

        self.total_calls += 1
        if cache_hit:
            self.total_cache_hits += 1
        self.total_prompt_tokens += pt
        self.total_completion_tokens += ct
        self.total_tokens += tt
        self.total_duration_ms += duration_ms
        if not success and error:
            self.error_count += 1
            self.last_error = error
            self.last_error_ts = now

    def snapshot(self) -> dict:
        """返回统计快照"""
        now = time.time()
        cutoff_1h = now - 3600
        recent = [r for r in self._records if r.ts >= cutoff_1h]
        calls_1h = len(recent)

        api_calls = [r for r in recent if not r.cache_hit and r.duration_ms > 0]
        avg_duration_ms = (
            int(sum(r.duration_ms for r in api_calls) / len(api_calls))
            if api_calls else 0
        )

        cache_hit_rate = (
            round(self.total_cache_hits / self.total_calls, 4)
            if self.total_calls > 0 else 0.0
        )

        file_info = self._get_file_info()
        last_call_at = self._records[-1].ts if self._records else None

        return {
            "name": self.name,
            "label": self.label,
            "stage": self.stage,
            "icon": self.icon,
            "total_calls": self.total_calls,
            "calls_1h": calls_1h,
            "cache_hits": self.total_cache_hits,
            "cache_hit_rate": cache_hit_rate,
            "total_tokens": self.total_tokens,
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "avg_duration_ms": avg_duration_ms,
            "last_call_at": last_call_at,
            "error_count": self.error_count,
            "last_error": self.last_error,
            **file_info,
        }

    def recent_calls(self, limit: int = 20) -> list[dict]:
        """返回最近 N 条调用记录"""
        calls = list(self._records)[-limit:]
        return [r.to_dict() for r in reversed(calls)]

    def _get_file_info(self) -> dict:
        """获取 prompt 文件元信息"""
        path = PROMPTS_DIR / f"{self.name}.txt"
        if not path.exists():
            return {"file_size_bytes": 0, "file_modified_at": None, "file_lines": 0}
        try:
            stat = path.stat()
            lines = path.read_text(encoding="utf-8").count("\n") + 1
            return {
                "file_size_bytes": stat.st_size,
                "file_modified_at": stat.st_mtime,
                "file_lines": lines,
            }
        except Exception:
            return {"file_size_bytes": 0, "file_modified_at": None, "file_lines": 0}

    def to_persist(self) -> dict:
        """返回需持久化的累计数据"""
        return {
            "total_calls": self.total_calls,
            "total_cache_hits": self.total_cache_hits,
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_tokens,
            "total_duration_ms": self.total_duration_ms,
            "error_count": self.error_count,
            "last_error": self.last_error,
            "last_error_ts": self.last_error_ts,
        }

    def load_persist(self, data: dict):
        """从持久化数据恢复"""
        self.total_calls = data.get("total_calls", 0)
        self.total_cache_hits = data.get("total_cache_hits", 0)
        self.total_prompt_tokens = data.get("total_prompt_tokens", 0)
        self.total_completion_tokens = data.get("total_completion_tokens", 0)
        self.total_tokens = data.get("total_tokens", 0)
        self.total_duration_ms = data.get("total_duration_ms", 0)
        self.error_count = data.get("error_count", 0)
        self.last_error = data.get("last_error")
        self.last_error_ts = data.get("last_error_ts")


class PromptStatsCollector:
    """Prompt 调用统计采集器（单例），由 extractor 在每次 LLM 调用后上报。"""

    def __init__(self):
        self._nodes: dict[str, _PromptNode] = {}
        self._lock = threading.Lock()
        self._last_save_ts: float = 0.0
        self._save_interval = 60
        self._load()

    def _get_or_create_node(self, name: str) -> _PromptNode:
        """按名获取或创建节点，label 从首行用途解析"""
        node = self._nodes.get(name)
        if node is not None:
            return node
        # 从 list_prompt_templates 取 description 作 label
        label = name
        for t in list_prompt_templates():
            if t.get("name") == name:
                label = (t.get("description") or name).strip()[:40] or name
                break
        node = _PromptNode(name=name, label=label, stage="提炼", icon="📄")
        self._nodes[name] = node
        return node

    def record(self, prompt_name: str, duration_ms: int = 0,
               usage: dict | None = None, success: bool = True,
               error: str | None = None, cache_hit: bool = False):
        """记录一次 prompt 调用"""
        usage = usage or {}
        with self._lock:
            node = self._get_or_create_node(prompt_name)
            node.record(duration_ms=duration_ms, usage=usage,
                        success=success, error=error, cache_hit=cache_hit)
        now = time.time()
        if now - self._last_save_ts > self._save_interval:
            self._save()
            self._last_save_ts = now

    def snapshot(self) -> list[dict]:
        """返回所有 prompt 的统计快照（含目录中的模板，未调用的显示 0）"""
        templates = list_prompt_templates()
        with self._lock:
            result = []
            seen = set()
            for t in templates:
                name = t.get("name", "")
                if not name or name in seen:
                    continue
                seen.add(name)
                node = self._get_or_create_node(name)
                result.append(node.snapshot())
            # 补充仅存在于 stats 中（文件已删）的节点
            for name, node in self._nodes.items():
                if name not in seen:
                    result.append(node.snapshot())
            result.sort(key=lambda x: x["name"])
        return result

    def get_detail(self, name: str) -> dict | None:
        """返回单个 prompt 详情（含模板内容、调用记录）"""
        from .extractor import get_prompt_content

        with self._lock:
            node = self._nodes.get(name)
            if node is None:
                node = self._get_or_create_node(name)
            snap = node.snapshot()
            recent = node.recent_calls(20)

        content = get_prompt_content(name) or ""
        system_prompt = (
            "你是一个专业的内容分析助手。请严格按照 JSON 格式输出分析结果，"
            "不要输出任何其他内容。确保 JSON 格式正确。"
        )

        return {
            **snap,
            "content": content,
            "system_prompt": system_prompt,
            "variables": ["CONTENT"],
            "recent_calls": recent,
        }

    def summary(self) -> dict:
        """返回全局汇总"""
        with self._lock:
            total_calls = sum(n.total_calls for n in self._nodes.values())
            total_tokens = sum(n.total_tokens for n in self._nodes.values())
            total_pt = sum(n.total_prompt_tokens for n in self._nodes.values())
            total_ct = sum(n.total_completion_tokens for n in self._nodes.values())
            total_cache = sum(n.total_cache_hits for n in self._nodes.values())
            total_errors = sum(n.error_count for n in self._nodes.values())

        cache_hit_rate = round(total_cache / total_calls, 4) if total_calls > 0 else 0.0
        success_rate = round(1 - total_errors / total_calls, 4) if total_calls > 0 else 1.0

        cost_input = total_pt / 1_000_000 * PRICE_INPUT_PER_M
        cost_output = total_ct / 1_000_000 * PRICE_OUTPUT_PER_M
        estimated_cost_usd = round(cost_input + cost_output, 4)

        return {
            "total_calls": total_calls,
            "total_tokens": total_tokens,
            "total_prompt_tokens": total_pt,
            "total_completion_tokens": total_ct,
            "total_cache_hits": total_cache,
            "cache_hit_rate": cache_hit_rate,
            "avg_success_rate": success_rate,
            "total_errors": total_errors,
            "estimated_cost_usd": estimated_cost_usd,
        }

    def _save(self):
        try:
            data = {}
            with self._lock:
                for name, node in self._nodes.items():
                    data[name] = node.to_persist()
            STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(STATS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("保存 prompt 统计失败: %s", e)

    def _load(self):
        if not STATS_FILE.exists():
            return
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            loaded = 0
            with self._lock:
                for name, saved in data.items():
                    node = self._get_or_create_node(name)
                    node.load_persist(saved)
                    loaded += 1
            logger.info("已恢复 prompt 统计数据 %d 个", loaded)
        except Exception as e:
            logger.error("加载 prompt 统计失败: %s", e)


prompt_stats = PromptStatsCollector()
