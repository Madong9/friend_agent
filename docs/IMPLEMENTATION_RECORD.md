# 实施与验收记录

记录日期：2026-08-16（Asia/Shanghai）

## 范围

工作区初始只有 1940 行需求文档，没有已有项目或 Git 仓库。本次从零实现了 Python/FastAPI 后端、SQLite 数据层、LLM 抽象、Agent/Planner/State/Trace、六种 Tool、确定性 Matching、四类 Memory、Feedback/Mutual Match/Block/Report/Safety、种子数据、React Web Demo、测试与文档。

## 分阶段实施

### Phase 0：检查

- 确认工作目录 `/home/robot/idea_work/friend_agent`。
- 读取完整需求文档。
- 确认 Python 3.13.9、Node 22.22.0；初始缺少 SQLAlchemy 和 httpx。

### Phase 1：配置、数据库、模型、Schema

- 建立环境配置、SQLAlchemy engine/session、七个模型和 Pydantic v2 Schema。
- 首次测试：SQLite User round trip，`1 passed`。
- 环境中 ROS pytest 插件误加载且缺 `lark`；通过 `pytest.ini` 明确禁用无关 ROS 插件，不改变业务代码。

### Phase 2：Seed 与 Matching

- 实现 Jaccard/时间 overlap、alias 规范化、Hard Filter、六维加权评分和稳定排序。
- 验证同兴趣同时间得分更高、本人/时间冲突被过滤：`3 passed`。
- Seed 首次输出 `added 50 users and 15 activities`，第二次输出 `added 0 users and 0 activities`，数据库计数保持 50/15。

### Phase 3：Memory、Feedback、Block

- 实现持久画像/偏好/Interaction Memory 与进程内 Session Memory。
- 实现有界衰减、Mutual Match 和双向不可推荐 Block。
- 测试结果：`4 passed`。

### Phase 4：LLM、Parser、Planner

- 实现 Provider 抽象、Mock 和 OpenAI-compatible Adapter。
- Profile/Intent 全部通过 Pydantic structured output。
- 实现透明九步 Planner；测试结果：`3 passed`。

### Phase 5：Tools

- 实现 BaseTool 与 Profile、Matching、Memory、Safety、Activity、Conversation Tool。
- 工具集成测试覆盖 profile、candidate search、诈骗/外链 signal 和安全破冰：`1 passed`。

### Phase 6：Agent Loop 与 Trace

- CampusSocialAgent 真实串联 Planner、State、LLM、Tools、Memory 和 Matching。
- Trace 恰好记录九步结构化操作，不记录隐藏思维链。
- Recommendation 和 PASS 后改排端到端测试：`2 passed`。

### Phase 7：FastAPI

- 实现规格要求的全部路由和额外自然语言画像路由。
- TestClient 覆盖推荐、Trace、反馈、Mutual Match、Block、Report、用户 CRUD：`2 passed`。

### Phase 8：Web Demo

- 实现 Profile、Agent Chat、Match Cards、反馈按钮和六维 Match Detail。
- `npm install`：19 packages，0 vulnerabilities。
- `npm run build`：Vite build 成功；JS gzip 63.03 kB，CSS gzip 1.72 kB。

### Phase 9：最终验收

执行：

```text
pytest -v
ruff check backend scripts tests
python -m compileall -q backend scripts
npm run build
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
curl /health
curl POST /agent/recommend
```

结果：

```text
pytest: 16 passed in 0.37s
ruff: All checks passed!
compileall: success
vite: built successfully
GET /health: HTTP 200, {"status":"ok"}
POST /agent/recommend: HTTP 200, Top 3 + plan + score + reasons + icebreakers + safety
```

真实 Demo 的意图解析为 `find_activity_partner / 羽毛球 / 周六下午 / 西区 / 休闲`，九步 Plan 完整，Safety 为 allow。Top 3 为阿青、小林、可欣，前两名在西区，第三名因校区只是软偏好而保留。

## 修复记录

- 安装缺失 SQLAlchemy、httpx、pytest-asyncio 和 Ruff。
- 隔离宿主 ROS pytest entry point，保证直接 `pytest -v` 可运行。
- Ruff 首轮发现两个未使用 import，移除后全通过。
- 最终审核补充了候选级 Safety 检查；Safety 步骤同时检查请求消息和排序候选。

## 验收结论

MVP 已达到本地运行目标。核心规则均有程序化实现与测试证据；没有 API Key、真实学生数据或隐私字段写死在仓库中。当前生产化阻碍是缺真实鉴权/校园认证、聊天与审核系统，以及持久化 Trace/Session Memory，这些均已明确记录而没有伪装成完整能力。

## 2026-08-25 复审完善

在原有 16 项测试全绿的基础上再次审计了需求覆盖、长期运行行为、安全边界和 UI 状态，修复了以下问题：

- 将“历史最后 20 个推荐累计抑制”改为“24 小时 PASS + 紧邻上一推荐页”，防止多次刷新后候选池逐步耗尽。
- 明确活动命中改用 containment，候选包含目标活动时 activity 特征为 1.0；兼容社交目标也按可接受目标集合满分处理。
- Mutual Match 只参考双方最新有效决策，后续 PASS 会撤销旧的 INTERESTED 对成 Match 的作用。
- Block 会把已有 Match 改为 `BLOCKED`，`/matches` 不再返回并立即撤销聊天资格；Block 后也禁止继续反馈建立 Match。
- 用户创建接口不再接受客户端 `verified` 字段，Mock 认证状态由服务端持有；用户写入增加长度、空白和额外字段验证。
- Safety 外链从字符串前缀判断改为 hostname 解析，拦截伪装校内域名。
- SQLite 连接启用 foreign keys、30 秒 busy timeout 和 pool pre-ping；测试 fixture 显式 dispose engine，消除 ResourceWarning。
- `.env` 可自动加载；`DEBUG_AGENT_TRACE=false` 可以真正关闭 Trace 保存；Trace 和 Session Memory 都增加 500 条进程内上限。
- OpenAI-compatible Adapter 支持注入 HTTP transport，并增加请求契约/structured output 测试。
- 修复前端切换 Demo 用户时旧画像短暂残留以及 uncontrolled form 不刷新的问题。

