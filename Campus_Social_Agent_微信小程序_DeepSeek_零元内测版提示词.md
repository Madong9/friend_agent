你现在是一名资深 AI Agent Engineer、Python Backend Engineer、Recommendation System Engineer、微信小程序工程师和 Full-stack Engineer。

我要你在当前目录中，基于现有项目继续开发并完成迁移：

# Campus Social Agent
中文名称：

# 校园搭子 AI Agent

目标版本：

# 微信小程序 + DeepSeek + 0 元封闭内测版

---

# 0. 最重要的工作方式

这不是让你重新写一份教程，也不是只生成架构文档。

你必须直接读取当前项目、理解现有实现，然后在不破坏已有正确代码的前提下继续开发。

你的工作循环必须是：

```text
读取当前目录
↓
阅读已有代码和测试
↓
判断哪些模块已经完成
↓
制定最小修改计划
↓
实现一个阶段
↓
运行测试
↓
发现错误
↓
修复错误
↓
重新测试
↓
记录实际结果
↓
再进入下一阶段
```

禁止：

```text
没有读项目就大规模重写
一次性生成所有文件后不测试
仅声称“应该可以运行”
删除已经正确工作的 Agent Core
把整个 Agent 简化成一次 llm.chat()
```

如果当前环境缺少某个外部工具，例如微信开发者工具、真实微信 AppID、云平台权限：

```text
可以完成代码和本地可验证部分
必须明确写出未实际验证的部分
禁止伪造“已在微信真机运行成功”
```

---

# 1. 项目目标

开发一个面向本校大学生的校园搭子 AI Agent。

用户可以用自然语言寻找：

```text
学习搭子
运动搭子
兴趣伙伴
校园活动伙伴
```

示例：

```text
帮我找几个周六下午能一起打羽毛球的人，最好在西区，水平休闲一点。
```

Agent 应自动执行：

```text
理解用户需求
↓
读取当前用户 Profile
↓
读取历史 Memory
↓
形成 Goal
↓
形成结构化 Intent
↓
制定 Plan
↓
选择并调用 Tool
↓
搜索候选人
↓
Hard Filter
↓
计算 Match Score
↓
Safety / Risk Check
↓
Rank
↓
Top K
↓
生成推荐理由
↓
生成破冰话题
↓
接受用户 Feedback
↓
更新 Memory
↓
影响下一轮推荐
```

这是一个 Agent System。

不是一次 LLM Completion。

---

# 2. 当前迁移目标

当前项目原本可能包含：

```text
Python
FastAPI
Pydantic
SQLAlchemy
SQLite
React / Vite 或尚未完成的 Web 前端
MockLLMProvider
OpenAICompatibleProvider
AgentState
Planner
Tools
Matching
Memory
Feedback
Safety
Agent Trace
```

现在目标是迁移为：

```text
微信原生小程序
        ↓
Backend API
        ↓
FastAPI
        ↓
CampusSocialAgent
        ↓
Planner / Tools / Matching / Memory / Safety
        ↓
SQLAlchemy Database

同时：

FastAPI
    ↓
OpenAICompatibleProvider
    ↓
DeepSeek API
```

必须遵循：

```text
Agent Core 尽量保留
React/Vite 不再作为 MVP 必需前端
微信小程序成为主要前端
本地开发继续允许 SQLite
云端数据库通过配置切换
DeepSeek API Key 只存在后端
封闭内测优先
正式上线不是本阶段目标
```

---

# 3. 封闭内测目标

当前不是正式商业上线。

目标用户规模：

```text
5～30 名同学
```

后续可以扩展：

```text
30～50 名同学
```

第一阶段真正要验证的是：

```text
同学是否愿意填写 Profile
同学是否愿意用自然语言描述“想找什么搭子”
推荐结果是否让用户觉得相关
用户是否愿意点击 LIKE / PASS / NOT_RELEVANT
是否会出现 Mutual Match
用户是否愿意第二次回来继续使用
```

不要为了正式上线过早实现：

```text
复杂微服务
Kubernetes
Kafka
Redis Cluster
复杂 RAG
GraphRAG
Multi-Agent
GPU Embedding
复杂向量数据库
实时聊天服务器
复杂风控平台
复杂管理后台
```

---

# 4. 0 元优先原则

本阶段要求：

```text
不购买云服务器
不购买域名
不主动开通付费基础设施
尽量使用免费额度 / 免费体验环境 / 本地开发资源
```

但必须注意：

```text
“0 元”是开发和小范围封闭测试目标
不是假设任何平台永久无限免费
```

因此：

1. 不要把 Backend 强绑定到某一家云服务。
2. 数据库通过 `DATABASE_URL` 配置。
3. LLM 通过 Provider 抽象。
4. 微信身份通过 Adapter / Service 封装。
5. Deployment 必须可替换。
6. 如果某个免费平台存在超时、休眠、配额限制，不要为了迁就平台破坏 Agent 架构。
7. 本地开发必须始终可运行。
8. 部署阶段如果当前环境无法完成真实云部署，要生成清晰的部署步骤，但不要声称已经完成云部署。

---

# 5. 核心技术原则

## Agent 负责

```text
Intent Understanding
Goal
Planning
Tool Selection
Tool Execution Orchestration
Observation
Recommendation Explanation
Icebreaker Generation
Memory Orchestration
Feedback Loop
Agent Trace
```

