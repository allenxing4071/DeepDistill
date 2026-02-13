#!/bin/bash
# 本文件核心用途：DeepDistill 部署脚本（本地 Docker 构建 + 重启 + 健康检查）
# ============================================================================
# DeepDistill 部署脚本 v1.0
# 多源内容深度蒸馏引擎 — 本地 Docker 部署管理
# ============================================================================
#
# 🚀 快捷命令（常用）:
#   ./scripts/deploy.sh deploy     # 一键部署（重建镜像 + 启动 + 健康检查）
#   ./scripts/deploy.sh backend    # 仅重建后端
#   ./scripts/deploy.sh frontend   # 仅重建前端
#   ./scripts/deploy.sh restart    # 快速重启（不重建镜像）
#
# 📊 状态命令:
#   ./scripts/deploy.sh status     # 查看容器状态
#   ./scripts/deploy.sh logs       # 查看实时日志
#   ./scripts/deploy.sh logs-b     # 仅后端日志
#   ./scripts/deploy.sh logs-f     # 仅前端日志
#
# 🛑 停止命令:
#   ./scripts/deploy.sh stop       # 停止所有容器
#
# 🔧 维护命令:
#   ./scripts/deploy.sh health     # 健康检查
#   ./scripts/deploy.sh clean      # 清理废弃镜像
#   ./scripts/deploy.sh nginx      # 重载 Nginx 配置
#   ./scripts/deploy.sh ssl-check  # 检查 SSL 证书到期时间
#
# ============================================================================

set -e

# ============================================================================
# 配置
# ============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$PROJECT_ROOT/docker-compose.yml"
ENV_FILE="$PROJECT_ROOT/.env"

# 服务配置
DOMAIN="deepdistill.kline007.top"
BACKEND_CONTAINER="deepdistill-backend"
FRONTEND_CONTAINER="deepdistill-ui"
BACKEND_PORT=8006
FRONTEND_PORT=3006
HEALTH_URL="http://localhost:${BACKEND_PORT}/health"
HEALTH_URL_HTTPS="https://${DOMAIN}/health"

# Nginx 配置（AITRADER 统一管理）
NGINX_CONTAINER="aitrader-nginx"
NGINX_CONF="$HOME/Documents/soft/AITRADER/nginx/nginx.conf"

# 部署锁（防止并发部署）
DEPLOY_LOCK="/tmp/deepdistill-deploy.lock"
DEPLOY_LOCK_ACQUIRED=0

# ============================================================================
# 颜色输出
# ============================================================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

log()  { echo -e "${BLUE}[$(date '+%H:%M:%S')]${NC} $1"; }
ok()   { echo -e "${GREEN}✅ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
err()  { echo -e "${RED}❌ $1${NC}"; }

# ============================================================================
# 部署锁（防止并发部署冲突）
# ============================================================================
acquire_deploy_lock() {
    if [ -f "$DEPLOY_LOCK" ]; then
        local lock_age=$(( $(date +%s) - $(stat -f %m "$DEPLOY_LOCK" 2>/dev/null || echo 0) ))
        if [ "$lock_age" -lt 600 ]; then
            local lock_info=$(cat "$DEPLOY_LOCK" 2>/dev/null || echo "unknown")
            err "部署锁被占用（${lock_info}，${lock_age}秒前）"
            warn "如需强制解锁：rm -f $DEPLOY_LOCK"
            exit 1
        fi
        warn "发现过期锁文件（${lock_age}秒），自动清理"
        rm -f "$DEPLOY_LOCK"
    fi
    echo "DeepDistill $(date '+%Y-%m-%d %H:%M:%S')" > "$DEPLOY_LOCK"
    DEPLOY_LOCK_ACQUIRED=1
    log "已获取部署锁"
}

release_deploy_lock() {
    if [ "$DEPLOY_LOCK_ACQUIRED" -eq 1 ]; then
        rm -f "$DEPLOY_LOCK"
        DEPLOY_LOCK_ACQUIRED=0
    fi
}

cleanup_on_exit() {
    release_deploy_lock 2>/dev/null || true
}
trap cleanup_on_exit EXIT

# ============================================================================
# Docker 检查
# ============================================================================
check_docker() {
    if ! docker info &>/dev/null; then
        err "Docker 未运行，请先启动 Docker Desktop"
        exit 1
    fi
}

# ============================================================================
# 健康检查
# ============================================================================
health_check() {
    local url="${1:-$HEALTH_URL}"
    local max_retries="${2:-10}"
    local interval="${3:-3}"

    log "健康检查: $url（最多等待 $((max_retries * interval)) 秒）"

    for i in $(seq 1 $max_retries); do
        local status=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "000")
        if [ "$status" = "200" ]; then
            ok "健康检查通过 ✓ (${i}/${max_retries})"
            return 0
        fi
        echo -ne "  等待中... (${i}/${max_retries}) HTTP=${status}\r"
        sleep "$interval"
    done

    err "健康检查失败（${max_retries} 次尝试后仍不可达）"
    warn "查看日志: ./scripts/deploy.sh logs"
    return 1
}

