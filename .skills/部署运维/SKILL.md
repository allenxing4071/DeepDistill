# DeepDistill 部署运维 Skill

## 触发词
用户说"部署"、"上线"、"重启"、"Docker"、"安装"、"环境"时执行本 Skill。

## 必须遵守的 Rules
- **R6（部署规范）**：未经用户明确授权，禁止执行任何部署操作
- **R0（变更控制）**：禁止在容器内直接修改代码
- **R10（Git Push）**：禁止自动 push

---

## 一、本地开发环境

### 系统要求
- macOS 13+ / Linux（Ubuntu 22.04+）
- Python 3.11+
- ffmpeg（`brew install ffmpeg`）
- GPU 可选：Mac MPS / NVIDIA CUDA

### 安装步骤

```bash
cd ~/Documents/soft/DeepDistill

# 1. 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 2. 安装项目（开发模式）
pip install -e ".[dev]"

# 3. 复制环境变量
cp .env.example .env
# 编辑 .env，填入 API Key（如需使用云端 LLM）

# 4. 验证安装
deepdistill --version
deepdistill config show
```

### 环境变量（.env）

```bash
# LLM API（可选，本地模型优先）
DEEPSEEK_API_KEY=
QWEN_API_KEY=

# 模型缓存路径（默认 ~/.cache/deepdistill/）
MODEL_CACHE_DIR=

# 日志级别
LOG_LEVEL=INFO
```

---

## 二、生产环境信息

### 服务器
- **阿里云**：`47.254.246.53`（与 KKline 共用同一台服务器）
- **SSH**：`ssh -i ~/Documents/soft/KKline/deploy/LH.pem -p 2222 root@47.254.246.53`
- **项目路径（服务器）**：`/opt/DeepDistill`

### 域名
- **域名**：`deepdistill.kline007.top`
- **DNS**：A 记录 → `47.254.246.53`
- **HTTPS**：由 `tradedesk-nginx` 反代（需配置 SSL 证书）

### 访问地址（规划）
- Web UI：`https://deepdistill.kline007.top`
- API：`https://deepdistill.kline007.top/api`
- 健康检查：`https://deepdistill.kline007.top/health`

---

## 三、Docker 部署（可选）

### 构建与运行

```bash
cd ~/Documents/soft/DeepDistill

# 构建镜像
docker build -t deepdistill .

# 运行（挂载数据目录）
docker run -v $(pwd)/output:/app/output \
           -v $(pwd)/config:/app/config \
           --env-file .env \
           deepdistill process /app/input/video.mp4
```

### Docker Compose（含 GPU 支持）

```yaml
# docker-compose.yml
services:
  deepdistill:
    build: .
    volumes:
      - ./input:/app/input
      - ./output:/app/output
      - ./config:/app/config
    env_file: .env
    # GPU 支持（NVIDIA）
    # deploy:
    #   resources:
    #     reservations:
    #       devices:
    #         - capabilities: [gpu]
```

---

## 四、部署脚本

统一使用 `scripts/deploy.sh`（后续开发）：

```bash
cd ~/Documents/soft/DeepDistill

# 本地
./scripts/deploy.sh start    # 启动
./scripts/deploy.sh stop     # 停止
./scripts/deploy.sh status   # 查看状态
./scripts/deploy.sh logs     # 查看日志

# 远程（需配置服务器信息）
./scripts/deploy.sh remote   # 同步代码 + 重建容器
```

---

## 五、依赖管理

### 核心依赖分组

| 分组 | 包含 | 安装方式 |
|---|---|---|
| core | 基础管线 + 文档提取 | `pip install deepdistill` |
| asr | faster-whisper + ffmpeg-python | `pip install deepdistill[asr]` |
| ocr | easyocr | `pip install deepdistill[ocr]` |
| video | PySceneDetect + YOLOv8 + MediaPipe | `pip install deepdistill[video]` |
| ai | LLM 客户端 | `pip install deepdistill[ai]` |
| all | 全部功能 | `pip install deepdistill[all]` |
| dev | 测试 + lint + 格式化 | `pip install deepdistill[dev]` |

---

## 六、常见问题

### ffmpeg 未安装
```bash
# macOS
brew install ffmpeg

# Ubuntu
sudo apt install ffmpeg
```

### MPS 不可用
- 确认 macOS 13+ 且 PyTorch 2.0+
- 部分模型不支持 MPS，会自动 fallback 到 CPU
- 检查：`python -c "import torch; print(torch.backends.mps.is_available())"`

### 模型下载慢
- 设置 `HF_ENDPOINT=https://hf-mirror.com`（国内镜像）
- 或手动下载到 `MODEL_CACHE_DIR` 指定路径

---

## 经验沉淀

<!-- 部署/环境/Docker 相关经验追加到此处 -->
