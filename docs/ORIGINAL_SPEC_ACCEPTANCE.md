# 原始提示词完整验收矩阵

本文件对应根目录《Codex 提示词：从零实现校园交友 AI Agent.md》的 39 节要求。状态“完成”表示已有代码与可重复验证证据；“完成并扩展”表示在不破坏原始边界的前提下增加了能力。

## 逐项验收

| 节 | 状态 | 实现与证据 |
|---:|---|---|
| 1 产品目标 | 完成 | `CampusSocialAgent` 支持学习、运动、兴趣和活动搭子，自然语言到推荐、反馈、记忆形成闭环。 |
| 2 核心技术原则 | 完成 | Agent 负责路由、规划、Tool、观察和解释；认证、Block、Hard Filter、Safety 与最终 Score 均为程序规则。 |
| 3 技术栈 | 完成 | FastAPI、Pydantic v2、SQLAlchemy 2、SQLite、pytest；Mock 与 OpenAI-compatible Provider 均存在，无硬编码 API Key。代码兼容 Python 3.10+，覆盖原要求的 3.11+。 |
| 4 项目目录 | 完成 | `backend/app/{agents,api,llm,matching,memory,models,schemas,services,tools}`、`frontend`、`scripts`、`tests`、`docs` 职责分离。 |
| 5 AgentState | 完成 | `backend/app/schemas/agent.py` 使用 Pydantic 强类型与 `default_factory`，覆盖会话、意图、约束、计划、候选、反馈、安全和最终响应。 |
| 6 Agent Trace | 完成并扩展 | 持久化记录 step、action、tool、输入/输出摘要、状态、耗时；含事件 ID、TTL、合并与所有权，不保存隐藏思维链。 |
| 7 User Model | 完成并扩展 | 原始字段齐全；`verified` 为服务端后台真值。另有校内邮箱、USTC CAS 身份、密码哈希和 Token 撤销字段。 |
| 8 Profile 数据 | 完成 | 支持表单 PATCH 与自然语言结构化解析/应用，输出通过 `ProfileParseResult` 校验。 |
| 9 Intent Parser | 完成 | `parse_social_intent()` 与 Provider 结构化输出支持活动、时间、校区及软硬约束；Mock 覆盖 Demo 与考研复习语义。 |
| 10 Planner | 完成并扩展 | 推荐保留透明九步 Plan；不同任务生成不同计划，并在缺槽位或零候选时受控重规划。 |
| 11 Matching Engine | 完成 | 数据库召回 → hard filter → 特征计算 → 加权分数 → 稳定排序；LLM 不选择候选。 |
| 12 Hard Filters | 完成 | 覆盖 self、推荐关闭、未认证、Block、强拒绝、社交目标、硬校区、时间冲突。 |
| 13 Matching Score | 完成 | 六维权重严格为 0.25/0.20/0.20/0.15/0.10/0.10，返回 total、features 和中文 reasons。 |
| 14 Semantic Similarity | 完成 | `SimilarityProvider` 接口与 Jaccard/tag 实现，无大型模型依赖，并保留 Embedding 扩展点。 |
| 15 Tools | 完成 | BaseTool 统一 name、description、input schema、async execute；六类 Tool 的规定 action 均实现。 |
| 16 Memory | 完成并扩展 | Profile、Preference、Interaction、Session 四类 Memory 及规定接口齐全；Session 已持久化并带 TTL/CAS/租约。 |
| 17 Feedback | 完成 | 九类反馈持久化；候选衰减和标签移动平均均有界，PASS 不永久支配全部推荐。 |
| 18 Mutual Match | 完成并扩展 | 双向最新 LIKE/INTERESTED 才 MATCHED，只开放站内聊天；另实现了持久 REST 消息和未读数。 |
| 19 Block | 完成 | 任一方向 Block 后双方互不推荐，已有 Match 失效且聊天权限撤销。 |
| 20 Safety | 完成 | 检测诈骗、贷款、私密图片、危险外链等 risk signal；不由模型直接永久封号。 |
| 21 Conversation Agent | 完成 | 破冰和话题只使用公开画像、共同兴趣、当前活动与校区级公开场景。 |
| 22 Activity | 完成 | Activity 模型与 15 条公开 Mock 活动齐全，查询始终过滤 `public=False`。 |
| 23 Seed Data | 完成 | `python scripts/seed_users.py` 自动迁移并幂等生成 50 个差异化用户、15 个活动。 |
| 24 FastAPI | 完成并扩展 | 原始 11 个端点全部存在；另含认证、画像解析和 Mutual Match 会话接口，Swagger 可执行。 |
| 25 Agent API | 完成 | `await CampusSocialAgent(db).run(user_id, message, limit, session_id)` 返回 goal、intent、plan、matches、icebreakers、session。 |
| 26 Demo | 完成 | `user001` 画像与示例请求可执行九步推荐，返回 Top 3、六维分、原因、破冰与 Safety。 |
| 27 Feedback Demo | 完成 | PASS 写 Interaction，24 小时内暂时抑制该候选；端到端测试验证下一轮不立即出现。 |
| 28 测试 | 完成 | 指定测试模块全部存在，两个指定函数名均存在；另覆盖权限、迁移、并发持久化和聊天。 |
| 29 前端 | 完成并扩展 | React + Vite 实现登录、Profile、Agent Chat、Match 卡片、反馈、六维详情和站内聊天。 |
| 30 Privacy | 完成 | `public_user()` 使用 allow-list；后台认证和校内身份字段不输出给候选；公开画像模型不存在手机号、宿舍、实时位置或身份证字段。 |
| 31 数据来源规则 | 完成 | 只使用用户主动画像、公开 Mock 活动与显式交互，无爬虫、GPS、课表读取或自动私信。 |
| 32 配置 | 完成并扩展 | `.env.example` 包含原始六项及 JWT、CAS、Session/Trace TTL 等可选配置。 |
| 33 开发顺序 | 完成 | 实施记录按 Phase 保存实现、测试、修复与复验结果。 |
| 34 开发要求 | 完成 | 后端测试、Ruff、编译、迁移、Seed、前端构建和真实 HTTP Demo 均实际执行。 |
| 35 不要过度设计 | 完成 | MVP 未引入 Kubernetes、Kafka、Redis Cluster、多 Agent、复杂 RAG、LangChain 或 GPU 模型。 |
| 36 学习目标 | 完成 | AgentState、Planner、Tools、Memory、Matching、Feedback Loop、Trace 均为独立清晰模块。 |
| 37 README | 完成 | README 包含 Architecture、Loop、State、Planner、Tools、Matching、Memory、Feedback、Safety、DB、API、Demo、Tests、启动和 Roadmap。 |
| 38 启动目标 | 完成并扩展 | 原始 venv → pip → seed → uvicorn 顺序可用；另提供 `./start.sh` 一键启动前后端。 |
| 39 最终汇报 | 完成 | README、架构文档、动态 Agent 文档、实施记录和本验收矩阵共同覆盖 12 项最终汇报内容。 |

