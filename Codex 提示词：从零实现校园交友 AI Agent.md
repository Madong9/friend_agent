你现在是一名资深 AI Agent Engineer、Python Backend Engineer、Recommendation System Engineer 和 Full-stack Engineer。

我要你直接在当前目录中，从 0 到 1 实现一个真正可运行的项目：

# Campus Social Agent

中文名称：

# 校园搭子 AI Agent

你的任务不是给我教程，也不是只生成架构文档，而是：

```text
读取项目
创建文件
实现代码
运行测试
发现错误
修复错误
重新测试
完成 Demo
```

直到 MVP 可以本地运行。

---

# 1. 产品目标

开发一个：

> 面向本校大学生，用自然语言寻找学习搭子、运动搭子、兴趣伙伴和校园活动伙伴的 AI Agent。

用户可以输入：

```text
帮我找几个周六下午能一起打羽毛球的人，最好在西区。
```

Agent 应自动执行：

```text
理解需求
↓
读取用户画像
↓
读取历史 Memory
↓
形成 Goal
↓
制定 Plan
↓
调用 Matching Tool
↓
Hard Filter
↓
计算 Match Score
↓
Risk Check
↓
Rank
↓
生成推荐解释
↓
生成破冰话题
↓
接受用户 Feedback
↓
更新 Memory
```

这是一个 Agent System。

不是一次 LLM Completion。

---

# 2. 核心技术原则

必须严格遵守：

## Agent 负责

```text
Intent Understanding

Goal

Planning

Tool Selection

Tool Execution

Observation

Recommendation Explanation

Memory

Feedback Loop
```

## 普通程序负责

```text
权限

Hard Filter

Block

隐私

数据库真实性

匹配分数

安全规则
```

不要让 LLM 决定：

```text
谁被封禁

谁能查看谁

谁是否被 Block

最终 Match Score
```

---

# 3. 技术栈

Backend：

```text
Python 3.11+

FastAPI

Pydantic v2

SQLAlchemy 2

SQLite
```

测试：

```text
pytest
```

LLM：

设计统一：

```python
class LLMProvider
```

至少实现：

```text
MockLLMProvider
```

并预留：

```text
OpenAICompatibleProvider
```

OpenAI-compatible provider 应可以用于：

```text
Qwen
DeepSeek
其他兼容接口
```

不得在代码里写死任何 API Key。

---

# 4. 项目目录

建议创建：

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

            activity_tool.py

            conversation_tool.py

            safety_tool.py

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

        schemas/

        services/

        api/

            users.py

            agent.py

            matches.py

            feedback.py

            activities.py

tests/

scripts/

    seed_users.py

data/

.env.example

requirements.txt

README.md
```

你可以适当调整。

但必须保证：

```text
Agent
LLM
Tool
Memory
Matching
Database
Safety
API
```

模块彼此解耦。

---

# 5. AgentState

使用 Pydantic 定义：

```python
class AgentState(BaseModel):
    session_id: str

    user_id: str

    user_message: str

    goal: str | None = None

    intent: dict = {}

    profile: dict = {}

    preferences: dict = {}

    hard_constraints: list = []

    soft_preferences: list = []

    plan: list = []

    tool_calls: list = []

    candidate_users: list = []

    filtered_candidates: list = []

    ranked_candidates: list = []

    recommendations: list = []

    feedback_history: list = []

    safety_result: dict = {}

    final_response: dict = {}
```

根据实际情况优化类型。

禁止使用 mutable default bug。

---

# 6. Agent Trace

我要研究 Agent Workflow。

必须实现：

```python
AgentTrace
```

记录：

```text
step

action

tool

input_summary

output_summary

status

duration
```

例如：

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
    "result_count": 23,
    "status": "success"
  }
]
```

注意：

不要保存模型隐藏 chain-of-thought。

只保存结构化操作轨迹。

---

# 7. User Model

用户至少包含：

```text
id

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

created_at
```

校园认证第一版：

```text
Mock verification
```

例如：

```text
verified=True
```

不要实现真实学校认证接口。

---

# 8. Profile 数据

系统必须支持：

```text
用户主动填写 Profile

以及

自然语言生成/更新 Profile
```

例如：

```text
我研一，喜欢跑步和摄影，平时比较慢热，晚上比较有时间。
```

解析：

```json
{
  "grade": "研一",
  "interests": [
    "跑步",
    "摄影"
  ],
  "social_style": "慢热",
  "availability": [
    "晚上"
  ]
}
```

必须使用 Pydantic Structured Output。

---

# 9. Intent Parser

例如输入：

```text
找几个周六下午能一起打羽毛球的人，最好西区。
```

输出：

```json
{
  "goal": "find_activity_partner",

  "activity": "badminton",

  "availability": [
    "saturday_afternoon"
  ],

  "campus": "west",

  "hard_constraints": [],

  "soft_preferences": [
    "campus"
  ]
}
```

实现：

```python
parse_social_intent()
```

