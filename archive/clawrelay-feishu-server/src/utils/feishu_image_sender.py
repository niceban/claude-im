#!/usr/bin/env python
# coding=utf-8
"""
Feishu Image Sender - 轻量 HTTP 服务

接收图片路径，上传到飞书并发送给用户。
作为独立进程运行，不依赖主 feishu-server。

启动方式:
    python feishu_image_sender.py [--port 50010]

HTTP 接口:
    POST /send-image
    Body: {"image_path": "/path/to/image.png", "receive_id": "chat_id", "receive_id_type": "chat_id"}
    → 上传图片并发送，返回 {"msg_id": "...", "image_key": "..."}

    POST /reply-image
    Body: {"image_path": "/path/to/image.png", "message_id": "..."}
    → 上传图片并回复指定消息

    GET /health
    → 健康检查
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# 添加项目根目录到 sys.path（使 from src.xxx import 生效）
_project_root = str(Path(__file__).parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# 加载 .env（从 feishu-server 目录加载）
_env_path = Path(_project_root) / ".env"
if _env_path.exists():
    load_dotenv(_env_path, override=False)

from aiohttp import web
from src.adapters.feishu_api import FeishuAPI

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ─── 全局 FeishuAPI 实例（复用，同一 bot 只创建一个） ────────────────────────
_feishu_api: FeishuAPI | None = None


def get_feishu_api() -> FeishuAPI:
    global _feishu_api
    if _feishu_api is None:
        app_id = os.environ.get("FEISHU_APP_ID")
        app_secret = os.environ.get("FEISHU_APP_SECRET")

        # fallback: 从 bots.yaml 读取
        if not app_id or not app_secret:
            try:
                import yaml
                bots_yaml = Path(_project_root) / "config" / "bots.yaml"
                if bots_yaml.exists():
                    with open(bots_yaml) as f:
                        cfg = yaml.safe_load(f)
                    default_bot = cfg.get("bots", {}).get("default", {})
                    app_id = app_id or default_bot.get("app_id", "")
                    app_secret = app_secret or default_bot.get("app_secret", "")
            except Exception as e:
                logger.warning("从 bots.yaml 读取凭证失败: %s", e)

        if not app_id or not app_secret:
            raise RuntimeError(
                "FEISHU_APP_ID / FEISHU_APP_SECRET 未设置，"
                "请确认 .env 或 config/bots.yaml 中配置了飞书凭证"
            )
        _feishu_api = FeishuAPI(app_id, app_secret)
        logger.info("FeishuAPI 初始化完成 (app_id=%s)", app_id[:8] + "...")
    return _feishu_api


# ─── HTTP Handlers ────────────────────────────────────────────────────────────

async def handle_send_image(request: web.Request) -> web.Response:
    """POST /send-image — 主动发送图片"""
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    image_path = body.get("image_path")
    receive_id = body.get("receive_id")
    receive_id_type = body.get("receive_id_type", "chat_id")

    if not image_path:
        return web.json_response({"error": "image_path is required"}, status=400)
    if not receive_id:
        return web.json_response({"error": "receive_id is required"}, status=400)

    path = Path(image_path)
    if not path.exists():
        return web.json_response({"error": f"File not found: {image_path}"}, status=404)

    try:
        image_bytes = path.read_bytes()
        feishu = get_feishu_api()
        image_key = await feishu.upload_image(image_bytes)
        if not image_key:
            return web.json_response({"error": "Image upload failed"}, status=500)

        msg_id = await feishu.send_image(receive_id, image_key, receive_id_type)
        if not msg_id:
            return web.json_response({"error": "Send image failed"}, status=500)

        logger.info("发送图片成功: msg_id=%s, image_key=%s", msg_id, image_key)
        return web.json_response({"msg_id": msg_id, "image_key": image_key})

    except Exception as e:
        logger.exception("发送图片失败: %s", e)
        return web.json_response({"error": str(e)}, status=500)


async def handle_reply_image(request: web.Request) -> web.Response:
    """POST /reply-image — 回复图片"""
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    image_path = body.get("image_path")
    message_id = body.get("message_id")
    quote_id = body.get("quote_id")  # optional

    if not image_path:
        return web.json_response({"error": "image_path is required"}, status=400)
    if not message_id:
        return web.json_response({"error": "message_id is required"}, status=400)

    path = Path(image_path)
    if not path.exists():
        return web.json_response({"error": f"File not found: {image_path}"}, status=404)

    try:
        image_bytes = path.read_bytes()
        feishu = get_feishu_api()
        image_key = await feishu.upload_image(image_bytes)
        if not image_key:
            return web.json_response({"error": "Image upload failed"}, status=500)

        msg_id = await feishu.reply_image(message_id, image_key, quote_id)
        if not msg_id:
            return web.json_response({"error": "Reply image failed"}, status=500)

        logger.info("回复图片成功: msg_id=%s, image_key=%s", msg_id, image_key)
        return web.json_response({"msg_id": msg_id, "image_key": image_key})

    except Exception as e:
        logger.exception("回复图片失败: %s", e)
        return web.json_response({"error": str(e)}, status=500)


async def handle_send_file(request: web.Request) -> web.Response:
    """POST /send-file — 主动发送文件（支持任意类型，如 zip/pdf/txt 等）"""
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    file_path = body.get("file_path")
    receive_id = body.get("receive_id")
    receive_id_type = body.get("receive_id_type", "chat_id")

    if not file_path:
        return web.json_response({"error": "file_path is required"}, status=400)
    if not receive_id:
        return web.json_response({"error": "receive_id is required"}, status=400)

    path = Path(file_path)
    if not path.exists():
        return web.json_response({"error": f"File not found: {file_path}"}, status=404)

    try:
        file_bytes = path.read_bytes()
        file_name = path.name
        feishu = get_feishu_api()

        file_key = await feishu.upload_file(file_bytes, file_name)
        if not file_key:
            return web.json_response({"error": "File upload failed"}, status=500)

        msg_id = await feishu.send_file(receive_id, file_key, file_name, receive_id_type)
        if not msg_id:
            return web.json_response({"error": "Send file failed"}, status=500)

        logger.info("发送文件成功: msg_id=%s, file_key=%s, file_name=%s", msg_id, file_key, file_name)
        return web.json_response({"msg_id": msg_id, "file_key": file_key, "file_name": file_name})

    except Exception as e:
        logger.exception("发送文件失败: %s", e)
        return web.json_response({"error": str(e)}, status=500)


async def handle_reply_file(request: web.Request) -> web.Response:
    """POST /reply-file — 回复文件消息"""
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    file_path = body.get("file_path")
    message_id = body.get("message_id")
    quote_id = body.get("quote_id")

    if not file_path:
        return web.json_response({"error": "file_path is required"}, status=400)
    if not message_id:
        return web.json_response({"error": "message_id is required"}, status=400)

    path = Path(file_path)
    if not path.exists():
        return web.json_response({"error": f"File not found: {file_path}"}, status=404)

    try:
        file_bytes = path.read_bytes()
        file_name = path.name
        feishu = get_feishu_api()

        file_key = await feishu.upload_file(file_bytes, file_name)
        if not file_key:
            return web.json_response({"error": "File upload failed"}, status=500)

        msg_id = await feishu.reply_file(message_id, file_key, file_name, quote_id)
        if not msg_id:
            return web.json_response({"error": "Reply file failed"}, status=500)

        logger.info("回复文件成功: msg_id=%s, file_name=%s", msg_id, file_name)
        return web.json_response({"msg_id": msg_id, "file_key": file_key, "file_name": file_name})

    except Exception as e:
        logger.exception("回复文件失败: %s", e)
        return web.json_response({"error": str(e)}, status=500)


async def handle_health(request: web.Request) -> web.Response:
    """GET /health — 健康检查"""
    return web.json_response({"status": "ok"})


# ─── Main ────────────────────────────────────────────────────────────────────

def create_app() -> web.Application:
    app = web.Application()
    app.router.add_post("/send-image", handle_send_image)
    app.router.add_post("/reply-image", handle_reply_image)
    app.router.add_post("/send-file", handle_send_file)
    app.router.add_post("/reply-file", handle_reply_file)
    app.router.add_get("/health", handle_health)
    return app


def main():
    parser = argparse.ArgumentParser(description="Feishu Image Sender HTTP Service")
    parser.add_argument("--port", type=int, default=50010, help="HTTP 端口 (默认 50010)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="监听地址 (默认 127.0.0.1)")
    args = parser.parse_args()

    # 预检查
    try:
        get_feishu_api()
        logger.info("Feishu API 凭证检查通过")
    except RuntimeError as e:
        logger.error("配置错误: %s", e)
        sys.exit(1)

    logger.info("启动 Feishu Sender Service: http://%s:%d", args.host, args.port)
    logger.info("接口: POST /send-image  POST /reply-image  POST /send-file  POST /reply-file  GET /health")
    web.run_app(create_app(), host=args.host, port=args.port, access_log=None)


if __name__ == "__main__":
    main()
