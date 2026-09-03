# 动态校园交友 Agent：设计、使用与验收

## 1. 本阶段解决的问题

早期 `CampusSocialAgent` 已经具备 State、Planner、Tools、Memory 和 Trace，但所有输入都执行同一套九步推荐流程。它适合作为可解释 workflow，却无法根据用户当前目标选择能力，也不能在信息不足或零候选时改变后续行动。

本阶段把它升级为“受控动态 Agent”：Agent 可以路由任务、追问缺失信息、在多轮会话中合并意图、根据过滤结果重规划，并在用户明确确认后放宽约束。模型仍不能绕过权限、安全规则或确定性评分。

## 2. 支持的任务

| 用户目标 | 典型输入 | `response_type` | 计划特点 |
|---|---|---|---|
| 找校园搭子 | `找周六下午的羽毛球搭子` | `recommendation` | 完整九步检索、过滤、评分、安全与破冰 |
| 补充缺失条件 | `找羽毛球搭子` → `周六下午` | `clarification` → `recommendation` | 第一轮解析后追问，第二轮合并部分意图 |
| 协商放宽约束 | `只能东区` → `可以放宽` | `no_results` → `recommendation` | 观察零候选，收到确认后只放宽建议的字段 |
| 查校园活动 | `西区有什么活动` | `activities` | 消息安全、意图解析、ActivityTool、响应生成 |
| 更新公开画像 | `更新画像：我喜欢跑步` | `profile_updated` | 结构化解析、白名单更新、记忆更新 |
| 解释推荐 | `为什么推荐小林` | `explanation` | 读取同一 Session 最近推荐及程序化理由 |

所有分支都返回相同的基础响应结构，因此 Web、Swagger 和 Python 调用方可以先根据 `response_type` 决定展示方式，再读取该分支的具体字段。

## 3. 多轮调用协议

第一轮请求可以不传 `session_id`：

```json
{
  "message": "找羽毛球搭子",
  "limit": 3
}
```

Agent 会返回：

```json
{
  "response_type": "clarification",
  "needs_clarification": true,
  "message": "你通常什么时间方便？例如周六下午、周末上午或工作日晚上。",
  "session_id": "..."
}
```

第二轮必须把返回的 Session 原样传回：

```json
{
  "message": "周六下午",
  "limit": 3,
  "session_id": "第一轮返回的 session_id"
}
```

数据库 Session Memory 保存 `user_id`、部分 `intent`、`pending_slot`、`pending_relaxation`、已明确放宽的字段以及最近推荐。服务端校验 Session 所属用户；另一个 Token 尝试续接会收到 403。Session 默认 24 小时未活动后过期，过期 Session 续接返回 404。

多个 Worker 可以从同一数据库恢复这些字段。为了避免同一 Session 的两个请求同时改写上下文，每轮执行会获取带超时的数据库租约；租约占用时并发请求返回 409，租约超时后可以由其他 Worker 接管。

Web 页面会自动保存当前 Agent Session。点击“新会话”会清空前端 Session，并让下一条消息创建新的上下文。

## 4. 路由和计划如何工作

`backend/app/agents/router.py` 的 `TaskRouter` 使用稳定规则把输入映射到产品允许的任务。它不会直接执行工具，也不能生成任意 action。若 Session 中存在待补字段或待确认放宽条件，Router 优先识别对应的续聊动作。

`backend/app/agents/planner.py` 为每类任务定义可审计动作列表。推荐路径保留原九步，以兼容原有算法和测试；活动、画像、解释分支使用不同的短计划。

运行中有两个重规划点：

1. `parse_intent` 后发现活动或时间缺失：截断未执行的检索步骤，替换为 `ask_clarification`；
2. `hard_filter` 后候选为零：截断评分等无意义步骤，替换为 `observe_no_candidates` 和 `request_constraint_relaxation`。

返回的 `plan` 是本轮实际计划，不是最初模板。Trace 是实际执行证据；同一个多轮 Session 的 Trace 会持久化追加并连续编号。每个内部 Trace 事件都有唯一 ID，陈旧 Worker 的保存操作会按事件合并，不会覆盖已经写入的步骤。

## 5. 约束放宽策略

Agent 不会因为“匹配不到”就静默修改需求。当前按以下顺序提出一个最小变更：

