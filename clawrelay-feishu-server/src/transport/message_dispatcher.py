"""
飞书消息分发器

接收飞书事件回调，路由到对应 handler 处理，
通过飞书 HTTP API 推送流式回复（500ms 节流编辑消息）。
"""

import asyncio
import base64
import json
import logging
import os
import re
import threading
import time
import uuid
from typing import Optional


def _preprocess_markdown(content: str) -> str:
    """预处理 markdown，转换飞书 markdown 组件不支持的语法。

    飞书 markdown 组件不支持 ATX 标题（# ## ###），
    将其转换为 **粗体** 形式，避免原样显示 ## 语法符号。
    """
    # ATX 标题：行首 # + 空格 + 标题文本
    # 转换规则：# ## ### 标题 → **标题**（保留多级标题的粗体样式）
    content = re.sub(r'^#{1,6}\s+(.+)$', r'**\1**', content, flags=re.MULTILINE)
    return content


def _split_into_card_batches(elements: list[dict], max_tables_per_card: int = 5) -> list[list[dict]]:
    """将 elements 拆分为多张卡片，每张最多 max_tables_per_card 个表格组件。

    飞书每张卡最多 5 个 table 组件。超过时拆成多条消息发送。
    非表格元素（markdown）跟随下一个表格归属同一批。
    """
    batches: list[list[dict]] = []
    current_batch: list[dict] = []
    current_table_count = 0

    for elem in elements:
        if elem.get("tag") == "table":
            # 检查是否需要在新批次的开头添加（当前批已达上限）
            if current_table_count >= max_tables_per_card:
                # 当前批已满，开始新批次
                batches.append(current_batch)
                current_batch = []
                current_table_count = 0
            current_table_count += 1
            current_batch.append(elem)
        else:
            # 非表格元素（markdown 等）直接添加
            current_batch.append(elem)

    if current_batch:
        batches.append(current_batch)

    return batches


def _parse_markdown_tables(content: str) -> list[dict]:
    """解析 markdown 内容，返回飞书卡片的 elements 列表。

    表格 -> native table 组件（支持完整 markdown cell，Feishu 7.14+）
    非表格 -> markdown 组件

    飞书 markdown 组件不支持 ATX 标题（# ## ###），由 _preprocess_markdown 预处理。

    飞书 table 组件文档：
    https://open.feishu.cn/document/uAjLw4CM/ukzMukzMukzM/feishu-cards/card-components/content-components/table
    """
    elements = []
    lines = content.split('\n')
    i = 0
    current_text_parts: list[str] = []

    def _flush_text():
        """将累积的非表格文本转为 markdown 元素"""
        nonlocal current_text_parts
        if current_text_parts:
            text = '\n'.join(current_text_parts).strip()
            if text:
                elements.append({"tag": "markdown", "content": text})
            current_text_parts = []

    while i < len(lines):
        line = lines[i]
        # 检测 markdown 表格行
        if re.match(r'^\s*\|.*\|\s*$', line):
            # 收集所有连续的表格行
            table_lines: list[str] = []
            while i < len(lines) and re.match(r'^\s*\|.*\|\s*$', lines[i]):
                table_lines.append(lines[i])
                i += 1

            # 跳过全分隔符行（|---|---），解析表头+数据行
            data_lines = [l for l in table_lines if not re.match(r'^\s*\|[\s\-:|]+\|\s*$', l)]
            if len(data_lines) >= 2:
                _flush_text()
                table_elem = _build_table_component(data_lines)
                if table_elem:
                    elements.append(table_elem)
            else:
                # 不是有效表格，当作普通文本
                current_text_parts.extend(table_lines)
            continue
        else:
            current_text_parts.append(line)
            i += 1

    _flush_text()
    return elements


