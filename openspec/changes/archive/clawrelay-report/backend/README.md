# Clawrelay Report Backend

这是 `clawrelay-report` 的后端服务。

## 角色

后端负责：

- 为管理后台提供 API
- 聚合 `clawrelay-feishu-server` 的真实数据
- 支撑 `http://localhost:5173` 这个唯一后台入口

## 本地地址

- API 服务：`http://localhost:8000`

注意：

- `8000` 不是对人使用的并列后台入口
- 它只服务于前端后台和开发调试
- 不在这里保留第二套聊天执行路径
