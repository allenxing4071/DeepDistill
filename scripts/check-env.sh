#!/usr/bin/env bash
# 本脚本核心用途：检查开发环境是否满足 DeepDistill 运行要求
# 包括 Python 版本、ffmpeg、GPU 可用性、磁盘空间等

set -euo pipefail

echo "=========================================="
echo "  DeepDistill 环境检查"
echo "=========================================="
echo ""

# 颜色
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m'

ok()   { echo -e "  ${GREEN}✅${NC} $1"; }
fail() { echo -e "  ${RED}❌${NC} $1"; }
warn() { echo -e "  ${YELLOW}⚠️${NC}  $1"; }

# 1. Python
echo "🐍 Python"
echo "------------------------------------------"
if command -v python3 &> /dev/null; then
    PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
    PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
    if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 11 ]; then
        ok "Python $PY_VER (>= 3.11)"
    else
        fail "Python $PY_VER (需要 >= 3.11)"
    fi
else
    fail "Python3 未安装"
fi

# pip
if command -v pip3 &> /dev/null || command -v pip &> /dev/null; then
    ok "pip 可用"
else
    fail "pip 未安装"
fi

echo ""

# 2. ffmpeg
echo "🎬 ffmpeg"
echo "------------------------------------------"
if command -v ffmpeg &> /dev/null; then
    FF_VER=$(ffmpeg -version 2>&1 | head -1 | awk '{print $3}')
    ok "ffmpeg $FF_VER"
else
    fail "ffmpeg 未安装 → brew install ffmpeg"
fi

echo ""

# 3. GPU
echo "🖥️  GPU / 加速"
echo "------------------------------------------"

# Mac MPS
if [ "$(uname)" = "Darwin" ]; then
    MPS_AVAIL=$(python3 -c "
try:
    import torch
    print('yes' if torch.backends.mps.is_available() else 'no')
except:
    print('unknown')
" 2>/dev/null || echo "unknown")

    if [ "$MPS_AVAIL" = "yes" ]; then
        ok "Apple MPS 可用"
    elif [ "$MPS_AVAIL" = "no" ]; then
        warn "Apple MPS 不可用（将使用 CPU）"
    else
        warn "无法检测 MPS（PyTorch 未安装或版本过低）"
    fi
fi

# NVIDIA CUDA
if command -v nvidia-smi &> /dev/null; then
    GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)
    GPU_MEM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader | head -1)
    ok "NVIDIA GPU: $GPU_NAME ($GPU_MEM)"
else
    if [ "$(uname)" != "Darwin" ]; then
        warn "NVIDIA GPU 未检测到（将使用 CPU）"
    fi
fi

echo ""

# 4. 磁盘空间
echo "💾 磁盘空间"
echo "------------------------------------------"
AVAIL_GB=$(df -g . 2>/dev/null | tail -1 | awk '{print $4}' || echo "unknown")
if [ "$AVAIL_GB" != "unknown" ] && [ "$AVAIL_GB" -ge 10 ]; then
    ok "可用空间 ${AVAIL_GB}GB (>= 10GB)"
elif [ "$AVAIL_GB" != "unknown" ]; then
    warn "可用空间 ${AVAIL_GB}GB (建议 >= 10GB，模型文件较大)"
else
    warn "无法检测磁盘空间"
fi

echo ""

# 5. 网络（模型下载）
echo "🌐 网络"
echo "------------------------------------------"
if curl -s --max-time 5 https://huggingface.co > /dev/null 2>&1; then
    ok "HuggingFace 可达"
else
    warn "HuggingFace 不可达 → 建议设置 HF_ENDPOINT=https://hf-mirror.com"
fi

echo ""
echo "=========================================="
echo "  环境检查完成"
echo "=========================================="