def _build_table_component(table_lines: list[str]) -> Optional[dict]:
    """将 markdown 表格行解析为飞书原生 table 组件。

    使用 markdown data_type（Feishu 7.14+），单元格内容支持完整 markdown。
    用户版本 7.64.6 满足要求。
    """
    if len(table_lines) < 2:
        return None

    # 解析表头
    header_cells = [c.strip() for c in table_lines[0].strip().strip('|').split('|')]
    num_cols = len(header_cells)

    # 解析数据行（跳过表头）
    rows: list[dict] = []
    for line in table_lines[1:]:
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        # 对齐列数
        row_dict: dict = {}
        for j, cell in enumerate(cells[:num_cols]):
            col_name = header_cells[j] if j < len(header_cells) else f"col_{j}"
            row_dict[col_name] = cell
        # 补齐空列
        for j in range(len(cells), num_cols):
            col_name = header_cells[j]
            row_dict[col_name] = ""
        if row_dict:
            rows.append(row_dict)

    # 构建 columns（使用 markdown data_type 支持完整格式）
    columns = []
    for h in header_cells:
        columns.append({
            "name": h,
            "display_name": h,
            "data_type": "markdown",
        })

    table_component = {
        "tag": "table",
        "page_size": min(len(rows) + 1, 10),  # 包含表头行
        "row_height": "low",
        "freeze_first_column": False,
        "header_style": {
            "text_align": "left",
            "text_size": "normal",
            "background_style": "none",
            "text_color": "grey",
            "bold": True,
            "lines": 1,
        },
        "columns": columns,
        "rows": rows,
    }
    return table_component

from lark_oapi.api.im.v1 import P2ImMessageReceiveV1

from config.bot_config import BotConfig
from src.adapters.feishu_api import FeishuAPI
from src.core.claude_relay_orchestrator import ClaudeOrchestrator
from src.core.session_manager import SessionManager
from src.handlers.command_handlers import CommandRouter

logger = logging.getLogger(__name__)

_RELAY_CONNECTION_HINT = (
    "Claude 服务暂时无法连接，请联系管理员检查：\n"
    "1. Claude CLI 是否已安装并配置 API Key\n"
    "2. Python claude-node 包是否正常安装"
)
_RELAY_HTTP_ERROR_HINT = "Claude 服务返回异常，请联系管理员检查。"

# 节流间隔(秒) - 飞书编辑消息 API 频率限制约 5次/秒
STREAM_THROTTLE_INTERVAL = 0.5


def _friendly_error(e: Exception) -> str:
    """根据异常类型返回友好的中文错误提示"""
    msg = str(e)

    # Claude-specific 错误（优先检测，避免被数字状态码误匹配）
    if "[Claude] Connection error" in msg:
        return _RELAY_CONNECTION_HINT
    if "[Claude] HTTP" in msg:
        return _RELAY_HTTP_ERROR_HINT

    # MCP / HTTP 错误码检测（401 / 403 / 429 / 500 / 502 / 503）
    if "401" in msg or "Unauthorized" in msg or "auth" in msg.lower():
        return "认证失败，请检查 API Key 配置是否正确。"
    if "403" in msg or "Forbidden" in msg:
        return "访问被拒绝，请检查权限配置。"
    if "429" in msg or "rate limit" in msg.lower() or "RateLimit" in msg:
        return "请求过于频繁，请稍后重试（~1分钟）。"
    if "500" in msg or "Internal Server Error" in msg:
        return "上游服务异常，请稍后重试。"
    if "502" in msg or "503" in msg or "Bad Gateway" in msg or "Service Unavailable" in msg:
        return "服务暂时不可用，请稍后重试。"
    if "timeout" in msg.lower() or "Timeout" in msg:
        return "请求超时，请重试或简化问题。"

    return "抱歉，处理出错，请稍后重试。"