完善后验收：25 项测试通过，后端覆盖率 94%，Ruff 与格式检查通过，Vite 构建通过，npm audit 0 漏洞。真实 Uvicorn 隔离库验收确认：连续三页为 A→B→A 轮换且相邻页无重复、PASS 下一轮不出现、9 步 Trace 完整、Block 后聊天资格撤销。

## 2026-08-25 第二阶段：认证、迁移与站内聊天

从可运行 Demo 继续推进到具备基础身份边界的内测原型：

- 新增随机盐 scrypt 密码哈希、PyJWT HS256 Access Token、`POST /auth/login` 与 `GET /auth/me`。
- Agent、Trace、画像、Feedback、Block、Report、Match 和聊天接口全部从 Bearer Token 推导当前用户，不再信任请求体中的 `user_id`。
- Trace 增加所属用户，其他登录用户读取返回 403；画像路径也执行对象级本人校验。
- 新增 Alembic `0001` 兼容基线与 `0002` 认证/消息迁移。Fresh DB 可完整创建，已有 SQLite 可保留数据并补列/表。
- 当前真实 `campus_social.db` 已升级到 `0002_add_auth_and_messages`，50 个 Demo 用户均补充登录密码哈希。
- 新增持久化 `messages` 表、会话列表、历史消息、未读数和标记已读 API。
- 只有有效 Mutual Match 且无 Block 的双方可以聊天；风险消息返回 422 且不写数据库，Block 立即撤销历史消息读取与新消息发送资格。
- React Web 新增登录页和“我的匹配”聊天页，移除可随意切换 `user_id` 的入口，所有敏感请求自动携带 Bearer Token。

验收结果：31 项测试通过、覆盖率 94%、Ruff/格式/编译通过、Alembic `current=head` 且 `check` 无待迁移差异、Vite 构建通过、npm audit 0 漏洞。真实 Uvicorn 临时数据库完整验证了 401 未授权拒绝、对象级 403、推荐、Trace 所有权、Mutual Match、安全消息、风险消息拦截以及 Block 撤销聊天。

## 2026-08-26：受控动态 Agent 升级

本阶段先修复认证和迁移继续演进后留下的 3 个过期测试：JWT 测试改为验证 `sub`、`ver`、`type` 的完整 payload；迁移测试不再写死旧版本号，而是读取 Alembic 当前 head，并验证 USTC identity、token revocation、school UID/display name 字段确实存在。

随后将固定九步推荐 workflow 升级为受控动态 Agent：

- 新增 `TaskRouter`，支持找搭子、查活动、画像更新、推荐解释、继续澄清和确认放宽约束；
- Planner 为不同任务生成不同计划，同时保持原推荐九步兼容；
- 信息缺少活动或时间时，Agent 在解析后重规划为追问，不执行无意义检索；
- `AgentRequest` 新增可选 `session_id`，下一轮可合并上一轮部分 Intent；
- Session 绑定用户，其他用户续接返回 403；
- Hard Filter 后零候选会生成观察步骤和一个最小放宽建议，只有收到明确确认才修改对应条件并重试；
- Session 保存最近推荐，可回答“为什么推荐某人”，解释使用程序化 `total` 和 `reasons`；
- 活动查询通过 `ActivityTool`，自然语言画像更新通过结构化 Parser 和 `ProfileTool` 白名单；
- 同一个 Session 的 Trace 跨轮追加并连续编号；
- React 页面自动携带 Session、展示追问/活动/解释，并提供“新会话”。

新增 `tests/test_dynamic_agent.py` 覆盖多轮补槽、动态 Plan、零候选协商、活动/画像/解释分支、Session 越权和 HTTP 多轮续接。回归结果为 `38 passed`，并消除了 Alembic 配置弃用警告。详细设计和调用协议见 `docs/DYNAMIC_AGENT.md`。

## 2026-08-26：Session 与 Trace 数据库持久化

为支持服务重启和多 Worker，本阶段移除了进程级 `_session_memory` 与 `_traces` 字典，新增 Alembic `0005_agent_state_persistence`，并用 `0006_agent_session_turn_lease` 兼容修复曾被 `create_all()` 提前创建的表：

- `agent_sessions` 保存用户、会话状态、版本、创建/更新时间、滑动过期时间和当前轮次租约；
- `agent_traces` 保存用户、结构化事件列表、版本、更新时间和过期时间；
- Session 默认 24 小时未活动后过期，Trace 默认保留 7 天且每个 Session 最多保留 1000 项；
- 应用启动以及 Session/Trace 读写会清理已过期记录；
- Session JSON 合并使用版本号 compare-and-swap，避免独立 Worker 更新时无条件覆盖；
- 同一个 Session 的并发轮次使用数据库租约串行化，冲突返回 HTTP 409，异常退出后租约可超时接管；
- TraceEntry 增加不对 API 暴露的事件 ID 和记录时间；Trace 保存按事件 ID 合并，并通过版本号重试，两个陈旧 Worker 的新增步骤都能保留；
- Trace API、Agent Loop、MemoryTool 均改为使用请求对应的 SQLAlchemy Session，不再依赖进程静态状态；
- 新增 TTL、Trace 上限和租约时间环境配置。
- 移除 API 启动时的隐式 `create_all()`，启动阶段只验证必要表/列，数据库结构统一由 Alembic 管理。

新增 `tests/test_agent_persistence.py`，用多个独立 SQLAlchemy Session 模拟进程重启与不同 Worker，覆盖多轮恢复、Session 字段合并、陈旧 Trace 写入合并、轮次租约冲突与过期删除。连同迁移结构断言，当前回归基线为 `43 passed`。

