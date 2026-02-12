# DeepDistill

> 多源内容深度蒸馏引擎 — 从视频/音频/图片/文档/网页中提炼结构化知识

## 项目简介

DeepDistill 从多种格式的内容中自动提取文本，通过 AI 深度分析生成结构化知识文档，并自动导出到 Google Drive 分类管理。

**核心特性：**

- **多源输入**：视频 (mp4/mov/avi/mkv)、音频 (mp3/wav/m4a)、图片 (JPG/PNG/WebP)、文档 (PDF/Word/PPT/Excel)、网页 (URL 抓取)
- **深度理解**：不只转文字，还分析视频的镜头切割、场景识别、动作检测、拍摄手法、风格特征、转场特效
- **AI 提炼**：DeepSeek / Qwen / Ollama 三提供商 Fallback，输出结构化摘要、关键词、核心逻辑
- **智能导出**：自动生成 ≤8 字中文标题，按内容自动分类到 Google Drive 子目录
- **本地优先**：默认全部本地处理，GPU (MPS/CUDA) 加速，隐私可控
- **高可用**：并发限流、内存保护、文件大小限制、定时清理、重试机制

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+（前端）
- Docker & Docker Compose
- ffmpeg（视频/音频处理必需）
- GPU (MPS/CUDA) 可选，加速 ASR/OCR/视频分析

### Docker 部署（推荐）

```bash
cd ~/Documents/soft/DeepDistill

# 1. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 API Key 等配置

# 2. 启动服务
docker-compose up -d

# 3. 访问
# 前端 UI: http://localhost:3006
# 后端 API: http://localhost:8006
# API 文档: http://localhost:8006/docs
# 健康检查: http://localhost:8006/health
```

### 本地开发

```bash
# 后端
cd ~/Documents/soft/DeepDistill
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[all,dev]"
uvicorn deepdistill.api:app --reload --port 8006

# 前端
cd frontend
npm install
npm run dev  # http://localhost:3006
```

## 系统架构

```
┌─────────────────────────────────────────────────────┐
│                    Web UI (Next.js)                  │
│         上传面板 / 结果列表 / 系统设置                  │
└──────────────────────┬──────────────────────────────┘
                       │ REST API
┌──────────────────────▼──────────────────────────────┐
│                 FastAPI 后端                          │
├─────────────────────────────────────────────────────┤
│ Layer 1: Ingestion    │ 格式识别 → 路由到对应处理器     │
│ Layer 2: Processing   │ ASR / OCR / 文档提取           │
│ Layer 3: Video        │ 镜头/场景/动作/风格/转场分析    │
│ Layer 4: AI Analysis  │ DeepSeek/Qwen/Ollama 结构化提炼│
│ Layer 5: Fusion       │ 去重/合并/补全 → Markdown/JSON  │
│ Layer 6: Export       │ Google Drive 自动分类导出       │
└─────────────────────────────────────────────────────┘
```

## API 接口

| 端点 | 方法 | 说明 |
|---|---|---|
| `/health` | GET | 健康检查 |
| `/api/config` | GET | 系统配置信息 |
| `/api/status` | GET | 实时组件状态（8 个组件） |
| `/api/process` | POST | 单文件上传处理 |
| `/api/process/batch` | POST | 批量文件上传（最多 20 个） |
| `/api/process/url` | POST | URL 网页抓取处理 |
| `/api/process/local` | POST | 本地文件路径处理 |
| `/api/tasks` | GET | 任务列表 |
| `/api/tasks/{id}` | GET | 任务详情 |
| `/api/tasks/{id}/export/google-docs` | POST | 导出到 Google Drive |
| `/api/export/categories` | GET | 导出分类列表 |

### 使用示例

```bash
# 提交 URL 处理（自动导出到 Google Drive）
curl -X POST http://localhost:8006/api/process/url \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/article", "options": {"auto_export": true}}'

# 查看任务状态
curl http://localhost:8006/api/tasks/{task_id}

# 手动导出到 Google Drive
curl -X POST http://localhost:8006/api/tasks/{task_id}/export/google-docs \
  -H "Content-Type: application/json" \
  -d '{"category": "技术文档", "doc_type": "doc"}'
```

## 配置说明

### 环境变量（.env）

