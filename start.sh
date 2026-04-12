#!/bin/bash
# Story2 项目启动脚本
# 用法: ./start.sh [命令]
#   无参数/start/restart - 启动/重启所有服务
#   stop                  - 停止所有服务
#   status                - 查看服务状态
#   logs                  - 查看日志（最后20行）
#   tail                  - 实时查看日志（Ctrl+C退出）
#   tail backend          - 仅实时查看后端日志
#   tail frontend         - 仅实时查看前端日志

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_PORT=8000
FRONTEND_PORT=3000
NETEASE_MUSIC_PORT=3001
BACKEND_LOG="/tmp/backend.log"
FRONTEND_LOG="/tmp/frontend.log"
NETEASE_MUSIC_LOG="/tmp/netease_music.log"
# 网易云音乐 API 路径（项目内置）
NETEASE_MUSIC_DIR="${NETEASE_MUSIC_DIR:-$PROJECT_DIR/netease-music-api}"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 停止服务
stop_services() {
    echo -e "${YELLOW}正在停止服务...${NC}"
    lsof -ti:$BACKEND_PORT | xargs kill -9 2>/dev/null
    lsof -ti:$FRONTEND_PORT | xargs kill -9 2>/dev/null
    lsof -ti:$NETEASE_MUSIC_PORT | xargs kill -9 2>/dev/null
    echo -e "${GREEN}服务已停止${NC}"
}

# 启动后端
start_backend() {
    echo -e "${YELLOW}启动后端服务 (端口 $BACKEND_PORT)...${NC}"
    cd "$PROJECT_DIR"
    source venv/bin/activate
    python3 run_api.py > $BACKEND_LOG 2>&1 &
    sleep 2
    if lsof -ti:$BACKEND_PORT > /dev/null 2>&1; then
        echo -e "${GREEN}✓ 后端启动成功${NC}"
    else
        echo -e "${RED}✗ 后端启动失败，查看日志: cat $BACKEND_LOG${NC}"
    fi
}

# 启动网易云音乐 API
start_netease_music() {
    if [ ! -d "$NETEASE_MUSIC_DIR" ]; then
        echo -e "${YELLOW}⚠ 网易云音乐 API 目录不存在: $NETEASE_MUSIC_DIR${NC}"
        echo -e "${YELLOW}  音乐功能将不可用。如需使用，请克隆: https://github.com/Binaryify/NeteaseCloudMusicApi${NC}"
        return
    fi
    
    echo -e "${YELLOW}启动网易云音乐 API (端口 $NETEASE_MUSIC_PORT)...${NC}"
    cd "$NETEASE_MUSIC_DIR"
    PORT=$NETEASE_MUSIC_PORT npm start > $NETEASE_MUSIC_LOG 2>&1 &
    sleep 3
    if lsof -ti:$NETEASE_MUSIC_PORT > /dev/null 2>&1; then
        echo -e "${GREEN}✓ 网易云音乐 API 启动成功${NC}"
    else
        echo -e "${RED}✗ 网易云音乐 API 启动失败，查看日志: cat $NETEASE_MUSIC_LOG${NC}"
    fi
}

# 启动前端
start_frontend() {
    echo -e "${YELLOW}启动前端服务 (端口 $FRONTEND_PORT)...${NC}"
    cd "$PROJECT_DIR/frontend"
    npm run dev > $FRONTEND_LOG 2>&1 &
    sleep 3
    if lsof -ti:$FRONTEND_PORT > /dev/null 2>&1; then
        echo -e "${GREEN}✓ 前端启动成功${NC}"
    else
        echo -e "${RED}✗ 前端启动失败，查看日志: cat $FRONTEND_LOG${NC}"
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
    if lsof -ti:$NETEASE_MUSIC_PORT > /dev/null 2>&1; then
        echo -e "  网易云音乐 (端口 $NETEASE_MUSIC_PORT): ${GREEN}运行中${NC}"
    else
        echo -e "  网易云音乐 (端口 $NETEASE_MUSIC_PORT): ${RED}未运行${NC}"
    fi
}

# 查看日志（静态）
show_logs() {
    echo -e "${YELLOW}=== 后端日志 (最后20行) ===${NC}"
    tail -20 $BACKEND_LOG 2>/dev/null || echo "无日志"
    echo ""
    echo -e "${YELLOW}=== 前端日志 (最后20行) ===${NC}"
    tail -20 $FRONTEND_LOG 2>/dev/null || echo "无日志"
}

# 实时查看日志
tail_logs() {
    local target="$1"
    
    case "$target" in
        backend)
            echo -e "${CYAN}实时查看后端日志 (Ctrl+C 退出)...${NC}"
            echo -e "${BLUE}========================================${NC}"
            tail -f $BACKEND_LOG 2>/dev/null || echo -e "${RED}日志文件不存在${NC}"
            ;;
        frontend)
            echo -e "${CYAN}实时查看前端日志 (Ctrl+C 退出)...${NC}"
            echo -e "${BLUE}========================================${NC}"
            tail -f $FRONTEND_LOG 2>/dev/null || echo -e "${RED}日志文件不存在${NC}"
            ;;
        *)
            # 同时查看两个日志（使用多窗口）
            echo -e "${CYAN}实时查看所有日志 (Ctrl+C 退出)...${NC}"
            echo -e "${BLUE}========================================${NC}"
            echo -e "${YELLOW}[后端]${NC} 黄色标签  |  ${GREEN}[前端]${NC} 绿色标签"
            echo -e "${BLUE}========================================${NC}"
            
            # 使用 sed 给日志加前缀标签
            tail -f $BACKEND_LOG 2>/dev/null | sed "s/^/${YELLOW}[后端]${NC} /" &
            BACKEND_PID=$!
            tail -f $FRONTEND_LOG 2>/dev/null | sed "s/^/${GREEN}[前端]${NC} /" &
            FRONTEND_PID=$!
            
            # 捕获 Ctrl+C 信号，清理后台进程
            trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo -e '\n${GREEN}已退出日志查看${NC}'; exit 0" INT
            
            # 等待
            wait
            ;;
    esac
}

# 启动所有服务
start_all() {
    stop_services
    sleep 1
    start_netease_music
    start_backend
    start_frontend
    echo ""
    show_status
    echo ""
    echo -e "${GREEN}访问地址:${NC}"
    echo "  本机: http://localhost:$FRONTEND_PORT"
    echo "  局域网: http://$(ipconfig getifaddr en0 2>/dev/null || echo "IP"):$FRONTEND_PORT"
    echo ""
    echo -e "${CYAN}实时查看日志: ./start.sh tail${NC}"
}

# 主逻辑
case "$1" in
    stop)
        stop_services
        ;;
    start)
        start_all
        ;;
    restart)
        start_all
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    tail)
        tail_logs "$2"
        ;;
    *)
        # 默认启动（同 start）
        start_all
        ;;
esac
