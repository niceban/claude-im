# config 模块规格

## 概述

config模块负责生成OpenClaw Gateway配置。核心是提供正确的`models.providers`配置片段，使Gateway能将请求路由到bridge服务。

## 配置片段规格

### models.providers 配置片段

```json
{
  "providers": {
    "claude-bridge": {
      "api": "openai-completions",
      "baseUrl": "http://127.0.0.1:18792",
      "models": {
        "claude-sonnet-4-6": {
          "contextWindow": 200000,
          "maxTokens": 8192
        }
      }
    }
  }
}
```

### 配置字段说明

| 字段 | 说明 | 值 |
|------|------|-----|
| `providers.claude-bridge` | provider名称 | 自定义 |
| `api` | API类型 | `"openai-completions"` |
| `baseUrl` | bridge服务地址 | `"http://127.0.0.1:18792"` |
| `models.*.contextWindow` | 上下文窗口大小 | `200000` (200k) |
| `models.*.maxTokens` | 最大生成token | `8192` |

## API Key配置

### 环境变量要求

| 变量 | 说明 | 要求 |
|------|------|------|
| `BRIDGE_API_KEY` | API认证密钥 | 必填，不得为默认值 |

### 启动校验

```python
# settings.py
API_KEY = os.getenv("BRIDGE_API_KEY")
if not API_KEY or API_KEY == "change-me-in-production":
    raise ValueError("BRIDGE_API_KEY must be set to a secure value")
```

**理由**：
- 与OpenAI API兼容
- 启动时检测默认值，拒绝启动
- 必需配置，不能有默认值

## 配置生成器

### generate_config() 函数

```python
def generate_config() -> dict:
    """生成OpenClaw models.providers配置"""
    return {
        "providers": {
            "claude-bridge": {
                "api": "openai-completions",
                "baseUrl": os.getenv("BRIDGE_BASE_URL", "http://127.0.0.1:18792"),
                "models": {
                    "claude-sonnet-4-6": {
                        "contextWindow": 200000,
                        "maxTokens": 8192
                    }
                }
            }
        }
    }
```

### claude-node版本固定

```python
# 固定 claude_node 版本
CLAUDE_NODE_VERSION = "1.0.0"  # 在配置中固定版本号
```

## 测试要求

1. **测试4.1.1**: 配置生成正确性测试
2. **测试4.1.2**: API Key校验测试（无效值拒绝启动）

## 验收标准

- [ ] models.providers配置格式正确
- [ ] baseUrl指向正确的bridge端口
- [ ] 模型contextWindow设置正确
- [ ] API Key启动时校验生效
- [ ] 版本号在配置中固定
- [ ] 所有测试通过