## 普通程序负责

```text
权限
用户身份
数据库真实性
Hard Filter
Block
Report
Privacy
最终 Match Score
排序规则
互相匹配状态
强安全规则
敏感字段控制
```

禁止让 LLM 最终决定：

```text
谁被封禁
谁是否 verified
谁能看到谁
Block 是否生效
最终 Match Score
是否已经 Mutual Match
是否泄露私人信息
```

---

# 6. 技术栈

## Backend

```text
Python 3.11+
FastAPI
Pydantic v2
SQLAlchemy 2
pytest
```

## Development Database

默认：

```text
SQLite
```

例如：

```text
sqlite:///./campus_social.db
```

## Cloud Database

必须通过 SQLAlchemy 配置兼容：

```text
MySQL
```

不要让业务代码依赖 SQLite 特有行为。

禁止把生产/云数据库密码写死在代码里。

## Frontend

本阶段直接使用：

```text
微信原生小程序
WXML
WXSS
JavaScript 或 TypeScript
```

不要为了 MVP 再实现 React + Vite。

如果当前项目已有 React 代码：

```text
不要无意义删除
可以保留为 legacy / prototype
但本阶段不继续扩展
```

## LLM

设计统一：

```python
class LLMProvider
```

至少保留：

```text
MockLLMProvider
OpenAICompatibleProvider
```

DeepSeek 通过：

```text
OpenAICompatibleProvider
```

调用。

不要另外复制一套重复的 DeepSeek Provider，除非现有兼容接口确实无法满足。

---

# 7. DeepSeek 配置

真实开发配置目标：

```text
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=
LLM_MODEL=deepseek-chat
```

具体 URL / Model 仍应从环境变量读取，不要散落在业务代码里。

必须做到：

```text
API Key 永远不出现在微信小程序源码
API Key 永远不返回给前端
API Key 不提交 Git
API Key 不写进测试快照
API Key 不写进日志
```

`.env.example` 中：

```text
LLM_API_KEY=
```

真实 `.env` 中才设置 Key。

必须确认 `.gitignore` 包含：

```text
.env
.env.*
```

但允许：

```text
.env.example
```

---

# 8. 推荐项目目录

优先在现有目录基础上调整，不要为了和本文完全一致而无意义移动大量文件。

建议目标：

```text
campus-social-agent/

backend/
    app/
        main.py
        config.py
        database.py

        agents/
            campus_agent.py
            planner.py
            state.py
            trace.py

        llm/
            base.py
            mock.py
            openai_compatible.py
            factory.py

        tools/
            base.py
            profile_tool.py
            matching_tool.py
            memory_tool.py
            safety_tool.py
            activity_tool.py
            conversation_tool.py

        matching/
            engine.py
            filters.py
            scorer.py
            similarity.py

        memory/
            manager.py

        models/
            user.py
            preference.py
            interaction.py
            match.py
            activity.py
            block.py
            report.py
            recommendation.py
            agent_session.py

        schemas/

        services/
            auth_service.py
            wechat_identity.py

        api/
            auth.py
            users.py
            agent.py
            matches.py
            feedback.py
            activities.py
            safety.py

miniprogram/
    app.js
    app.json
    app.wxss

    services/
        api.js
        auth.js

    pages/
        index/
        profile/
        agent/
        matches/
        match-detail/
        matched/
        settings/

    components/
        match-card/
        score-bar/
        empty-state/

tests/

scripts/
    seed_users.py

data/

.env.example
.gitignore
requirements.txt
README.md
```

必须保证以下模块彼此解耦：

```text
Agent
LLM
Tool
Memory
Matching
Database
Safety
Auth
API
Mini Program
```

---

# 9. AgentState

使用 Pydantic。

示例：

```python
class AgentState(BaseModel):
    session_id: str
    user_id: str
    user_message: str

    goal: str | None = None
    intent: dict = Field(default_factory=dict)

    profile: dict = Field(default_factory=dict)
    preferences: dict = Field(default_factory=dict)

    hard_constraints: list = Field(default_factory=list)
    soft_preferences: list = Field(default_factory=list)

    plan: list = Field(default_factory=list)
    tool_calls: list = Field(default_factory=list)

    candidate_users: list = Field(default_factory=list)
    filtered_candidates: list = Field(default_factory=list)
    ranked_candidates: list = Field(default_factory=list)

    recommendations: list = Field(default_factory=list)

    feedback_history: list = Field(default_factory=list)
    safety_result: dict = Field(default_factory=dict)

    final_response: dict = Field(default_factory=dict)
```

根据实际项目优化强类型。

禁止 mutable default bug。

---

# 10. Agent Trace

必须保留：

```python
AgentTrace
```

至少记录：

```text
step
action
tool
input_summary
output_summary
status
duration
metadata
```

示例：

```json
[
  {
    "step": 1,
    "action": "load_profile",
    "tool": "ProfileTool",
    "status": "success"
  },
  {
    "step": 2,
    "action": "parse_intent",
    "tool": "LLM",
    "status": "success"
  },
  {
    "step": 3,
    "action": "search_candidates",
    "tool": "MatchingTool",
    "status": "success",
    "result_count": 23
  }
]
```

