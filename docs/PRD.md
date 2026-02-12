# DeepDistill — 产品需求文档 (PRD)

> **版本**: v0.1.0（初稿）
> **日期**: 2026-02-12
> **作者**: Allen Xing

---

## 1. 项目概述

### 1.1 项目名称

**DeepDistill** — 多源内容深度蒸馏引擎

### 1.2 一句话定义

从视频、音频、图片、文档等多源内容中，通过 AI 深度理解与分析，自动提炼出结构化知识，并支持素材再生成。

### 1.3 核心价值

| 痛点 | DeepDistill 解决方案 |
|---|---|
| 视频/音频内容难以检索和复用 | 自动转文字 + 结构化提炼 |
| 图片中的文字信息散落无法利用 | OCR 提取 + AI 归纳 |
| 文档/网页信息碎片化 | 多源融合 + 去重补全 |
| 视频只提取文字，丢失视觉信息 | 视频增强分析（镜头/场景/风格/动作） |
| 提炼后的知识难以再利用 | 输出 Skill 文档 / Markdown / JSON，支持下游创作 |
| 依赖云端 API，隐私不可控 | 本地优先架构，GPU 加速，敏感内容不出本机 |

### 1.4 目标用户

- **内容创作者**：需要从大量视频/文档中快速提炼素材和灵感
- **知识工作者**：需要将碎片化信息整理为结构化知识库
- **研究人员**：需要从多源资料中提取核心观点和数据
- **团队/组织**：需要统一管理和复用内部知识资产

---

## 2. 系统架构

### 2.1 分层架构总览

```
┌─────────────────────────────────────────────┐
│  Layer 1 — 输入层 (Ingestion)                │
│  多源内容统一接入：视频/音频/图片/文档/网页     │
├─────────────────────────────────────────────┤
│  Layer 2 — 内容处理层 (Processing)            │
│  各格式 → 文本提取（ASR / OCR / 文档解析）     │
├─────────────────────────────────────────────┤
│  Layer 3 — 视频增强分析层 (Video Analysis)     │
│  镜头/场景/动作/风格/转场 深度视觉理解          │
├─────────────────────────────────────────────┤
│  Layer 4 — AI 分析层 (AI Analysis)            │
│  LLM 结构化提炼：核心逻辑/关键词/摘要          │
├─────────────────────────────────────────────┤
│  Layer 5 — 融合输出层 (Fusion & Output)       │
│  去重/合并/补全 → Skill文档/Markdown/JSON      │
│  + 视觉素材再生成                              │
├─────────────────────────────────────────────┤
│  Layer 6 — 知识管理层 (Knowledge Management)  │
│  飞书/Notion/Obsidian 分类管理 + 下游创作      │
└─────────────────────────────────────────────┘
```

### 2.2 技术选型总表

| 层级 | 模块 | 技术栈 | 部署方式 | 硬件需求 |
|---|---|---|---|---|
| 输入层 | 格式识别与路由 | Python (magic/mimetypes) | 本地 | CPU |
| 处理层 | 视频/音频转文字 | ffmpeg + faster-whisper | 本地 GPU (MPS) | GPU 8GB+ |
| 处理层 | 文档/网页提取 | PyPDF2 / python-pptx / BeautifulSoup | 本地 | CPU |
| 处理层 | 图片 OCR | EasyOCR / PaddleOCR | 本地 GPU/CPU | GPU 可加速 |
| 视频分析 | 镜头切割 | PySceneDetect | 本地 | CPU/GPU |
| 视频分析 | 场景识别 | YOLOv8 / Segment Anything | 本地 GPU / API | GPU 8GB+ |
| 视频分析 | 动作识别 | MediaPipe / OpenPose | 本地 GPU/CPU | GPU 优先 |
| 视频分析 | 风格/拍摄手法 | CLIP / Video Swin / TimeSformer | 本地 GPU / API | GPU 16GB+ |
| 视频分析 | 转场/特效 | 自定义特征提取 | 本地 | CPU/GPU |
| AI 分析 | 短内容提炼 | 本地轻量 LLM (DeepSeek/Qwen) | 本地 | GPU/CPU |
| AI 分析 | 中长内容提炼 | DeepSeek V3 + Qwen Max API | API | — |
| 融合输出 | 结构化输出 | Python | 本地 | CPU |
| 融合输出 | 素材生成 | Stable Diffusion / RunwayML | 本地 GPU / API | GPU 16GB+ |
| 知识管理 | 文档管理 | 飞书 / Notion / Obsidian API | 本地/云 | CPU |

---

## 3. 功能需求（按优先级分期）

### 3.1 P0 — MVP（最小可用产品）

> 目标：跑通"内容输入 → 文本提取 → AI 提炼 → 结构化输出"核心链路

