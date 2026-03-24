#!/bin/bash
# Claude-IM 状态检查
# 用法: ./scripts/status.sh

LOG_DIR="$HOME/claude-im/logs"

echo "📊 Claude-IM 服务状态"
echo "======================"

# clawrelay-api 状态
if curl -s --max-time 2 http://localhost:50009/health > /dev/null 2>&1; then
    echo "✅ clawrelay-api: 运行中"
    curl -s http://localhost:50009/health | python3 -m json.tool 2>/dev/null || curl -s http://localhost:50009/health
else
    echo "❌ clawrelay-api: 未运行"
fi

# feishu-server 状态
if ps aux | grep -v grep | grep -q "python3 main.py"; then
    echo "✅ feishu-server: 运行中"
    PID=$(ps aux | grep -v grep | grep "python3 main.py" | awk '{print $1}')
    echo "   PID: $PID"
else
    echo "❌ feishu-server: 未运行"
fi

# 端口占用
echo ""
echo "🔌 端口占用 (:50009):"
lsof -i :50009 2>/dev/null | tail -n +2 || echo "   无"

# 最近的日志
echo ""
echo "📝 最近 feishu-server 日志 (最后 5 行):"
tail -5 "$LOG_DIR/feishu-server.log" 2>/dev/null || echo "   无日志文件"