禁止保存：

```text
模型隐藏 chain-of-thought
完整 DeepSeek 请求中的秘密信息
API Key
不必要的私人信息
```

只保存：

```text
结构化操作轨迹
```

---

# 11. User Model

至少包含：

```text
id
wechat_openid
nickname
school
campus
grade
major
bio

social_goals
interests
activities
availability
social_style
avoidances

recommendation_enabled
verified
is_mock

created_at
updated_at
```

要求：

```text
wechat_openid 必须允许为空
```

原因：

```text
seed 用户 / 本地测试用户不一定有真实微信 OpenID
```

必须有唯一性约束策略：

```text
真实微信用户的 wechat_openid 不重复
Mock 用户可以没有 wechat_openid
```

---

# 12. Mock 用户规则

继续保留 Seed Data。

至少生成：

```text
50 个虚拟用户
```

用于：

```text
Matching Engine 测试
前期冷启动测试
只有少量真人时保证有候选结果
```

User 增加：

```text
is_mock: bool
```

前端展示 Mock 用户时必须明确：

```text
测试用户
```

或：

```text
Demo
```

禁止让真实体验成员误认为 Mock Profile 是真实同学。

必须支持配置：

```text
SHOW_MOCK_USERS=true
```

后续真人足够时可以关闭。

---

# 13. 微信身份设计

第一阶段目标不是复杂微信授权体系。

优先实现一个清晰的身份适配层：

```text
WechatIdentityService
```

负责：

```text
从后端可信请求上下文获取微信身份
将微信身份映射为内部 user_id
创建或读取用户
```

禁止：

```text
直接信任前端传入的任意 user_id
```

API 尽量使用：

```text
/users/me
/matches/me
```

而不是让客户端决定：

```text
/users/{任意 user_id}
/matches/{任意 user_id}
```

本地开发必须支持：

```text
DEV_AUTH_MODE
```

例如：

```text
DEV_AUTH_MODE=true
DEV_USER_ID=user001
```

使开发者在没有真实微信环境时仍能本地测试。

必须明确：

```text
DEV_AUTH_MODE 只能用于 development/test
production-like 模式禁止默认启用
```

---

# 14. 第一版不要实现复杂微信授权

暂不要求：

```text
微信手机号授权
真实姓名
身份证
学校官方认证 API
微信头像授权流程
复杂 UnionID 体系
```

Profile 由用户主动填写：

```text
nickname
school
campus
grade
major
interests
availability
social_goals
bio
```

校园认证第一版继续使用：

```text
Mock verification
verified=True
```

但 UI 必须避免误导用户“已完成真实学校认证”。

可以显示：

```text
内测用户
```

不要显示：

```text
官方学校实名认证
```

除非未来真的实现。

---

# 15. Profile 数据

支持两种方式：

```text
表单主动填写
自然语言生成 / 更新 Profile
```

例如：

```text
我研一，喜欢跑步和摄影，平时比较慢热，晚上比较有时间。
```

解析：

```json
{
  "grade": "研一",
  "interests": ["跑步", "摄影"],
  "social_style": "慢热",
  "availability": ["晚上"]
}
```

必须使用：

```text
Pydantic Structured Output
```

解析失败要：

```text
安全降级
保留原 Profile
返回可理解的错误
不要把非法结构直接写数据库
```

---

# 16. Intent Parser

输入：

```text
找几个周六下午能一起打羽毛球的人，最好西区，水平休闲一点。
```

输出结构示例：

```json
{
  "goal": "find_activity_partner",
  "activity": "badminton",
  "availability": ["saturday_afternoon"],
  "campus": "west",
  "skill_level": "casual",
  "hard_constraints": [],
  "soft_preferences": ["campus", "skill_level"]
}
```

实现：

```python
parse_social_intent()
```

要求：

```text
DeepSeek 能生成结构化结果
MockLLM 仍能完成测试
LLM 失败时允许最小规则 fallback
```

---

# 17. Planner

保留：

```python
Planner.create_plan(state)
```

第一版 Planner 不需要复杂 ReAct。

推荐：

```text
规则主导
+
可选 LLM structured planning
```

典型计划：

```text
load_profile
load_memory
parse_intent
search_candidates
hard_filter
score_candidates
safety_check
rank_candidates
generate_recommendation
record_recommendation
```

不要为了“像 Agent”而无限循环。

必须设置：

```text
最大步骤数
工具失败处理
可中止状态
```

---

# 18. Matching Engine

这是核心业务算法。

禁止：

```text
把所有 Profile 全部发给 DeepSeek
让 DeepSeek凭感觉选 Top 3
```

必须 deterministic：

```python
MatchingEngine
```

流程：

```text
candidate retrieval
↓
hard filter
↓
feature calculation
↓
weighted score
↓
ranking
```

LLM 可以：

```text
理解自然语言
生成推荐解释
```

LLM 不负责最终排序分数。

---

# 19. Hard Filters

至少包括：

```text
self
recommendation_enabled=False
not verified
blocked relation
previous strong rejection
明确不兼容 social_goal
用户设置的 hard campus constraint
明确时间完全冲突
```

任何 Hard Filter 失败：

```text
candidate 必须删除
```

特别测试：

```text
Block 双向不可推荐
```

