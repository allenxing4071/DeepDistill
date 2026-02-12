# DeepDistill 开发指南

## 开发环境搭建

### 前置依赖

```bash
# macOS
brew install python@3.11 node ffmpeg

# 验证
python3 --version   # >= 3.11
node --version       # >= 18
ffmpeg -version
```

### 后端开发

```bash
cd ~/Documents/soft/DeepDistill

# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装全部依赖（含开发工具）
pip install -e ".[all,dev]"

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入 DEEPSEEK_API_KEY / QWEN_API_KEY 等

# 启动开发服务器（热重载）
uvicorn deepdistill.api:app --reload --port 8006
```

### 前端开发

```bash
cd ~/Documents/soft/DeepDistill/frontend

npm install

# 开发模式（连接本地后端）
NEXT_PUBLIC_API_URL=http://localhost:8006 npm run dev
# 访问 http://localhost:3006
```

### Docker 开发

```bash
cd ~/Documents/soft/DeepDistill

# 构建并启动
docker-compose up -d

# 仅重建后端（代码修改后）
docker-compose build --no-cache backend && docker-compose up -d backend

# 仅重建前端
docker-compose build --no-cache frontend && docker-compose up -d frontend

# 查看日志
docker logs deepdistill-backend -f --tail 50
docker logs deepdistill-ui -f --tail 50
```

## 模块架构

### 六层管线

```
Layer 1: Ingestion (ingestion/)
    │  格式识别 → 路由到对应处理器
    ▼
Layer 2: Processing (processing/)
    │  ASR (faster-whisper) / OCR (EasyOCR) / 文档提取
    ▼
Layer 3: Video Analysis (video_analysis/)  [可选]
    │  镜头切割 / 场景识别 / 动作检测 / 拍摄手法 / 风格特征 / 转场检测
    ▼
Layer 4: AI Analysis (ai_analysis/)
    │  LLM 结构化提炼 (DeepSeek / Qwen / Ollama)
    ▼
Layer 5: Fusion (fusion/)
    │  去重 / 合并 / 补全 / 格式化 → Markdown / JSON / Skill
    ▼
Layer 6: Export (export/)
       Google Drive 导出（自动分类 + 中文标题）
```

### 模块接口说明

#### Layer 1: Ingestion (`ingestion/router.py`)

```python
class IngestionRouter:
    def identify(self, file_path: Path) -> str:
        """识别文件类型，返回: video/audio/document/image/webpage"""

    def route(self, file_path: Path) -> dict:
        """路由到对应处理器，返回处理结果"""
```

#### Layer 2: Processing

**ASR (`processing/asr.py`)**
```python
class ASRProcessor:
    def transcribe(self, audio_path: Path) -> str:
        """音频/视频 → 文本（faster-whisper）"""
```

**OCR (`processing/ocr.py`)**
```python
class OCRProcessor:
    def extract_text(self, image_path: Path) -> str:
        """图片 → 文本（EasyOCR / PaddleOCR）"""
```

**Document (`processing/document.py`)**
```python
class DocumentProcessor:
    def extract(self, doc_path: Path) -> str:
        """文档 → 文本（PDF/Word/PPT/Excel/HTML/TXT）"""
```

#### Layer 3: Video Analysis (`video_analysis/`)

| 模块 | 类 | 输入 | 输出 |
|---|---|---|---|
| `scene_detector.py` | SceneDetector | 视频路径 | 场景列表 + 关键帧 |
| `object_detector.py` | ObjectDetector | 关键帧 | 物体列表 + 场景描述 |
| `action_detector.py` | ActionDetector | 关键帧 | 动作列表 |
| `cinematography.py` | CinematographyAnalyzer | 关键帧 | 景别/构图/镜头运动 |
| `style_analyzer.py` | StyleAnalyzer | 关键帧+场景 | 风格向量(12维) |
| `transition_detector.py` | TransitionDetector | 视频路径 | 转场列表 |

#### Layer 4: AI Analysis (`ai_analysis/`)

```python
class LLMClient:
    def analyze(self, text: str, context: dict = None) -> dict:
        """LLM 结构化提炼，返回 {summary, key_points, keywords, structure}"""
        # Fallback 链: Ollama → DeepSeek → Qwen
```

#### Layer 5: Fusion (`fusion/`)

```python
class FusionProcessor:
    def process(self, result: ProcessingResult) -> ProcessingResult:
        """去重/合并/补全/质量检查"""
```

