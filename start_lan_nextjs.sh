#!/bin/bash
# Story2 局域网访问启动脚本（Next.js版本）
# 确保前后端服务都能被局域网设备（iPad/手机）访问

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_PORT=8000
FRONTEND_PORT=3000

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   Story2 局域网访问启动${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 获取本机局域网IP
LAN_IP=$(ipconfig getifaddr en0 2>/dev/null || ifconfig | grep 'inet ' | grep -v '127.0.0.1' | awk '{print $2}' | head -1)

if [ -z "$LAN_IP" ]; then
    echo -e "${RED}✗ 无法获取局域网IP地址${NC}"
    echo -e "${YELLOW}  请确保已连接到WiFi网络${NC}"
    exit 1
fi

echo -e "${GREEN}✓ 检测到局域网IP: $LAN_IP${NC}"
echo ""

# 停止已有服务
echo -e "${YELLOW}正在停止现有服务...${NC}"
lsof -ti:$BACKEND_PORT | xargs kill -9 2>/dev/null
lsof -ti:$FRONTEND_PORT | xargs kill -9 2>/dev/null
sleep 1

# 启动后端（绑定到0.0.0.0）
echo -e "${YELLOW}启动后端服务 (0.0.0.0:$BACKEND_PORT)...${NC}"
cd "$PROJECT_DIR"
source venv/bin/activate
export API_HOST="0.0.0.0"
export API_PORT="$BACKEND_PORT"
# ★ 设置 CORS 允许局域网访问
export CORS_ORIGINS="http://$LAN_IP:3000,http://$LAN_IP:8000,http://$LAN_IP:8501"
python run_api.py > /tmp/story2_backend.log 2>&1 &
BACKEND_PID=$!
sleep 3

if lsof -ti:$BACKEND_PORT > /dev/null 2>&1; then
    echo -e "${GREEN}✓ 后端启动成功 (PID: $BACKEND_PID)${NC}"
else
    echo -e "${RED}✗ 后端启动失败，查看日志: cat /tmp/story2_backend.log${NC}"
    exit 1
fi

# 启动前端（绑定到0.0.0.0）
echo -e "${YELLOW}启动前端服务 (0.0.0.0:$FRONTEND_PORT)...${NC}"
cd "$PROJECT_DIR/frontend"
npm run dev -- -H 0.0.0.0 -p $FRONTEND_PORT > /tmp/story2_frontend.log 2>&1 &
FRONTEND_PID=$!
sleep 5

if lsof -ti:$FRONTEND_PORT > /dev/null 2>&1; then
    echo -e "${GREEN}✓ 前端启动成功 (PID: $FRONTEND_PID)${NC}"
else
    echo -e "${RED}✗ 前端启动失败，查看日志: cat /tmp/story2_frontend.log${NC}"
    kill -9 $BACKEND_PID 2>/dev/null
    exit 1
fi

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}✓ 服务启动成功！${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${YELLOW}访问地址：${NC}"
echo -e "  ${GREEN}本机：${NC}     http://localhost:$FRONTEND_PORT"
echo -e "  ${GREEN}局域网：${NC}   http://$LAN_IP:$FRONTEND_PORT"
echo ""
echo -e "${YELLOW}iPad/手机访问步骤：${NC}"
echo -e "  1. 确保设备连接到同一WiFi网络"
echo -e "  2. 在浏览器中打开: ${BLUE}http://$LAN_IP:$FRONTEND_PORT${NC}"
echo -e "  3. 如果无法访问，请检查防火墙设置"
echo ""
echo -e "${YELLOW}调试信息：${NC}"
echo -e "  后端日志: tail -f /tmp/story2_backend.log"
echo -e "  前端日志: tail -f /tmp/story2_frontend.log"
echo ""
echo -e "${YELLOW}停止服务：${NC}"
echo -e "  按 ${RED}Ctrl+C${NC} 或运行: ./start.sh stop"
echo ""

# 保持脚本运行
wait
