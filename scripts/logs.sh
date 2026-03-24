#!/bin/bash
# Claude-IM 实时日志
# 用法: ./scripts/logs.sh [api|feishu|all]

LOG_DIR="$HOME/claude-im/logs"
MODE="${1:-all}"

mkdir -p "$LOG_DIR"

case "$MODE" in
    api)
        echo "📝 clawrelay-api 日志 (Ctrl+C 退出)"
        tail -f "$LOG_DIR/clawrelay-api.log"
        ;;
    feishu)
        echo "📝 feishu-server 日志 (Ctrl+C 退出)"
        tail -f "$LOG_DIR/feishu-server.log"
        ;;
    all|*)
        echo "📝 clawrelay-api + feishu-server 日志 (Ctrl+C 退出)"
        tail -f "$LOG_DIR/clawrelay-api.log" "$LOG_DIR/feishu-server.log"
        ;;
esac
