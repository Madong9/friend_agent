# API 调用示例

先执行数据库迁移、Seed 并启动服务：

```bash
alembic upgrade head
python scripts/seed_users.py
uvicorn backend.app.main:app --reload
```

## 登录与 Bearer Token

所有画像、Agent、反馈、Match、Trace 和聊天接口都要求当前用户 Token。Demo 用户统一密码是 `CampusDemo123!`。

```bash
curl -X POST http://127.0.0.1:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"school_email":"user001@ustc.edu.cn","password":"CampusDemo123!"}'
```

复制响应里的 `access_token`。后续示例中的 `<TOKEN>` 替换成该值。服务端从 Token 的 `sub` 获取当前用户，不接受请求体伪造 `user_id`。

## 注册用户

```bash
curl -X POST http://127.0.0.1:8000/users \
  -H 'Content-Type: application/json' \
  -d '{
    "id":"demo-new-user",
    "school_email":"demo-new-user@ustc.edu.cn",
    "password":"SecureDemo123!",
    "nickname":"新同学",
    "campus":"西区",
    "grade":"大一",
    "major":"数学"
  }'
```

注册只接受允许的校内邮箱域名。系统也提供 USTC CAS 登录入口；本地密码登录主要用于 Demo 和开发验收。

## 自然语言画像

```bash
curl -X POST http://127.0.0.1:8000/users/user001/profile/parse \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <TOKEN>' \
  -d '{"text":"我研一，喜欢跑步和摄影，比较慢热，晚上有空。","apply":true}'
```

`apply=false` 时只预览 structured output，不写数据库。Token 用户必须与路径用户一致。

## 可选 AI 社交风格分析

只分析用户主动填写的非敏感社交偏好，且必须显式传入 `consent=true`：

```bash
curl -X POST http://127.0.0.1:8000/users/me/personality/analyze \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <TOKEN>' \
  -d '{"text":"我比较慢热，喜欢提前约好，两三个人活动最舒服。","consent":true}'
```

后端只保存有限枚举标签、温和摘要和更新时间，不保存这段分析原文，不推断心理健康、政治、宗教、性取向、健康、家庭或经济状况。任一方没有主动分析时，原有匹配总分保持不变；双方都有标签时，兼容度以 10% 上限参与排序。删除：

```bash
curl -X DELETE http://127.0.0.1:8000/users/me/personality \
  -H 'Authorization: Bearer <TOKEN>'
```

## Agent 推荐与 Trace

```bash
curl -X POST http://127.0.0.1:8000/agent/recommend \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <TOKEN>' \
  -d '{"message":"找周六下午羽毛球搭子，最好西区，水平休闲一点。","limit":3}'
```

从返回中复制 `session_id`：

```bash
curl http://127.0.0.1:8000/agent/SESSION_ID/trace \
  -H 'Authorization: Bearer <TOKEN>'
```

Trace 只能由该 Session 的创建者读取。

Session 默认 24 小时未活动后过期，Trace 默认保留 7 天。过期资源返回 404；如果同一 Session 正被另一个 Worker 处理，并发续接返回 409。时间和租约可通过 `AGENT_SESSION_TTL_MINUTES`、`AGENT_TRACE_TTL_DAYS` 与 `AGENT_TURN_LOCK_SECONDS` 调整。

### 多轮澄清与动态任务

信息不完整时，响应会包含 `response_type=clarification`、`needs_clarification=true` 和追问文本。把同一个 Session 带入下一轮：

```bash
curl -X POST http://127.0.0.1:8000/agent/chat \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <TOKEN>' \
  -d '{"message":"周六下午","limit":3,"session_id":"<SESSION_ID>"}'
```

活动查询、画像更新、推荐解释和零候选约束协商也复用这个入口：

```json
{"message":"西区有什么活动"}
{"message":"更新画像：我喜欢跑步，周日下午有空"}
{"message":"为什么推荐小林","session_id":"<SESSION_ID>"}
{"message":"可以放宽","session_id":"<等待确认的 SESSION_ID>"}
```

响应的 `response_type` 决定本轮是推荐、澄清、零候选、活动、画像更新、解释还是安全拦截。详细协议见 [动态 Agent 说明](DYNAMIC_AGENT.md)。

陌生活动会被加入当前用户的活动偏好。若精确活动暂无候选，本次需求以 `OPEN` 保存 14 天；后来有真实候选时会生成站内通知。查看、暂停需求与读取通知：

```bash
curl http://127.0.0.1:8000/partner-requests \
  -H 'Authorization: Bearer <TOKEN>'
curl -X PATCH http://127.0.0.1:8000/partner-requests/1 \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <TOKEN>' \
  -d '{"status":"PAUSED"}'
curl http://127.0.0.1:8000/notifications?unread_only=true \
  -H 'Authorization: Bearer <TOKEN>'
curl -X POST http://127.0.0.1:8000/notifications/1/read \
  -H 'Authorization: Bearer <TOKEN>'
```

## Feedback 与 Mutual Match

用户 A 使用自己的 Token：

```bash
curl -X POST http://127.0.0.1:8000/feedback \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <USER001_TOKEN>' \
  -d '{"candidate_id":"user002","feedback":"INTERESTED"}'
```

用户 B 使用自己的 Token：

```bash
curl -X POST http://127.0.0.1:8000/feedback \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <USER002_TOKEN>' \
  -d '{"candidate_id":"user001","feedback":"LIKE"}'
```

第二个意向到达后 `matched=true`，双方才获得站内聊天资格。

## 站内聊天

查看会话：

```bash
curl http://127.0.0.1:8000/conversations \
  -H 'Authorization: Bearer <TOKEN>'
```

发送与读取消息：

```bash
curl -X POST http://127.0.0.1:8000/conversations/user002/messages \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <USER001_TOKEN>' \
  -d '{"body":"周六下午一起打羽毛球吗？"}'

curl http://127.0.0.1:8000/conversations/user002/messages \
  -H 'Authorization: Bearer <USER001_TOKEN>'
```

没有 Mutual Match 或任一方 Block 时返回 403。带诈骗、贷款或危险外链信号的消息返回 422，并且不会写入数据库。

## Block 与 Report

```bash
curl -X POST http://127.0.0.1:8000/block \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <TOKEN>' \
  -d '{"blocked_user_id":"user004"}'

curl -X POST http://127.0.0.1:8000/report \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <TOKEN>' \
  -d '{"reported_user_id":"user010","category":"FRAUD","reason":"发送疑似贷款链接"}'
```

举报类别只允许 `HARASSMENT`、`FRAUD`、`FAKE_IDENTITY`、`INAPPROPRIATE_CONTENT`、`OTHER`。Block 后双方不再互相推荐，已有 Match 和聊天资格立即撤销；Report 保持 `PENDING`，不会由 LLM 自动永久封禁。

## Activities

公开活动不要求登录：

```bash
curl 'http://127.0.0.1:8000/activities?campus=西区&tag=羽毛球'
```

完整字段校验、Bearer 授权和在线执行入口以 `/docs` 为准。