MockLLM 必须能够对 Demo 请求生成合理结果。

---

# 10. Planner

实现：

```python
Planner.create_plan(state)
```

例如：

```json
[
  {
    "step": 1,
    "action": "load_profile"
  },

  {
    "step": 2,
    "action": "load_memory"
  },

  {
    "step": 3,
    "action": "parse_intent"
  },

  {
    "step": 4,
    "action": "search_candidates"
  },

  {
    "step": 5,
    "action": "hard_filter"
  },

  {
    "step": 6,
    "action": "score_candidates"
  },

  {
    "step": 7,
    "action": "safety_check"
  },

  {
    "step": 8,
    "action": "rank_candidates"
  },

  {
    "step": 9,
    "action": "generate_recommendation"
  }
]
```

第一版 Planner 可以：

```text
规则 + LLM structured planning
```

结合实现。

不要为了 Agent 感强行做复杂 ReAct。

---

# 11. Matching Engine

这是核心。

禁止：

```text
把所有 Profile 给 LLM，让 LLM 自己挑人。
```

实现 deterministic：

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

---

# 12. Hard Filters

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

---

# 13. Matching Score

默认：

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

必须返回：

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
  }
}
```

同时保存：

```text
match reasons
```

---

# 14. Semantic Similarity

第一版不要增加复杂依赖。

先实现：

```text
Jaccard / tag similarity
```

同时设计：

```python
SimilarityProvider
```

接口。

未来可实现：

```text
FAISS

Embedding

pgvector
```

MVP 不要求必须下载巨大 Embedding Model。

---

# 15. Tools

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

实现：

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

## ConversationTool

```text
generate_icebreaker

generate_topics
```

---

# 16. Memory

实现：

```python
MemoryManager
```

至少区分：

```text
Profile Memory

Preference Memory

Interaction Memory

Session Memory
```

接口：

```python
load_user_memory(user_id)

record_feedback(...)

record_recommendation(...)

update_preference(...)

get_recent_candidates(...)
```

---

# 17. Feedback

实现：

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

存数据库。

不同反馈对推荐权重产生有限调整。

禁止：

```text
一次 PASS 永久改变所有推荐。
```

例如采用：

```text
moving average

decay

bounded weight adjustment
```

实现最简单透明版本即可。

---

# 18. Mutual Match

必须实现：

```text
A interested B

B interested A

↓

MATCHED
```

不能：

```text
A 点赞 B
↓
自动开放所有私人信息
```

Match 后只开放：

```text
站内聊天资格
```

MVP 不需要真实聊天服务器。

---

# 19. Block

实现：

```python
block_user(A, B)
```

之后：

```text
A 不推荐 B

B 不推荐 A
```

测试必须覆盖。

---

# 20. Safety

第一版实现简单规则 SafetyTool。

检测示例：

```text
刷单

贷款

裸照

私密照片

危险外链

明显诈骗关键词
```

注意：

这是：

```text
risk signal
```

而不是直接让模型随意永久封禁用户。

处罚逻辑与 SafetyTool 分开。

---

# 21. Conversation Agent

生成破冰话题时：

只能使用：

```text
双方主动公开的信息

共同兴趣

当前活动需求

校园公开场景
```

例如：

```text
共同兴趣：

羽毛球

破冰：

看到你也喜欢羽毛球，你平时一般在哪个场地打？
```

禁止：

```text
推断家庭经济情况

推断性格疾病

推断政治宗教

利用精确位置

使用未经授权的动态
```

---

# 22. Activity

创建 Mock Activity 数据库。

至少 15 个校园活动。

例如：

```text
羽毛球

夜跑

摄影 walk

考研自习

英语角

桌游

篮球

读书会
```

结构：

```text
activity_id

name

campus

location

time

tags

capacity

public
```

---

# 23. Seed Data

实现：

```bash
python scripts/seed_users.py
```

生成：

```text
50 个虚拟用户

15 个校园活动
```

虚拟用户的数据应该有足够差异。

包括：

```text
不同校区

不同专业

不同年级

不同兴趣

不同时间

不同社交目的
```

这样测试 Matching Engine。

---

# 24. FastAPI

实现：

```text
POST /users

GET /users/{user_id}

PATCH /users/{user_id}

POST /agent/chat

POST /agent/recommend

GET /matches/{user_id}

POST /feedback

POST /block

POST /report

GET /activities

GET /agent/{session_id}/trace
```

必须可在：

```text
/docs
```

测试。

---

# 25. Agent API

核心：

```python
agent = CampusSocialAgent(...)

result = await agent.run(
    user_id=user_id,
    message=message
)
```

返回：

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

---

# 26. Demo

Seed 用户：

```text
user001

研一

西区

兴趣：

羽毛球
跑步
摄影

周末下午有空

目标：

运动搭子
兴趣朋友
```

输入：

```text
帮我找几个周六下午可以一起打羽毛球的人，最好西区，水平休闲一点。
```

要求执行：

```text
parse intent

