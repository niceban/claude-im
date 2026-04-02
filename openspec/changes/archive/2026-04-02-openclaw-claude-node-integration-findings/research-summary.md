# Research Summary — deep-1775095086

## Cycle 1

### Step 1: Codebase Analysis - Production Config
- **Finding**: 当前走 cliBackends (wrapper.py)，不是 provider
- **Key insight**: Port 18793 (clawrelay_bridge) 已废弃，与当前路由无关
- **cliBackends 是 text-only fallback**：tools disabled, no streaming

---

### Step 2 & 3: Docs + GitHub Research - Provider Config

**models.providers 完整配置示例**:
```json
{
  "models": {
    "providers": {
      "<providerId>": {
        "baseUrl": "http://localhost:8787/v1",
        "apiKey": "local-dev",
        "api": "openai-completions",
        "models": [{
          "id": "sonnet",
          "name": "Claude via bridge",
          "contextWindow": 200000,
          "supportsTools": true
        }]
      }
    }
  }
}
```

**api 类型枚举**:
| api 值 | 含义 |
|--------|------|
| `"openai-completions"` | OpenAI Chat Completions 兼容 |
| `"anthropic-messages"` | Anthropic Messages API |
| `"ollama"` | Ollama 原生 API |

**cliBackends vs models.providers**:
| 维度 | models.providers | cliBackends |
|------|-----------------|-------------|
| 通信 | HTTP 请求 | stdin/CLI 参数 |
| 场景 | 云 API / 本地 HTTP 服务 | 本地 CLI agent |
| tools | 支持 | 不支持 (text-only fallback) |

**关键发现**: 两者是正交机制，可以同时配置！

---

## Architecture Decision

**当前架构 (错误)**:
```
Feishu → Gateway → cliBackends → wrapper.py → claude_node → Claude CLI
                                              (text-only fallback)
```

**正确架构**:
```
Feishu → Gateway → models.providers (HTTP) → bridge → claude_node → Claude CLI
                                    (full capability)
```

**最小改动方案**:
1. 保持 cliBackends 作为 fallback
2. 新增 models.providers 指向新的 bridge 服务
3. bridge 实现 `/v1/chat/completions` 接口
4. bridge 内部调用 claude_node

---

## External Resources

- OpenClaw schema: `openclaw/src/config/zod-schema.core.ts`
- Provider 配置示例: `Light-Heart-Labs/DreamServer/openclaw.json`
- Ollama 配置: `models.providers.ollama` with native `api: "ollama"`
