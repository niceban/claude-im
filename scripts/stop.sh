#!/bin/bash
# Claude-IM 停止脚本

echo "停止 Claude-IM 标准路径中的本地 helper 进程..."

if pkill -f "python3 main.py" 2>/dev/null; then
    echo "feishu-server 已停止"
else
    echo "feishu-server 未运行"
fi

echo "report 栈未在此脚本中统一停止，请在 /Users/c/clawrelay-report 中单独管理。"