↓

load profile

↓

load memory

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
```

结果示例：

```text
小林

Score: 0.89

为什么推荐：

都喜欢羽毛球

周六下午都有时间

都在西区

双方都希望找运动搭子

建议开场：

你平时周六会去哪打球？最近正好想找一个固定球搭子。
```

---

# 27. Feedback Demo

之后调用：

```text
PASS candidate_1
```

系统：

```text
record_feedback
```

重新执行推荐。

要求：

```text
candidate_1 不立即重复出现

排名发生合理改变
```

---

# 28. 测试

使用：

```text
pytest
```

必须覆盖：

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

---

# 29. 前端

Backend 完成之后再实现简单 Web 前端。

推荐：

```text
React + Vite
```

页面：

## Profile

修改个人信息。

## Agent

类似 Chat UI：

```text
你最近想找什么样的搭子？
```

## Match

卡片：

```text
昵称

年级

专业

Bio

共同兴趣

Match Score

推荐理由
```

按钮：

```text
感兴趣

跳过

不相关
```

## Match Detail

可视化显示：

```text
Interest     92%

Activity    100%

Time         80%

SocialGoal  100%

Location     70%
```

以后再迁移：

```text
微信小程序
```

第一版不要因为小程序认证阻碍 MVP。

---

# 30. Privacy

必须做到：

```text
后台 verified

前台 nickname
```

禁止向其他用户输出：

```text
学号

手机

宿舍

精确实时位置

身份证
```

---

# 31. 数据来源规则

MVP 禁止实现：

```text
朋友圈抓取

社交平台爬虫

GPS 长期追踪

偷拍

非授权课表读取

自动替用户发送私人消息
```

未来如接入外部数据：

必须通过：

```text
显式授权

Adapter

Permission Check
```

---

# 32. 配置

创建：

```text
.env.example
```

内容：

```text
APP_ENV=development

DATABASE_URL=sqlite:///./campus_social.db

LLM_PROVIDER=mock

LLM_BASE_URL=

LLM_API_KEY=

LLM_MODEL=

DEBUG_AGENT_TRACE=true
```

---

# 33. 开发顺序

严格按照下面顺序。

不要一次性生成所有文件然后不测试。

## Phase 0

检查当前目录：

```bash
pwd
find . -maxdepth 2 -type f
```

如果已有项目：

先阅读代码。

---

## Phase 1

建立：

```text
config

database

models

schemas
```

测试。

---

## Phase 2

完成：

```text
seed data

matching engine

hard filters

scoring
```

测试。

---

## Phase 3

完成：

```text
memory
feedback
block
```

测试。

---

## Phase 4

完成：

```text
LLM provider

intent parser

planner
```

测试。

---

## Phase 5

完成：

```text
tools
```

测试。

---

## Phase 6

完成：

```text
CampusSocialAgent
Agent Loop
Trace
```

做 end-to-end test。

---

## Phase 7

完成：

```text
FastAPI
```

使用：

```text
pytest

curl

FastAPI TestClient
```

真实测试。

---

## Phase 8

实现 Web Demo。

---

## Phase 9

运行：

```text
完整测试

lint

Demo
```

修复所有可以修复的问题。

---

# 34. 开发要求

每完成一个阶段：

```text
实现

↓

运行测试

↓

检查报错

↓

修复

↓

重新测试

↓

进入下一阶段
```

不要仅仅声称：

```text
应该可以运行。
```

必须实际运行。

---

# 35. 不要过度设计

第一版禁止引入：

```text
Kubernetes

Kafka

Redis Cluster

复杂微服务

复杂 Multi-Agent

复杂 RAG

复杂 GraphRAG

LangChain 大量抽象

需要 GPU 的 Embedding 模型
```

除非确实必要。

---

# 36. 我真正想学习的东西

在这个项目中，我最希望理解：

```text
AgentState

Planner

Tools

Memory

Matching

Feedback Loop

Agent Trace
```

因此代码必须清晰。

不能把整个 Agent 写成：

```python
response = llm.chat(prompt)
```

这不算 Agent。

---

# 37. README

最后创建完整：

```text
README.md
```

包含：

```text
Architecture

Agent Loop

Agent State

Planner

Tools

Matching Algorithm

Memory

Feedback

Safety

Database

API

Demo

Tests

How to Run

Future Roadmap
```

---

# 38. 启动目标

最终我应该可以：

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

全部核心测试通过。

---

# 39. 最终汇报

全部实现以后告诉我：

```text
1. 项目目录

2. Agent 架构

3. Agent Loop

4. 每个 Tool 是什么

5. Matching Algorithm

6. Memory 如何工作

7. Feedback 如何改变推荐

8. Safety 如何工作

9. 如何启动

10. pytest 结果

11. Demo 请求与输出

12. 当前还有哪些 Mock

13. 下一阶段最值得开发的 3 个功能
```

不要只提供代码片段。

直接开始检查当前目录并实现项目。