class MessageDispatcher:
    """飞书消息分发与回复"""

    def __init__(self, bot_config: BotConfig, loop: asyncio.AbstractEventLoop):
        self.config = bot_config
        self.bot_key = bot_config.bot_key
        self._loop = loop

        # 飞书 HTTP API 客户端
        self.feishu_api = FeishuAPI(bot_config.app_id, bot_config.app_secret)

        # 命令路由器
        self.command_router = CommandRouter()

        # Claude Relay 编排器
        # 从 os.environ 提取认证 token（load_dotenv 已加载 .env），
        # 并合并 bot_config.env_vars，一并传给 subprocess
        env = dict(bot_config.env_vars or {})
        for key in ("ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL"):
            if key in os.environ and key not in env:
                env[key] = os.environ[key]
        self.orchestrator = ClaudeOrchestrator(
            bot_key=bot_config.bot_key,
            working_dir=bot_config.working_dir or "",
            model=bot_config.model or "",
            system_prompt=bot_config.system_prompt or "",
            env_vars=env or None,
        )

        # 预热 controller（消除首次消息 30s 冷启动）
        # 在后台线程运行，避免阻塞事件循环
        threading.Thread(target=self.orchestrator.adapter.prewarm, daemon=True).start()

        # 会话管理
        self.session_manager = SessionManager()

        # 机器人名称（用于过滤@提及）
        self.bot_name = bot_config.name or ""

        # 消息去重
        self._processed_msgids: dict[str, float] = {}

        # 加载自定义命令
        self._load_custom_commands()

        logger.info("[Dispatcher:%s] 初始化完成", self.bot_key)

    def reload_config(self, new_bot_config: "BotConfig"):
        """热更新：使用新配置重新初始化 orchestrator（当前用于 system_prompt 更新）"""
        import os
        self.config = new_bot_config
        env = dict(new_bot_config.env_vars or {})
        for key in ("ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL"):
            if key in os.environ and key not in env:
                env[key] = os.environ[key]
        self.orchestrator = ClaudeOrchestrator(
            bot_key=new_bot_config.bot_key,
            working_dir=new_bot_config.working_dir or "",
            model=new_bot_config.model or "",
            system_prompt=new_bot_config.system_prompt or "",
            env_vars=env or None,
            allowed_tools=new_bot_config.allowed_tools,
            max_concurrent_sessions=new_bot_config.max_concurrent_sessions,
            max_memory_mb=new_bot_config.max_memory_mb,
        )
        # 预热新 controller
        threading.Thread(target=self.orchestrator.adapter.prewarm, daemon=True).start()
        logger.info("[Dispatcher:%s] 配置热更新完成，orchestrator 已重建", self.bot_key)

    def _load_custom_commands(self):
        if not self.config.custom_commands:
            return
        for module_path in self.config.custom_commands:
            try:
                import importlib
                module = importlib.import_module(module_path)
                if hasattr(module, 'register_commands'):
                    module.register_commands(self.command_router)
                    logger.info("[Dispatcher:%s] 加载自定义命令: %s", self.bot_key, module_path)
            except Exception as e:
                logger.error("[Dispatcher:%s] 加载自定义命令失败: %s (%s)", self.bot_key, module_path, e)

    # ---- 事件入口（同步，由 SDK 线程调用） ----

    def on_message_event(self, data: P2ImMessageReceiveV1):
        """处理接收消息事件（同步入口，由飞书 SDK 回调线程调用）

        将异步处理任务调度到主事件循环。
        """
        logger.info("[Dispatcher:%s] on_message_event 被调用，准备调度异步任务", self.bot_key)
        future = asyncio.run_coroutine_threadsafe(
            self._handle_message_event(data),
            self._loop,
        )

        def _on_done(f):
            exc = f.exception()
            if exc:
                logger.error("[Dispatcher:%s] 异步任务异常: %s", self.bot_key, exc, exc_info=exc)

        future.add_done_callback(_on_done)

    # ---- 异步消息处理 ----

    async def _handle_message_event(self, data: P2ImMessageReceiveV1):
        """异步处理消息事件"""
        event = data.event
        message = event.message
        sender = event.sender

        message_id = message.message_id
        msg_type = message.message_type
        chat_id = message.chat_id
        chat_type = message.chat_type  # "p2p" | "group"
        open_id = sender.sender_id.open_id

        # 消息去重
        if message_id in self._processed_msgids:
            return
        self._processed_msgids[message_id] = time.time()
        self._cleanup_processed_msgids()

        session_key = chat_id if chat_type == "group" else open_id

        logger.info(
            "[Dispatcher:%s] 收到消息: msg_type=%s, user=%s, chat_type=%s, session_key=%s",
            self.bot_key, msg_type, open_id, chat_type, session_key
        )

        # Bot 白名单检查（防止其他 bot 伪造消息）
        if self.config.allowed_bots and self.config.app_id not in self.config.allowed_bots:
            logger.warning(
                "[Dispatcher:%s] Bot app_id %s 不在 allowed_bots 白名单中，拒绝处理",
                self.bot_key, self.config.app_id
            )
            return

        # 用户白名单检查
        if self.config.allowed_users and open_id not in self.config.allowed_users:
            logger.warning("[Dispatcher:%s] 用户 %s 不在白名单中", self.bot_key, open_id)
            await self.feishu_api.reply_text(message_id, "抱歉，您没有使用此机器人的权限。")
            return

        # 按消息类型路由
        if msg_type == "text":
            await self._handle_text(message_id, message, open_id, session_key, chat_type)
        elif msg_type == "post":
            await self._handle_post(message_id, message, open_id, session_key, chat_type)
        elif msg_type == "image":
            await self._handle_image(message_id, message, open_id, session_key, chat_type)
        elif msg_type == "file":
            await self._handle_file(message_id, message, open_id, session_key, chat_type)
        else:
            logger.warning("[Dispatcher:%s] 暂不支持的消息类型: %s", self.bot_key, msg_type)
            await self.feishu_api.reply_text(message_id, f"暂不支持处理 {msg_type} 类型的消息。")

    async def _handle_text(self, message_id: str, message, user_id: str, session_key: str, chat_type: str):
        """处理文本消息"""
        try:
            content_json = json.loads(message.content)
            original_content = content_json.get("text", "").strip()
        except (json.JSONDecodeError, AttributeError):
            original_content = ""

        if not original_content:
            return

        # 群聊中：检查是否 @ 了机器人，未 @ 则忽略
        if chat_type == "group" and not self._is_bot_mentioned(message, original_content):
            logger.info("[Dispatcher:%s] 群聊消息但机器人未被@，忽略", self.bot_key)
            return

        # 过滤 @机器人 前缀
        content = re.sub(r'@_user_\d+\s*', '', original_content).strip()
        if self.bot_name and content.startswith(f"@{self.bot_name}"):
            content = content[len(f"@{self.bot_name}"):].strip()

        if not content:
            return

        await self._handle_text_content(message_id, message, content, user_id, session_key, chat_type)

    async def _handle_post(self, message_id: str, message, user_id: str, session_key: str, chat_type: str):
        """处理富文本(post)消息，提取文本和图片"""
        try:
            content_json = json.loads(message.content)
        except (json.JSONDecodeError, AttributeError):
            await self.feishu_api.reply_text(message_id, "富文本消息解析失败，请重试。")
            return

        # 飞书 post content 结构: {"title": "...", "content": [[{tag, ...}, ...], ...]}
        # content 可能在 zh_cn / en_us / ja_jp 等语言 key 下
        post_body = content_json
        for lang_key in ("zh_cn", "en_us", "ja_jp"):
            if lang_key in content_json:
                post_body = content_json[lang_key]
                break

        title = post_body.get("title", "")
        paragraphs = post_body.get("content", [])

        text_parts = []
        image_keys = []

        if title:
            text_parts.append(title)

        for paragraph in paragraphs:
            for element in paragraph:
                tag = element.get("tag", "")
                if tag == "text":
                    text_parts.append(element.get("text", ""))
                elif tag == "a":
                    link_text = element.get("text", "")
                    href = element.get("href", "")
                    text_parts.append(f"{link_text}({href})" if href else link_text)
                elif tag == "img":
                    img_key = element.get("image_key", "")
                    if img_key:
                        image_keys.append(img_key)
                elif tag == "at":
                    # 跳过 @机器人 自身
                    pass

        text_content = "\n".join(text_parts).strip()

        # 群聊中：检查是否 @ 了机器人，未 @ 则忽略（图片消息除外，有图即处理）
        if chat_type == "group" and not image_keys and not self._is_bot_mentioned(message, text_content):
            logger.info("[Dispatcher:%s] 群聊消息但机器人未被@，忽略", self.bot_key)
            return

        # 过滤 @机器人 前缀
        text_content = re.sub(r'@_user_\d+\s*', '', text_content).strip()
        if self.bot_name and text_content.startswith(f"@{self.bot_name}"):
            text_content = text_content[len(f"@{self.bot_name}"):].strip()

        if not text_content and not image_keys:
            return

        # 如果有图片，走多模态处理
        if image_keys:
            content_blocks = []
            if text_content:
                content_blocks.append({"type": "text", "text": text_content})
            else:
                content_blocks.append({"type": "text", "text": "[用户发送了富文本消息，包含图片] 请描述或分析图片内容"})

            for img_key in image_keys:
                image_bytes = await self.feishu_api.download_resource(message_id, img_key, "image")
                if image_bytes:
                    b64 = base64.b64encode(image_bytes).decode("utf-8")
                    content_blocks.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"},
                    })

            stream_id = uuid.uuid4().hex[:12]
            log_context = {'chat_type': chat_type, 'message_type': 'post'}

            on_stream_delta = self._make_stream_card_callback(message.chat_id, text_content, user_message_id=message_id)

            try:
                await self.orchestrator.handle_multimodal_message(
                    user_id=user_id,
                    content_blocks=content_blocks,
                    stream_id=stream_id,
                    session_key=session_key,
                    log_context=log_context,
                    on_stream_delta=on_stream_delta,
                )
            except Exception as e:
                logger.error("[Dispatcher:%s] 处理富文本消息失败: %s", self.bot_key, e, exc_info=True)
                await self.feishu_api.edit_text(message_id, _friendly_error(e))
        else:
            # 纯文本富文本，当作普通文本处理
            await self._handle_text_content(message_id, message, text_content, user_id, session_key, chat_type)

    async def _handle_text_content(self, message_id: str, message, content: str, user_id: str, session_key: str, chat_type: str):
        """处理已提取的纯文本内容（供 _handle_text 和 _handle_post 复用）"""
        # 检查命令
        normalized = content.strip().lower()

        # 重置会话
        if normalized in ("reset", "new", "clear", "重置", "清空"):
            await self.session_manager.clear_session(self.bot_key, session_key)
            await self.feishu_api.reply_text(message_id, "会话已重置，可以开始新的对话。")
            return

        # 停止任务
        stop_msg = re.sub(r'[^\w\u4e00-\u9fff]', '', normalized)
        if stop_msg in ("stop", "停止", "暂停", "停"):
            from src.core.task_registry import get_task_registry
            cancelled, _ = get_task_registry().cancel(f"{self.bot_key}:{session_key}")
            if cancelled:
                await self.feishu_api.reply_text(message_id, "已停止当前任务。")
            else:
                await self.feishu_api.reply_text(message_id, "当前没有正在运行的任务。")
            return

        # 检查内置命令
        handler = self.command_router.handlers.get(content) or self.command_router.handlers.get(normalized)
        if handler:
            stream_id = uuid.uuid4().hex[:12]
            try:
                msg_json, _ = handler.handle(content, stream_id, user_id)
                msg_data = json.loads(msg_json)
                if msg_data.get("msgtype") == "stream":
                    text_content = msg_data.get("stream", {}).get("content", "")
                else:
                    text_content = str(msg_data)
                await self.feishu_api.reply_text(message_id, text_content)
            except Exception as e:
                logger.error("[Dispatcher:%s] 命令处理失败: %s", self.bot_key, e, exc_info=True)
                await self.feishu_api.reply_text(message_id, f"命令处理出错：{e}")
            return

        # 调用 AI 处理
        stream_id = uuid.uuid4().hex[:12]
        log_context = {
            'chat_type': chat_type,
            'chat_id': message.chat_id,
            'message_type': 'text',
        }

        on_stream_delta = self._make_stream_card_callback(message.chat_id, content, user_message_id=message_id)

        try:
            result_text = await self.orchestrator.handle_text_message(
                user_id=user_id,
                message=content,
                stream_id=stream_id,
                session_key=session_key,
                log_context=log_context,
                on_stream_delta=on_stream_delta,
            )
            # 检测返回内容中的图片路径，自动发送到飞书
            if result_text:
                await self._maybe_send_images_in_response(message_id, result_text)
        except Exception as e:
            logger.error("[Dispatcher:%s] 处理文本消息失败: %s", self.bot_key, e, exc_info=True)
            await self.feishu_api.reply_text(message_id, _friendly_error(e))

    async def _handle_image(self, message_id: str, message, user_id: str, session_key: str, chat_type: str):
        """处理图片消息"""
        try:
            content_json = json.loads(message.content)
            image_key = content_json.get("image_key", "")
        except (json.JSONDecodeError, AttributeError):
            image_key = ""

        if not image_key:
            await self.feishu_api.reply_text(message_id, "图片获取失败，请重试。")
            return

        # 下载图片
        image_bytes = await self.feishu_api.download_resource(message_id, image_key, "image")
        if not image_bytes:
            await self.feishu_api.reply_text(message_id, "图片下载失败，请重试。")
            return

        # 编码为 data URI
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        data_uri = f"data:image/png;base64,{b64}"

        content_blocks = [
            {"type": "text", "text": "[用户发送了一张图片] 请描述或分析这张图片"},
            {"type": "image_url", "image_url": {"url": data_uri}},
        ]

        stream_id = uuid.uuid4().hex[:12]
        log_context = {'chat_type': chat_type, 'message_type': 'image'}

        on_stream_delta = self._make_stream_card_callback(message.chat_id, "[用户发送了一张图片] 请描述或分析这张图片", user_message_id=message_id)

        try:
            result_text = await self.orchestrator.handle_multimodal_message(
                user_id=user_id,
                content_blocks=content_blocks,
                stream_id=stream_id,
                session_key=session_key,
                log_context=log_context,
                on_stream_delta=on_stream_delta,
            )
            if result_text:
                await self._maybe_send_images_in_response(message_id, result_text)
        except Exception as e:
            logger.error("[Dispatcher:%s] 处理图片消息失败: %s", self.bot_key, e, exc_info=True)
            await self.feishu_api.edit_text(message_id, _friendly_error(e))

    async def _handle_file(self, message_id: str, message, user_id: str, session_key: str, chat_type: str):
        """处理文件消息"""
        try:
            content_json = json.loads(message.content)
            file_key = content_json.get("file_key", "")
            file_name = content_json.get("file_name", "unknown")
        except (json.JSONDecodeError, AttributeError):
            file_key = ""
            file_name = "unknown"

        if not file_key:
            await self.feishu_api.reply_text(message_id, "文件获取失败，请重试。")
            return

        file_bytes = await self.feishu_api.download_resource(message_id, file_key, "file")
        if not file_bytes:
            await self.feishu_api.reply_text(message_id, "文件下载失败，请重试。")
            return

        # 编码为 data URI
        b64 = base64.b64encode(file_bytes).decode("utf-8")
        import mimetypes
        mime_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"
        file_data = {
            "type": "file_url",
            "file_url": {
                "url": f"data:{mime_type};base64,{b64}",
                "filename": file_name,
            },
        }

        stream_id = uuid.uuid4().hex[:12]
        log_context = {
            'chat_type': chat_type,
            'message_type': 'file',
            'file_info': [{'filename': file_name}],
        }

        on_stream_delta = self._make_stream_card_callback(message.chat_id, f"[用户发送了文件: {file_name}]", user_message_id=message_id)

        try:
            result_text = await self.orchestrator.handle_file_message(
                user_id=user_id,
                message=f"[用户发送了文件: {file_name}] 请分析这个文件的内容。",
                files=[file_data],
                stream_id=stream_id,
                session_key=session_key,
                log_context=log_context,
                on_stream_delta=on_stream_delta,
            )
            if result_text:
                await self._maybe_send_images_in_response(message_id, result_text)
        except Exception as e:
            logger.error("[Dispatcher:%s] 处理文件消息失败: %s", self.bot_key, e, exc_info=True)
            await self.feishu_api.edit_text(message_id, _friendly_error(e))

    # ---- 流式推送（通过编辑消息实现） ----

    def _make_stream_delta_callback(self, reply_msg_id: str):
        """创建带节流的 on_stream_delta 回调

        通过反复编辑已发送的消息来模拟流式效果。
        """
        state = {
            'last_pushed_text': "",
            'last_push_time': 0.0,
            'throttle_task': None,
        }
        push_lock = asyncio.Lock()

        async def on_stream_delta(accumulated_text: str, finish: bool, tool_names: list = None):
            if finish:
                if state['throttle_task'] and not state['throttle_task'].done():
                    state['throttle_task'].cancel()
                await self.feishu_api.edit_text(reply_msg_id, accumulated_text)
                state['last_pushed_text'] = accumulated_text
                return

            now = time.monotonic()
            elapsed = now - state['last_push_time']

            if elapsed >= STREAM_THROTTLE_INTERVAL and accumulated_text != state['last_pushed_text']:
                async with push_lock:
                    await self.feishu_api.edit_text(reply_msg_id, accumulated_text)
                    state['last_pushed_text'] = accumulated_text
                    state['last_push_time'] = time.monotonic()
            elif state['throttle_task'] is None or state['throttle_task'].done():
                captured_text = accumulated_text

                async def delayed_push():
                    await asyncio.sleep(STREAM_THROTTLE_INTERVAL - elapsed)
                    async with push_lock:
                        if captured_text != state['last_pushed_text']:
                            await self.feishu_api.edit_text(reply_msg_id, captured_text)
                            state['last_pushed_text'] = captured_text
                            state['last_push_time'] = time.monotonic()

                state['throttle_task'] = asyncio.create_task(delayed_push())

        return on_stream_delta

    def _make_stream_card_callback(
        self, receive_id: str, user_message: str = "", receive_id_type: str = "chat_id",
        user_message_id: str = None
    ):
        """创建流式响应回调。

        - 流式过程中添加 "Typing" 打字中表情动画
        - finish 后全量解析 markdown 表格为 native table，一次性发送
        - 动态标题：从用户消息提取前25字符
        """
        raw_title = user_message.strip()[:25]
        title = f"🤖 {raw_title}" if raw_title else "🤖 Claude"
        if len(user_message.strip()) > 25:
            title += "..."

        state = {
            'message_id': None,      # 响应卡片的 message_id
            'reaction_id': None,      # Typing 表情的 reaction_id
            'sent_thinking': False,
        }
        push_lock = asyncio.Lock()

        async def _add_typing_indicator():
            """添加 Typing 打字中表情到用户的消息"""
            if not user_message_id:
                return
            async with push_lock:
                if state['reaction_id'] is None:
                    try:
                        reaction_id = await self.feishu_api.add_reaction(
                            user_message_id, emoji_type="Typing"
                        )
                        if reaction_id:
                            state['reaction_id'] = reaction_id
                    except Exception as e:
                        logger.warning(f"[Dispatcher] 添加 Typing 表情失败: {e}")

        async def _remove_typing_indicator():
            """删除 Typing 打字中表情"""
            if not user_message_id or not state['reaction_id']:
                return
            async with push_lock:
                try:
                    await self.feishu_api.delete_reaction(
                        user_message_id, state['reaction_id']
                    )
                    state['reaction_id'] = None
                except Exception as e:
                    logger.warning(f"[Dispatcher] 删除 Typing 表情失败: {e}")

        async def on_stream_delta(accumulated_text: str, finish: bool, tool_names: list = None):
            if not finish:
                # 首次非finish调用 → 添加 Typing 表情
                if not state['sent_thinking']:
                    state['sent_thinking'] = True
                    await _add_typing_indicator()
                return

            # finish 时一次性发送完整内容
            await _remove_typing_indicator()
            async with push_lock:
                elements = _parse_markdown_tables(_preprocess_markdown(accumulated_text))
                batches = _split_into_card_batches(elements, max_tables_per_card=5)

                # 清空之前的 thinking 卡片
                if state['message_id'] and batches:
                    try:
                        await self.feishu_api.edit_text(
                            state['message_id'],
                            f"🤖 {title} — 整理中..."
                        )
                    except Exception:
                        pass

                for batch_idx, batch_elements in enumerate(batches):
                    batch_suffix = f" ({batch_idx + 1}/{len(batches)})" if len(batches) > 1 else ""
                    card_body = {
                        "config": {"wide_screen_mode": True},
                        "header": {
                            "title": {
                                "tag": "plain_text",
                                "content": f"{title}{batch_suffix}",
                            },
                            "template": "blue",
                        },
                        "elements": batch_elements,
                    }
                    msg_id = await self.feishu_api.send_card(
                        receive_id, card_body, receive_id_type
                    )
                    if not msg_id:
                        batch_tag = f" {batch_idx + 1}/{len(batches)}" if len(batches) > 1 else ""
                        logger.error("[Dispatcher:%s] 发送卡片%s失败", self.bot_key, batch_tag)
                        return
                    batch_tag = f" {batch_idx + 1}/{len(batches)}" if len(batches) > 1 else ""
                    logger.info("[Dispatcher:%s] 发送卡片%s成功 (tables=%d)",
                                self.bot_key, batch_tag,
                                sum(1 for e in batch_elements if e.get("tag") == "table"))

        return on_stream_delta

    # ---- 工具方法 ----

    def _is_bot_mentioned(self, message, text: str) -> bool:
        """检查消息中是否 @ 了本机器人（优先用 SDK mentions 字段，fallback 到文本）"""
        # 方法1: 使用 SDK 的 mentions 字段（最可靠）
        mentions = getattr(message, 'mentions', None) or []
        if mentions:
            for mention in mentions:
                mention_name = getattr(mention, 'name', None) or ''
                mention_key = getattr(mention, 'key', None) or ''
                if self.bot_name and mention_name == self.bot_name:
                    return True
                if self.bot_key and mention_key == self.bot_key:
                    return True
        # 方法2: fallback 到文本匹配
        return self._is_bot_mentioned_in_text(text)

    def _is_bot_mentioned_in_text(self, text: str) -> bool:
        """检查文本中是否 @ 了机器人（群聊时调用）"""
        if not text:
            return False
        # 检查 @_user_\d+ 格式（飞书内部用户 ID）
        if re.search(r'@_user_\d+', text):
            return True
        # 检查 @机器人名称 格式（精确匹配单词边界）
        if self.bot_name:
            pattern = r'@' + re.escape(self.bot_name) + r'(?:\s|$|[^\w\u4e00-\u9fff])'
            if re.search(pattern, text):
                return True
        return False

    async def _maybe_send_images_in_response(self, message_id: str, text: str):
        """检测文本中的图片路径，上传到飞书并回复图片给用户"""
        import re
        from pathlib import Path

        # 匹配常见的图片文件路径
        img_pattern = re.compile(
            r'(/[^\s"\'<>]+\.(?:png|jpg|jpeg|gif|webp|bmp|svg)|'
            r'[A-Za-z]:\\[^\s"\'<>]+\.(?:png|jpg|jpeg|gif|webp|bmp)|'
            r'(?:minimax_outputs|video-understanding|outputs|[^/\s]+)/(?:[^/\s]+/)*[^/\s]+\.(?:png|jpg|jpeg|gif|webp))',
            re.IGNORECASE
        )
        seen = set()
        for match in img_pattern.finditer(text):
            path_str = match.group(0).strip()
            if path_str in seen:
                continue
            seen.add(path_str)
            path = Path(os.path.expanduser(path_str))
            if not path.exists() or not path.is_file():
                continue
            try:
                image_bytes = path.read_bytes()
                image_key = await self.feishu_api.upload_image(image_bytes)
                if image_key:
                    await self.feishu_api.reply_image(message_id, image_key)
                    logger.info("[Dispatcher:%s] 自动发送图片成功: %s", self.bot_key, path.name)
            except Exception as e:
                logger.warning("[Dispatcher:%s] 自动发送图片失败: %s (%s)", self.bot_key, path.name, e)

    def _cleanup_processed_msgids(self):
        now = time.time()
        expired = [k for k, v in self._processed_msgids.items() if now - v > 300]
        for k in expired:
            del self._processed_msgids[k]
