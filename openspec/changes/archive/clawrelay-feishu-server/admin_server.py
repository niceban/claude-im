#!/usr/bin/env python
# coding=utf-8
"""
Admin API Server（独立进程，端口 8080）

启动方式：
    python admin_server.py

与主 bot 进程通过 SQLite SessionStore 共享数据。
WebSocket 端点：ws://localhost:8080/api/v1/ws/{session_id}
"""

import asyncio
import logging
import os
import threading
from dotenv import load_dotenv
from pathlib import Path

# 添加项目根目录到 path
ROOT = Path(__file__).parent
import sys
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv(override=False)

# ─── 创建 Admin App ────────────────────────────────────────────────────────

admin_app = FastAPI(
    title="ClawRelay Admin API",
    version="1.0.0",
    description="会话管理、Metrics、热更新",
)

admin_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 延迟导入路由避免循环依赖
from src.admin import routes  # noqa: E402


@admin_app.on_event("startup")
async def startup_event():
    logger.info("=" * 60)
    logger.info("ClawRelay Admin API 启动")
    logger.info("=" * 60)
    # 启动 metrics 采集
    from src.core.metrics import get_metrics_collector
    loop = asyncio.get_event_loop()
    mc = get_metrics_collector()
    mc.start(loop)
    logger.info("Metrics 采集器已启动")


@admin_app.on_event("shutdown")
async def shutdown_event():
    from src.core.metrics import get_metrics_collector
    mc = get_metrics_collector()
    await mc.stop()
    logger.info("Admin API 已关闭")


# 挂载路由
admin_app.include_router(routes.router)


# ─── 入口 ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ClawRelay Admin API Server")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址")
    parser.add_argument("--port", type=int, default=8080, help="监听端口")
    args = parser.parse_args()

    logger.info("启动 Admin API: http://%s:%d", args.host, args.port)
    logger.info("  - Metrics:  http://%s:%d/api/v1/metrics", args.host, args.port)
    logger.info("  - Sessions: http://%s:%d/api/v1/sessions", args.host, args.port)
    logger.info("  - WebSocket: ws://%s:%d/api/v1/ws/<session_id>", args.host, args.port)

    uvicorn.run(
        admin_app,
        host=args.host,
        port=args.port,
        log_level="info",
    )
