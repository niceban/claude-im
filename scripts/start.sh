#!/bin/bash
# Claude-IM 启动脚本
# 标准架构：feishu-server 直连 claude-node；report 为独立全栈服务

set -e

FEISHU_SERVER_DIR="${FEISHU_SERVER_DIR:-$HOME/clawrelay-feishu-server}"
LOG_DIR="${LOG_DIR:-$HOME/claude-im/logs}"

mkdir -p "$LOG_DIR"

echo "启动 Claude-IM（标准模式）..."
echo "  - IM 路径: clawrelay-feishu-server -> claude-node"
echo "  - 唯一管理后台入口: http://localhost:5173"
echo "  - Report 路径: clawrelay-report (独立管理)"

if ps aux | grep -v grep | grep "python3 main.py" | grep -q "$FEISHU_SERVER_DIR"; then
    echo "feishu-server 已在运行"
else
    echo "启动 feishu-server..."
    cd "$FEISHU_SERVER_DIR"
    nohup python3 main.py > "$LOG_DIR/feishu-server.log" 2>&1 &
    sleep 3

    if tail -5 "$LOG_DIR/feishu-server.log" | grep -qi "connected\\|websocket"; then
        echo "feishu-server 启动成功"
    else
        echo "feishu-server 状态待确认，查看日志: $LOG_DIR/feishu-server.log"
    fi
fi

echo ""
echo "report 栈不由本脚本直接启动，请在 /Users/c/clawrelay-report 中单独管理。"
echo "对人使用的后台入口固定为: http://localhost:5173"