## 关键安全与可信边界

- 客户端不能提交或修改 `verified`；校内邮箱注册与 CAS 回调只能由服务端设置认证状态。
- 未认证用户不能密码登录、不能用 Bearer Token 访问业务 API，也不会进入推荐候选。
- 候选公开输出不含 `school_email`、`school_uid`、`school_display_name`、`password_hash`、`verified`。
- ProfileTool 只能更新明确白名单字段；ActivityTool 只返回公开活动；ConversationTool 只从公开共同点生成内容。
- 同一 Session 跨 Worker 的并发轮次由数据库租约阻止，Trace 不保存模型隐藏推理。

## 可重复验收命令

```bash
python -m ruff check backend scripts migrations tests
python -m ruff format --check backend scripts migrations tests
python -m compileall -q backend scripts migrations
python -m pytest -v
python -m alembic current
python -m alembic check
python scripts/seed_users.py
npm --prefix frontend run build
```

一键真实运行验收：

```bash
BACKEND_PORT=8010 FRONTEND_PORT=5180 BACKEND_RELOAD=false ./start.sh
```

浏览器检查前端和 `/docs`，或登录后提交：

```text
帮我找几个周六下午可以一起打羽毛球的人，最好西区，水平休闲一点。
```

## 2026-08-26 最终验收结果

```text
Python: 3.13.9
Ruff format: 94 files already formatted
Ruff check: All checks passed
compileall: success
pytest: 46 passed in 2.61s
Alembic current: 0007_repair_legacy_profile (head)
Alembic check: No new upgrade operations detected
Seed (已有库): added 0 users and 0 activities
数据库计数: 50 users / 50 verified / 15 activities / 15 public
Vite build: success
npm audit: found 0 vulnerabilities
```

随后在全新临时 SQLite 上执行一次 `./start.sh`。脚本从空库自动运行 `0001` 到 `0007`、Seed 50/15、启动 Uvicorn 和 Vite。真实 HTTP 验收结果：

```text
GET frontend: 200
GET /health: 200 {"status":"ok"}
POST /auth/login: user001
POST /agent/recommend: recommendation / find_activity_partner / 9 steps
Top 3: 阿青 0.8667, 小林 0.8250, 同学47 0.7417
每位候选: 6 个 score features
后台身份字段泄漏: 0
GET trace: 9 entries
```

按 `Ctrl+C` 后 8013/5183 端口均确认释放，临时数据库目录已删除。

## 有意扩展与当前 Mock

- 原始要求只需 Mock verification；项目增加了可配置 USTC CAS，但本地仍默认使用虚拟校内邮箱与 Demo 密码，真实部署必须配置学校服务。
- 原始要求不需要真实聊天服务器；项目增加了权限受控的 REST 站内消息，但尚无 WebSocket 实时推送。
- LLM 默认仍是确定性 Mock；OpenAI-compatible Adapter 已就绪，但需要部署者显式提供服务地址、模型与 Key。
- 50 个用户和 15 个活动全部是虚拟数据；Safety 是可审计规则信号，尚无人工审核后台。
- SQLite 适合本地 Demo；生产多 Worker 建议切换 PostgreSQL 并增加独立清理任务和指标。