## 2026-08-26：考研意图与一键启动完善

- 将“复习、备考、刷题、考研”统一规范化为 `find_study_partner / 自习`，该规则位于 Provider 之后，因此 Mock 和真实 LLM 都受相同语义边界约束；
- “找一个在西区……”会把校区识别为硬条件，“最好西区”仍保持软偏好；
- 学习搭子请求未提供时间时，如果公开画像已有可用时间，会直接用于软排序而不重复追问；
- 前端增加同步请求锁、1.5 秒同文本重复抑制、空输入禁用和成功后清空输入，避免快速点击产生多个相同 POST；
- 新增根目录 `start.sh`，自动创建本地 `.env`、检查/安装依赖、执行 Alembic、幂等 Seed、等待后端健康、启动 Vite，并在 Ctrl+C 时联动停止两端；
- Seed 不再调用 `create_all()`，保持 Alembic 是唯一 Schema 来源。

真实验收使用原句“我要准备考研，你帮我找一个在西区一起复习的搭子”，一次 POST 直接返回 `find_study_partner`、`activity=自习`、`hard_constraints=[campus]` 和 3 位西区候选。`./start.sh` 在备用端口完整启动后，后端健康检查和前端 HTML 均成功，Ctrl+C 后两个端口都确认关闭。当前回归基线为 `45 passed`。

## 2026-08-26：原始 39 项最终收口

本轮重新按《Codex 提示词：从零实现校园交友 AI Agent.md》的 39 节逐项审计，不把既有功能通过视为全部要求天然满足。收口内容包括：

- 恢复数据库与 ORM 中服务端持有的 `verified` 真值；密码登录、Bearer Token 和 Hard Filter 都拒绝未认证用户，公开 DTO 与 Tool 输出不暴露该后台字段；
- 将 Feedback 真正接入 Preference Memory：LIKE、PASS 等公开候选反馈会对兴趣/活动标签产生有界移动平均，并以 30% 比例参与 feedback 特征；
- 补齐 Tool 契约测试，覆盖 `generate_topics`、私有活动过滤、Profile 更新白名单、`check_block` 与公开字段 allow-list；
- 新增 `0007_repair_legacy_profile`，让只有部分 `users` 列的旧库补齐原始 Profile 字段并保留已有行；统一 ORM 唯一索引声明后，Alembic autogenerate 无漂移；
- `python scripts/seed_users.py` 现在会先升级到 Alembic head，严格支持提示词中的空库启动顺序，同时保持二次执行 0 新增；
- 新增 `docs/ORIGINAL_SPEC_ACCEPTANCE.md`，记录 39 节要求、实现位置和验证证据。

最终验收在全新临时 SQLite 上通过 `./start.sh` 自动执行 7 个迁移并写入 50 个已认证虚拟用户和 15 个公开活动。真实 HTTP 流程确认前端 200、健康检查 200、Demo 登录成功、推荐 200、九步 Trace 完整；示例羽毛球请求返回阿青 0.8667、小林 0.8250、同学47 0.7417，三位候选均有六维特征且后台身份字段泄漏数为 0。Ctrl+C 后前后端端口全部释放，临时库已删除。

最终结果记录在完整验收矩阵中；后端回归基线为 `46 passed`，Ruff 格式/规则、compileall、Alembic current/check、Vite build 和 npm audit 均通过。

## 2026-08-28：微信小程序 Phase 10～12 收口与真实性复审

本轮没有把“71 项测试已绿”直接等同于整个微信迁移完成，而是重新对照 63 节规格检查小程序请求字段、身份边界、真实用户候选资格、LLM 厂商协议、容器和真机路径。保留了原有 `CampusSocialAgent`、动态 Planner、Tool Loop、Matching、数据库 Session/Trace、Feedback 和 Safety 架构，没有改写为固定页面 workflow。

### 审计发现与修复

1. 小程序画像页把 GET 响应中的 `id/is_mock/created_at` 原样 PATCH，触发后端 extra-forbid 422；改为显式字段 allow-list，并为合法的 `school` 自助更新补齐 Schema。
2. 推荐页没有保存 Agent 返回的推荐队列，Matches 页因此可能为空；反馈后的移除也没有持久化。新增本地推荐队列 service，Agent/Matches/Detail 三页共享，并补齐请求 loading/disabled 状态。
3. `services/api.js` 写死 localhost，不适合真机；新增 `miniprogram/config.js`、storage/ext config 覆盖以及 `scripts/start_mobile_backend.sh`，自动打印局域网 URL。
4. 新微信用户没有校邮，而 Hard Filter 只认可 `school_email`，导致真实微信用户永远不能作为候选；受信身份调整为校邮或已映射的 `wechat_openid`。
5. 开发免登录模式会在无效 Bearer Token 时静默切换成 dev user；现在只有完全无 token 才能使用 dev identity，无效 token 始终 401。
6. Feedback enum 暴露内部 `MATCHED/BLOCK/REPORT` 状态；现在公共反馈只允许 LIKE/PASS/NOT_RELEVANT，Block/Report 必须使用专用路由。
7. 微信身份调用未完整处理 Secret 缺失、网络失败和非 JSON；现统一转换为清洗后的服务错误，并测试首次创建与复用。
8. LLM Trace 在 fallback 前提前记录 provider，观察不到真实回退；现每个 LLM 步骤记录实际 provider 和 metadata。
9. DeepSeek `/chat/completions` 的 JSON Output 与通用 `json_schema` 不兼容；新增 `LLM_RESPONSE_FORMAT=auto`，DeepSeek 自动使用 `json_object` 并在 system prompt 中注入完整结构约束。空响应、HTTP 错误、非法 JSON 和 schema 错误统一封装，不把上游响应或 Key 暴露给客户端。
10. 当时的云数据库草案缺少对应驱动，Docker 使用 root 且没有健康检查；先补齐非 root 用户、健康检查和 `.dockerignore`，数据库方案随后在 PG 模式环境阶段统一切换到 Psycopg/PostgreSQL。

