#!/bin/bash
# Claude-IM 启动脚本
# 用法: ./scripts/start.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAWRELAY_API_DIR="$HOME/clawrelay-api"
FEISHU_SERVER_DIR="$HOME/clawrelay-feishu-server"
LOG_DIR="$HOME/claude-im/logs"

mkdir -p "$LOG_DIR"

echo "🚀 启动 Claude-IM 服务..."

# 检查 clawrelay-api
if lsof -i :50009 >/dev/null 2>&1; then
    echo "⚠️  clawrelay-api 已在运行 (端口 50009)"
else
    echo "📦 启动 clawrelay-api..."
    cd "$CLAWRELAY_API_DIR"
    nohup ./clawrelay-api > "$LOG_DIR/clawrelay-api.log" 2>&1 &
    sleep 2

    if curl -s http://localhost:50009/health | grep -q "healthy"; then
        echo "✅ clawrelay-api 启动成功 (PID: $!)"
    else
        echo "❌ clawrelay-api 启动失败，查看日志: $LOG_DIR/clawrelay-api.log"
        exit 1
    fi
fi

# 检查 feishu-server
if ps aux | grep -v grep | grep "python3 main.py" | grep -q "$FEISHU_SERVER_DIR"; then
    echo "⚠️  feishu-server 已在运行"
else
    echo "📦 启动 feishu-server..."
    cd "$FEISHU_SERVER_DIR"
    nohup python3 main.py > "$LOG_DIR/feishu-server.log" 2>&1 &
    sleep 3

    if tail -5 "$LOG_DIR/feishu-server.log" | grep -q "connected\|WebSocket"; then
        echo "✅ feishu-server 启动成功 (PID: $!)"
    else
        echo "⚠️  feishu-server 状态未知，查看日志: $LOG_DIR/feishu-server.log"
    fi
fi

echo ""
echo "📊 服务状态:"
curl -s http://localhost:50009/health
echo ""
echo "📝 日志位置: $LOG_DIR/"
echo "   clawrelay-api: $LOG_DIR/clawrelay-api.log"
echo "   feishu-server: $LOG_DIR/feishu-server.log"