即：

```text
A block B
```

之后：

```text
A 不推荐 B
B 不推荐 A
```

---

# 20. Matching Score

默认权重可继续使用：

```text
interest_similarity      0.25
activity_similarity      0.20
availability_similarity  0.20
social_goal_similarity   0.15
location_similarity      0.10
feedback_adjustment      0.10
```

实现：

```python
score_candidate(user, candidate, intent)
```

返回：

```json
{
  "total": 0.86,
  "features": {
    "interest": 0.90,
    "activity": 1.0,
    "availability": 0.80,
    "social_goal": 1.0,
    "location": 0.70,
    "feedback": 0.80
  },
  "reasons": [
    "共同兴趣：羽毛球",
    "周六下午时间匹配",
    "社交目标一致"
  ]
}
```

所有分数应：

```text
透明
可测试
可解释
有上下界
```

---

# 21. Similarity

MVP 不引入大型 Embedding Model。

先使用：

```text
Jaccard
tag overlap
规则归一化
```

保留接口：

```python
class SimilarityProvider:
    ...
```

未来才考虑：

```text
Embedding
FAISS
pgvector
```

---

# 22. Tools

定义：

```python
BaseTool
```

每个 Tool 至少包含：

```text
name
description
input schema
execute()
```

至少实现：

## ProfileTool

```text
load_profile
update_profile
```

## MatchingTool

```text
search_candidates
rank_candidates
```

## MemoryTool

```text
load_memory
update_memory
```

## SafetyTool

```text
check_block
check_candidate
check_message
```

## ActivityTool

```text
find_activity
```

活动功能可以作为次优先级，不要阻塞核心搭子推荐。

## ConversationTool

```text
generate_icebreaker
generate_topics
```

---

# 23. Memory

保留四类概念：

```text
Profile Memory
Preference Memory
Interaction Memory
Session Memory
```

第一版实现必须简单透明。

接口：

```text
load_user_memory(user_id)
record_feedback(...)
record_recommendation(...)
update_preference(...)
get_recent_candidates(...)
```

数据库可优先使用：

```text
users
feedback
recommendations
matches
blocks
agent_sessions
```

禁止第一版引入：

```text
向量记忆
复杂 Memory Agent
长期自动推断敏感人格
```

---

# 24. Feedback

至少支持：

```text
LIKE
PASS
INTERESTED
MATCHED
CHATTED
MET
NOT_RELEVANT
BLOCK
REPORT
```

封闭内测 UI 第一阶段主要使用：

```text
LIKE
PASS
NOT_RELEVANT
BLOCK
REPORT
```

所有反馈存数据库。

反馈对权重只能有限调整。

禁止：

```text
一次 PASS 永久改变所有推荐
```

可以采用：

```text
bounded adjustment
moving average
简单 decay
recent candidate suppression
```

---

# 25. Mutual Match

必须保留。

逻辑：

```text
A LIKE / INTERESTED B

B LIKE / INTERESTED A

↓

MATCHED
```

不能：

```text
A 单方面 LIKE B
↓
直接开放对方私人联系方式
```

MVP Match 后可以开放：

```text
站内“已互相感兴趣”状态
破冰建议
```

第一版不需要真实实时聊天服务器。

如果没有聊天功能：

```text
不要假装已有聊天能力
```

---

# 26. Block / Report

实现：

```python
block_user(A, B)
```

之后：

```text
A 不推荐 B
B 不推荐 A
```

Report：

```text
记录 report
标记 risk signal
```

处罚系统和 SafetyTool 分开。

禁止让 LLM：

```text
仅凭一句话永久封禁用户
```

---

# 27. Safety

第一版实现简单规则 SafetyTool。

风险信号示例：

```text
刷单
贷款
裸照
私密照片
危险外链
明显诈骗关键词
诱导转账
```

这是：

```text
risk signal
```

不是：

```text
自动永久封禁
```

小程序前端必须能：

```text
Block
Report
```

---

# 28. Conversation / Icebreaker

生成破冰话题时只能使用：

```text
双方主动公开的信息
共同兴趣
当前活动需求
校园公开场景
```

可以：

```text
看到你也喜欢羽毛球，你平时周六一般在哪个场地打？
```

禁止：

```text
推断家庭经济情况
推断疾病
推断政治宗教
推断性取向
利用精确位置
使用未经授权的动态
泄露内部 OpenID
```

---

# 29. 隐私

后台可有：

```text
wechat_openid
verified
internal user id
```

其他用户可看到：

```text
nickname
grade
major
bio
共同兴趣
粗粒度 campus
用户主动公开的 availability
```

禁止输出：

```text
wechat_openid
学号
手机号
宿舍号
身份证
精确实时位置
API Key
内部数据库字段
```

---

# 30. API

在现有 API 基础上迁移。

建议：

```text
POST /auth/wechat

POST /users
GET /users/me
PATCH /users/me

POST /agent/chat
POST /agent/recommend

GET /matches/me
GET /matches/{match_id}

POST /feedback
POST /block
POST /report

GET /activities

GET /agent/{session_id}/trace
```

如果已有：

```text
GET /users/{user_id}
GET /matches/{user_id}
```

不要粗暴删除。

可以：

```text
保留给测试 / admin / compatibility
```