1. 如果校区被明确声明为硬条件，建议把校区从硬条件改为软偏好；
2. 否则如果存在明确时间，建议放宽可用时间；
3. 如果没有可安全自动建议的字段，只提示用户主动调整需求。

只有消息包含明确肯定表达并且 Session 正在等待确认时，才进入 `CONFIRM_RELAXATION`。应用改动后重新执行检索；如果仍为零候选，可以继续提出下一个最小放宽建议。

## 6. 安全和权限边界

- 当前用户只从 JWT `sub` 获取，请求体不能传 `user_id` 冒充他人；
- Session 和 Trace 都绑定 `user_id`；
- 用户画像只能通过 `ProfileTool.ALLOWED_UPDATES` 更新；
- LLM 输出必须通过 Pydantic Schema，不能直接拼接工具参数或 SQL；
- 候选必须通过推荐开关、身份、Block、强拒绝、时间和显式校区等 Hard Filter；
- 最终六维特征、权重、总分和稳定排序由 Python 程序计算；
- 风险消息和候选由 `SafetyTool` 检查，模型没有封禁权限；
- 推荐解释只读取公开候选字段、程序化分数和理由。

## 7. Trace 示例

首次发送 `找羽毛球搭子` 时，Trace 为：

```text
1 load_profile
2 load_memory
3 parse_intent
4 ask_clarification
```

在同一个 Session 回答 `周六下午` 后继续追加：

```text
5  load_profile
6  load_memory
7  merge_clarification
8  search_candidates
9  hard_filter
10 score_candidates
11 safety_check
12 rank_candidates
13 generate_recommendation
```

Trace 只记录输入/输出的键、数量、长度、状态与耗时摘要，不记录模型隐藏思维链或敏感正文。

## 8. 代码入口

- `backend/app/agents/campus_agent.py`：Agent Loop 与各任务分支；
- `backend/app/agents/router.py`：受控任务路由；
- `backend/app/agents/planner.py`：任务计划与重规划；
- `backend/app/schemas/agent.py`：请求、响应、Intent、State；
- `backend/app/memory/manager.py`：持久用户记忆、Session TTL、版本合并与轮次租约；
- `backend/app/agents/trace.py`：数据库 Trace、事件合并、保留上限与 TTL；
- `backend/app/models/agent_session.py`：`agent_sessions` 数据模型；
- `backend/app/models/agent_trace.py`：`agent_traces` 数据模型；
- `migrations/versions/0005_persist_agent_sessions_and_traces.py`：持久化迁移；
- `migrations/versions/0006_agent_session_turn_lease.py`：兼容已存在表的租约列迁移；
- `tests/test_dynamic_agent.py`：动态行为和 Session 权限测试。
- `tests/test_agent_persistence.py`：重启/多 Worker、陈旧写合并、租约和过期清理测试。

## 9. 验收命令

```bash
python -m pytest -q
ruff check backend scripts tests
ruff format --check backend scripts tests
python -m compileall -q backend scripts
cd frontend && npm run build
```

动态行为测试覆盖：

- 信息不足时停止推荐并追问；
- 下一轮按 Session 合并活动和时间；
- 不经确认绝不放宽硬校区条件；
- 确认后重新检索并返回候选；
- 活动、画像和解释请求走不同 Plan；
- 解释使用真实 `total` 和 `reasons`；
- 另一个用户不能续接 Session；
- 原有九步推荐、Trace、反馈、匹配、认证、迁移和聊天测试继续通过。

## 10. 持久化配置与下一阶段

```text
AGENT_SESSION_TTL_MINUTES=1440
AGENT_TRACE_TTL_DAYS=7
AGENT_TRACE_MAX_ENTRIES=1000
AGENT_TURN_LOCK_SECONDS=120
```

本地 SQLite 已能验证重启恢复和多个独立 Session 共享状态。CloudBase shared-PG 通过 HTTP Adapter 和事务 RPC 保存 Session/Trace，并保留相同的租约与合并语义；后续应增加周期清理任务、冲突率和 Trace 写入延迟指标。之后再考虑增强中文时间规范化和语义召回；这些能力必须继续受 action allow-list、Hard Filter 和离线评估约束。

API 启动时只校验必要表和租约列，不再调用 `create_all()` 自动修改 Schema；未执行到最新迁移时会明确提示先运行 `alembic upgrade head`。