# ============================================================================
# 一键部署（全量重建）
# ============================================================================
do_deploy() {
    check_docker
    acquire_deploy_lock

    echo ""
    echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${CYAN}  DeepDistill 一键部署${NC}"
    echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════${NC}"
    echo ""

    cd "$PROJECT_ROOT"

    # 1. 停止旧容器
    log "停止旧容器..."
    docker compose -f "$COMPOSE_FILE" down 2>/dev/null || true

    # 2. 清理旧镜像（加速重建）
    log "清理旧镜像..."
    docker rmi $(docker images --filter "reference=deepdistill*" -q) 2>/dev/null || true

    # 3. 重建镜像（无缓存）
    log "重建镜像（无缓存）..."
    docker compose -f "$COMPOSE_FILE" build --no-cache

    # 4. 启动服务
    log "启动服务..."
    docker compose -f "$COMPOSE_FILE" up -d

    # 5. 等待启动
    log "等待服务启动..."
    sleep 5

    # 6. 健康检查
    health_check "$HEALTH_URL" 15 3

    # 7. 清理废弃镜像层
    log "清理废弃镜像层..."
    docker image prune -f 2>/dev/null || true

    # 8. 重载 Nginx
    do_nginx_reload

    release_deploy_lock

    echo ""
    ok "部署完成！"
    echo ""
    echo -e "  ${CYAN}Web UI${NC}:  https://${DOMAIN}"
    echo -e "  ${CYAN}API${NC}:     https://${DOMAIN}/api/"
    echo -e "  ${CYAN}API 文档${NC}: https://${DOMAIN}/docs"
    echo -e "  ${CYAN}健康检查${NC}: https://${DOMAIN}/health"
    echo ""
}

# ============================================================================
# 仅重建后端
# ============================================================================
do_backend() {
    check_docker
    acquire_deploy_lock

    echo ""
    log "重建后端..."
    cd "$PROJECT_ROOT"

    docker compose -f "$COMPOSE_FILE" stop backend 2>/dev/null || true
    docker compose -f "$COMPOSE_FILE" build --no-cache backend
    docker compose -f "$COMPOSE_FILE" up -d backend

    log "等待后端启动..."
    sleep 5
    health_check "$HEALTH_URL" 15 3

    release_deploy_lock
    ok "后端重建完成！"
}

# ============================================================================
# 仅重建前端
# ============================================================================
do_frontend() {
    check_docker
    acquire_deploy_lock

    echo ""
    log "重建前端..."
    cd "$PROJECT_ROOT"

    docker compose -f "$COMPOSE_FILE" stop frontend 2>/dev/null || true
    docker compose -f "$COMPOSE_FILE" build --no-cache frontend
    docker compose -f "$COMPOSE_FILE" up -d frontend

    log "等待前端启动..."
    sleep 5

    local status=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${FRONTEND_PORT}" 2>/dev/null || echo "000")
    if [ "$status" = "200" ]; then
        ok "前端重建完成！"
    else
        warn "前端启动中，HTTP=${status}，请稍后检查"
    fi

    release_deploy_lock
}