| 编号 | 功能 | 描述 | 验收标准 |
|---|---|---|---|
| P0-01 | CLI 入口 | 命令行输入文件路径，自动识别格式并处理 | `deepdistill process <file>` 可运行 |
| P0-02 | 视频/音频转文字 | ffmpeg 提取音轨 + faster-whisper 转录 | 中文/英文视频转录准确率 ≥ 90% |
| P0-03 | 文档提取 | PDF/Word/PPT → 纯文本 | 保留标题层级和段落结构 |
| P0-04 | 图片 OCR | 图片中文字提取 | 中英文混合识别可用 |
| P0-05 | AI 结构化提炼 | LLM 对提取文本做摘要/关键词/核心逻辑 | 输出 JSON 结构化结果 |
| P0-06 | Markdown 输出 | 提炼结果输出为 Markdown 文件 | 格式清晰、可直接阅读 |
| P0-07 | 配置系统 | YAML/TOML 配置文件，支持模型选择/输出格式等 | 配置项可覆盖默认值 |

### 3.2 P1 — 视频增强分析

> 目标：视频不只提取文字，还理解视觉内容

| 编号 | 功能 | 描述 | 验收标准 |
|---|---|---|---|
| P1-01 | 镜头切割 | 自动检测场景切换点 | 切割准确率 ≥ 85% |
| P1-02 | 场景识别 | 识别每个镜头中的场景/物体 | 输出场景标签列表 |
| P1-03 | 人物/动作识别 | 检测人物姿态和动作 | 输出动作描述 |
| P1-04 | 拍摄手法分析 | 识别构图/景别/镜头类型 | 输出拍摄手法标签 |
| P1-05 | 风格特征提取 | 色彩/光影/节奏/视觉冲击力 | 输出风格向量 (embedding) |
| P1-06 | 视觉+文本融合 | 将视觉分析结果与转录文本合并 | 输出包含视觉描述的完整提炼 |

### 3.3 P2 — 高级输出与知识管理

> 目标：提炼结果可落地、可复用、可管理

| 编号 | 功能 | 描述 | 验收标准 |
|---|---|---|---|
| P2-01 | Skill 文档输出 | 输出为可交互/可复用的 Skill 文档格式 | 符合 Skill 文档规范 |
| P2-02 | 批量处理 | 支持目录级批量输入 | 自动遍历目录，逐文件处理 |
| P2-03 | 去重与合并 | 多文件提炼结果去重、合并、补全 | 跨文件知识点不重复 |
| P2-04 | 知识库对接 | 输出到飞书/Notion/Obsidian | API 推送成功 |
| P2-05 | 素材再生成 | 基于提炼文字 + 风格向量生成新图片 | 生成图片与原风格一致 |
| P2-06 | Web UI | 简易 Web 界面，拖拽上传、查看结果 | 可通过浏览器操作 |

---

## 4. 非功能需求

### 4.1 性能

| 指标 | 目标 |
|---|---|
| 5 分钟视频转录 | ≤ 2 分钟（本地 GPU MPS） |
| 10 页 PDF 提取 | ≤ 5 秒 |
| 单文件 AI 提炼 | ≤ 30 秒（API）/ ≤ 60 秒（本地） |
| 批量 100 文件 | 支持队列化处理，不 OOM |

### 4.2 隐私与安全

- **本地优先**：默认所有处理在本地完成，敏感内容不出本机
- **API 可选**：仅在用户明确配置后才调用云端 API
- **无数据上传**：不自动上传任何用户内容到第三方服务
- **密钥管理**：API Key 通过 `.env` 管理，不进入版本控制

### 4.3 可扩展性

- **插件化架构**：每个处理模块（ASR/OCR/LLM/视频分析）可独立替换
- **模型可切换**：通过配置文件切换不同的 ASR/LLM/OCR 模型
- **输出格式可扩展**：新增输出格式只需实现 OutputFormatter 接口

---

## 5. 技术架构设计

### 5.1 目录结构（规划）

```
DeepDistill/
├── deepdistill/              # 核心 Python 包
│   ├── __init__.py
│   ├── __main__.py           # CLI 入口
│   ├── config.py             # 配置管理
│   ├── pipeline.py           # 主管线编排
│   ├── ingestion/            # Layer 1: 输入层
│   │   ├── __init__.py
│   │   ├── router.py         # 格式识别与路由
│   │   └── formats.py        # 支持的格式定义
│   ├── processing/           # Layer 2: 内容处理层
│   │   ├── __init__.py
│   │   ├── asr.py            # 视频/音频转文字 (faster-whisper)
│   │   ├── ocr.py            # 图片文字提取 (EasyOCR/PaddleOCR)
│   │   └── document.py       # 文档/网页提取
│   ├── video_analysis/       # Layer 3: 视频增强分析层
│   │   ├── __init__.py
│   │   ├── scene_detect.py   # 镜头切割
│   │   ├── object_detect.py  # 场景/物体识别
│   │   ├── pose_detect.py    # 人物/动作识别
│   │   ├── style_analyze.py  # 风格/拍摄手法分析
│   │   └── transition.py     # 转场/特效识别
│   ├── ai_analysis/          # Layer 4: AI 分析层
│   │   ├── __init__.py
│   │   ├── llm_client.py     # LLM 调用封装
│   │   ├── prompts/          # 提示词模板
│   │   └── extractor.py      # 结构化提炼逻辑
│   ├── fusion/               # Layer 5: 融合输出层
│   │   ├── __init__.py
│   │   ├── merger.py         # 去重/合并/补全
│   │   ├── formatters/       # 输出格式化器
│   │   │   ├── markdown.py
│   │   │   ├── json_fmt.py
│   │   │   └── skill_doc.py
│   │   └── generator.py      # 素材再生成
│   └── knowledge/            # Layer 6: 知识管理层
│       ├── __init__.py
│       ├── notion.py
│       ├── feishu.py
│       └── obsidian.py
├── docs/                     # 项目文档
│   ├── PRD.md                # 本文件：产品需求文档
│   └── architecture.md       # 架构设计文档（后续）
├── tests/                    # 测试
├── config/                   # 配置文件模板
│   └── default.yaml
├── .env.example              # 环境变量模板
├── .gitignore
├── pyproject.toml            # 项目元数据与依赖
└── README.md
```

