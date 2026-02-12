# DeepDistill 项目入门

## 触发词
用户说"项目结构"、"怎么跑"、"入门"时执行本 Skill。

## 必须遵守的 Rules
- 修改任何核心模块前先阅读本 Skill 了解架构（R0 要求）
- 新经验写入本文件"经验沉淀"区（R8 要求）

## 核心定位

DeepDistill 是一个多源内容深度蒸馏引擎，从视频/音频/图片/文档/网页中自动提取文本，通过 AI 深度分析生成结构化知识，并支持视觉素材再生成。

**核心特性：**
- 多源输入（视频/音频/图片/文档/网页）
- 深度理解（不只转文字，还分析视频的镜头/场景/风格/动作）
- AI 提炼（LLM 结构化输出摘要/关键词/核心逻辑）
- 本地优先（默认全部本地处理，GPU MPS 加速，隐私可控）
- 插件化（ASR/OCR/LLM/视频分析模块可独立替换）

## 项目结构

```
DeepDistill/
├── deepdistill/              # 核心 Python 包
│   ├── __init__.py
│   ├── __main__.py           # CLI 入口
│   ├── config.py             # 配置管理
│   ├── pipeline.py           # 主管线编排
│   ├── ingestion/            # Layer 1: 输入层（格式识别与路由）
│   ├── processing/           # Layer 2: 内容处理层（ASR/OCR/文档提取）
│   ├── video_analysis/       # Layer 3: 视频增强分析层
│   ├── ai_analysis/          # Layer 4: AI 分析层（LLM 提炼）
│   ├── fusion/               # Layer 5: 融合输出层（去重/合并/格式化）
│   └── knowledge/            # Layer 6: 知识管理层（飞书/Notion/Obsidian）
├── docs/                     # 项目文档
│   └── PRD.md                # 产品需求文档
├── scripts/                  # 工具脚本
├── tests/                    # 测试
├── config/                   # 配置文件
│   └── default.yaml
├── .cursor/rules/            # Cursor Rules
├── .skills/                  # Skills 知识库
├── .env.example              # 环境变量模板
├── .gitignore
├── pyproject.toml
└── README.md
```

## 六层管线架构

```
输入文件/目录
     │
     ▼
Layer 1: Ingestion Router（格式识别，分发到对应处理器）
     │
     ├── 视频/音频 → Layer 2: ASR Processor → 转录文本
     ├── 图片      → Layer 2: OCR Processor → 提取文本
     ├── 文档/网页  → Layer 2: Doc Processor → 提取文本
     │
     ▼
Layer 3: Video Analyzer [可选]（镜头/场景/动作/风格分析）
     │
     ▼
Layer 4: AI Analyzer（LLM 结构化提炼）
     │
     ▼
Layer 5: Fusion Engine（去重/合并/补全/格式化输出）
     │
     ├── Markdown / JSON / Skill 文档
     └── [可选] 素材再生成
```

## 快速上手

### 安装
```bash
cd ~/Documents/soft/DeepDistill
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 基本使用
```bash
# 处理单个文件
deepdistill process video.mp4

# 处理目录
deepdistill process ./my-content/

# 查看配置
deepdistill config show
```

### 环境要求
- Python 3.11+
- ffmpeg（视频/音频处理必需）
- GPU (MPS/CUDA) 可选，加速 ASR/OCR/视频分析

## 技术选型速查

| 能力 | 技术 | 本地/API | 硬件需求 |
|---|---|---|---|
| 语音转文字 | ffmpeg + faster-whisper | 本地 GPU (MPS) | GPU 8GB+ |
| 图片 OCR | EasyOCR / PaddleOCR | 本地 GPU/CPU | GPU 可加速 |
| 文档解析 | PyPDF2 / python-pptx / BeautifulSoup | 本地 | CPU |
| 镜头切割 | PySceneDetect | 本地 | CPU/GPU |
| 场景识别 | YOLOv8 / Segment Anything | 本地 GPU / API | GPU 8GB+ |
| 动作识别 | MediaPipe / OpenPose | 本地 GPU/CPU | GPU 优先 |
| 风格分析 | CLIP / Video Swin | 本地 GPU / API | GPU 16GB+ |
| AI 提炼 | DeepSeek / Qwen | 本地 + API | GPU/CPU |

## 经验沉淀

<!-- 项目架构/结构相关经验追加到此处 -->