# ============================================================================
# 快速重启（不重建镜像）
# ============================================================================
do_restart() {
    check_docker

    echo ""
    log "快速重启..."
    cd "$PROJECT_ROOT"

    docker compose -f "$COMPOSE_FILE" restart

    log "等待服务恢复..."
    sleep 5
    health_check "$HEALTH_URL" 10 3

    ok "重启完成！"
}

# ============================================================================
# 停止服务
# ============================================================================
do_stop() {
    check_docker

    echo ""
    log "停止所有容器..."
    cd "$PROJECT_ROOT"
    docker compose -f "$COMPOSE_FILE" down

    ok "已停止"
}

# ============================================================================
# 查看状态
# ============================================================================
do_status() {
    check_docker

    echo ""
    echo -e "${BOLD}${CYAN}═══ DeepDistill 服务状态 ═══${NC}"
    echo ""

    # 容器状态
    docker compose -f "$COMPOSE_FILE" ps 2>/dev/null || warn "容器未运行"

    echo ""

    # 后端健康检查
    local backend_status=$(curl -s -o /dev/null -w "%{http_code}" "$HEALTH_URL" 2>/dev/null || echo "000")
    if [ "$backend_status" = "200" ]; then
        echo -e "  后端 API:  ${GREEN}● 正常${NC} (HTTP ${backend_status})"
    else
        echo -e "  后端 API:  ${RED}● 异常${NC} (HTTP ${backend_status})"
    fi

    # 前端检查
    local frontend_status=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${FRONTEND_PORT}" 2>/dev/null || echo "000")
    if [ "$frontend_status" = "200" ]; then
        echo -e "  前端 UI:   ${GREEN}● 正常${NC} (HTTP ${frontend_status})"
    else
        echo -e "  前端 UI:   ${RED}● 异常${NC} (HTTP ${frontend_status})"
    fi

    # HTTPS 检查
    local https_status=$(curl -s -o /dev/null -w "%{http_code}" "$HEALTH_URL_HTTPS" 2>/dev/null || echo "000")
    if [ "$https_status" = "200" ]; then
        echo -e "  HTTPS:     ${GREEN}● 正常${NC} (HTTP ${https_status})"
    else
        echo -e "  HTTPS:     ${RED}● 异常${NC} (HTTP ${https_status})"
    fi

    echo ""
}

# ============================================================================
# 查看日志
# ============================================================================
do_logs() {
    check_docker
    cd "$PROJECT_ROOT"
    docker compose -f "$COMPOSE_FILE" logs -f --tail=100
}

do_logs_backend() {
    check_docker
    cd "$PROJECT_ROOT"
    docker compose -f "$COMPOSE_FILE" logs -f --tail=100 backend
}

do_logs_frontend() {
    check_docker
    cd "$PROJECT_ROOT"
    docker compose -f "$COMPOSE_FILE" logs -f --tail=100 frontend
}

# ============================================================================
# Nginx 重载
# ============================================================================
do_nginx_reload() {
    if docker ps --format '{{.Names}}' | grep -q "$NGINX_CONTAINER"; then
        log "重载 Nginx..."
        docker exec "$NGINX_CONTAINER" nginx -s reload 2>/dev/null && ok "Nginx 已重载" || warn "Nginx 重载失败"
    else
        warn "Nginx 容器 ($NGINX_CONTAINER) 未运行，跳过重载"
    fi
}

# ============================================================================
# 清理废弃镜像
# ============================================================================
do_clean() {
    check_docker

    echo ""
    log "清理废弃 Docker 镜像..."

    local before=$(docker images | wc -l)
    docker image prune -f 2>/dev/null
    docker builder prune -f 2>/dev/null || true
    local after=$(docker images | wc -l)

    ok "清理完成（镜像数: ${before} → ${after}）"
}

