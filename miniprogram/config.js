// 小程序运行配置。业务页面不要直接拼后端地址或云托管信息。
//
// local/public/http 都使用 wx.request。只有 local 允许用 Storage/ext config
// 覆盖 API 地址；public/http 始终使用代码中的正式 API_BASE_URL。
// cloud 使用 wx.cloud.callContainer；sdk 使用 @cloudbase/js-sdk callContainer。
const API_BASE_URL = 'https://campus-social-agent-304566-11-1476699034.sh.run.tcloudbase.com';
// 这两个值仅供可关联的 CloudBase callContainer 模式使用，不影响 wx.request。
const CLOUDBASE_ENV_ID = 'campus-social-d3gsie43e1ca1bc6c';
const CLOUDBASE_SERVICE_NAME = 'campus-social-agent';
// 仅 sdk 模式使用。这里只能填写 CloudBase Publishable Key，严禁填写
// 后端 CLOUDBASE_API_KEY、SecretId 或 SecretKey。
const CLOUDBASE_PUBLISHABLE_KEY = 'eyJhbGciOiJSUzI1NiIsImtpZCI6IjEyYWE4YjczLTc4NDYtNDkzZC1hM2Q0LTczMjI1MWI1OGVmMiJ9.eyJpc3MiOiJodHRwczovL2NhbXB1cy1zb2NpYWwtZDNnc2llNDNlMWNhMWJjNmMuYXAtc2hhbmdoYWkudGNiLWFwaS50ZW5jZW50Y2xvdWRhcGkuY29tIiwic3ViIjoiYW5vbiIsImF1ZCI6ImNhbXB1cy1zb2NpYWwtZDNnc2llNDNlMWNhMWJjNmMiLCJleHAiOjQwOTE3NjU0NzUsImlhdCI6MTc4ODA4MjI3NSwibm9uY2UiOiJsM3FpOS1oU1RQV0d3MktzNTFHZEt3IiwiYXRfaGFzaCI6ImwzcWk5LWhTVFBXR3cyS3M1MUdkS3ciLCJuYW1lIjoiQW5vbnltb3VzIiwic2NvcGUiOiJhbm9ueW1vdXMiLCJwcm9qZWN0X2lkIjoiY2FtcHVzLXNvY2lhbC1kM2dzaWU0M2UxY2ExYmM2YyIsIm1ldGEiOnsicGxhdGZvcm0iOiJQdWJsaXNoYWJsZUtleSJ9LCJyb2xlIjoiYW5vbiIsImlzX2Fub255bW91cyI6dHJ1ZSwiYXBwX21ldGFkYXRhIjp7InByb3ZpZGVyIjoiYW5vbnltb3VzIiwicHJvdmlkZXJzIjpbImFub255bW91cyJdfSwidXNlcl9tZXRhZGF0YSI6eyJuYW1lIjoiQW5vbnltb3VzIn0sInVzZXJfdHlwZSI6IiIsImNsaWVudF90eXBlIjoiY2xpZW50X3VzZXIiLCJpc19zeXN0ZW1fYWRtaW4iOmZhbHNlfQ.SnpfYMv02IMC8h41qaCRqUpmWgjZ7xbBg2Z8eqvt1NFjpR8Zu6xeD33cELcpUpn_BTA-5X68o0k7eJQCf0Oo2ZRL7bBr9QOJYPb0lOgJQuzF_iXZKLCUXdbdu47LHgpiAWFUwh7oOkb_mqNFgatsT4FYNdUdQSSIKfIm3ovXkIxkw30vzGy2ZHpofVj08TIz-qS3fMntOOYnLYtmAbYKAuvNn5DH7zvHWRt8tzSyzPhMkUWeJNGea03o9qZmRBIjSILoYPHtLVLBrR0CehbvqJSvRmyUkoy828Strx5U1T4BTxG5ti2t1i2CLiuxafNQsr6mIHWki-Tn69abSTuysA';
// 正式体验版使用 sdk；历史 apiMode/apiBaseUrl Storage 不能覆盖此发布设置。
const API_MODE = 'sdk';

function normalizeApiBaseUrl(value) {
  const normalized = String(value || '').trim().replace(/\/+$/, '');
  if (!/^https?:\/\//.test(normalized)) {
    throw new Error('API_BASE_URL 必须是 http:// 或 https:// 地址');
  }
  return normalized;
}

function getApiBaseUrl(mode = API_MODE) {
  // 只有显式 local 开发模式允许临时覆盖：
  // wx.setStorageSync('apiBaseUrl', 'http://电脑局域网IP:8000')
  const normalizedMode = String(mode || API_MODE).trim().toLowerCase();
  if (normalizedMode !== 'local') {
    return normalizeApiBaseUrl(API_BASE_URL);
  }
  let runtimeOverride = '';
  if (typeof wx !== 'undefined') {
    runtimeOverride = wx.getStorageSync('apiBaseUrl') || '';
    if (!runtimeOverride && typeof wx.getExtConfigSync === 'function') {
      const extConfig = wx.getExtConfigSync() || {};
      runtimeOverride = extConfig.apiBaseUrl || '';
    }
  }
  return normalizeApiBaseUrl(runtimeOverride || API_BASE_URL);
}

function getCloudbaseConfig(
  modeOverride = API_MODE,
  publishableKeyOverride = CLOUDBASE_PUBLISHABLE_KEY
) {
  let envId = '';
  let serviceName = '';
  if (typeof wx !== 'undefined') {
    envId = wx.getStorageSync('cloudbaseEnvId') || '';
    serviceName = wx.getStorageSync('cloudbaseServiceName') || '';
    if (typeof wx.getExtConfigSync === 'function') {
      const extConfig = wx.getExtConfigSync() || {};
      envId = envId || extConfig.cloudbaseEnvId || '';
      serviceName = serviceName || extConfig.cloudbaseServiceName || '';
    }
  }
  envId = String(envId || CLOUDBASE_ENV_ID).trim();
  serviceName = String(serviceName || CLOUDBASE_SERVICE_NAME).trim();
  // Transport mode is a release-time setting. Never let persistent Storage or
  // ext-config silently downgrade a public experience build to local mode.
  const mode = String(modeOverride || API_MODE).trim().toLowerCase();
  if (!['auto', 'cloud', 'sdk', 'local', 'public', 'http'].includes(mode)) {
    throw new Error('API_MODE 必须是 auto、cloud、sdk、local、public 或 http');
  }
  const enabled = mode === 'cloud' || (mode === 'auto' && Boolean(envId && serviceName));
  const sdkEnabled = mode === 'sdk';
  if (enabled && (!envId || !serviceName)) {
    throw new Error('CloudBase 模式必须配置环境 ID 和服务名');
  }
  const publishableKey = String(publishableKeyOverride || '').trim();
  if (sdkEnabled && (!envId || !serviceName || !publishableKey)) {
    throw new Error('SDK 模式必须配置环境 ID、服务名和 Publishable Key');
  }
  return {
    enabled,
    sdkEnabled,
    envId,
    serviceName,
    publishableKey,
    mode,
  };
}

module.exports = {
  API_BASE_URL,
  CLOUDBASE_ENV_ID,
  CLOUDBASE_SERVICE_NAME,
  CLOUDBASE_PUBLISHABLE_KEY,
  API_MODE,
  getApiBaseUrl,
  getCloudbaseConfig,
  normalizeApiBaseUrl,
};
