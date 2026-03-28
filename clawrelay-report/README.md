# Clawrelay Report

`clawrelay-report` 是项目唯一的管理后台产品。

## 唯一入口

- 管理后台入口：`http://localhost:5173`

`http://localhost:8000` 只是后台 API，不作为并列后台入口对外描述。

## 定位

本项目是一个完整的后台系统，而不是模板演示，也不是 Grafana 替代页。

标准职责：

- 后端 API
- 前端管理界面
- 真实业务数据接入
- 面向管理/运维使用的后台能力

## 架构关系

```text
clawrelay-feishu-server
  -> clawrelay-report backend
  -> clawrelay-report frontend (http://localhost:5173)
```

## 当前标准约束

- 唯一管理后台入口是 `http://localhost:5173`
- `8000` 仅为内部 API 服务
- 不把 SSE 写成已确认能力
- 不保留与当前产品方向无关的平行方案
