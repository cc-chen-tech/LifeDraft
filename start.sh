#!/bin/bash
# Story2 项目启动脚本
# 用法: ./start.sh [命令]
#   无参数 - 启动前后端服务
#   stop   - 停止所有服务
#   restart - 重启所有服务
#   status - 查看服务状态
#   logs   - 查看日志

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_PORT=8000
FRONTEND_PORT=3000

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 停止服务
stop_services() {
    echo -e "${YELLOW}正在停止服务...${NC}"
    lsof -ti:$BACKEND_PORT | xargs kill -9 2>/dev/null
    lsof -ti:$FRONTEND_PORT | xargs kill -9 2>/dev/null
    echo -e "${GREEN}服务已停止${NC}"
}

# 启动后端
start_backend() {
    echo -e "${YELLOW}启动后端服务 (端口 $BACKEND_PORT)...${NC}"
    cd "$PROJECT_DIR"
    source venv/bin/activate
    python run_api.py > /tmp/backend.log 2>&1 &
    sleep 2
    if lsof -ti:$BACKEND_PORT > /dev/null 2>&1; then
        echo -e "${GREEN}✓ 后端启动成功${NC}"
    else
        echo -e "${RED}✗ 后端启动失败，查看日志: cat /tmp/backend.log${NC}"
    fi
}

# 启动前端
start_frontend() {
    echo -e "${YELLOW}启动前端服务 (端口 $FRONTEND_PORT)...${NC}"
    cd "$PROJECT_DIR/frontend"
    npm run dev > /tmp/frontend.log 2>&1 &
    sleep 3
    if lsof -ti:$FRONTEND_PORT > /dev/null 2>&1; then
        echo -e "${GREEN}✓ 前端启动成功${NC}"
    else
        echo -e "${RED}✗ 前端启动失败，查看日志: cat /tmp/frontend.log${NC}"
    fi
}

# 查看状态
show_status() {
    echo -e "${YELLOW}服务状态:${NC}"
    if lsof -ti:$BACKEND_PORT > /dev/null 2>&1; then
        echo -e "  后端 (端口 $BACKEND_PORT): ${GREEN}运行中${NC}"
    else
        echo -e "  后端 (端口 $BACKEND_PORT): ${RED}未运行${NC}"
    fi
    if lsof -ti:$FRONTEND_PORT > /dev/null 2>&1; then
        echo -e "  前端 (端口 $FRONTEND_PORT): ${GREEN}运行中${NC}"
    else
        echo -e "  前端 (端口 $FRONTEND_PORT): ${RED}未运行${NC}"
    fi
}

# 查看日志
show_logs() {
    echo -e "${YELLOW}=== 后端日志 (最后20行) ===${NC}"
    tail -20 /tmp/backend.log 2>/dev/null || echo "无日志"
    echo ""
    echo -e "${YELLOW}=== 前端日志 (最后20行) ===${NC}"
    tail -20 /tmp/frontend.log 2>/dev/null || echo "无日志"
}

# 主逻辑
case "$1" in
    stop)
        stop_services
        ;;
    restart)
        stop_services
        sleep 1
        start_backend
        start_frontend
        show_status
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    *)
        # 默认启动
        stop_services
        sleep 1
        start_backend
        start_frontend
        echo ""
        show_status
        echo ""
        echo -e "${GREEN}访问地址:${NC}"
        echo "  本机: http://localhost:$FRONTEND_PORT"
        echo "  局域网: http://$(ipconfig getifaddr en0 2>/dev/null || echo "IP"):$FRONTEND_PORT"
        ;;
esac
