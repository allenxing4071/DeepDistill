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

### 本地 Docker 命令
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

### deploy.sh 脚本命令
```bash
cd ~/Documents/soft/DeepDistill

# ——— 本地部署 ———
./scripts/deploy.sh deploy      # 一键部署（全量重建）
./scripts/deploy.sh backend     # 仅重建后端
./scripts/deploy.sh frontend    # 仅重建前端
./scripts/deploy.sh restart     # 快速重启
./scripts/deploy.sh status      # 查看状态
./scripts/deploy.sh logs        # 查看日志

# ——— 远程 SSH 部署（自动检测 NAT 回环并 fallback）———
./scripts/deploy.sh remote-deploy   # 同步代码 + 远程重建 + 健康检查
./scripts/deploy.sh remote-status   # 查看远程容器状态
./scripts/deploy.sh remote-logs     # 查看远程实时日志

# 远程配置可通过环境变量覆盖：
# REMOTE_HOST（默认 deepdistill.kline007.top）
# REMOTE_PORT（默认 2222）
# REMOTE_USER（默认 allenxing00）
# REMOTE_PROJECT_DIR（默认 ~/Documents/soft/DeepDistill）
# REMOTE_SSH_KEY（默认空，使用 SSH 密钥认证）
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

### 经验：deploy.sh 远程 SSH 部署方案 + NAT 回环自动 fallback
- 现象: 需要从外网通过 SSH 远程部署 DeepDistill（域名 deepdistill.kline007.top → 125.69.16.136 → 本机 Mac Studio）
- 根因: 本机是家宽环境，需要路由器端口映射 + SSH 服务开启；从本机通过公网 IP 回连自己时 TP-Link TL-R479G+ 不支持 NAT 回环（Hairpin NAT），导致 `Connection reset by peer`
- 解决:
  1. macOS 开启 SSH：`sudo systemsetup -setremotelogin on`
  2. 路由器端口映射：外网 2222 → 192.168.0.5:22 (TCP)，通过 TP-Link API 添加：
     `curl -s -X POST 'http://192.168.0.1/stok=<token>/ds' -H 'Content-Type: application/json' -d '{"virtual_server":{"table":"virtual_server","para":{"name":"SSH_DeepDistill","interface":"WAN1","ext_port":"2222","int_port":"22","int_ip":"192.168.0.5","protocol":"TCP","state":"1"}},"method":"add"}'`
  3. deploy.sh 新增 `remote-deploy/remote-status/remote-logs` 三个命令
  4. 内置 `_resolve_ssh_target()` 智能检测：先尝试公网 SSH，失败则自动 fallback 到 `127.0.0.1:22`
  5. macOS SSH 会话 PATH 不含 Docker Desktop 路径，`remote_ssh()` 自动注入 `export PATH=/usr/local/bin:/opt/homebrew/bin:$PATH`
  6. 本机 fallback 且目录相同时自动跳过 rsync
  7. 本机 SSH 密钥认证：将 `~/.ssh/id_ed25519.pub` 追加到 `~/.ssh/authorized_keys`
- 验证: `./scripts/deploy.sh remote-status` 自动 fallback 并成功输出容器状态
- 关联: R6(部署规范), scripts/deploy.sh, 路由器 TP-Link TL-R479G+ (192.168.0.1)
- 日期: 2026-02-13

### 经验：TP-Link TL-R479G+ 企业级路由器 API 操作
- 现象: 需要通过脚本/命令行管理路由器端口映射，无需手动登录 Web 界面
- 根因: TP-Link 企业级路由器提供 JSON API（`/stok=<token>/ds`），可直接 curl 操作
- 解决:
  1. 登录获取 stok token（从 Web 登录后 URL 中提取）
  2. 添加虚拟服务器规则：`POST /stok=<token>/ds` + JSON body（method: add）
  3. 查询规则：`POST /stok=<token>/ds` + JSON body（method: get）
  4. 注意：stok 有时效性，过期需重新登录获取
- 验证: API 返回 `{"error_code":0}` 表示成功
- 关联: R6(部署规范), 路由器管理地址 http://192.168.0.1
- 日期: 2026-02-13

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