### 新增文件

- `.dockerignore`
- `miniprogram/config.js`
- `miniprogram/utils/profile.js`
- `miniprogram/services/recommendations.js`
- `scripts/start_mobile_backend.sh`
- `scripts/check_miniprogram.py`
- `tests/test_miniprogram_static.py`
- `tests/test_cloud_readiness.py`
- `docs/MINIPROGRAM_DEVICE_TEST.md`
- `docs/CLOUDBASE_DEPLOYMENT.md`
- `docs/CLOSED_BETA_CHECKLIST.md`
- `docs/MINIPROGRAM_SPEC_ACCEPTANCE.md`

### 主要修改文件

- 后端：`auth.py`、`auth_service.py`、`wechat_identity.py`、`filters.py`、`feedback.py`、`user.py`、`trace.py`、`campus_agent.py`、LLM Provider/Factory/Config、Agent/Auth API。
- 小程序：统一 API 层、Profile/Agent/Matches/Match Detail 页面及对应模板/样式。
- 工程：`Dockerfile`、`requirements.txt`、`.env.example`、`.gitignore`、`README.md` 和相关测试。

### 实际验证

- Python 回归：`81 passed, 3 skipped`；3 个 skip 都是需要显式启用且会消耗额度的真实 LLM 集成测试。
- Mini Program 静态合同：页面/组件文件、JSON、Node JS 语法、WXML/WXSS、API exports、后端路由和客户端敏感信息检查通过。
- Docker：镜像实际构建成功；容器迁移到 `0008`、Seed 50 用户/15 活动、以 uid `app` 非 root 运行、health 状态 healthy。
- HTTP：容器内实际请求 `/health`、`/users/me` 和 `/agent/recommend`；羽毛球请求返回 9 步计划与阿青 0.8667、小林 0.825、同学47 0.7417，Trace 记录 provider=mock。
- 局域网：移动后端脚本实际监听 `0.0.0.0`，localhost 和自动识别的局域网 IP 均可访问 `/health`，停止后端口正常释放。

真实 DeepSeek、微信开发者工具/手机扫码、`jscode2session`、CloudBase Run 和 5～30 人体验需要外部 Key、设备或账号权限，未伪造为已完成。云数据库方案后来根据已创建的 PG 模式环境改为 CloudBase PostgreSQL。操作与验收边界写入新增的真机、云托管、封闭内测和 Phase 验收文档。

### 2026-08-28 GLM 与微信凭据校准

项目实际 `.env` 使用 USTC OpenAI-compatible 网关和 `glm-5.3-flash`，并已配置微信 AppID/Secret；后端 AppID 与小程序项目配置一致。GLM 官方 Chat Completions 与 DeepSeek 一样使用 `json_object` 而非 `json_schema`，因此 `auto` 模式增加按 `glm-` 模型名识别，兼容被机构网关隐藏的上游厂商。

第一次真实 GLM 请求还发现宿主设置了 `socks://` 代理；httpx 只接受 `socks5://`，客户端会在发请求前失败并触发 Mock fallback。依赖改为 `httpx[socks]`，同时 LLM 和微信客户端默认 `OUTBOUND_HTTP_TRUST_ENV=false`，不再被宿主代理静默劫持；确需代理时可以显式开启并使用受支持的 URL。关闭宿主代理后的最小真实 GLM structured-output 请求成功返回，证明当前 Key、网关、模型和 `json_object` 协议可用。

随后在全新临时数据库中强制 `LLM_FALLBACK_TO_MOCK=false`，实际运行原句“我要准备考研，帮我找一个在西区一起复习的搭子”：返回 `recommendation`、`find_study_partner`、9 步 plan 和 3 名候选，Trace 的 `parse_intent` tool/provider 都是 `openai_compatible`，没有 `:fallback`。GLM 协议新增 MockTransport 回归测试后，全量基线更新为 `82 passed, 3 skipped`。

### 2026-08-28 手机域名校验修复

首次手机扫码报告 `request:fail url not in domain list`。复查确认本地 private config 已有 `urlCheck=false`，但普通“预览”仍不是局域网 HTTP 的可靠调试路径，而且开发者工具模拟器的 storage 不会自动同步到手机。公共 `project.config.json` 补齐 `urlCheck=false`，真机文档和启动脚本改为明确使用“真机调试”，并要求在连接后的远程控制台写入手机自己的 `apiBaseUrl`。网络错误现在附带实际请求 URL，能直接识别手机误用 `127.0.0.1` 的情况；普通预览和体验版继续要求 HTTPS 合法域名。

修正 URL 后手机进一步报告 `ERR_ADDRESS_UNREACHABLE`。电脑默认网卡地址为 `100.64.158.53/18`，属于 `100.64.0.0/10` 共享地址段，后端同时确认仍监听 `0.0.0.0:8000` 且本机 health 正常，因此判定为校园网/公共 Wi-Fi 终端隔离。启动脚本新增共享地址段告警，真机文档要求先从手机浏览器验证 `/health`，失败时切换手机热点、家庭局域网或 HTTPS 部署。

### 2026-08-28 CloudBase PostgreSQL 与 callContainer 收口

项目拥有者已创建 `campus-social` CloudBase 免费体验环境，并明确它是 PostgreSQL 模式。本轮保留该环境，把云部署从旧 MySQL 草案整体切换为 PostgreSQL，本地 SQLite 和所有 Agent/Matching/Memory/API 业务逻辑保持不变。