# ============================================================================
# SSL 证书检查
# ============================================================================
do_ssl_check() {
    echo ""
    log "检查 SSL 证书: ${DOMAIN}"

    local cert_info=$(echo | openssl s_client -connect "${DOMAIN}:443" -servername "$DOMAIN" 2>/dev/null | openssl x509 -noout -dates 2>/dev/null)
    if [ -n "$cert_info" ]; then
        echo "$cert_info"
        ok "证书信息获取成功"
    else
        err "无法获取证书信息（HTTPS 可能未配置）"
    fi
}

# ============================================================================
# 交互式菜单
# ============================================================================
show_menu() {
    echo ""
    echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${CYAN}  DeepDistill 部署管理 v1.0${NC}"
    echo -e "${BOLD}${CYAN}  域名: ${DOMAIN}${NC}"
    echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  ${BOLD}部署命令:${NC}"
    echo -e "    ${GREEN}1${NC}) deploy     一键部署（全量重建）"
    echo -e "    ${GREEN}2${NC}) backend    仅重建后端"
    echo -e "    ${GREEN}3${NC}) frontend   仅重建前端"
    echo -e "    ${GREEN}4${NC}) restart    快速重启"
    echo ""
    echo -e "  ${BOLD}状态命令:${NC}"
    echo -e "    ${GREEN}5${NC}) status     查看状态"
    echo -e "    ${GREEN}6${NC}) logs       查看日志"
    echo -e "    ${GREEN}7${NC}) health     健康检查"
    echo ""
    echo -e "  ${BOLD}维护命令:${NC}"
    echo -e "    ${GREEN}8${NC}) stop       停止服务"
    echo -e "    ${GREEN}9${NC}) clean      清理废弃镜像"
    echo -e "    ${GREEN}0${NC}) nginx      重载 Nginx"
    echo ""
    echo -ne "  请选择 [0-9]: "
    read -r choice

    case "$choice" in
        1|deploy)   do_deploy ;;
        2|backend)  do_backend ;;
        3|frontend) do_frontend ;;
        4|restart)  do_restart ;;
        5|status)   do_status ;;
        6|logs)     do_logs ;;
        7|health)   health_check "$HEALTH_URL" ;;
        8|stop)     do_stop ;;
        9|clean)    do_clean ;;
        0|nginx)    do_nginx_reload ;;
        *)          err "无效选择: $choice" ;;
    esac
}

# ============================================================================
# 主入口
# ============================================================================
main() {
    case "${1:-}" in
        deploy|d)       do_deploy ;;
        backend|b)      do_backend ;;
        frontend|f)     do_frontend ;;
        restart|r)      do_restart ;;
        stop)           do_stop ;;
        status|s)       do_status ;;
        logs|l)         do_logs ;;
        logs-b|lb)      do_logs_backend ;;
        logs-f|lf)      do_logs_frontend ;;
        health|h)       health_check "$HEALTH_URL" ;;
        clean|c)        do_clean ;;
        nginx|n)        do_nginx_reload ;;
        ssl-check|ssl)  do_ssl_check ;;
        help|--help|-h)
            echo "用法: $0 <command>"
            echo ""
            echo "部署命令:"
            echo "  deploy, d       一键部署（全量重建）"
            echo "  backend, b      仅重建后端"
            echo "  frontend, f     仅重建前端"
            echo "  restart, r      快速重启（不重建镜像）"
            echo ""
            echo "状态命令:"
            echo "  status, s       查看容器状态"
            echo "  logs, l         查看所有日志"
            echo "  logs-b, lb      仅后端日志"
            echo "  logs-f, lf      仅前端日志"
            echo "  health, h       健康检查"
            echo ""
            echo "维护命令:"
            echo "  stop            停止所有容器"
            echo "  clean, c        清理废弃镜像"
            echo "  nginx, n        重载 Nginx"
            echo "  ssl-check, ssl  检查 SSL 证书"
            echo ""
            echo "无参数则显示交互式菜单"
            ;;
        "")             show_menu ;;
        *)
            err "未知命令: $1"
            echo "使用 $0 --help 查看帮助"
            exit 1
            ;;
    esac
}

main "$@"
