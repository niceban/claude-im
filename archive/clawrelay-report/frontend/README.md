# Clawrelay Report Frontend

这是 `clawrelay-report` 的前端，也就是项目唯一管理后台的界面层。

## 唯一入口

- 本地访问地址：`http://localhost:5173`

## 角色

前端负责：

- 登录后的后台页面
- 会话、历史、指标等管理视图
- 调用 `http://localhost:8000` 后端 API

## 约束

- `5173` 是唯一对人入口
- 不把 `8000` 当成并列后台
- 不把 SSE 写成已确认能力
