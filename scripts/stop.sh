#!/bin/bash
# Claude-IM 停止脚本
# 用法: ./scripts/stop.sh

echo "🛑 停止 Claude-IM 服务..."

# 停止 clawrelay-api
if pkill -f "clawrelay-api" 2>/dev/null; then
    echo "✅ clawrelay-api 已停止"
else
    echo "ℹ️  clawrelay-api 未运行"
fi

# 停止 feishu-server
if pkill -f "python3 main.py" 2>/dev/null; then
    echo "✅ feishu-server 已停止"
else
    echo "ℹ️  feishu-server 未运行"
fi

sleep 1

# 验证
if lsof -i :50009 >/dev/null 2>&1; then
    echo "⚠️  端口 50009 仍被占用:"
    lsof -i :50009
else
    echo "✅ 端口 50009 已释放"
fi
