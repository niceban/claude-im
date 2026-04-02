# integration 模块规格

## 概述

integration模块验证完整请求链路。

## 测试清单

### test_integration.py

```python
@pytest.mark.integration
class TestChatCompletions:
    """HTTP → bridge → claude_node → Claude CLI"""

    def test_single_request(self):
        """单次请求完整链路"""
        response = requests.post(
            "http://localhost:18792/v1/chat/completions",
            json={
                "model": "claude-sonnet-4-6",
                "messages": [{"role": "user", "content": "Hello"}]
            },
            headers={"X-API-Key": "test-key"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "choices" in data
        assert data["choices"][0]["message"]["content"] != "(placeholder...)"

    def test_conversation_id_mapping(self):
        """conversation_id → session_id映射"""
        conv_id = "test-conv-123"
        # 第一个请求
        r1 = requests.post(..., json={"conversation_id": conv_id, ...})
        # 第二个请求（同一conversation_id）
        r2 = requests.post(..., json={"conversation_id": conv_id, ...})
        # 验证session被复用
        pass

    def test_multi_turn_conversation(self):
        """多轮对话"""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
            {"role": "user", "content": "How are you?"}
        ]
        r = requests.post(..., json={"messages": messages})
        assert "choices" in r.json()
```

### test_e2e.py

```python
@pytest.mark.e2e
class TestFeishuBridge:
    """飞书 → Gateway → bridge → claude_node"""

    def test_feishu_message_to_response(self):
        """飞书消息 → 响应"""
        # 需要真实飞书WebSocket连接
        # 或mock飞书消息格式
        pass

    def test_streaming_response(self):
        """流式响应E2E"""
        response = requests.post(
            "http://localhost:18792/v1/chat/completions",
            json={
                "model": "claude-sonnet-4-6",
                "messages": [{"role": "user", "content": "Count to 10"}],
                "stream": True
            },
            stream=True
        )
        chunks = list(response.iter_content())
        assert len(chunks) > 1  # 多个chunk
```

## 验收标准

- [ ] 端到端测试覆盖完整链路
- [ ] 多轮对话正确处理
- [ ] 流式响应E2E验证
- [ ] 错误恢复链路验证
