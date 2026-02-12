#!/bin/bash
# 宿主机服务控制 watcher
# 监听 data/.service-ctl/ 目录下的信号文件，执行对应的启停操作。
# 用法：在宿主机上运行 ./scripts/service-watcher.sh（后台常驻）

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CTL_DIR="$PROJECT_DIR/data/.service-ctl"
SD_DIR="$PROJECT_DIR/../stable-diffusion-webui-forge"
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

# ── Stable Diffusion 控制 ──
start_sd() {
  if _sd_is_running; then
    log "SD WebUI 已在运行"
    echo '{"ok":true,"msg":"already running"}' > "$CTL_DIR/sd.result"
    return
  fi
  if [ ! -d "$SD_DIR" ]; then
    log "SD WebUI 目录不存在: $SD_DIR"
    echo '{"ok":false,"msg":"SD WebUI not installed"}' > "$CTL_DIR/sd.result"
    return
  fi
  log "启动 SD WebUI Forge..."
  cd "$SD_DIR" && nohup bash webui.sh > "$PROJECT_DIR/data/sd-webui.log" 2>&1 &
  # 等待启动（最多 120 秒）
  for i in $(seq 1 40); do
    sleep 3
    if curl -s http://localhost:7860/sdapi/v1/sd-models > /dev/null 2>&1; then
      log "SD WebUI 启动成功（耗时 $((i*3)) 秒）"
      echo '{"ok":true,"msg":"started"}' > "$CTL_DIR/sd.result"
      return
    fi
  done
  log "SD WebUI 启动超时"
  echo '{"ok":false,"msg":"start timeout"}' > "$CTL_DIR/sd.result"
}

_sd_is_running() {
  curl -s --max-time 2 http://localhost:7860/sdapi/v1/sd-models > /dev/null 2>&1
}

stop_sd() {
  if ! _sd_is_running; then
    log "SD WebUI 未在运行"
    echo '{"ok":true,"msg":"already stopped"}' > "$CTL_DIR/sd.result"
    return
  fi
  log "停止 SD WebUI..."
  # 找到监听 7860 端口的进程并 kill
  SD_PID=$(lsof -ti :7860 2>/dev/null | head -1)
  if [ -n "$SD_PID" ]; then
    kill "$SD_PID" 2>/dev/null || true
    sleep 3
    # 如果还在，强制 kill
    if _sd_is_running; then
      kill -9 "$SD_PID" 2>/dev/null || true
      # 也 kill 相关的 python 子进程
      pkill -9 -P "$SD_PID" 2>/dev/null || true
      sleep 2
    fi
  fi
  # 兜底：kill 所有 SD 相关进程
  if _sd_is_running; then
    lsof -ti :7860 2>/dev/null | xargs kill -9 2>/dev/null || true
    sleep 2
  fi
  if ! _sd_is_running; then
    log "SD WebUI 已停止"
    echo '{"ok":true,"msg":"stopped"}' > "$CTL_DIR/sd.result"
  else
    log "SD WebUI 停止失败"
    echo '{"ok":false,"msg":"stop failed"}' > "$CTL_DIR/sd.result"
  fi
}

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

  # SD WebUI
  if [ -f "$CTL_DIR/sd.start" ]; then
    rm -f "$CTL_DIR/sd.start" "$CTL_DIR/sd.result"
    start_sd &
  fi
  if [ -f "$CTL_DIR/sd.stop" ]; then
    rm -f "$CTL_DIR/sd.stop" "$CTL_DIR/sd.result"
    stop_sd &
  fi

  sleep 1
done
