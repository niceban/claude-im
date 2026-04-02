# async-stream 模块规格

## 概述

async-stream模块实现SSE流式推送。核心是利用claude_node的send_nowait() + on_message callback实现实时流式响应。

## 当前状态

当前只支持同步阻塞模式，stream参数被忽略：
```python
# server.py
stream = body.get("stream", False)  # 被提取但未使用
return JSONResponse(content={...})  # 总是返回非流式
```

## 目标架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    流式响应架构                                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  client → POST /v1/chat/completions (stream=true)            │
│                │                                                │
│                ▼                                                │
│  server.py → adapter.send_async(prompt, stream_id, on_message_cb)│
│                │                                                │
│                ▼                                                │
│  claude_node → controller.send_nowait(prompt)  ← 非阻塞       │
│                │                                                │
│                ▼                                                │
│  on_message callback ← 每个token实时触发                        │
│                │                                                │
│                ▼                                                │
│  SSE chunk → client                                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## SSE格式（OpenAI兼容）

### 流式响应格式

**OpenAI标准SSE格式**：
```
data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","created":1709404800,"model":"claude-sonnet-4-6","choices":[{"index":0,"delta":{"content":"H"},"finish_reason":null}]}

data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","created":1709404800,"model":"claude-sonnet-4-6","choices":[{"index":0,"delta":{"content":"e"},"finish_reason":null}]}

data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","created":1709404800,"model":"claude-sonnet-4-6","choices":[{"index":0,"delta":{"content":"llo"},"finish_reason":null}]}

data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","created":1709404800,"model":"claude-sonnet-4-6","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}
```

### 字段说明

| 字段 | OpenAI标准 | 说明 |
|------|------------|------|
| id | 必需 | chatcmpl-{8char_hex} |
| object | 必需 | "chat.completion.chunk" |
| created | 必需 | Unix timestamp |
| model | 必需 | 模型名 |
| choices[0].index | 必需 | 0 |
| choices[0].delta.content | 必需 | 增量token内容 |
| choices[0].delta.role | 可选 | assistant（首chunk可选） |
| choices[0].finish_reason | 必需 | null=进行中, "stop"=完成 |

### 非流式响应格式（OpenAI标准）

```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1709404800,
  "model": "claude-sonnet-4-6",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": "Hello!"
    },
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 5,
    "total_tokens": 15
  }
}
```

## Race Condition解决方案

### 问题

原始设计中`on_message`作为实例属性设置在共享的controller上：
```python
# 问题代码
self.controller.on_message = on_message_callback  # 并发请求会互相覆盖
```

### 解决方案：per-request流式队列

每个请求有独立的流式队列，controller的on_message只是往队列推数据：

```python
import asyncio
from queue import Queue
from typing import Optional

class StreamQueue:
    """per-request流式队列"""
    def __init__(self):
        self.queue: Queue = Queue()
        self.done = False

    def put(self, msg) -> None:
        self.queue.put(msg)

    def set_done(self) -> None:
        self.done = True

    async def async_get(self):
        """异步获取消息"""
        while True:
            if not self.queue.empty():
                return self.queue.get()
            elif self.done:
                return None
            await asyncio.sleep(0.01)  # 避免busy wait

class ClaudeControllerProcess:
    def __init__(self, session_id: str):
        # ...
        self._stream_queues: dict[str, StreamQueue] = {}  # per-request队列

    def send_async(self, prompt: str, stream_id: str, on_message_callback=None):
        """非阻塞发送，设置per-request流式队列"""
        # 创建per-request队列
        sq = StreamQueue()
        self._stream_queues[stream_id] = sq

        # 设置全局callback往per-request队列推
        def queue_callback(msg):
            sq.put(msg)

        self.controller.on_message = queue_callback
        self.controller.send_nowait(prompt)

    async def stream_generator(self, stream_id: str, timeout: float = 120):
        """异步生成器，yield SSE chunks"""
        sq = self._stream_queues.get(stream_id)
        if not sq:
            return

        start_time = asyncio.get_event_loop().time()

        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout:
                yield self._make_chunk(stream_id, "", finish_reason="timeout")
                break

            msg = await sq.async_get()
            if msg is None:  # done
                break

            # 转换为OpenAI SSE格式
            content = msg.content if hasattr(msg, 'content') else ""
            yield self._make_chunk(stream_id, content)

    def _make_chunk(self, stream_id: str, content: str, finish_reason: Optional[str] = None):
        """创建OpenAI兼容的chunk"""
        return f"data: {json.dumps({
            'id': f'chatcmpl-{stream_id[:8]}',
            'object': 'chat.completion.chunk',
            'created': int(time.time()),
            'model': 'claude-sonnet-4-6',
            'choices': [{
                'index': 0,
                'delta': {'content': content},
                'finish_reason': finish_reason
            }]
        })}\n\n"
```

### server.py流式endpoint

```python
import uuid
import json
import time

async def chat_completions(request: Request):
    body = await request.json()
    stream = body.get("stream", False)
    conversation_id = body.get("conversation_id", str(uuid.uuid4())[:8])

    if stream:
        stream_id = conversation_id
        session_id = session_manager.get_or_create_session(conversation_id)

        async def event_generator():
            adapter = get_process_manager()
            adapter.send_async(prompt=format_messages(body["messages"]), stream_id=stream_id)

            async for chunk in adapter.stream_generator(stream_id, timeout=120):
                yield chunk

            yield "data: [DONE]\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")
    else:
        # 非流式路径（同步）
        result = adapter.send_message(...)
        return JSONResponse(content=format_sync_response(result))
```

## 实现

### adapter.py 异步方法

```python
class ClaudeControllerProcess:
    def send_async(self, prompt: str, stream_id: str, on_message_callback=None):
        """非阻塞发送，设置流式队列"""
        sq = StreamQueue()
        self._stream_queues[stream_id] = sq

        def queue_callback(msg):
            sq.put(msg)

        self.controller.on_message = queue_callback
        self.controller.send_nowait(prompt)

    async def stream_generator(self, stream_id: str, timeout: float = 120):
        """异步生成器"""
        sq = self._stream_queues.get(stream_id)
        if not sq:
            return

        while True:
            msg = await sq.async_get()
            if msg is None:
                break
            yield self._make_chunk(stream_id, msg.content)
```

## 接口规格

### POST /v1/chat/completions (stream=true)

**Request**:
```json
{
  "model": "claude-sonnet-4-6",
  "messages": [{"role": "user", "content": "Hello"}],
  "stream": true
}
```

**Response** (SSE - OpenAI兼容):
```
data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","created":1709404800,"model":"claude-sonnet-4-6","choices":[{"index":0,"delta":{"content":"H"},"finish_reason":null}]}

data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","created":1709404800,"model":"claude-sonnet-4-6","choices":[{"index":0,"delta":{"content":"ello"},"finish_reason":null}]}

data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","created":1709404800,"model":"claude-sonnet-4-6","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}

data: [DONE]
```

## 测试要求

1. **测试5.1.1**: SSE响应格式符合OpenAI标准
2. **测试5.1.2**: per-request队列正确隔离
3. **测试5.1.3**: stream=true/false开关
4. **测试5.1.4**: 并发请求不影响各自流式输出

## 验收标准

- [ ] SSE格式符合OpenAI标准
- [ ] 并发请求流式输出不互相干扰
- [ ] stream=false走非流式路径
- [ ] 超时处理正确
- [ ] 所有测试通过
