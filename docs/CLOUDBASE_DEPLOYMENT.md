# CloudBase shared-PG HTTP API 部署手册

目标架构：

```text
微信小程序
  -> wx.request + 云托管公网 HTTPS
  -> CloudBase 云托管 FastAPI
  -> 阿里百炼 qwen3.7-flash
  -> CloudBase PostgreSQL HTTP API / PostgREST
```

当前 `campus-social` 免费体验环境是 PostgreSQL 共享集群，不支持 PostgreSQL 协议直连，也暂时不能升级。本方案只使用环境 ID、后端 API Key 和 HTTPS Data API；不需要 host、port、数据库密码、公网数据库地址或独享集群。

官方参考：

- [CloudBase PostgreSQL 连接方式](https://docs.cloudbase.net/database/postgresql/connecting-to-postgresql)
- [PostgreSQL HTTP API](https://docs.cloudbase.net/http-api/pgdb/postgresql-restful-api)
- [数据库函数与事务 RPC](https://docs.cloudbase.net/database/postgresql/functions)
- [PG 身份认证与 API Key](https://docs.cloudbase.net/authentication-v2/auth/auth-pg)
- [小程序 `wx.cloud.callContainer`](https://docs.cloudbase.net/run/develop/access/mini)

## 1. 运行模式

本地开发：

```text
DATA_BACKEND=sqlite
DATABASE_URL=sqlite:///./campus_social.db
```

CloudBase staging：

```text
DATA_BACKEND=cloudbase_http
CLOUDBASE_ENV_ID=<环境ID>
CLOUDBASE_API_KEY=<后端API Key>
```

HTTP Adapter 自动生成基础地址：

```text
https://<环境ID>.api.tcloudbasegateway.com/v1/rdb/rest
```

普通表 CRUD 使用 `/v1/rdb/rest/{table}`。Feedback、Mutual Match、Block、Report、消息发送、Agent Session 租约和 Trace 合并通过 `/v1/rdb/rest/rpc/{function_name}` 在数据库单事务中执行。

## 2. 初始化数据库 Schema

初始化文件：

[`deployment/cloudbase_schema.sql`](../deployment/cloudbase_schema.sql)

该文件由当前 SQLAlchemy 模型、Alembic 0001～0009 head 和受控 RPC 模板生成，包含：

- 12 张业务表、外键、唯一约束和索引；
- HTTP 写入需要的服务端默认值；
- Alembic head 版本记录；
- Mutual Match、Feedback、Block、Report、Session、Trace 和消息事务函数；
- `service_role` 表/序列权限；
- 每个特权 RPC 的服务角色显式校验。

重新生成：

```bash
python scripts/generate_cloudbase_schema.py
```

控制台操作：

1. 进入 CloudBase 控制台，选择 `campus-social` 环境。
2. 打开“数据库 → PostgreSQL → SQL 编辑器”。
3. 新建查询，把 `deployment/cloudbase_schema.sql` 全部复制进去。
4. 确认当前选中的是 `campus-social`，执行一次。
5. 在“表”中确认 `users`、`agent_sessions`、`agent_traces`、`partner_requests`、`notifications` 等表存在。
6. 在“数据库函数”中确认 `campus_record_feedback`、`campus_block_user`、`campus_agent_session_update` 等函数存在。

初始化 SQL 使用一个事务；任何语句失败都会回滚。最新 0009 文件同时使用 `IF NOT EXISTS` 和兼容性 `ALTER`，可在已有 0008 环境上新增需求池、通知、性格字段和举报分类。执行前仍应做一次备份，并确认整段事务成功；不要删除当前环境。

0008→0009 的生成顺序固定为：创建缺失表 → 为旧表补字段并回填 → 创建索引 → 设置默认值 → 安装 RPC。这样 `reports.category` 会先创建，再创建 `ix_reports_category`。若此前执行旧文件已出现 `SQLSTATE 42703`，该事务不会提交；如果 SQL 编辑器仍提示事务已中止，先单独执行 `ROLLBACK;`，再完整执行最新文件，不要只从报错行继续。

## 3. 创建后端 API Key

进入：

```text
CloudBase 控制台
→ campus-social
→ 环境管理
→ API 密钥
→ 创建 API Key
```

必须创建后端 `API Key`，它对应 JWT 的 `service_role`；不要使用前端 `Publishable Key`。API Key 能绕过 RLS，只允许放在云托管服务环境变量中，严禁写入小程序、`.env.example`、Git、日志或聊天消息。

环境 ID 不是 Secret；API Key 是 Secret。API Key 只由你自己复制到控制台，不需要发给我。

## 4. 创建云托管服务

1. 在同一个 `campus-social` 环境进入“云托管”。
2. 新建服务，服务名使用 `campus-social-agent`。
3. 上传 `deployment/cloudbase-campus-social-agent.zip`。
4. 构建方式选择 Dockerfile，容器端口填写 `8000`。
5. 免费内测先设最小实例数 0、最大实例数 1，规格与费用以控制台当前显示为准。
6. 当前小程序通过 `wx.request` 调用，因此必须保持公网 HTTPS 访问开启。

部署包内也包含 `deployment/cloudbase_schema.sql`，但必须在部署服务前先在 SQL 编辑器执行它。

## 5. staging 环境变量模板

以下全部在云托管服务的环境变量页面填写。尖括号内容由你本人填写，不要发给我。

```text
APP_ENV=staging
DATA_BACKEND=cloudbase_http
CLOUDBASE_ENV_ID=<环境ID>
CLOUDBASE_API_KEY=<自己创建的后端API Key>
CLOUDBASE_HTTP_TIMEOUT_SECONDS=15

JWT_SECRET=<自己生成的至少32字节随机值>
JWT_ACCESS_TOKEN_MINUTES=120
JWT_ISSUER=campus-social-agent

WECHAT_APP_ID=<自己填写>
WECHAT_APP_SECRET=<自己填写>
WECHAT_CODE2SESSION_URL=https://api.weixin.qq.com/sns/jscode2session

LLM_PROVIDER=openai_compatible
LLM_BASE_URL=<阿里百炼OpenAI-compatible地址>
LLM_API_KEY=<自己填写>
LLM_MODEL=qwen3.7-flash
LLM_TIMEOUT_SECONDS=30
LLM_RESPONSE_FORMAT=auto
LLM_FALLBACK_TO_MOCK=false
OUTBOUND_HTTP_TRUST_ENV=false

DEV_AUTH_MODE=false
SHOW_MOCK_USERS=true
ALLOW_MOCK_VERIFICATION=true
REQUIRE_CAMPUS_VERIFICATION=false
DEBUG_AGENT_TRACE=true
AGENT_SESSION_TTL_MINUTES=1440
AGENT_TRACE_TTL_DAYS=7
AGENT_TRACE_MAX_ENTRIES=1000
AGENT_TURN_LOCK_SECONDS=120
```

不填写 `DATABASE_URL`、PG host、PG port、PG user 或 PG password。`CLOUDBASE_PG_API_URL` 也可以省略；只有官方网关地址发生变化或测试 Mock 时才覆盖。

`REQUIRE_CAMPUS_VERIFICATION=false` 适合当前微信封闭内测：微信账号尚未完成校园身份绑定时仍能体验。只有在 CAS/校邮绑定流程已对小程序用户可用后，才改为 `true`；届时未认证用户仍可编辑画像，但 Agent、匹配、反馈、聊天、举报和通知会返回 403。

生成 JWT Secret：

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## 6. 小程序配置

真实联调已验证 CloudBase anonymous auth、Gateway/`callContainer()`、FastAPI JWT、`/users/me` 和 `/agent/chat`。正式体验版配置为：

```js
const API_BASE_URL = 'https://campus-social-agent-304566-11-1476699034.sh.run.tcloudbase.com';
const CLOUDBASE_ENV_ID = 'campus-social-d3gsie43e1ca1bc6c';
const CLOUDBASE_SERVICE_NAME = 'campus-social-agent';
const API_MODE = 'sdk';
```

`sdk` 使用 CloudBase JS SDK v3，并保留 `API_BASE_URL` 给 `public/http` 回退。运行模式只取代码中的 `API_MODE`，不读取 Storage/ext-config 的 `apiMode`；`apiBaseUrl` 只在编译时明确选择 `local` 时读取。因此手机里遗留的 `apiMode='local'` 或 `http://100.64.x.x:8000` 不能影响 SDK 体验版。

上传体验版时保持 `sdk`；不要改成 `cloud` 或 `auto`。`public/http`、`local`、`cloud` 适配仍保留，但不是本次体验版默认路径。

微信小程序后台应已把 `https://campus-social-d3gsie43e1ca1bc6c.api.tcloudbasegateway.com` 登记为 `request` 合法域名。`*.run.tcloudbase.com` 只是 `public/http` 回退时才使用的地址。小程序不持有数据库 API Key，也不直接访问 PostgreSQL HTTP API。

### 6.1 CloudBase JS SDK v3 transport

项目默认 `API_MODE='sdk'`，通过 `@cloudbase/js-sdk` v3 的 `app.callContainer()` 访问：

```text
https://campus-social-d3gsie43e1ca1bc6c.api.tcloudbasegateway.com
```

该 Gateway 当前要求 CloudBase 凭据，因此 SDK 初始化必须填写 **Publishable Key**。进入 CloudBase 控制台，选择 `campus-social` 环境，然后进入“环境管理 → API 密钥”（部分新版界面显示为“API Key 管理”），创建或复制 Key Type 为 `publish_key` 的 Publishable Key。只把该值填入小程序 [config.js](../miniprogram/config.js) 的 `CLOUDBASE_PUBLISHABLE_KEY`；严禁填写后端 `CLOUDBASE_API_KEY`、SecretId 或 SecretKey。

Gateway 与 FastAPI 使用双 Header，职责严格分离：

```text
Authorization: Bearer <CloudBase Publishable Key>       # SDK 自动管理
X-Campus-Authorization: Bearer <FastAPI JWT>             # 业务 JWT
```

后端只是在原鉴权依赖入口优先提取 `X-Campus-Authorization`，之后仍执行同一套 JWT 签名、issuer、exp、token version 和用户查询校验。没有 Header 的 `/auth/wechat`、`/health`、`/__tcb_probe__` 不受影响；public/local 仍用原 `Authorization`。

Publishable Key 只是客户端 API 凭据，`callContainer()` 还要求 CloudBase OAuth 登录态。进入 CloudBase 控制台“身份认证 → 登录方式”，开启“允许匿名登入”。这个匿名 CloudBase 身份只用于获取 Gateway/CloudRun 所需的 OAuth session，不是校园搭子业务用户，也不替代 FastAPI 的微信登录。

SDK adapter 按 v3.9.0 顺序注册 Auth 与 CloudRun，调用 `app.auth({ persistence: 'local' })`，并在首次容器请求前执行 `signInAnonymously()`。其 `{ data, error }` 结果必须没有 `error` 且包含 `data.session.access_token` 才会继续。并发请求共享同一个登录 Promise；内存中复用成功 session，检测到 Gateway OAuth token 失效时同一会话代次只重新登录一次。`wx.login → /auth/wechat → FastAPI JWT` 保持不变，后续业务请求仍通过 `X-Campus-Authorization` 传递 FastAPI JWT。

首次构建 npm：

```bash
cd miniprogram
npm ci
```

随后在微信开发者工具执行“工具 → 构建 npm”，确认生成 `miniprogram_npm` 后重新编译。当前代码没有把默认模式切到 `sdk`；手工验证 SDK 基础链路时，可在开发者工具控制台运行：

```js
const cloudbase = require('@cloudbase/js-sdk/app')
const { registerAuth } = require('@cloudbase/js-sdk/auth')
const { registerCloudrun } = require('@cloudbase/js-sdk/cloudrun')
registerAuth(cloudbase)
registerCloudrun(cloudbase)
const sdkApp = cloudbase.init({
  env: 'campus-social-d3gsie43e1ca1bc6c',
  accessKey: '<只在本机填写 Publishable Key>'
})
const auth = sdkApp.auth({ persistence: 'local' })
;(async () => {
  const { data, error } = await auth.signInAnonymously()
  if (error) throw error
  if (!data || !data.session || !data.session.access_token) {
    throw new Error('CloudBase OAuth session missing')
  }
  const response = await sdkApp.callContainer({
    name: 'campus-social-agent',
    method: 'GET',
    path: '/health'
  })
  console.log(response)
})().catch(console.error)
```

v3.9.0 `miniprogram_dist` 的 `requestContainer()` 在小程序分支直接返回 `await response.data`，因此上述 `response` 本身应为 `{ status: 'ok' }`，不要假定存在 `response.result`。项目响应归一化以这个真实结构为主，同时只对明确符合 transport envelope 的 `result`、`data` 或 `result.data` 兼容解包，不会递归猜测普通业务 JSON。如果 Gateway 返回 403，在 CloudBase“权限控制”中确认 Publishable Key 对应的匿名角色已被授予 CloudRun HTTP API 访问策略；不要改用 service-role API Key。真实联调已通过 `wx.login → /auth/wechat → /users/me → /agent/chat`，现可保持 `sdk` 上传体验版。

## 7. 首次发布检查

服务启动会：

1. 用 HTTP API 检查 `users` 表是否可访问；
2. 清理过期 Session/Trace；
3. 通过 HTTP CRUD 幂等写入 50 个 Mock 用户和 15 个活动；
4. 启动 Uvicorn。

常见错误：

- `401/403`：API Key 类型不对、被吊销，或没有作为 `CLOUDBASE_API_KEY` 注入；
- `404`：尚未执行初始化 SQL、环境 ID错误，或 PostgREST metadata 尚未刷新；
- `permission denied`：初始化 SQL未完整执行，缺少表/序列权限；
- RPC `forbidden`：使用了 Publishable Key/用户 Access Token，而不是后端 API Key；
- timeout：检查云托管是否有访问 CloudBase HTTPS 网关的出站能力。

日志不得打印 API Key、微信 Secret、GLM Key、JWT、openid 或完整隐私画像。

## 8. 发布后冒烟清单

- [ ] 服务健康检查正常
- [ ] Seed 日志显示首次新增 50 用户/15 活动，重启后新增 0/0
- [ ] 微信登录能创建并复用同一个用户
- [ ] 画像重开后仍存在
- [ ] Agent 返回 Top 3 与 Trace
- [ ] 陌生活动零结果后写入需求池；第二位同活动用户出现时第一位收到通知
- [ ] 用户明确同意后可生成性格分析，删除后性格字段清空且不再参与评分
- [ ] LIKE/PASS 可持久化
- [ ] 两个真实用户双向 LIKE 才建立 Match
- [ ] Block 后 Match 变为 `BLOCKED`，不能继续聊天
- [ ] 举报必须选择结构化类别并保留文字说明
- [ ] 发布新版本后 Session/Trace 可继续读取
- [ ] 小程序和构建产物中不存在 `CLOUDBASE_API_KEY`

## 9. 本地验收命令

```bash
python scripts/generate_cloudbase_schema.py
python -m pytest -q
ruff check backend migrations scripts tests
python scripts/check_miniprogram.py
python scripts/beta_metrics.py
docker build -t campus-social-agent .
./scripts/package_cloudbase.sh
./scripts/package_miniprogram.sh
unzip -t deployment/cloudbase-campus-social-agent.zip
unzip -t deployment/campus-social-miniprogram.zip
```
