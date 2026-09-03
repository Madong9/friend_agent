# 微信小程序迁移验收记录（2026-08-28）

验收依据：`Campus_Social_Agent_微信小程序_DeepSeek_零元内测版提示词.md`。本记录区分“代码完成”“本地实际运行”和“需要外部账号/设备”。

## Phase 0～12 状态

| 阶段 | 状态 | 实际证据 |
|---|---|---|
| 0 Baseline | 已完成 | 读取现有架构、迁移和测试；保留 Agent Core |
| 1 Backend | 已完成 | FastAPI、SQLAlchemy、Alembic、认证与安全测试通过 |
| 2 LLM Provider | 已完成 | 当前 `glm-5.3-flash` structured output 与完整 Agent 已真实调用；GLM/DeepSeek JSON object、Mock fallback 与错误隔离有测试 |
| 3 Agent Core | 已完成 | 动态 Planner、9 步 Tool Loop、State/Memory/Trace 持久化 |
| 4 API Migration | 已完成 | 微信身份、画像、推荐、反馈、匹配、Block/Report API |
| 5 Mini Program | 已完成，真机待验 | 六个页面、三个组件、集中 API 层；静态检查通过 |
| 6 Profile | 已完成 | PATCH allow-list 修复，画像序列化契约有测试 |
| 7 Agent Page | 已完成 | 提交、加载态、Top 3、本地推荐队列与 Trace 链路 |
| 8 Feedback | 已完成 | LIKE/PASS/NOT_RELEVANT；服务端状态不可由客户端伪造 |
| 9 Mutual Match | 已完成 | 双向 LIKE 才建 Match，Mock Match 禁止聊天 |
| 10 Cloud-ready DB | 代码与本地 SQL验证完成 | 本地 SQLAlchemy/SQLite；云端 CloudBase HTTP/PostgREST Adapter；初始化 SQL、事务 RPC 和 service_role 门禁已在 PostgreSQL 16 执行通过；CloudBase 控制台待发布 |
| 11 Deployment-ready | 本地完成 | Docker 实际构建、非 root 运行、健康检查和 HTTP 冒烟通过；云端待部署 |
| 12 Closed Beta | 清单完成，未开始 | 真机、云托管、5～30 人内测均需项目拥有者外部执行 |

## 15 项成功标准

| # | 标准 | 结果 |
|---:|---|---|
| 1 | Backend 本地可以启动 | 通过：本机和 Docker 均实际启动 |
| 2 | Seed 可以生成测试用户 | 通过：空数据库迁移后生成 50 用户、15 活动 |
| 3 | DeepSeek Provider 可配置 | 通过：环境变量与 Adapter 已实现 |
| 4 | Mock 测试不消耗真实 API | 通过：默认 Mock，真实集成测试需显式 opt-in |
| 5 | Agent End-to-End 测试通过 | 通过 |
| 6 | 小程序核心页面已实现 | 通过：代码与静态检查；真机布局待验 |
| 7 | 小程序 API 与 Schema 对齐 | 通过：路由/字段静态契约测试 |
| 8 | Profile 可以保存 | 通过：API E2E；真机交互待验 |
| 9 | 自然语言找搭子得到 Top 3 | 通过：实际 HTTP 返回 9 步计划与 Top 3 |
| 10 | LIKE/PASS 可以记录 | 通过 |
| 11 | Block 后永远不推荐 | 通过：硬过滤与 E2E 测试 |
| 12 | Mutual Match 正确 | 通过：双向意向测试 |
| 13 | Mock 用户明确标记 | 通过：Schema、页面和聊天门禁 |
| 14 | 隐私字段不泄露 | 通过：公开 schema allow-list 与测试 |
| 15 | 具备零成本内测部署适配能力 | 通过（适配能力）：Docker/CloudBase shared-PG HTTP API/callContainer/部署文档；实际费用与云发布待确认 |

## 本轮修复的关键缺口

- 小程序 API 地址从硬编码改为 `config.js` + 运行时覆盖，增加局域网一键启动脚本。
- 画像 PATCH 改为显式字段 allow-list，允许合法 `school` 更新，不再把服务端字段回传导致 422。
- 推荐队列和反馈移除在页面间持久化，补齐 Match detail API 导出与加载/重复点击状态。
- 微信真实用户以 `wechat_openid` 作为受信身份参与硬过滤；真实用户不再因缺少校邮而永久无候选。
- 无效 Bearer Token 不再静默降级为开发用户；客户端不能通过 feedback 伪造 MATCHED/BLOCK/REPORT。
- 微信凭据、网络异常和无效 JSON 统一返回安全错误，不泄露上游细节。
- Trace 记录实际 LLM provider 和 metadata，回退后能观察到 `:fallback`。
- DeepSeek Chat Completions 使用 `json_object` 模式，并把结构要求放入 Prompt；无效/空响应转为可控 503 或开发 Mock 回退。
- 增加 CloudBase PostgREST Repository Adapter、非 root Docker、健康检查和 `.dockerignore`，避免本地 Secret 进入构建上下文。
- 代码保留 `wx.cloud.callContainer` 适配能力；正式体验版使用 `@cloudbase/js-sdk` v3 + `API_MODE=sdk` 调用 CloudBase Gateway，并通过 CloudBase 匿名 OAuth 与 `X-Campus-Authorization` FastAPI JWT 实现双鉴权。历史本地 `apiMode` / `apiBaseUrl` Storage 不能覆盖正式 transport；`public/local/cloud` 仍保留。
- Alembic head 汇总为 `deployment/cloudbase_schema.sql`；CloudBase 运行期不需要 PostgreSQL 协议驱动。

DeepSeek 当前 Chat Completions 的 JSON Output 官方说明要求 `response_format={"type":"json_object"}`，且提示词必须包含 JSON 及结构约束；实现据此兼容：[DeepSeek JSON Output](https://api-docs.deepseek.com/guides/json_mode/)。

## 验证边界

已实际验证：Python 全量测试 `98 passed, 3 skipped`、Ruff、SQLite Alembic fresh/legacy upgrade、幂等 Seed、CloudBase HTTP CRUD/RPC 请求合同、初始化 SQL与事务函数、Mini Program 静态及 `callContainer` 契约、前端构建、Docker build/run/health、容器非 root、真实 HTTP Agent Top 3、局域网地址 `/health`，以及当前 Key 下 `glm-5.3-flash` 的真实 structured output/9 步 Agent（Trace 无 fallback）。

未实际验证：当前 CloudBase 环境中的 SQL初始化、云托管到 Data API 的真实 HTTPS 请求、真实 `jscode2session`、体验版和真实同学内测。微信 AppID/Secret 已由项目拥有者配置且 AppID 与小程序一致，但没有手机产生的一次性登录 code。当前使用 GLM，因此没有单独验证 DeepSeek Key。

后续执行文档：

- [真机联调](MINIPROGRAM_DEVICE_TEST.md)
- [云托管部署](CLOUDBASE_DEPLOYMENT.md)
- [封闭内测清单](CLOSED_BETA_CHECKLIST.md)
