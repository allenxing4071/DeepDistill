#!/usr/bin/env bash
# 本脚本核心用途：开发自检脚本，检查代码质量、类型、测试等
# 对应 Rules R1（功能验证）— Medium/Large 变更时必须执行

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "=========================================="
echo "  DeepDistill 开发自检"
echo "=========================================="
echo ""

PASS=0
FAIL=0
SKIP=0

check() {
    local name="$1"
    shift
    echo -n "  [$name] ... "
    if "$@" > /dev/null 2>&1; then
        echo "✅ PASS"
        ((PASS++))
    else
        echo "❌ FAIL"
        ((FAIL++))
    fi
}

skip() {
    local name="$1"
    local reason="$2"
    echo "  [$name] ... ⏭️  SKIP ($reason)"
    ((SKIP++))
}

# 1. Python 语法检查
echo "📋 代码质量检查"
echo "------------------------------------------"

if command -v python3 &> /dev/null; then
    check "Python 可用" python3 --version
else
    skip "Python 可用" "python3 未安装"
fi

if [ -d "deepdistill" ]; then
    # ruff lint（如果安装了）
    if command -v ruff &> /dev/null; then
        check "Ruff lint" ruff check deepdistill/
    else
        skip "Ruff lint" "ruff 未安装 (pip install ruff)"
    fi

    # mypy 类型检查（如果安装了）
    if command -v mypy &> /dev/null; then
        check "Mypy 类型检查" mypy deepdistill/ --ignore-missing-imports
    else
        skip "Mypy 类型检查" "mypy 未安装 (pip install mypy)"
    fi
else
    skip "代码检查" "deepdistill/ 目录不存在（尚未创建代码）"
fi

echo ""

# 2. 测试
echo "🧪 测试"
echo "------------------------------------------"

if [ -d "tests" ] && [ "$(find tests -name 'test_*.py' | head -1)" ]; then
    if command -v pytest &> /dev/null; then
        check "Pytest" pytest tests/ -q --no-header
    else
        skip "Pytest" "pytest 未安装 (pip install pytest)"
    fi
else
    skip "Pytest" "tests/ 目录为空或不存在"
fi

echo ""

# 3. 配置检查
echo "⚙️  配置检查"
echo "------------------------------------------"

check ".gitignore 存在" test -f .gitignore
check ".env.example 或 .env 存在" test -f .env.example -o -f .env

if [ -f ".env" ]; then
    # 检查 .env 没有被 git 追踪
    if git ls-files --error-unmatch .env > /dev/null 2>&1; then
        echo "  [.env 未入库] ... ❌ FAIL (.env 被 git 追踪！)"
        ((FAIL++))
    else
        check ".env 未入库" true
    fi
else
    skip ".env 未入库" ".env 不存在"
fi

echo ""

# 4. 依赖检查
echo "📦 依赖检查"
echo "------------------------------------------"

check "pyproject.toml 存在" test -f pyproject.toml

if command -v ffmpeg &> /dev/null; then
    check "ffmpeg 可用" ffmpeg -version
else
    skip "ffmpeg 可用" "ffmpeg 未安装 (brew install ffmpeg)"
fi

echo ""

# 汇总
echo "=========================================="
echo "  结果：✅ $PASS 通过 | ❌ $FAIL 失败 | ⏭️  $SKIP 跳过"
echo "=========================================="

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