但小程序客户端默认使用：

```text
/me
```

身份由后端决定。

---

# 31. Agent API

核心调用保持：

```python
agent = CampusSocialAgent(...)

result = await agent.run(
    user_id=user_id,
    message=message,
)
```

返回示例：

```json
{
  "goal": "find_activity_partner",
  "intent": {},
  "plan": [],
  "matches": [],
  "suggested_icebreakers": [],
  "session_id": ""
}
```

小程序所需字段必须稳定。

建议额外返回：

```text
display_name
score
score_breakdown
reasons
is_mock
match_status
```

---

# 32. 微信小程序页面

本阶段直接实现微信原生小程序。

至少完成：

## 32.1 Index / Home

展示：

```text
产品名称
一句简介
进入 Agent
进入 Profile
查看 Matches
```

## 32.2 Profile

用户填写：

```text
昵称
学校
校区
年级
专业
Bio
兴趣
常见活动
有空时间
社交目标
社交风格
避免项
```

支持：

```text
保存
加载现有 Profile
自然语言补充 Profile
```

## 32.3 Agent

Chat-like UI：

```text
你最近想找什么样的搭子？
```

输入示例：

```text
周六下午想找两个羽毛球搭子，最好在西区，休闲一点。
```

需要：

```text
发送 loading
错误状态
空状态
请求成功
推荐结果跳转
```

## 32.4 Matches

卡片显示：

```text
昵称
年级
专业
Bio
共同兴趣
Match Score
推荐理由
测试用户标记（如果 is_mock=true）
```

按钮：

```text
感兴趣
跳过
不相关
```

## 32.5 Match Detail

显示：

```text
Interest
Activity
Time
SocialGoal
Location
Feedback
```

例如：

```text
Interest     92%
Activity    100%
Time         80%
SocialGoal  100%
Location     70%
```

还要显示：

```text
推荐理由
破冰建议
Block
Report
```

## 32.6 Matched

只有 Mutual Match 后展示：

```text
🎉 你们互相感兴趣
```

展示：

```text
对方公开信息
共同点
破冰建议
```

不要开放：

```text
手机号
精确位置
非公开联系方式
```

---

# 33. 小程序 API 封装

统一创建：

```text
miniprogram/services/api.js
```

不要让每个 Page 自己重复写网络逻辑。

至少封装：

```text
getMe()
updateMe()
agentChat(message)
getMatches()
sendFeedback(...)
blockUser(...)
reportUser(...)
```

必须统一处理：

```text
base endpoint / cloud adapter
auth headers
错误码
loading
JSON
timeout
```

后续部署方式变化时：

```text
优先只修改 services/api.js / backend adapter
```

不要修改所有页面。

---

# 34. 本地开发模式

必须保证没有微信云环境时也可以运行 Backend。

支持：

```text
APP_ENV=development
DEV_AUTH_MODE=true
DEV_USER_ID=user001
```

FastAPI：

```text
可以直接 uvicorn 启动
```

测试：

```text
curl
pytest
FastAPI TestClient
```

小程序开发阶段如果无法直接连接本地 Backend：

```text
允许通过可配置 API_BASE_URL / cloud adapter
```

不要在业务代码硬编码 localhost。

---

# 35. 数据库配置

`.env.example` 建议：

```text
APP_ENV=development

DATABASE_URL=sqlite:///./campus_social.db

LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=
LLM_MODEL=deepseek-chat

DEV_AUTH_MODE=true
DEV_USER_ID=user001

SHOW_MOCK_USERS=true
ALLOW_MOCK_VERIFICATION=true

WECHAT_APP_ID=
WECHAT_APP_SECRET=

DEBUG_AGENT_TRACE=true
```

注意：

```text
WECHAT_APP_SECRET 只能存在后端
```

禁止放入：

```text
miniprogram/
```

---

# 36. 数据库迁移策略

不要为了小程序迁移破坏本地 SQLite。

必须实现：

```text
Development → SQLite
Cloud/Test → MySQL-compatible
```

要求 ORM：

```text
避免 SQLite 特有 SQL
避免业务代码拼数据库方言
通过 SQLAlchemy Session
```

如果现有项目没有迁移工具：

```text
MVP 可以先使用 create_all + seed
```

但 README 必须注明未来建议：

```text
Alembic
```

不要为了本轮 MVP 强行加入复杂迁移工作，除非现有项目已经用了 Alembic。

---

# 37. Seed Data

实现：

```bash
python scripts/seed_users.py
```

生成：

```text
至少 50 个虚拟用户
```

活动数据可以：

```text
至少 10～15 个
```

虚拟用户必须有足够差异：

```text
不同校区
不同专业
不同年级
不同兴趣
不同时间
不同社交目的
不同 social style
```

必须有：

```text
user001
```

建议：

```text
研一
西区
羽毛球
跑步
摄影
周末下午有空
运动搭子
兴趣朋友
```

并：

```text
is_mock=true
```

---

# 38. Demo

核心 Demo：

用户：

```text
user001
```

输入：

```text
帮我找几个周六下午可以一起打羽毛球的人，最好西区，水平休闲一点。
```

实际执行：

```text
load profile
↓
load memory
↓
parse intent with DeepSeek / Mock
↓
search candidates
↓
hard filter
↓
score
↓
safety
↓
rank
↓
Top 3
↓
generate reasons
↓
generate icebreakers
↓
record recommendation
```

