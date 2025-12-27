#!/bin/bash

# 配置
APP_PORT=5003
BROWSER_PORT=5005
APP_LOG="app.log"
BROWSER_LOG="browser.log"

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 获取当前目录
WORKDIR=$(cd "$(dirname "$0")" && pwd)
cd "$WORKDIR"

# 检查环境
check_env() {
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}[!] 未检测到 python3，请先安装 Python 3.10+${NC}"
        exit 1
    fi
    
    # 检查是否需要安装依赖
    if [ ! -d "venv" ] && ! python3 -c "import flask, playwright, requests" 2>/dev/null; then
        echo -e "${BLUE}[*] 检测到依赖缺失，正在安装...${NC}"
        python3 -m pip install -r requirements.txt
        python3 -m playwright install chromium
    fi
}

# 停止服务
stop_services() {
    echo -e "${BLUE}[*] 正在停止服务...${NC}"
    
    # 杀掉占用端口的进程
    PIDS=$(lsof -t -i:$APP_PORT -i:$BROWSER_PORT 2>/dev/null)
    if [ -n "$PIDS" ]; then
        echo -e "${YELLOW}[-] Kill process: $PIDS${NC}"
        kill -9 $PIDS 2>/dev/null
    fi
    
    # 双重保险：按名称杀进程
    pkill -f "browser_server.py" 2>/dev/null
    pkill -f "app.py" 2>/dev/null
    
    echo -e "${GREEN}[+] 服务已停止${NC}"
}

# 启动服务
start_services() {
    check_env
    stop_services
    
    echo -e "${BLUE}[*] 正在启动 Browser Service (Port: $BROWSER_PORT)...${NC}"
    export PORT=$BROWSER_PORT
    nohup python3 -u browser_server.py > "$BROWSER_LOG" 2>&1 &
    BPID=$!
    
    # 等待端口就绪
    for i in {1..30}; do
        if lsof -i:$BROWSER_PORT >/dev/null 2>&1; then
            echo -e "${GREEN}[+] Browser Service 启动成功 (PID: $BPID)${NC}"
            break
        fi
        if [ $i -eq 30 ]; then
            echo -e "${RED}[!] Browser Service 启动超时，请查看 $BROWSER_LOG${NC}"
            exit 1
        fi
        sleep 0.5
    done
    
    echo -e "${BLUE}[*] 正在启动 Main API (Port: $APP_PORT)...${NC}"
    export PORT=$APP_PORT
    export BROWSER_SERVICE_URL="http://localhost:$BROWSER_PORT"
    nohup python3 -u app.py > "$APP_LOG" 2>&1 &
    APID=$!
    
    # 等待端口就绪
    for i in {1..30}; do
        if lsof -i:$APP_PORT >/dev/null 2>&1; then
            echo -e "${GREEN}[+] Main API 启动成功 (PID: $APID)${NC}"
            break
        fi
        if [ $i -eq 30 ]; then
            echo -e "${RED}[!] Main API 启动超时，请查看 $APP_LOG${NC}"
            exit 1
        fi
        sleep 0.5
    done

    echo -e "\n${GREEN}=== zAI2API 服务运行中 ===${NC}"
    echo -e "Web 面板:   ${BLUE}http://localhost:$APP_PORT${NC}"
    echo -e "API 地址:   ${BLUE}http://localhost:$APP_PORT/v1/chat/completions${NC}"
    echo -e "默认账号:   admin / admin"
    echo -e "日志命令:   ./start.sh log"
}

# 查看日志
view_logs() {
    tail -f "$APP_LOG" "$BROWSER_LOG"
}

# 查看状态
check_status() {
    echo -e "${BLUE}[*] 服务状态检查:${NC}"
    if lsof -i:$BROWSER_PORT >/dev/null 2>&1; then
        echo -e "Browser Service: ${GREEN}RUNNING (Port $BROWSER_PORT)${NC}"
    else
        echo -e "Browser Service: ${RED}STOPPED${NC}"
    fi
    
    if lsof -i:$APP_PORT >/dev/null 2>&1; then
        echo -e "Main API:        ${GREEN}RUNNING (Port $APP_PORT)${NC}"
    else
        echo -e "Main API:        ${RED}STOPPED${NC}"
    fi
}

# 主逻辑
case "$1" in
    start)
        start_services
        ;;
    stop)
        stop_services
        ;;
    restart)
        stop_services
        start_services
        ;;
    log|logs)
        view_logs
        ;;
    status)
        check_status
        ;;
    *)
        if [ -z "$1" ]; then
            start_services
        else
            echo "用法: $0 {start|stop|restart|log|status}"
            exit 1
        fi
        ;;
esac