### 5.2 核心流程

```
用户输入文件/目录
       │
       ▼
  Ingestion Router
  (识别格式，分发到对应处理器)
       │
       ├── 视频/音频 → ASR Processor → 转录文本
       ├── 图片      → OCR Processor → 提取文本
       ├── 文档/网页  → Doc Processor → 提取文本
       │
       ▼
  [可选] Video Analyzer
  (镜头切割 → 场景识别 → 动作/风格分析)
       │
       ▼
  AI Analyzer
  (LLM 结构化提炼：摘要/关键词/核心逻辑/标签)
       │
       ▼
  Fusion Engine
  (去重/合并/补全/结构化)
       │
       ├── Markdown 输出
       ├── JSON 输出
       ├── Skill 文档输出
       └── [可选] 素材再生成
```

### 5.3 设计原则

1. **管线模式 (Pipeline)**：每一层的输出是下一层的输入，层间通过标准数据结构传递
2. **插件化**：每个处理器实现统一接口，可独立替换（如 whisper → 其他 ASR）
3. **本地优先**：默认不调用任何云端 API，用户显式开启后才使用
4. **渐进增强**：MVP 只需 Layer 1-2-4-5，视频分析层和知识管理层按需启用
5. **配置驱动**：所有行为通过配置文件控制，代码中不硬编码参数

---

## 6. 开发计划

### Phase 1 — MVP 骨架（1-2 周）

- [ ] 项目初始化：pyproject.toml、CLI 入口、配置系统
- [ ] 输入层：格式识别与路由
- [ ] 处理层：视频/音频 ASR（faster-whisper）
- [ ] 处理层：文档提取（PDF/Word/PPT）
- [ ] 处理层：图片 OCR（EasyOCR）
- [ ] AI 分析层：LLM 调用封装 + 结构化提炼
- [ ] 输出层：Markdown 格式化输出
- [ ] 端到端测试：一个视频 → 完整 Markdown 输出

### Phase 2 — 视频增强（2-3 周）

- [ ] 镜头切割（PySceneDetect）
- [ ] 场景识别（YOLOv8）
- [ ] 动作识别（MediaPipe）
- [ ] 风格特征提取（CLIP）
- [ ] 视觉+文本融合提炼

### Phase 3 — 高级功能（3-4 周）

- [ ] 批量处理与队列
- [ ] 去重与跨文件合并
- [ ] Skill 文档输出格式
- [ ] 知识库对接（Notion/飞书）
- [ ] Web UI（可选）
- [ ] 素材再生成（可选）

---

## 7. 风险与约束

| 风险 | 影响 | 缓解措施 |
|---|---|---|
| Mac GPU (MPS) 兼容性 | 部分模型不支持 MPS | 提供 CPU fallback，标注兼容矩阵 |
| 大文件内存溢出 | 长视频/大文档处理 OOM | 分块处理 + 流式管线 |
| LLM API 成本 | 大量调用费用高 | 本地轻量模型优先 + 缓存 + token 预估 |
| 模型精度不足 | OCR/ASR 中文识别率低 | 提供模型切换配置 + 后处理校正 |
| 视频分析模型体积大 | 下载/加载慢 | 按需下载 + 模型缓存 + 轻量替代方案 |

---

## 8. 术语表

| 术语 | 定义 |
|---|---|
| ASR | Automatic Speech Recognition，自动语音识别 |
| OCR | Optical Character Recognition，光学字符识别 |
| LLM | Large Language Model，大语言模型 |
| MPS | Metal Performance Shaders，Apple GPU 加速框架 |
| Skill 文档 | 结构化的可交互知识文档格式 |
| 风格向量 | 视频/图片的视觉特征 embedding，用于风格迁移和素材生成 |
| Pipeline | 管线/流水线，数据依次经过多个处理阶段 |
