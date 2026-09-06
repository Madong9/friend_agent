# Campus Social Agent 全项目审计与验证记录

日期：2026-09-05

## 结论

本轮完成后端、小程序、legacy Web、CloudBase 数据适配、数据库升级路径、部署脚本和比赛提交材料的整体复核。没有修改 Agent、Planner、Matching Score、Hard Filter、PostgreSQL Schema 或线上部署配置；没有发布小程序、部署后端或执行数据库迁移。

当前本地验收结果为 `176 passed, 3 skipped`。Ruff、小程序静态检查、全部小程序 JavaScript 语法、前端生产构建、Python 依赖一致性和两套 npm 生产依赖审计均通过。隔离 SQLite 上的真实 Uvicorn HTTP 冒烟验证了健康检查、登录、`/users/me` 和 `/agent/chat`，Agent 返回 3 名候选。

## 本轮修复

### 1. CloudBase Data API 故障边界

- 增加全局 `CloudBaseDataError` 处理器，把数据服务连接、读取和上游 HTTP 故障统一转换为清洗后的 HTTP 503。
- 日志只记录 operation、上游状态码和异常类型，不记录 API Key、Authorization、请求/响应正文或用户数据。
- CloudBase 上游 401 不再直接传给小程序，避免被误判为 FastAPI 业务 JWT 过期并触发错误重登。

### 2. SDK 发布目标不可被旧 Storage 改写

- `sdk` 模式固定使用代码审阅过的 CloudBase 环境和服务名。
- 历史 `cloudbaseEnvId`、`cloudbaseServiceName`、`apiMode`、`apiBaseUrl` Storage 不会改变 SDK 体验版的目标。
- `cloud/auto` 的既有运行时 CloudBase target 覆盖和 `local` 的 API URL 覆盖仍保留；`public/http/cloud` transport 未删除。

### 3. SDK 错误归一化

- FastAPI 嵌套 `detail` 优先于微信适配层的 `errMsg: request:ok`。
- 4xx/5xx 能显示真实的清洗后业务错误；没有响应正文时回退到 HTTP 状态，不再把成功 transport 标记显示成失败原因。

### 4. 小程序页面可靠性与可读性

- Agent 候选分数统一转换为 0～100 的整数百分比，恢复历史会话时也执行同一归一化。
- 匹配页增加加载、失败、重试和反馈后刷新失败状态，避免网络故障时静默显示空列表。
- 通知页明确区分等待、暂停、已找到候选和过期；终态需求不再显示无效暂停按钮，并防止重复提交。
- Mutual Match 详情在 `/users/me` 刷新失败时仍显示已保存的对方资料和安全破冰建议。
- 画像、设置和聊天页补齐异步失败、按钮禁用与可见错误状态，避免未处理 Promise 或二次空对象异常。
- 微信开发者工具重新开启合法域名、TLS 和证书校验，减少“工具可用、真机失败”的配置偏差。

### 5. Web 和依赖可复现性

- 清理 Web OAuth 回调后同时移除 hash token、`auth_error` 和 `auth_stage`，防止刷新重复消费或 URL 残留。
- React/Vite 依赖从 `latest` 固定为 lockfile 中已验证的精确版本，保证重新安装结果可复现。

### 6. 文档和比赛材料一致性

- README 中相互矛盾的 `public`/`sdk` 默认 transport 描述已统一为当前真实的 `sdk`。
- 自动化基线统一更新为 `176 passed, 3 skipped`。
- 增加比赛材料再生成脚本，PDF 使用 headless Chrome、DOCX 使用 LibreOffice；可部署程序包按源码白名单生成，并排除 `.env`、本地数据库、虚拟环境、依赖缓存和开发者私有配置。
- 修复小程序源码打包脚本遗漏 `miniprogram_npm` 的问题，避免把未引用模块和 source map 带入交付包；回归检查锁定该排除规则。
- 关闭 headless Chrome 的默认 PDF 页眉页脚，生成材料不再暴露本机 `file://` 路径。

## 核心边界复核

- 双 Header 仍保持职责分离：CloudBase OAuth 管 Gateway，`X-Campus-Authorization` 中的 FastAPI JWT 仍执行原签名、issuer、exp、token version 和用户查询校验。
- `/auth/wechat` 继续使用 `wx.login code → code2session → FastAPI JWT`，CloudBase 匿名用户不会替代业务用户。
- LLM 只负责结构化语义和经同意的有限社交风格分析；候选硬过滤和最终分数仍由确定性程序产生。
- Block、Report、Mutual Match、消息权限、Session/Trace 等关键云端写入仍走现有 PostgreSQL RPC。
- 0009 汇总 SQL 的旧表加列顺序位于依赖索引和默认值操作之前；真实 PostgreSQL 0008→0009 数据保留测试继续通过。
- 小程序可包含 CloudBase Publishable Key；后端 API Key、LLM Key、JWT Secret、微信 AppSecret 和 service-role 凭据不得进入客户端或提交包。
- 本机 `.env` 与一个被 Git 忽略的旧环境备份原为组/其他用户可读，本轮已把两者文件权限收紧为 `0600`；它们均未进入 Git 或任何生成 ZIP。旧备份如已无用途，应由项目所有者确认后删除；若曾经外发，应轮换其中的凭据。

## 已知但未擅自改变的限制

1. 当前封闭内测尚未完成微信用户与校园身份的产品化绑定，因此 `REQUIRE_CAMPUS_VERIFICATION=false` 只能用于受控体验，不能等同于正式校园认证。
2. 传统邮箱注册路径只检查邮箱域名，没有邮件验证码闭环；在绑定流程完成前不应把它宣传为已验证校内身份。
3. CloudBase HTTP Adapter 的普通多请求写入不是通用数据库事务；安全关键路径已经使用 RPC，其余未来新增写操作应继续优先采用幂等 RPC。
4. 数据服务暂未对写请求做自动网络重试。盲目重试非幂等 mutation 可能重复写入，因此当前选择返回可诊断的 503，由用户安全重试。
5. 当前没有 Refresh Token 轮换、WebSocket/订阅推送、限流、完整举报审核与申诉后台。
6. Docker 启动时的 Mock Seed 和 `SHOW_MOCK_USERS=true` 是冷启动内测策略；扩大真实用户范围前应评估关闭，并继续保留“测试用户”显著标识。

## 最终验证命令

```bash
./.venv/bin/python -m pytest -q
./.venv/bin/ruff check .
./.venv/bin/python scripts/check_miniprogram.py
find miniprogram -type f -name '*.js' \
  -not -path '*/node_modules/*' \
  -not -path '*/miniprogram_npm/*' -print0 | xargs -0 -n1 node --check
(cd frontend && npm run build && npm audit --omit=dev)
(cd miniprogram && npm audit --omit=dev)
./.venv/bin/python -m pip check
```

三个 skipped 用例是必须显式启用且会调用真实外部 LLM 的集成测试，不属于失败。本轮没有为追求“全绿”而调用或消耗线上模型额度。