- 这一阶段曾按“可协议直连”的假设增加 PostgreSQL wire driver；共享集群能力确认后，该方案与驱动已完整撤销，改为下一节的 HTTP API Adapter；
- 审计 Alembic 0001～0008 后，在真实 PostgreSQL 16 fresh migration 中发现 Alembic 默认 `alembic_version.version_num VARCHAR(32)` 无法容纳 0003 起的长 revision ID；0002 在 PostgreSQL 上先将其扩为 `VARCHAR(128)`；
- 真实 PostgreSQL 16 已验证全新库 0001→0008、50 用户/15 活动幂等 Seed、`alembic current/check`、JSON 列，以及仅有 `users(id)` 和一条历史记录的 legacy migration；历史行和默认值均保留；
- 小程序统一 API 层增加 CloudBase 模式：配置环境 ID 后执行 `wx.cloud.callContainer` 并设置 `X-WX-SERVICE`，未配置时继续使用本地 `wx.request`；
- 新增可执行 Node 契约测试，确认 `/agent/chat` 的 method、data、JWT、环境 ID 和服务名均正确传入 `callContainer`，且不会误调用 `wx.request`；
- 云托管手册改为现有 PG 模式环境的连接参数、Psycopg URL、环境变量、发布与日志验收步骤，明确 Secret 只由项目拥有者在控制台填写。

该阶段回归、SQLite migration/Seed、Vite、Docker 和 `/health` 均通过；但后续控制台确认免费 shared-PG 不支持协议直连，因此不再作为当前云部署证据。

### 2026-08-28 CloudBase shared-PG HTTP API 改造

控制台确认免费 PostgreSQL 是共享集群、没有 PostgreSQL 协议直连，升级入口暂不可用。本轮不删除现有环境、不要求独享集群，彻底撤销 wire-protocol 云端方案：

- 本地保持 `DATA_BACKEND=sqlite`、SQLAlchemy 和 Alembic；云端使用 `DATA_BACKEND=cloudbase_http`；
- 新增 `repositories/cloudbase_http.py`，把现有服务消费的窄 Session/Unit-of-Work 接口翻译为 PostgREST CRUD，AgentState、Planner、评分、过滤、Memory 数据结构和 API Schema 不变；
- Mutual Match + Feedback 偏好学习、Block、Report、消息发送、Agent Session 租约和 Trace 合并封装为 PostgreSQL Function，通过 `/rpc/{function_name}` 单事务调用；
- 每个 `SECURITY DEFINER` RPC 都检查 JWT claim `role=service_role`，不把 RPC 可达性或 `GRANT EXECUTE` 单独当作安全边界；
- 新增 `scripts/generate_cloudbase_schema.py`，从当前模型与 Alembic 0001～0008 head 生成 `deployment/cloudbase_schema.sql`，包含表、索引、默认值、版本和事务函数；
- requirements 移除 PostgreSQL wire driver，CloudBase staging 不再需要 host、port、database、user 或 password；
- Docker 启动的 Seed 在 HTTP 模式跳过 Alembic，通过 Adapter 幂等写入；服务 lifespan 通过 Data API 做 schema 可访问检查；
- `.env.example`、README、架构、验收、部署手册和部署包全部切换为环境 ID + 后端 API Key。

初始化 SQL已在一次性 PostgreSQL 16 中完整执行；随后以 `service_role` 真实验证表 CRUD、双向 LIKE 创建 Match、偏好写入、Block 原子修改 Match、Report、真实用户消息、Session acquire/release 和 Trace 保存，并确认 anon 角色无法调用特权 RPC。CloudBase HTTP Adapter 使用 MockTransport 验证了 REST path、过滤表达式、精确 count、JWT header、CRUD、JSON 原地更新、RPC 参数和错误清洗。最终 Python 全量回归为 `98 passed, 3 skipped`，本地 SQLite 业务测试全部保留通过。

## 2026-08-29：找搭子闭环与可选 AI 性格推荐

本轮目标是把产品从“一次性返回推荐卡片”推进为持续找搭子的 Agent，同时让大模型参与非敏感社交风格分析，但不把它变成身份判断、心理测评或不可解释的最终裁决。原有 Planner、Hard Filter、Feedback、Mutual Match、Memory 和 Safety 规则均保留。

### 陌生活动与持续需求闭环

- 用户明确说“找飞盘搭子”等任意活动时，结构化 Intent 允许开放词表；活动文本通过消息显式出现校验、长度上限、去重和 Safety 后加入本人 `activities`，不会污染公共 `activities` 活动事件表。
- Agent 在 Matching Tool 返回后增加活动精确约束：优先只保留公开画像中包含相同活动的用户。没有精确候选时，不会自动拿其他运动凑数，而是询问是否同意放宽活动。
- 零结果写入 `partner_requests`，按 Session 幂等更新，默认有效 14 天，支持 `OPEN / PAUSED / FULFILLED / EXPIRED`。列表读取时自动标记过期需求；重新开启已过期需求会续期 14 天。
- 后续用户提出相同规范化活动且实际推荐包含先前请求者时，为先前请求者创建一次去重的 `NEW_PARTNER_CANDIDATE` 通知。通知不暴露微信 openid、校邮、学号或私人联系方式。
- 多轮澄清继续使用持久化 `session_id`；只放宽被确认的字段。例如同意放宽时间后仍保持原活动精确条件，不会再次询问活动，也不会暗中同时放宽活动。

### 可选 AI 社交风格分析

- 新增 `POST /users/me/personality/analyze`。请求必须显式 `consent=true`；小程序还要求用户先打开同意开关并输入至少 10 个字。
- LLM Prompt 只允许从本次主动自述提取五个有限维度：互动能量、计划习惯、沟通方式、群体偏好和熟悉节奏；明确禁止推断心理疾病、智力、政治、宗教、性取向、健康、家庭、经济情况，也不使用 MBTI 或确定性人格标签。
- 数据库只保存有限枚举标签、温和中文摘要和更新时间，不保存分析原文或完整 Prompt。用户可通过 `DELETE /users/me/personality` 一次清空同意状态、标签、摘要和更新时间。
- 性格兼容度只在双方都有标签时启用，最终分数为原确定性总分的 90% 加兼容度 10%；任一方缺失时完全沿用原总分。性格不进入 Hard Filter，不能覆盖 Block、认证、安全、活动精确匹配或时间规则。
- 候选详情只展示用户主动公开的摘要；分数条增加“社交风格”维度，并在高兼容时给出“公开社交风格较合拍”的解释。

