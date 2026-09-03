// app.js — 启动时尝试微信登录；失败（如未配 AppID）时静默降级，
// 由后端 DEV_AUTH_MODE 提供本地开发身份。
const api = require('./services/api.js');
const config = require('./config.js');

App({
  globalData: {
    token: null,
    user: null,
  },
  onLaunch() {
    const cloudbase = config.getCloudbaseConfig();
    if (cloudbase.enabled && wx.cloud) {
      wx.cloud.init({
        env: cloudbase.envId,
        traceUser: true,
      });
    }
    api.ensureToken();
  },
});
