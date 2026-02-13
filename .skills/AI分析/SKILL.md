# DeepDistill AI 分析 Skill

> **核心原则：AI 分析层是知识蒸馏的核心。LLM 的输入质量和 Prompt 设计直接决定提炼效果。**

## 触发词
用户说"AI分析"、"提炼"、"LLM"、"prompt"、"结构化"、"摘要"、"关键词"时执行本 Skill。

## 必须遵守的 Rules
- **R0（变更控制）**：LLM 调用和 Prompt 属于核心链路，修改前必须征得用户同意
- **R5（安全）**：禁止泄露 API Key；调用云端 API 前必须提示用户
- **R8（经验沉淀）**：LLM/Prompt 相关经验追加到本文件

---

## 一、LLM 分层策略

### 模型选择

| 内容长度 | 模型 | 部署方式 | 说明 |
|---|---|---|---|
| 短内容（< 2000 字） | DeepSeek 轻量 / Qwen 轻量 | 本地 | 成本低、速度快 |
| 中长内容（2000-10000 字） | DeepSeek V3 API | 云端 API | 精度高 |
| 长内容（> 10000 字） | DeepSeek V3 + Qwen Max 双模型 | 云端 API | 交叉验证，提高可靠性 |

### 本地 vs API 决策
```
内容长度 ≤ 2000 字 且 本地模型可用？
  ├── 是 → 使用本地轻量模型
  └── 否 → 检查 API Key 是否配置
           ├── 是 → 使用云端 API（提示用户）
           └── 否 → 报错，提示配置 API Key
```

---

## 二、结构化提炼输出

### 标准输出结构（JSON）

```json
{
  "title": "内容标题/文件名",
  "summary": "200 字以内的核心摘要",
  "key_points": [
    "核心观点 1",
    "核心观点 2"
  ],
  "keywords": ["关键词1", "关键词2"],
  "structure": {
    "type": "教程/分析/叙事/演讲/...",
    "sections": [
      {
        "heading": "章节标题",
        "content": "章节摘要",
        "timestamp": "00:01:30"
      }
    ]
  },
  "metadata": {
    "source_type": "video/audio/document/image",
    "language": "zh/en",
    "word_count": 5000,
    "processing_time_sec": 12.5,
    "model_used": "deepseek-v3",
    "confidence": 0.85
  }
}
```

---

## 三、Prompt 管理

### 原则
- 所有 Prompt 模板放在 `deepdistill/ai_analysis/prompts/` 目录
- 禁止在代码中硬编码 Prompt 文本
- Prompt 文件使用中文说明用途，提示词本身可用英文
- 每个 Prompt 文件顶部标注：用途、输入格式、期望输出格式

### Prompt 模板清单

| 文件 | 用途 |
|---|---|
| `summarize.txt` | 通用内容摘要（默认） |
| `extract_structure.txt` | 提取文档结构与层级 |
| `extract_keywords.txt` | 关键词与标签提取 |
| `video_narrate.txt` | 视频内容叙述（结合视觉分析） |
| `merge_sources.txt` | 多源内容融合提炼 |

### 模板管理 API

- `list_prompt_templates()` — 列出 prompts 目录下所有 .txt 模板（供设置页/API 使用）
- `get_prompt_content(name)` — 获取指定模板内容，禁止路径穿越
- 配置项：`ai.prompt_template` / `AI_PROMPT_TEMPLATE` 指定默认模板名

### Prompt 统计（prompt_stats）

- 采集器：`ai_analysis/prompt_stats.py`
- 记录：调用频率、Token 消耗、耗时、缓存命中率、错误信息
- 持久化：`data/prompt_stats.json`
- 设置页：通过 `/api/config` / 设置页面展示统计

---

## 四、成本控制

- 本地模型优先，减少 API 调用
- 长文本先分块摘要，再合并（避免单次超长 prompt）
- 缓存已处理结果（相同输入不重复调用）
- 记录每次调用的 token 消耗，便于成本追踪

---

## 五、质量检查

- [ ] 输出 JSON 格式合法
- [ ] summary 不超过 200 字
- [ ] key_points 至少 2 条
- [ ] keywords 至少 3 个
- [ ] 无幻觉内容（与原文核实）
- [ ] 多语言内容正确识别语种

---

## JSON 响应解析（_parse_json_response）

LLM 有时输出带 markdown 代码块或前后缀，解析策略：
1. 直接 `json.loads(response)` 尝试
2. 提取 ` ```json ... ``` ` 代码块
3. 提取首尾 `{` 和 `}` 之间的内容
4. 失败时返回 `{summary: 前500字, key_points: [], keywords: [], parse_error: true}`

## 经验沉淀

<!-- LLM 调用/Prompt 调优相关经验追加到此处 -->