结果示例：

```text
小林
Score: 0.89

为什么推荐：
- 都喜欢羽毛球
- 周六下午都有时间
- 都在西区
- 双方都希望找运动搭子

建议开场：
你平时周六一般去哪打球？最近正好想找一个固定球搭子。
```

注意：

```text
Demo 输出不要求和示例完全一样
但必须真实由当前代码运行得到
```

---

# 39. Feedback Demo

调用：

```text
PASS candidate_1
```

系统：

```text
record_feedback
```

再次推荐时：

```text
candidate_1 不应立即重复出现
排名应合理变化
```

LIKE 流程：

```text
A LIKE B
```

记录状态。

再模拟：

```text
B LIKE A
```

应：

```text
MATCHED
```

必须测试。

---

# 40. DeepSeek 容错

真实 API 调用必须处理：

```text
timeout
HTTP error
invalid JSON
structured output parse error
rate limit
empty response
```

策略：

```text
不要直接让整个 API 崩溃
记录结构化 Trace
返回安全错误
测试环境可 fallback Mock
```

生产-like 模式不要悄悄伪装成真实 DeepSeek 成功。

如果 fallback：

```text
必须在日志/trace 中标记 provider=fallback
```

---

# 41. LLM 成本控制

用户已经有 DeepSeek API。

仍然要求减少无意义调用。

匹配流程中：

```text
Hard Filter
Score
Rank
Block
Feedback
```

全部普通程序执行。

DeepSeek 主要用于：

```text
Intent Parser
自然语言 Profile Parser
Recommendation Explanation
Icebreaker
可选 Planner
```

禁止：

```text
每个候选人单独发一次大 Prompt
把 50 个完整 Profile 全发给 DeepSeek
```

推荐：

```text
先程序算 Top K
再把最终少量公开字段交给 LLM 生成解释
```

---

# 42. 测试

使用：

```text
pytest
```

必须至少覆盖：

```text
test_profile_parser
test_intent_parser
test_matching_score
test_hard_filter
test_block
test_feedback
test_memory
test_agent_plan
test_agent_tools
test_recommendation
test_api
test_end_to_end
test_mutual_match
test_mock_user_flag
test_dev_auth
test_user_me
```

尤其必须存在：

```python
def test_blocked_users_never_match():
    ...
```

以及：

```python
def test_same_interest_and_time_get_higher_score():
    ...
```

以及：

```python
def test_mutual_like_creates_match():
    ...
```

以及：

```python
def test_client_cannot_impersonate_arbitrary_user():
    ...
```

---

# 43. 测试真实 DeepSeek

普通 pytest 默认不要消耗真实 API Token。

默认：

```text
MockLLMProvider
```

或 mock 网络层。

额外提供一个：

```text
manual / integration
```

测试方式：

例如：

```text
RUN_LLM_INTEGRATION=1
```

才调用真实 DeepSeek。

真实测试至少验证：

```text
intent structured parsing
profile structured parsing
recommendation explanation
```

禁止把真实 API Key 写进 test 文件。

---

# 44. 小程序测试

如果当前环境有微信开发者工具：

```text
实际运行并检查
```

如果没有：

至少做到：

```text
检查 app.json
检查 page 路径
检查 JS/TS 语法
检查 API service
检查后端 schema 是否一致
检查基础 WXML/WXSS
```

最终汇报必须区分：

```text
已真实运行验证
静态验证
尚未真机验证
```

禁止伪造。

---

# 45. 封闭体验版

本阶段最终产品目标：

```text
微信小程序体验版
```

不是：

```text
正式公开发布
```

目标：

```text
添加少量同学为体验成员
扫码使用
```

但部署平台和微信后台属于外部权限。

如果当前开发环境无法自动操作：

```text
不要阻塞代码完成
生成 README 中的人工步骤
```

人工步骤必须明确包括：

```text
创建/选择微信小程序项目
配置 AppID
配置后端访问
上传小程序代码
设置体验版本
添加体验成员
发体验二维码
```

不要声称这些外部步骤已完成。

---

# 46. 部署抽象

不要把业务逻辑写死到某个云厂商 SDK。

后端必须可以：

```text
本地运行
容器运行
Serverless / HTTP Function 适配
```

小程序必须通过统一 API Adapter。

如果需要某云厂商专属调用方式：

```text
放在 adapter
```

例如：

```text
miniprogram/services/api.js
backend/services/deployment_adapter.py
```

这样未来可以替换：

```text
CloudBase
其他免费/低成本平台
自有服务器
```

而不重写 Agent。

---

# 47. 0 元部署验证原则

目标是：

```text
优先选择当前可用的免费额度方案
```

但不要在代码中假设：

```text
某平台永久免费
某平台永远没有超时限制
某免费额度永远不变化
```

README 写：

```text
“部署方案需要按测试时平台当前免费额度选择”
```

并至少保留：

```text
Local Development
Container Deployment
Serverless Adapter
```

如果当前环境能完成一种免费部署：

```text
实际完成并记录
```

如果不能：

```text
代码保持可部署
给出逐步部署说明
```

---

# 48. Docker

如果现有项目已经适合容器化，增加：

