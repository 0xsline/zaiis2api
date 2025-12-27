#!/bin/bash

# 定义颜色
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}[*] 正在检查环境...${NC}"

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[!] 未检测到 python3，请先安装 Python 3.10+${NC}"
    exit 1
fi

# 检查依赖 (简单检查)
if ! python3 -m pip freeze | grep -q "flask"; then
    echo -e "${BLUE}[*] 正在安装依赖...${NC}"
    python3 -m pip install -r requirements.txt playwright
    python3 -m playwright install chromium
fi

echo -e "${BLUE}[*] 正在启动服务...${NC}"

# 1. 启动 Browser Service (强制端口 5005)
export PORT=5005
if pgrep -f "browser_server.py" > /dev/null; then
    echo -e "${RED}[!] Browser Service 已经在运行中，跳过启动${NC}"
else
    echo -e "${GREEN}[+] 启动 Browser Service (Port: 5005)...${NC}"
    nohup python3 browser_server.py > browser.log 2>&1 &
fi

# 等待几秒确保 Browser Service 启动
sleep 2

# 2. 启动 Main App (连接到 5005)
export BROWSER_SERVICE_URL=http://localhost:5005
if pgrep -f "app.py" > /dev/null; then
    echo -e "${RED}[!] Main App 已经在运行中，跳过启动${NC}"
else
    echo -e "${GREEN}[+] 启动 Main App (Port: 5003)...${NC}"
    nohup python3 app.py > app.log 2>&1 &
fi

echo -e "${BLUE}[*] 等待服务就绪...${NC}"
sleep 3

# 检查进程
if pgrep -f "browser_server.py" > /dev/null && pgrep -f "app.py" > /dev/null; then
    echo -e "\n${GREEN}=== 服务启动成功 ===${NC}"
    echo -e "Web 面板: ${BLUE}http://localhost:5003${NC}"
    echo -e "默认账号: admin / admin"
    echo -e "API 地址: http://localhost:5003/v1/chat/completions"
    echo -e "日志查看: tail -f app.log browser.log"
else
    echo -e "\n${RED}[!] 服务启动可能失败，请检查 app.log 或 browser.log${NC}"
fi
