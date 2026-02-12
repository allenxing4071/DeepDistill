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

## 二、生产环境信息（本机部署）

### 服务器
- **本机 Mac**：`125.69.16.136`
- **项目路径**：`~/Documents/soft/DeepDistill`

### 域名
- **域名**：`deepdistill.kline007.top`
- **DNS**：A 记录 → `125.69.16.136`
- **HTTPS**：由 `aitrader-nginx` 容器反代（AITRADER 项目统一管理）
- **SSL 证书**：Let's Encrypt，由 `aitrader-certbot` 容器自动续期
  - 证书路径：`AITRADER/nginx/ssl/deepdistill-fullchain.pem`
  - 私钥路径：`AITRADER/nginx/ssl/deepdistill-privkey.pem`
  - 有效期至：2026-05-13

### Docker 容器
| 服务 | 容器名 | 端口映射 | 说明 |
|---|---|---|---|
| 后端 | `deepdistill-backend` | `8006:8000` | FastAPI + 管线处理 |
| 前端 | `deepdistill-ui` | `3006:3000` | Next.js Web UI |

### 访问地址
- Web UI：`https://deepdistill.kline007.top`
- API：`https://deepdistill.kline007.top/api/`
- API 文档：`https://deepdistill.kline007.top/docs`
- 健康检查：`https://deepdistill.kline007.top/health`

### Nginx 反代架构
```
用户 → aitrader-nginx:443 (HTTPS)
       ├── deepdistill.kline007.top → host.docker.internal:3006 (前端)
       ├── deepdistill.kline007.top/api/ → host.docker.internal:8006 (后端)
       ├── deepdistill.kline007.top/docs → host.docker.internal:8006 (API 文档)
       └── deepdistill.kline007.top/health → host.docker.internal:8006 (健康检查)
```

- Nginx 配置文件：`~/Documents/soft/AITRADER/nginx/nginx.conf`
- DeepDistill 独立 docker-compose，不加入 aitrader 网络
- Nginx 通过 `host.docker.internal` 访问宿主机端口

---

## 三、Docker 部署

### 构建与运行

```bash
cd ~/Documents/soft/DeepDistill

# 一键构建并启动
docker compose up -d --build

# 查看状态
docker compose ps

# 查看日志
docker compose logs -f

# 仅查看后端日志
docker compose logs -f backend

# 停止
docker compose down

# 重启
docker compose restart
```

### Docker Compose 配置
- 后端：`Dockerfile`（Python 3.11 + ffmpeg）
- 前端：`frontend/Dockerfile`（Node 20 + Next.js standalone）
- 数据卷：`./data` 和 `./config` 挂载到容器
- 前端依赖后端健康检查通过后才启动
- `NEXT_PUBLIC_API_URL` 构建时烧入为 `https://deepdistill.kline007.top`

---

## 四、部署操作速查

```bash
cd ~/Documents/soft/DeepDistill

# 重建并启动（代码变更后）
docker compose up -d --build

# 仅重建后端
docker compose up -d --build backend

# 仅重建前端
docker compose up -d --build frontend

# 重载 Nginx（修改反代配置后）
docker exec aitrader-nginx nginx -s reload

# 查看 SSL 证书到期时间
openssl s_client -connect deepdistill.kline007.top:443 -servername deepdistill.kline007.top 2>/dev/null | openssl x509 -noout -dates

# 手动续期 SSL 证书
docker exec aitrader-certbot certbot renew
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

### 经验：本机多项目 Docker 部署 + 统一 Nginx 反代
- 现象: 本机（125.69.16.136）已运行多个项目（AITrader/AICoin/TradeDesk/KKline/FlowEdge），需要新增 DeepDistill
- 根因: 所有项目共用 `aitrader-nginx` 容器做统一入口（80/443），各项目独立 docker-compose
- 解决:
  1. DeepDistill 独立 docker-compose，端口 8006(后端)/3006(前端)
  2. 在 AITRADER nginx.conf 添加 upstream + server blocks
  3. Nginx 通过 `host.docker.internal` 访问宿主机端口
  4. 先生成自签名证书占位 → 重载 Nginx → certbot 申请正式证书 → 替换 → 再重载
- 验证: `curl https://deepdistill.kline007.top/health` 返回 `{"status":"ok"}`
- 关联: R6(部署规范), AITRADER/nginx/nginx.conf, docker-compose.yml
- 日期: 2026-02-12