| 变量 | 说明 | 默认值 |
|---|---|---|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 | — |
| `QWEN_API_KEY` | 通义千问 API 密钥 | — |
| `OLLAMA_BASE_URL` | Ollama 本地服务地址 | `http://host.docker.internal:11434` |
| `GOOGLE_CREDENTIALS_PATH` | Google OAuth2 凭证文件路径 | `config/credentials.json` |
| `GOOGLE_DRIVE_FOLDER` | Google Drive 根文件夹名 | `DeepDistill` |
| `DEEPDISTILL_MAX_CONCURRENT` | 最大并发管线数 | `3` |
| `DEEPDISTILL_MAX_FILE_SIZE` | 单文件大小限制（字节） | `2147483648`（2GB） |
| `DEEPDISTILL_MAX_TASKS` | 最大任务数 | `1000` |

### Google Drive 自动分类

导出时自动根据 AI 分析结果推断分类，放入对应子文件夹：

| 分类 | 触发关键词 |
|---|---|
| 技术文档 | API、Docker、Python、框架、编程、架构… |
| 市场分析 | 市场、交易、投资、加密、比特币、区块链… |
| 学习笔记 | 教程、学习、入门、指南、tutorial… |
| 创意素材 | 设计、素材、图片、视频、UI/UX… |
| 会议纪要 | 会议、纪要、讨论、决议… |
| 法律法规 | 法律、法规、条例、合规、监管… |
| 投诉维权 | 投诉、维权、举报、违规… |
| 其他 | 以上均不匹配时的默认分类 |

## 技术栈

| 能力 | 技术 | 本地/API |
|---|---|---|
| 语音转文字 | ffmpeg + faster-whisper | 本地 (CUDA/CPU) |
| 图片 OCR | EasyOCR / PaddleOCR | 本地 (GPU/CPU) |
| 文档解析 | PyPDF2 / python-docx / python-pptx / openpyxl | 本地 |
| 网页抓取 | httpx + BeautifulSoup | 本地 |
| 镜头切割 | PySceneDetect + OpenCV fallback | 本地 |
| 场景识别 | YOLOv8 + OpenCV fallback | 本地 |
| 动作识别 | MediaPipe + OpenCV fallback | 本地 |
| 拍摄手法 | OpenCV 光流分析 | 本地 |
| 风格特征 | OpenCV + NumPy（色彩/光影/节奏） | 本地 |
| 转场检测 | 帧间差异 + 亮度模式分析 | 本地 |
| AI 提炼 | DeepSeek V3 / Qwen Max / Ollama | API + 本地 |
| 素材生成 | Stable Diffusion WebUI / DALL-E | 本地 + API |
| 文档导出 | Google Drive API (Doc/Word/Excel) | API |
| 前端 | Next.js 14 + React 18 + Tailwind CSS | — |
| 后端 | FastAPI + Uvicorn | — |

## 项目结构

```
DeepDistill/
├── deepdistill/              # 核心 Python 包
│   ├── api.py                # FastAPI 服务（11 个端点）
│   ├── config.py             # 配置管理
│   ├── pipeline.py           # 主管线编排
│   ├── ingestion/            # Layer 1: 输入层（格式识别与路由）
│   ├── processing/           # Layer 2: 内容处理层（ASR/OCR/文档提取）
│   ├── video_analysis/       # Layer 3: 视频增强分析层（6 个子模块）
│   ├── ai_analysis/          # Layer 4: AI 分析层（LLM 提炼）
│   ├── fusion/               # Layer 5: 融合输出层（去重/合并/格式化）
│   └── export/               # Layer 6: 导出层（Google Drive）
├── frontend/                 # Next.js 前端
│   ├── app/                  # 页面（首页/结果/设置）
│   ├── components/           # 组件库
│   └── lib/                  # 工具函数
├── tests/                    # 测试用例
├── docs/                     # 项目文档
├── config/                   # 配置文件
├── data/                     # 运行时数据（Docker 卷挂载）
├── .skills/                  # Skills 知识库
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## 文档

- [产品需求文档 (PRD)](docs/PRD.md)
- [增强版内容管线设计](docs/Enhanced_Content_Pipeline.md)
- [开发指南](docs/DEVELOPMENT.md)

## 运行测试

```bash
cd ~/Documents/soft/DeepDistill
source .venv/bin/activate
pytest tests/ -v
```

## License

MIT
