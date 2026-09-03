# 微信小程序真机联调手册

本手册用于完成“开发者工具 + 手机真机调试”这项外部验收。代码仓库已经验证后端能监听局域网地址，但仍需要项目拥有者在微信开发者工具和手机上完成扫码。局域网 HTTP 地址只用于临时真机调试；当前正式预览/体验版使用云托管公网 HTTPS + `wx.request`。

## 1. 启动局域网后端

电脑和手机连接同一个 Wi-Fi，在项目根目录执行：

```bash
LLM_PROVIDER=mock DEV_AUTH_MODE=true ./scripts/start_mobile_backend.sh
```

脚本会执行迁移和幂等 Seed，然后打印类似下面的信息：

```text
手机地址：http://192.168.1.20:8000
wx.setStorageSync('apiBaseUrl', 'http://192.168.1.20:8000')
```

先用电脑验证打印出的地址：

```bash
curl http://192.168.1.20:8000/health
```

如果手机不能访问，请依次检查：手机和电脑是否同一网段、电脑防火墙是否放行该端口、Wi-Fi 是否开启了客户端隔离，以及当前 IP 是否来自真实无线网卡而不是 VPN/容器网卡。

如果脚本识别到 `100.64.0.0/10` 地址并且手机报告 `ERR_ADDRESS_UNREACHABLE`，通常是校园网/公共 Wi-Fi 的客户端隔离，不是 FastAPI 故障。改用以下任一网络后重新运行脚本获取新 IP：

1. 手机开启热点，让电脑连接手机热点；
2. 手机和电脑连接允许设备互访的家庭路由器；
3. 部署到当前 CloudBase 云托管，开启公网 HTTPS，并通过 `wx.request` 访问。

先在手机浏览器访问脚本打印的 `/health`；只有它返回 `{"status":"ok"}` 后再调试小程序。

## 2. 导入小程序

1. 微信开发者工具选择“导入项目”，目录选 `miniprogram/`。
2. 本地 UI 联调可使用测试号；验证真实 `wx.login` 必须使用自己的小程序 AppID。
3. 开发者工具的本地调试设置中临时开启“不校验合法域名、web-view、TLS 版本以及 HTTPS 证书”。这个开关只适用于开发调试，不能代替体验版的合法域名配置。
4. 不要先点普通“预览”，点击工具栏的“真机调试”并扫码。
5. 等远程调试器连接手机后，在这个远程控制台执行启动脚本打印的 `wx.setStorageSync(...)`。此时命令写入的是手机运行环境；在普通模拟器控制台执行不会自动同步到手机。
6. 返回小程序页面重新触发请求，所有请求会通过 `miniprogram/config.js` 读取该地址。

也可以在扫码前直接把 `miniprogram/config.js` 的 `API_BASE_URL` 改成电脑局域网地址。这个方式能把地址带入手机包，但普通预览仍然会进行域名校验；局域网 HTTP 依然要使用“真机调试”。恢复 storage 默认值：

```javascript
wx.removeStorageSync('apiBaseUrl')
```

## 3. 身份模式

本地 UI 联调建议保持：

```text
APP_ENV=development
DEV_AUTH_MODE=true
DEV_USER_ID=user001
LLM_PROVIDER=mock
SHOW_MOCK_USERS=true
```

此模式用于验证页面与 Agent 主链，不验证真实微信身份。验证真实登录时必须关闭 `DEV_AUTH_MODE`，并在后端设置 `WECHAT_APP_ID`、`WECHAT_APP_SECRET`；Secret 绝不能进入小程序源码。

## 4. 手机真机调试

开发者工具点击“真机调试”，手机微信扫码。至少完整走一遍：

1. 进入画像页，修改昵称、校区、兴趣、空闲时间并保存，重新进入后仍能读取。
2. 输入“我要准备考研，帮我找一个在西区一起复习的搭子”。
3. 确认加载态只出现一次、没有重复提交，返回 Top 3 且 Mock 候选都有“测试用户”标记。
4. 对一名候选点“感兴趣”，对另一名点“跳过”，刷新页面后已处理卡片不应重新出现在本地队列。
5. 验证 Block 后该用户不再进入下一轮推荐；验证举报入口能提交且不会泄露联系方式。
6. 用两个真实测试身份互相 LIKE，确认只在双向 LIKE 后建立 Mutual Match。Mock 参与的匹配必须显示测试匹配且不能聊天。

## 5. UX 检查表

- [ ] iPhone 和 Android 至少各一台没有横向溢出
- [ ] 昵称、理由、破冰话题的长文本没有覆盖按钮
- [ ] 请求期间按钮禁用，连续点击不会发出多次请求
- [ ] 空列表、断网、401、500 都有可理解提示
- [ ] 返回上一页后推荐处理状态保持一致
- [ ] 安全区、键盘弹起、下拉滚动和小屏幕布局正常
- [ ] Mock/真实用户标识足够醒目
- [ ] 隐私说明、拉黑、举报入口可找到

## 当前验证边界

2026-08-28 已实际验证 `start_mobile_backend.sh` 在 `0.0.0.0` 启动，并可通过自动识别的局域网 IP 访问 `/health`。当前机器没有微信开发者工具和手机控制权，因此扫码、真机布局、真实 `wx.login` 尚未声称通过。

## `request:fail url not in domain list`

这个错误表示微信客户端在网络请求发出前拦截了 URL，FastAPI 不会出现访问日志。

局域网联调：确认 `project.config.json` / 本地项目设置中的 `urlCheck=false`，使用“真机调试”而不是“预览”，并在远程调试控制台写入手机自己的 `apiBaseUrl` storage。错误提示末尾会显示实际请求 URL；它必须是电脑局域网 IP，不能是 `127.0.0.1`。

普通预览/体验版：保持 `config.js` 的 `API_MODE='sdk'`，由 CloudBase JS SDK 匿名登录后调用 Gateway/`callContainer()`。发布模式只取代码常量，手机里遗留的 `apiMode` 或 `apiBaseUrl` 不会改变 SDK transport。开发者工具需已构建 npm，CloudBase 需已开启匿名登入。本地联调时可临时改为 `local`，公网 HTTPS 回退可改为 `public`，上传前恢复为 `sdk`。