**输出格式器 (`fusion/formatters/`)**
- `markdown.py` → Markdown 文件
- `json_fmt.py` → 结构化 JSON
- `skill_fmt.py` → Skill 文档格式

#### Layer 6: Export (`export/google_docs.py`)

```python
class GoogleDocsExporter:
    def export_task_result(self, task, category=None, fmt="doc", export_format="doc"):
        """导出到 Google Drive，返回 list[dict]"""
        # 自动生成中文标题 + 自动分类 + 源文件保留

    @staticmethod
    def _generate_short_title(task: dict) -> str:
        """从 AI 结果提取 ≤8 字中文标题"""

    @staticmethod
    def _auto_categorize(task: dict) -> str:
        """根据关键词自动推断分类"""
```

### 主管线 (`pipeline.py`)

```python
class DeepDistillPipeline:
    def process(self, source_path: Path, options: dict = None,
                progress_callback=None) -> ProcessingResult:
        """
        完整管线：输入 → 处理 → [视频分析] → AI 提炼 → 融合输出
        progress_callback(progress: int, label: str) 用于实时进度回调
        """
```

### API 服务 (`api.py`)

关键设计：
- **并发控制**：`asyncio.Semaphore(MAX_CONCURRENT_PIPELINES)` 限制同时处理的管线数
- **内存保护**：API 返回时截断大文本字段，内部处理保留完整文本
- **文件限制**：单文件 2GB，批量总计 2GB
- **定时清理**：每 10 分钟清理过期任务和临时文件
- **自动导出**：`options.auto_export=true` 时处理完自动导出到 Google Drive

## 代码规范

### Python

- 类型注解：所有函数参数和返回值必须有类型注解
- 文件头注释：每个文件顶部必须有中文用途说明（1-3 行）
- 代码注释：优先使用中文
- 日志：使用 `logging` 模块，关键操作必须记录日志
- 异常处理：外部 API 调用必须有重试机制

### TypeScript / React

- 组件：函数式组件 + Hooks
- 样式：Tailwind CSS，响应式优先（`sm:` / `md:` / `lg:`）
- 状态管理：React useState/useEffect，无全局状态库

### Git 提交

```
feat: 新增功能
fix: 修复 Bug
refactor: 重构（不改变行为）
docs: 文档更新
test: 测试用例
chore: 构建/配置变更
```

## 添加新的处理器

以添加新的文档格式为例：

```python
# 1. 在 processing/document.py 中添加处理方法
def _extract_from_new_format(self, path: Path) -> str:
    """提取 .xyz 格式的文本"""
    ...

# 2. 在 ingestion/router.py 中注册格式
DOCUMENT_EXTENSIONS = {".pdf", ".docx", ..., ".xyz"}

# 3. 在 processing/document.py 的 extract() 中添加分支
elif suffix == ".xyz":
    return self._extract_from_new_format(path)
```

## 添加新的 AI 提供商

```python
# 在 ai_analysis/llm_client.py 中：

# 1. 添加提供商配置
PROVIDERS = {
    "ollama": {...},
    "deepseek": {...},
    "qwen": {...},
    "new_provider": {
        "base_url": "https://api.new-provider.com/v1",
        "model": "model-name",
        "api_key_env": "NEW_PROVIDER_API_KEY",
    },
}

# 2. 在 config.py 中添加配置项
NEW_PROVIDER_API_KEY = os.getenv("NEW_PROVIDER_API_KEY", "")
```

## 添加新的导出分类

```python
# 在 export/google_docs.py 中：

# 1. 添加到 CATEGORIES 字典
CATEGORIES = {
    ...,
    "新分类": "新分类",
}

# 2. 在 _auto_categorize() 中添加关键词映射
category_keywords = {
    ...,
    "新分类": ["关键词1", "关键词2", ...],
}
```

## 常见问题

### faster-whisper MPS 不支持
faster-whisper 底层使用 CTranslate2，不支持 Apple MPS。Mac 上会自动 fallback 到 CPU（int8 量化）。如需 GPU 加速，使用 NVIDIA CUDA。

### Google Drive 认证失败
1. 确认 `config/credentials.json` 存在且有效
2. 删除 `config/token.json` 重新授权
3. 确认 Google Cloud Console 中已启用 Drive API

### Docker 容器内无法连接 Ollama
使用 `host.docker.internal` 而非 `localhost`：
```
OLLAMA_BASE_URL=http://host.docker.internal:11434
```
