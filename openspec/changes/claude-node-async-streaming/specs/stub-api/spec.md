# stub-api 模块规格

## 概述

stub-api模块负责HTTP层，实现OpenAI-compatible API接口。核心任务是**替换当前Stub代码**，真实调用adapter层。

## 当前状态

```python
# server.py:97-118 (STUB - 必须替换)
return JSONResponse(content={
    "choices": [{
        "message": {
            "content": "(placeholder - adapter not yet connected)"  # ← STUB
        }
    }]
})
```

## 目标状态

```python
# server.py chat_completions (实现后)
async def chat_completions(request: Request) -> JSONResponse:
    # 1. 提取conversation_id
    body = await request.json()
    conversation_id = body.get("conversation_id", "default")

    # 2. 获取或创建session
    session_id = session_manager.get_or_create_session(conversation_id)

    # 3. 调用adapter
    adapter = get_process_manager()
    result = adapter.send_message(
        prompt=format_messages(body["messages"]),
        session_id=session_id
    )

    # 4. 转换为OpenAI格式
    return JSONResponse(content={
        "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": body.get("model", "claude-sonnet-4-6"),
        "choices": [{
            "message": {
                "role": "assistant",
                "content": result["text"]
            },
            "finish_reason": "stop",
            "index": 0
        }],
        "usage": {
            "prompt_tokens": result.get("prompt_tokens", 0),
            "completion_tokens": result.get("completion_tokens", 0),
            "total_tokens": result.get("total_tokens", 0)
        }
    })
```

## 接口规格

### POST /v1/chat/completions

**Request**:
```json
{
  "model": "claude-sonnet-4-6",
  "messages": [
    {"role": "system", "content": "You are helpful."},
    {"role": "user", "content": "Hello"}
  ],
  "stream": false,
  "conversation_id": "opt-xxx-xxx"  // 可选
}
```

**Response**:
```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1709404800,
  "model": "claude-sonnet-4-6",
  "choices": [{
    "message": {
      "role": "assistant",
      "content": "Hello! How can I help?"
    },
    "finish_reason": "stop",
    "index": 0
  }],
  "usage": {
    "prompt_tokens": 20,
    "completion_tokens": 15,
    "total_tokens": 35
  }
}
```

### GET /v1/models

**Response**:
```json
{
  "object": "list",
  "data": [
    {
      "id": "claude-sonnet-4-6",
      "object": "model",
      "created": 1709404800,
      "owned_by": "anthropic"
    }
  ]
}
```

### GET /health

**Response**:
```json
{
  "status": "ok",
  "version": "1.0.0"
}
```

### 错误格式（OpenAI标准）

```json
{
  "error": {
    "message": "Error description",
    "type": "invalid_request_error",
    "code": "invalid_api_key",
    "param": null,
    "status": 401
  }
}
```

**说明**：
- `status`: HTTP状态码（放在response body中）
- `code`: 机器可读的错误码字符串（如`invalid_api_key`），不是HTTP状态码
- `type`: OpenAI错误类型（`authentication_error`, `invalid_request_error`, `timeout`, `internal_error`）
- `param`: 关联参数名（可选）
```

## 测试要求

1. **测试1.1.1**: mock adapter.send_message()，验证调用参数
2. **测试1.1.2**: 断言响应content不是"(placeholder...)"
3. **测试1.1.3**: adapter返回error时，验证error格式
4. **测试1.1.4**: 验证conversation_id → session_id映射

## 验收标准

- [ ] 响应不是占位符
- [ ] 真实调用adapter.send_message()
- [ ] 错误正确传播
- [ ] 所有测试通过