### 小程序、身份与治理

- Agent 页把消息、Session、当前约束和快捷回复持久化到本地 Storage，重开页面可继续同一会话；增加“新需求”、活动/时间/校区约束提示和确认快捷按钮。
- 新增通知与需求页，可读取通知、标记已读、暂停/重开需求；新增 Mutual Match 站内聊天页，采用 4 秒 REST 轮询并沿用后端已读、Block、Mock 禁聊和消息 Safety 规则。
- Profile 页新增可撤销 AI 社交风格分析；匹配详情展示可解释性格摘要；举报改成固定类别加文字说明。
- 新增 `REQUIRE_CAMPUS_VERIFICATION`。为 `true` 时未认证微信用户仍能登录和维护画像，但 Agent、匹配、反馈、聊天、举报、需求与通知统一返回 403。当前封闭内测尚无微信账号校园绑定入口，因此 staging 应暂时保持 `false`。
- 新增 `scripts/beta_metrics.py`，输出画像完成、需求履约、LIKE/PASS、Mutual Match、消息、未读通知、待审核举报和次日回访聚合指标；不输出用户 ID、消息、Prompt、性格原文或 Secret。

### Schema 与部署

- Alembic head 升级为 `0009_partner_loop_personality`：增加 `partner_requests`、`notifications`，为 `users` 增加校园认证与性格字段，为 `reports` 增加结构化类别。
- `deployment/cloudbase_schema.sql` 已从 0009 metadata 重新生成，包含已有 CloudBase 环境的兼容性 `ALTER`、新表/索引/默认值、service role 权限和更新后的 `campus_report_user` RPC。
- 本地 `campus_social.db` 已从 0008 原地升级到 0009，旧用户、反馈、报告和消息均保留。CloudBase shared-PG 不运行 Alembic，必须在 SQL 编辑器执行最新生成文件后再部署新容器。

### 验证证据

- `pytest -q`：`128 passed, 3 skipped`；跳过项仍是需显式启用且会调用真实外部 LLM 的集成测试。
- `ruff check backend tests scripts migrations`：通过。
- `python scripts/check_miniprogram.py`：页面/组件、JSON、JavaScript、WXML/WXSS、API facade、后端路由和客户端 Secret 边界全部通过。
- 新回归覆盖：四轮会话只放宽时间、陌生活动后续发现与通知、通知对象权限、需求到期/重开、性格分析同意/删除、性格评分缺失回退与 10% 上限、校园认证边界、中文时间变体规范化、fresh/legacy 0009 migration 和 CloudBase Schema 同步。

### 2026-08-29 公网 HTTPS 小程序 transport 校准

控制台进一步确认：当前 PostgreSQL CloudBase 环境无法通过微信云开发关联，但云托管公网 HTTPS 已通过小程序 `wx.request` 真机验证。因此正式体验版不使用 `wx.cloud.callContainer`，并继续保留当前配置：公网 `API_BASE_URL` + `API_MODE='local'`。这里的 `local` 是历史 transport 名称，不表示目标必须是本机地址。

为减少后续误解，`config.js` 新增 `public/http` 两个等价别名：`local/public/http` 均走 `wx.request`；只有 `cloud` 和云配置完整时的 `auto` 才走 `wx.cloud.callContainer`。没有修改现有 `API_MODE='local'`，也没有改变已经验证的请求行为。README、云部署手册、真机手册、内测清单和迁移验收说明均已改为公网 HTTPS 方案，并明确体验版不要切换到 `cloud/auto`。新增两个 Node transport 合同用例分别验证 `public` 和 `http` 必须调用 `wx.request`，当前全量基线更新为 `130 passed, 3 skipped`。

### 2026-08-29 CloudBase 0008→0009 SQL 顺序修复

已有 CloudBase 数据库执行第一版 0009 汇总 SQL 时，在 `ix_reports_category` 报 `SQLSTATE 42703`。根因是 `CREATE TABLE IF NOT EXISTS reports (...)` 对已存在的 0008 表不会补列，而 metadata 索引遍历发生在兼容性 `ALTER TABLE reports ADD COLUMN category` 之前。全新数据库因此正常，原地升级失败。

生成器现将全部 0009 旧表兼容操作提前到索引遍历之前，固定顺序为：建缺失表 → 补旧表字段/回填 → 建索引 → 设置默认值 → 版本/RPC。系统审计确认 0009 在旧表上新增 `users` 五个校园认证/性格字段和 `reports.category`；`reports.category` 是唯一立即被新索引引用的字段，六个字段现在都在任何依赖语句之前创建。

新增固定的完整 0008 PostgreSQL schema fixture，以及使用本地 `postgres:16-alpine` 的真实升级测试。测试写入两名历史用户、历史举报、交互、偏好和活动，执行实际 `generate()` 产物，并验证：六个旧表新字段存在、分类索引存在、需求/通知表存在、版本为 0009、校内身份回填正确、历史字段和值完整不变、旧举报自动得到 `OTHER`，且第二次执行仍不丢数据。全量结果为 `132 passed, 3 skipped`，Ruff 通过。

### 2026-08-30 体验版 Storage 地址隔离

真机体验版仍请求历史 `http://100.64.158.53:8000`，定位为 `getApiBaseUrl()` 无条件优先读取长期保存的 `apiBaseUrl`。这使公网发布配置和本地调试覆盖缺少明确边界。

体验版现改为 `API_MODE='public'`。`public/http` 继续走 `wx.request`，但固定使用代码中的公网 HTTPS；只有编译时显式 `local` 才允许从 Storage 或 ext-config 覆盖 `apiBaseUrl`。发布运行模式不再读取 Storage/ext-config 的 `apiMode`，因此旧的 `apiMode='local'` 也无法把体验版降级回本地 transport。统一 API 层把已解析的 transport mode 传给 `getApiBaseUrl(mode)`，`cloud` 分支仍保持 `wx.cloud.callContainer`，后端没有变化。

