#!/bin/bash
# Claude-IM 实时日志
# 用法: ./scripts/logs.sh [feishu|report-backend|report-frontend|all]

LOG_DIR="${LOG_DIR:-$HOME/claude-im/logs}"
MODE="${1:-all}"

mkdir -p "$LOG_DIR"

tail_if_exists() {
    local file="$1"
    if [ -f "$file" ]; then
        tail -f "$file"
    else
        echo "日志文件不存在: $file"
        exit 1
    fi
}

case "$MODE" in
    feishu)
        echo "feishu-server 日志 (Ctrl+C 退出)"
        tail_if_exists "$LOG_DIR/feishu-server.log"
        ;;
    report-backend)
        echo "report-backend 日志 (Ctrl+C 退出)"
        tail_if_exists "$LOG_DIR/report-backend.log"
        ;;
    report-frontend)
        echo "report-frontend 日志 (Ctrl+C 退出)"
        tail_if_exists "$LOG_DIR/report-frontend.log"
        ;;
    all|*)
        echo "本地可见日志 (Ctrl+C 退出)"
        files=()
        [ -f "$LOG_DIR/feishu-server.log" ] && files+=("$LOG_DIR/feishu-server.log")
        [ -f "$LOG_DIR/report-backend.log" ] && files+=("$LOG_DIR/report-backend.log")
        [ -f "$LOG_DIR/report-frontend.log" ] && files+=("$LOG_DIR/report-frontend.log")

        if [ "${#files[@]}" -eq 0 ]; then
            echo "没有可用日志文件"
            exit 1
        fi

        tail -f "${files[@]}"
        ;;
esac
