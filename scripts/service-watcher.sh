#!/bin/bash
# 宿主机服务控制 watcher
# 监听 data/.service-ctl/ 目录下的信号文件，执行对应的启停操作。
# 用法：在宿主机上运行 ./scripts/service-watcher.sh（后台常驻）
# 注意：DeepDistill 跑在 Docker 时，必须在本机单独运行此脚本，否则「启动服务」不会生效。

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CTL_DIR="$PROJECT_DIR/data/.service-ctl"
# SD 目录：优先用环境变量 SD_WEBUI_DIR，否则默认与 DeepDistill 同级的 stable-diffusion-webui-forge
SD_DIR="${SD_WEBUI_DIR:-$PROJECT_DIR/../stable-diffusion-webui-forge}"
LOG_FILE="$PROJECT_DIR/data/service-watcher.log"

mkdir -p "$CTL_DIR"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# ── Ollama 控制（macOS App 模式 + CLI 模式兼容） ──
_ollama_is_running() {
  # 检查 Ollama API 是否可达（最可靠的方式）
  curl -s --max-time 2 http://localhost:11434/api/tags > /dev/null 2>&1
}

start_ollama() {
  if _ollama_is_running; then
    log "Ollama 已在运行"
    echo '{"ok":true,"msg":"already running"}' > "$CTL_DIR/ollama.result"
    return
  fi
  log "启动 Ollama..."
  # 优先尝试 macOS App 方式
  if [ -d "/Applications/Ollama.app" ]; then
    open -a Ollama
  else
    nohup ollama serve > /dev/null 2>&1 &
  fi
  # 等待启动
  for i in $(seq 1 15); do
    sleep 2
    if _ollama_is_running; then
      log "Ollama 启动成功（耗时 $((i*2)) 秒）"
      echo '{"ok":true,"msg":"started"}' > "$CTL_DIR/ollama.result"
      return
    fi
  done
  log "Ollama 启动超时"
  echo '{"ok":false,"msg":"start timeout"}' > "$CTL_DIR/ollama.result"
}

stop_ollama() {
  if ! _ollama_is_running; then
    log "Ollama 未在运行"
    echo '{"ok":true,"msg":"already stopped"}' > "$CTL_DIR/ollama.result"
    return
  fi
  log "停止 Ollama..."
  # macOS App 方式：killall 直接终止（不会被 launchd 重启）
  killall "Ollama" 2>/dev/null || true
  sleep 3
  if ! _ollama_is_running; then
    log "Ollama 已停止"
    echo '{"ok":true,"msg":"stopped"}' > "$CTL_DIR/ollama.result"
  else
    # 二次尝试
    killall -9 "Ollama" 2>/dev/null || true
    pkill -9 -f "ollama" 2>/dev/null || true
    sleep 2
    if ! _ollama_is_running; then
      log "Ollama 已强制停止"
      echo '{"ok":true,"msg":"force stopped"}' > "$CTL_DIR/ollama.result"
    else
      log "Ollama 停止失败"
      echo '{"ok":false,"msg":"stop failed"}' > "$CTL_DIR/ollama.result"
    fi
  fi
}

# （已移除 Stable Diffusion 控制 — 不再集成 SD WebUI）

# ── 主循环：监听信号文件 ──
log "Service Watcher 启动，监听目录: $CTL_DIR"

while true; do
  # Ollama
  if [ -f "$CTL_DIR/ollama.start" ]; then
    rm -f "$CTL_DIR/ollama.start" "$CTL_DIR/ollama.result"
    start_ollama &
  fi
  if [ -f "$CTL_DIR/ollama.stop" ]; then
    rm -f "$CTL_DIR/ollama.stop" "$CTL_DIR/ollama.result"
    stop_ollama &
  fi

  sleep 1
done
