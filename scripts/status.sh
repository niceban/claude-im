#!/bin/bash
# Claude-IM 状态检查

LOG_DIR="${LOG_DIR:-$HOME/claude-im/logs}"

echo "Claude-IM 标准状态"
echo "==================="

if ps aux | grep -v grep | grep -q "python3 main.py"; then
    echo "feishu-server: 运行中"
else
    echo "feishu-server: 未运行"
fi

if curl -s --max-time 2 http://localhost:8000/api/v1/utils/health-check/ >/dev/null 2>&1; then
    echo "report-backend-api: 运行中 (:8000)"
else
    echo "report-backend-api: 未确认"
fi

if curl -s --max-time 2 http://localhost:5173/ >/dev/null 2>&1; then
    echo "admin-ui: 运行中 (:5173, 唯一后台入口)"
else
    echo "admin-ui: 未确认"
fi

echo ""
echo "最近 feishu-server 日志:"
tail -5 "$LOG_DIR/feishu-server.log" 2>/dev/null || echo "无日志文件"