```text
Dockerfile
```

示例目标：

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
```

根据项目实际路径调整。

必须测试：

```text
至少构建 Docker image（如果当前环境有 Docker）
```

如果无 Docker：

```text
不要声称构建成功
```

---

# 49. 前端 UX 原则

内测优先简单。

不要为了炫技引入复杂 UI 框架。

要求：

```text
清晰
移动端友好
按钮够大
错误提示明确
loading 明确
空状态明确
Mock 用户明确标记
```

第一版不需要：

```text
复杂动画
复杂主题系统
社交动态 Feed
复杂 IM
```

---

# 50. 冷启动

真实内测用户很少。

允许：

```text
真人 + Mock 候选人混合
```

但必须：

```text
Mock 用户明显标记
不能形成真实联系方式
不能让测试者误以为 Mock 是真实同学
```

推荐结果可配置：

```text
SHOW_MOCK_USERS=true
```

未来真人足够：

```text
SHOW_MOCK_USERS=false
```

---

# 51. 正式数据和 Mock 数据隔离

所有 Mock 用户：

```text
is_mock=true
```

所有真实微信用户：

```text
is_mock=false
```

Mutual Match：

```text
真实用户 ↔ Mock 用户
```

默认不要产生“真实可联系 Match”。

可以返回：

```text
demo_match
```

或：

```text
测试匹配，不开放联系
```

必须避免产品误导。

---

# 52. 安全的用户展示 Schema

后端不要直接把 SQLAlchemy User model 全部序列化给小程序。

建立：

```text
PublicUserSchema
PrivateMeSchema
```

`PrivateMeSchema` 可以包含：

```text
自己的完整 Profile
```

`PublicUserSchema` 只能包含：

```text
id / public id
nickname
grade
major
campus
bio
interests
social_goals
availability（用户允许公开的粗粒度）
is_mock
```

禁止包含：

```text
wechat_openid
内部 auth 字段
敏感信息
```

---

# 53. Agent Trace API

保留：

```text
GET /agent/{session_id}/trace
```

但：

```text
只允许当前用户查看自己的 trace
```

开发模式可以放宽用于测试。

Trace 前端不是 MVP 必需页面。

主要用于：

```text
调试
研究 Agent Workflow
```

---

# 54. README

最终更新完整：

```text
README.md
```

至少包含：

```text
Project Goal
Architecture
Mini Program Architecture
Agent Loop
Agent State
Planner
Tools
Matching Algorithm
Memory
Feedback
Mutual Match
Safety
Privacy
Auth
DeepSeek Integration
Database
API
Mock Users
Local Development
Tests
Mini Program Development
Closed Beta Workflow
Deployment Abstraction
Zero-cost Testing Strategy
Known Limitations
Future Roadmap
```

---

# 55. 本地启动目标

最终至少可以：

```bash
python -m venv .venv

source .venv/bin/activate

pip install -r requirements.txt

python scripts/seed_users.py

