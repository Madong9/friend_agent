# 单微信号双用户 E2E 验证

这个脚本用于“真实微信用户 A + 一次性合成用户 B”的封闭验证，不增加 HTTP
测试接口，也不绕过生产匹配和通知服务。它从 CloudBase 中选择 A 的有效 OPEN
飞盘需求，用 `MatchingEngine` 校验 B，再调用 Agent 正在使用的
`PartnerLoopService.record_request()` 生成通知。

## 安全边界

- B 使用 `e2e-frisbee-b-*` ID、`[E2E临时]飞盘搭子B` 昵称、
  `e2e_local` identity provider 和 `@e2e.invalid` 合成校邮。
- B 是临时 `is_mock=false` 用户，因为 staging 的 `SHOW_MOCK_USERS=false` 会从
  候选检索中排除 mock 用户；脚本没有修改这条生产规则。
- B 没有微信 OpenID。脚本不创建或打印 JWT、OpenID、API Key、service role 或
  微信 Secret。
- 默认运行不写数据库；必须显式使用 `--execute`。
- `.e2e/partner-loop.json` 只保存 B 的 E2E 标识、来源 session 和本次通知 ID，
  不保存 A 的身份信息。手机验证完成前不要删除该文件。
- `--cleanup` 会复核全部 E2E 标记，然后删除 B、B 相关交互/匹配/消息和本次通知；
  不会删除 A 的画像和原 OPEN 需求。

## 只读预检

默认无参数运行会连接当前配置的数据库，但只执行 SELECT，不创建 B、不写
manifest，也不调用 commit：

```bash
./.venv/bin/python scripts/e2e_partner_loop.py
```

唯一请求会显示 request 数字 ID、活动、校区、时间、状态和匹配预检结论。存在多条
OPEN 飞盘请求时会安全列出各 request ID 与需求字段，再用下面的只读命令选定：

```bash
./.venv/bin/python scripts/e2e_partner_loop.py --request-id REQUEST_ID
```

预检不会显示用户 ID、昵称、OpenID、JWT 或任何 Secret。

## 执行

先让 A 在体验版明确发送“找高新区周六下午的飞盘搭子”，并确认
`partner_requests` 中生成一条有效 `OPEN` 请求。预检全部为 `yes` 后运行：

```bash
./.venv/bin/python scripts/e2e_partner_loop.py --execute
```

如果数据库中同时有多条 OPEN 飞盘需求，脚本只输出数量冲突，不输出用户标识。
在 CloudBase 控制台确认目标请求的数字 ID 后运行：

```bash
./.venv/bin/python scripts/e2e_partner_loop.py --execute --request-id REQUEST_ID
```

成功摘要应全部为 `yes`。此时 A 在体验版进入“我的 → 新候选通知”，可看到
“发现新的搭子候选”；重新发送原找搭子需求时，标记为 E2E 的 B 应成为候选。

验证完成后立即清理：

```bash
./.venv/bin/python scripts/e2e_partner_loop.py --cleanup
```

脚本不执行 migration、不重新部署后端，也不修改 CloudBase Auth、SDK transport
或 FastAPI JWT。
