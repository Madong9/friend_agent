# 项目复审与完善报告（2026-08-25）

## 审计范围

本次针对可运行性、需求覆盖、长期推荐行为、安全与隐私边界、API 合同、前端状态和文档一致性进行了完整复审。基线为 16 项测试、Ruff 和 Vite 构建均通过；因此重点不是修复显式报错，而是发现“短测试看不出、持续使用会暴露”的问题。

## 发现与处理

| 级别 | 问题 | 处理 | 验证 |
|---|---|---|---|
| 高 | Block 后已有 Match 仍展示聊天资格 | Match 改为 `BLOCKED`，列表仅返回 `MATCHED`，Block 后禁止反馈重建 | Service 测试 + 真实 HTTP 验收 |
| 高 | 客户端可提交 `verified` | `UserCreate` 禁止额外字段，认证状态只由服务端赋值 | API 422 测试 |
| 中 | 最近 20 次推荐累计排除会消耗候选池 | 改为 24h PASS 与紧邻上一页抑制 | Memory 测试 + 三轮 HTTP 推荐 |
| 中 | 旧 INTERESTED 在后续 PASS 后仍可能触发 Match | Mutual Match 只读取最新用户决策 | Feedback 顺序测试 |
| 中 | `campus.example.evil.test` 可绕过 URL 前缀判断 | 使用 `urlsplit().hostname` 与精确域规则 | Safety spoof 测试 |
| 中 | 明确羽毛球命中会因候选还有其他活动只得 0.5 | 活动采用 containment，明确命中为 1.0 | Matching feature 测试 |
| 低 | SQLite 外键声明未真正启用 | connect event 执行 `PRAGMA foreign_keys=ON` | 数据库连接测试 |
| 低 | 测试 engine 未 dispose，覆盖率运行出现 ResourceWarning | fixture 与独立 engine 显式释放 | 覆盖率回归无警告 |
| 低 | Trace/Session Memory 无界增长 | 各限制为进程内最近 500 个会话 | 代码审查与回归 |
| 低 | 前端切换 ID 时可能显示旧画像 | 请求竞态保护、先清空画像、表单按用户重建 | Vite production build |

## 验收证据

```text
pytest -q: 25 passed
pytest --cov=backend.app: 94%
ruff check: All checks passed!
ruff format --check: all files formatted
python -m compileall: success
npm run build: success
npm audit --audit-level=high: 0 vulnerabilities
```

真实 Uvicorn 使用临时 SQLite 和完整 50/15 Seed 数据。连续推荐页分别为：

```text
Page A: user003, user002, user047
Page B: user004, user042, user043
Page A: user003, user002, user047
```

相邻页无交集，而更早候选能够重新进入，不会耗尽。随后 PASS `user003`，下一次推荐不包含该用户。`user001` 与 `user002` 双向感兴趣后获得聊天资格，Block 后 `/matches/user001` 返回空数组。

## 仍然明确保留的 MVP 边界

- API 已有 JWT 登录态和对象级授权，但没有学校 SSO、Refresh Token 与服务端 Token 撤销，仍不能直接用于生产学生数据。
- 校园认证、用户与活动数据仍是 Mock。
- Trace/Session Memory 有界但仍是进程内存，多 worker 不共享。
- Safety 是风险信号，不是完整治理、人工审核或处罚系统。
- 没有数据库迁移框架；模型升级到生产前应引入 Alembic。
- 站内聊天已有持久化 REST 消息与安全检查，但没有 WebSocket 实时推送和审核后台。

这些边界已经在 README 与架构文档中公开，不影响本地教学和 MVP 演示。