uvicorn backend.app.main:app --reload
```

访问：

```text
http://127.0.0.1:8000/docs
```

测试：

```bash
pytest -v
```

核心测试通过。

---

# 56. 本地 DeepSeek Demo

设置真实 `.env`：

```text
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=<用户自己的 key>
LLM_MODEL=deepseek-chat
```

然后提供一个实际可运行 Demo：

```text
user001
↓
“帮我找几个周六下午可以一起打羽毛球的人，最好西区，水平休闲一点。”
↓
DeepSeek Intent
↓
Matching
↓
Top 3
↓
DeepSeek Explanation
```

如果当前环境没有用户的真实 Key：

```text
不要伪造真实 DeepSeek 测试
使用 Mock 测试
并给出用户本地运行命令
```

---

# 57. 开发顺序

严格按阶段执行。

## Phase 0 - Audit

运行：

```bash
pwd
find . -maxdepth 3 -type f
```

阅读：

```text
README
requirements
backend
tests
frontend / miniprogram
env config
```

先回答自己：

```text
哪些已经完成？
哪些测试已经通过？
哪些不应该重写？
```

运行现有测试。

---

## Phase 1 - Preserve Agent Core

确认：

```text
AgentState
Planner
Tools
Matching
Memory
Feedback
Safety
Trace
```

现有逻辑可运行。

只修 bug，不无意义重写。

运行测试。

---

## Phase 2 - DeepSeek

确认：

```text
OpenAICompatibleProvider
Factory
Structured Output
Timeout
Error Handling
Mock Provider
```

实现 DeepSeek 配置。

运行：

```text
LLM unit tests
parser tests
```

如有真实 Key，再运行 opt-in integration test。

---

## Phase 3 - Auth Model

增加：

```text
wechat_openid
is_mock
updated_at
```

实现：

```text
WechatIdentityService
DEV_AUTH_MODE
/users/me
```

运行测试。

---

## Phase 4 - API Migration

完成：

```text
/auth/wechat
/users/me
/agent/chat
/agent/recommend
/matches/me
/feedback
/block
/report
```

运行：

```text
pytest
FastAPI TestClient
curl
```

---

## Phase 5 - Mini Program Skeleton

创建：

```text
miniprogram/
```

完成：

```text
app
routing
api service
home
profile
agent
matches
```

检查语法和路径。

---

## Phase 6 - Profile Flow

打通：

```text
Mini Program
↓
GET /users/me
↓
Edit Profile
↓
PATCH /users/me
↓
Reload
```

---

## Phase 7 - Agent Flow

打通：

```text
Agent Page
↓
POST /agent/chat
↓
CampusSocialAgent
↓
DeepSeek / Mock
↓
Matching
↓
Top 3
↓
Matches Page
```

---

## Phase 8 - Feedback

打通：

```text
LIKE
PASS
NOT_RELEVANT
BLOCK
REPORT
```

验证：

```text
下一轮推荐变化
Blocked 永不出现
```

---

## Phase 9 - Mutual Match

验证：

```text
A LIKE B
B LIKE A
MATCHED
```

完成 Matched 页面。

---

## Phase 10 - Cloud-ready Database

确保：

```text
SQLite development
MySQL-compatible cloud
```

不要破坏本地测试。

---

## Phase 11 - Deployment-ready

完成：

```text
Dockerfile
env docs
deployment adapter
mini program API config
```

如果有可用免费平台权限：

```text
实际部署测试
```

否则：

```text
完成可部署代码 + README
```

---

## Phase 12 - Closed Beta Checklist

生成清单：

```text
微信 AppID
体验成员
后端 URL / cloud adapter
数据库
DeepSeek Key
Seed / Mock Users
隐私说明
Block / Report
体验二维码
```

不要进行正式发布。

---

# 58. 每阶段验收

每完成一阶段：

```text
实现
↓
测试
↓
报告真实错误
↓
修复
↓
再次测试
↓
记录实际通过数量
↓
进入下一阶段
```

禁止：

```text
“看起来没问题”
“应该能运行”
“理论上通过”
```

必须尽可能实际执行。

---

# 59. 不要过度设计

第一版禁止主动引入：

```text
Kubernetes
Kafka
Redis Cluster
复杂 Microservices
复杂 Multi-Agent
复杂 RAG
GraphRAG
LangChain 大量抽象
GPU Embedding
实时 WebSocket Chat
复杂推荐训练流水线
```

除非当前项目已经依赖且移除成本更高。

---

# 60. 我真正想学习的 Agent 内容

代码必须让我能够清楚理解：

```text
AgentState
Planner
Tools
Tool Execution
Observation
Memory
Matching
Feedback Loop
Agent Trace
LLM Provider
```

不要把所有逻辑塞进：

```python
response = llm.chat(prompt)
```

这不算这个项目需要的 Agent。

---

# 61. 成功标准

本轮成功不是“正式上线”。

成功标准是：

```text
1. Backend 本地可以启动
2. Seed 可以生成测试用户
3. DeepSeek Provider 可配置
4. Mock 测试不消耗真实 API
5. Agent End-to-End 测试通过
6. 小程序核心页面已实现
7. 小程序 API 层与后端 Schema 对齐
8. Profile 可以保存
9. 自然语言找搭子可以得到 Top 3
10. LIKE / PASS 可以记录
11. Block 后永远不推荐
12. Mutual Match 正确
13. Mock 用户明确标记
14. 隐私字段不泄露
15. 项目具备零成本封闭内测的部署适配能力
```

---

# 62. 最终汇报格式

全部完成后告诉我：

```text
1. 你首先检查到了什么现有项目状态

2. 哪些已有模块被保留

3. 哪些文件被新增

4. 哪些文件被修改

5. 最终项目目录

6. 当前 Agent 架构

7. Agent Loop

8. AgentState 如何变化

9. Planner 如何工作

10. 每个 Tool 是什么

11. Matching Algorithm

12. Memory 如何工作

13. Feedback 如何改变推荐

14. Mutual Match 如何工作

15. Safety / Block / Report 如何工作

16. 微信身份如何映射到内部 User

17. DeepSeek 如何调用

18. DeepSeek API Key 如何保护

19. 小程序页面有哪些

20. 小程序如何调用 Backend

21. SQLite 和云 MySQL 如何切换

22. pytest 实际结果

23. 实际 Demo 请求与输出

24. 哪些部分真实运行验证过

25. 哪些部分只做了静态验证

26. 当前还有哪些 Mock

27. 当前还没有完成哪些外部步骤

28. 如何本地启动

29. 如何打开小程序开发环境

30. 如何进行 5～30 人封闭体验测试

31. 当前 0 元部署策略是什么

32. 下一阶段最值得开发的 3 个功能
```

---

# 63. 最后再强调

本轮迁移的核心不是：

```text
做一个看起来像 AI 的微信页面
```

而是：

```text
把原来的真正 Agent System
稳定地接到微信小程序上
```

必须保留：

```text
AgentState
Planner
Tools
Memory
Matching
Feedback Loop
Trace
```

同时做到：

```text
DeepSeek 负责自然语言智能
普通程序负责确定性业务规则
微信小程序负责交互
FastAPI 负责后端 API
数据库负责真实状态
```

请现在直接开始：

```text
检查当前目录
读取已有项目
运行现有测试
判断迁移起点
然后按照 Phase 0 → Phase 12 逐阶段完成
```

不要先向我复述整份需求。

不要只给我教程。

不要只给我代码片段。

直接在项目里实施、测试、修复，并最终汇报真实结果。