Node 合同测试覆盖三条路径：`public/http` 在 Storage 同时存有 `apiMode='local'` 和 `http://100.64.158.53:8000` 时仍请求正式 HTTPS；显式 `local` 仍接受 `127.0.0.1` 覆盖；显式 `cloud` 继续传递 env、service header、JWT、method、path 和 body 给 `callContainer`。新增独立小程序源码打包脚本，排除 private config、`.save`、`.env`、后端和本地数据库。

最终验证结果：Ruff 全部通过，Pytest 为 `132 passed, 3 skipped`，小程序 manifest/API/JavaScript/秘密边界静态检查通过，两个 ZIP 均通过压缩完整性检查。部署包 `cloudbase-campus-social-agent.zip` 的 SHA256 为 `20462cee7e84e07e8e04e3366d0a69b1f0738235f5a1b985ea546d0d874cb1f8`；体验版源码包 `campus-social-miniprogram.zip` 的 SHA256 为 `600aa1b1d196ee4b33f755b10dda5ec6a4cc79df43a53cc8473802af9ee7deab`。

### 2026-08-30 CloudBase 冷启动超时余量

公网健康检查实测 CloudBase 首次缩容唤醒约需 21 秒，普通请求原有 20 秒客户端 timeout 可能使首次 `/auth/wechat` 在服务即将就绪时提前失败。统一小程序请求层现将普通接口 timeout 调整为 30 秒，`/agent/chat` 保持 60 秒；网络 transport、Base URL、JWT 登录、401 重试和后端业务逻辑均未改变。

新增 `wx.request` 合同测试在同一 public transport 下同时断言 `/users/me=30000ms` 和 `/agent/chat=60000ms`，静态检查也固定验证这组配置。最终 Ruff 和小程序静态检查通过，Pytest 为 `133 passed, 3 skipped`。重新生成的 `campus-social-miniprogram.zip` 已通过压缩完整性和包内源码一致性检查，SHA256 为 `f221cde288acb15ee9aa7809a883381b1ac087d34786a63de4e2f866924a4657`。

### 2026-08-30 CloudBase JS SDK v3 双 Header 适配

为避免体验版直接访问 `*.run.tcloudbase.com`，增加未默认启用的 `sdk` transport：固定依赖 `@cloudbase/js-sdk` v3，按需注册 CloudRun 组件并调用 `app.callContainer()`，成功响应读取 `result`，普通接口/Agent 分别使用 30/60 秒 timeout。默认 `API_MODE` 仍为 `public`，local/public/http/cloud 代码未删除。

CloudBase Gateway 与现有 FastAPI JWT 都使用标准 Authorization，无法在同一值中共存。因此 SDK 保留 `Authorization` 给 Publishable Key，并通过 `X-Campus-Authorization` 传输原 FastAPI JWT。后端没有增加全局 middleware；只在原 `HTTPBearer` 鉴权依赖入口增加凭据选择，Header 存在时仍必须通过原 JWT 签名、issuer、exp、token version、用户存在性和验证状态检查，不能仅凭 Header 存在获得身份。实现和测试均不记录两个 token。

客户端合同测试确认 SDK 模式只调用 `app.callContainer()`，不调用 `wx.request` 或 `wx.cloud.callContainer`；`/auth/wechat`、`/users/me`、`/agent/chat` 的 path、method、data、30/60 秒 timeout 与业务 JWT 均正确传递，成功响应从 `result` 解包。后端回归同时验证原 Authorization、扩展 Header、伪造 token 以及双 Header 优先级；`/health` 和 `/__tcb_probe__` 保持公开。

依赖固定为 `@cloudbase/js-sdk==3.9.0`，npm audit 无漏洞。最终 Ruff、Node 语法和小程序静态安全检查通过，Pytest 为 `138 passed, 3 skipped`；跳过项仍是必须显式启用真实外部 LLM 的集成测试。未切换默认 `API_MODE`，未上传或发布体验版。

本地重新生成的 CloudBase 后端部署包 `cloudbase-campus-social-agent.zip` SHA256 为 `8ca03980cde4fe6e2678ad81ae321daf9a8a99cc94691d5ca35ab93c9b537578`；小程序源码包 `campus-social-miniprogram.zip` SHA256 为 `40c423741244d6316baa4756d511f7699d362177628aea5fca3aa0d0b2a4d6c0`。两者均排除 `.env`、私密配置、依赖缓存和本地数据库。

### 2026-08-30 CloudBase SDK OAuth 会话修复

真机联调确认仅向 `cloudbase.init()` 传 Publishable Key 不足以调用 CloudRun：v3.9.0 的请求层还要求 app 上存在 OAuth instance，并从中取得 access token。SDK adapter 现先注册 `@cloudbase/js-sdk/auth` 与 CloudRun，初始化 `app.auth({ persistence: 'local' })`，首次 SDK 请求在任何 `callContainer()` 之前调用 `signInWithOpenId({ useWxCloud: false })`。

实现按 v3.9.0 的新返回合同检查 `{ data, error }`：存在 `error`、缺少 `data.session` 或缺少 `session.access_token` 都直接终止，不会继续访问容器。多个并发 API 共享单一登录 Promise；成功后复用 OAuth session。Gateway session 失效会按 auth generation 合并并发刷新并只安全重试容器一次；FastAPI 返回且带 `detail` 的业务 401 不会误触发 CloudBase 重认证，仍由原业务 JWT 重登路径处理。

CloudBase OAuth 只承担 Gateway 身份；`/auth/wechat` 仍执行微信 code2session 并签发 FastAPI JWT，后续业务请求仍只把该 JWT 放入 `X-Campus-Authorization`。默认 `API_MODE` 已恢复并保持 `public`，没有发布体验版。

新增 Node 合同回归覆盖 Auth/CloudRun 各注册一次、Auth instance 只初始化一次、首次登录、并发单飞、`{data,error}` 登录失败短路、session 成功后调用、失效后重认证、双 Header、`/auth/wechat` 无业务 JWT，以及 public/local/cloud 不回归。二次复核还直接加载 v3.9.0 `miniprogram_dist`，确认真实 bundle 注册后 `app.auth()`、`oauthInstance` 和 `callContainer()` 均可用；错误适配补充读取微信请求适配器实际使用的 `error.data.detail`，并验证 FastAPI 业务 401 不会触发 CloudBase OAuth 重登。最终 Pytest 为 `142 passed, 3 skipped`，Ruff、Node 语法、小程序静态安全检查和 npm audit 全部通过。

### 2026-08-31 CloudBase Gateway 匿名 Auth

CloudBase 控制台已开启“允许匿名登入”后，SDK transport 的 Gateway 会话建立从微信 OpenID 登录改为 `auth.signInAnonymously()`。这个调整仅替换 CloudBase OAuth 的登录方式：匿名 access token 只供 Gateway/`callContainer()` 验证；`wx.login → /auth/wechat → FastAPI JWT` 及 `X-Campus-Authorization` 业务鉴权完全保留。

现有单飞登录 Promise、`persistence: 'local'` session、登录结果 `{data,error}` 校验、OAuth session 失效后按代次合并重登并且最多重试容器一次的逻辑均未改变。带 `detail` 的 FastAPI 业务 401 仍不得触发 CloudBase 重登。默认 `API_MODE='public'`，未发布体验版。匿名登录定向回归包括零参数调用、并发单飞、失败短路、session 失效重登和业务 401 隔离。最终 Pytest 为 `142 passed, 3 skipped`，Ruff、Node 语法、小程序静态安全检查与 npm audit 全部通过，npm audit 为 0 个漏洞。

### 2026-08-31 CloudBase SDK 响应归一化

真实 Gateway 联调中 `/auth/wechat` 已返回 HTTP 200，但小程序未写入 FastAPI JWT。根因是客户端固定读取 `res.result`，而安装的 `@cloudbase/js-sdk` v3.9.0 `miniprogram_dist/cloudrun/index.js` 在非 `node-sdk` 分支实际返回 `await response.data`，即 FastAPI JSON 本体。通过直接调用该真实 `requestContainer()` 的无网络 smoke 验证，返回对象与模拟 FastAPI body 是同一对象，且没有 `result` wrapper。

`normalizeSdkResponse()` 现以直接 JSON 为主路径，仅在对象键集符合已知 transport envelope 时兼容 `res.result`、`res.data` 和 `res.result.data`，避免误拆同时含业务 `id` 与 `data` 字段的普通 JSON。SDK 登录回归使用虚构 token，确认 `/auth/wechat` 直接响应最终调用 `setToken()`，后续 `/users/me` 直接 JSON 也被正确传递；测试不输出或快照任何真实 token。

Profile 页加载现先验证 user 对象，失败时统一进入 `catch`，清空 form、结束 loading、设置可见 `loadError` 并提供“重新加载”，不再继续访问 `user.interests`。CloudBase 匿名 Auth、双 Header、FastAPI JWT 校验、Agent 和数据库逻辑均未修改，默认 `API_MODE='public'`，未发布。最终 Pytest 为 `145 passed, 3 skipped`，Ruff、相关 Node JS 语法、小程序静态安全检查全部通过，npm audit 为 0 个漏洞。

### 2026-08-31 体验版 SDK transport 定版

真实小程序联调已连续验证 `POST /auth/wechat`、`GET /users/me` 和 `POST /agent/chat` 均返回 200，FastAPI JWT 已写入小程序 Storage。因此体验版默认 transport 正式切换为 `API_MODE='sdk'`，Publishable Key 继续作为允许放在客户端的发布密钥。CloudBase 匿名 Auth、FastAPI JWT、双 Header、Agent、Matching、PostgreSQL 与后端部署均未修改。

发布模式仍只由代码中的 `API_MODE` 决定，不读取 Storage/ext-config 的 `apiMode`；`apiBaseUrl` 仅在显式 `local` 时可用。新增合同回归验证 Storage 同时遗留 `apiMode='local'` 和局域网 `apiBaseUrl` 时，默认仍只调用 SDK，不触发 `wx.request` 或 `wx.cloud.callContainer`。未引用的旧 `config.js.save` 和 `project.private.config.json` 已加入开发者工具上传忽略列表。对实际可上传的 193 个文件进行了禁止模式与 `.env` 中现有 Secret 真实值交叉扫描，未发现后端 Secret；Publishable Key 按客户端发布密钥策略保留。最终 Pytest 为 `147 passed, 3 skipped`，Ruff、全部小程序源码 JS 语法、小程序静态安全检查均通过，npm audit 为 0 个漏洞，SDK 版本确认为 3.9.0。本次未重新部署后端、未执行数据库迁移，也未自动上传或发布体验版。

### 2026-08-31 微信开发版上传

开发者工具 CLI 登录验证成功后执行了 npm 构建。首次上传被微信服务器以错误码 80051 拒绝：源码包 3761KB，超过主包 2MB 限制。体积分解确认实际使用的 CloudBase app/auth/cloudrun 三个自包含 bundle 约 516KB，超额来自 npm 构建目录中未引用的 SDK 模块、依赖和 source map。

项目配置启用 `ignoreUploadUnusedFiles=true` 并关闭 `uploadWithSourceMap`，不删除或改写 CloudBase SDK 运行模块。重新上传后服务器接受的总包大小为 591.9KB，开发版 `0.1.0-beta.1`（备注“CloudBase SDK transport 体验版”）上传成功。该操作只创建微信小程序开发版，尚未设为体验版、未提交审核、未正式发布。
