// services/api.js — 统一网络封装：base URL、鉴权、错误码、loading 与 timeout
// 部署方式变化时优先只改 config.js / 后端 adapter，不改各个页面。

const config = require('../config.js');
const cloudbaseSdk = require('./cloudbase-sdk.js');

function getToken() {
  try {
    return wx.getStorageSync('token');
  } catch (e) {
    return null;
  }
}

function setToken(token) {
  wx.setStorageSync('token', token);
}

function clearToken() {
  wx.removeStorageSync('token');
  loginPromise = null;
}

function errorMessage(detail, statusCode) {
  if (typeof detail === 'string') {
    return detail;
  }
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || JSON.stringify(item)).join('；');
  }
  return detail ? JSON.stringify(detail) : '请求失败 ' + statusCode;
}

function sdkStatusCode(value) {
  const numeric = Number(value);
  return numeric >= 400 && numeric <= 599 ? numeric : null;
}

function sdkHttpStatusCode(value) {
  const numeric = Number(value);
  return numeric >= 100 && numeric <= 599 ? numeric : null;
}

function sdkErrorNodes(error) {
  if (!error || typeof error !== 'object') {
    return [];
  }
  const nodes = [error];
  ['result', 'data', 'response'].forEach((key) => {
    if (error[key] && typeof error[key] === 'object') {
      nodes.push(error[key]);
    }
  });
  if (error.result && error.result.data && typeof error.result.data === 'object') {
    nodes.push(error.result.data);
  }
  return nodes;
}

function sdkErrorValue(error, keys) {
  const nodes = sdkErrorNodes(error);
  for (let index = 0; index < nodes.length; index += 1) {
    for (let keyIndex = 0; keyIndex < keys.length; keyIndex += 1) {
      const value = nodes[index][keys[keyIndex]];
      if (value !== undefined && value !== null && value !== '') {
        return value;
      }
    }
  }
  return undefined;
}

function sdkErrorType(error) {
  const message = String(
    sdkErrorValue(error, ['errMsg', 'message', 'error_description']) || ''
  ).toLowerCase();
  if (message.includes('timeout') || message.includes('超时')) {
    return 'timeout';
  }
  if (sdkStatusCode(sdkErrorValue(error, ['statusCode', 'status']))) {
    return 'http';
  }
  if (sdkErrorValue(error, ['code', 'error_code'])) {
    return 'gateway';
  }
  return message.includes('request:fail') ? 'network' : 'sdk';
}

function logSdkFailureDiagnostic(path, error, elapsedMs) {
  if (!isDiagnosticRuntime()) {
    return;
  }
  const rawCode = sdkErrorValue(error, ['code', 'error_code']);
  const safeCode =
    typeof rawCode === 'string' && /^[A-Za-z0-9_.-]{1,80}$/.test(rawCode)
      ? rawCode
      : null;
  console.info({
    path,
    errorType: sdkErrorType(error),
    statusCode:
      sdkStatusCode(sdkErrorValue(error, ['statusCode', 'status'])) || null,
    code: safeCode,
    hasDetail: Boolean(sdkErrorValue(error, ['detail'])),
    elapsedMs: Math.max(0, Math.round(elapsedMs || 0)),
  });
}

function sdkError(error, requestUrl, timeout) {
  const statusCode = sdkStatusCode(
    sdkErrorValue(error, ['statusCode', 'status', 'code'])
  );
  const rawMessage = sdkErrorValue(error, [
    'detail',
    'message',
    'errMsg',
    'error_description',
  ]);
  const timedOut = sdkErrorType(error) === 'timeout';
  const detail = timedOut
    ? 'CloudBase SDK 请求超时（' + Math.round(timeout / 1000) + ' 秒）'
    : rawMessage || 'CloudBase SDK 请求失败';
  const wrapped = new Error(errorMessage(detail, statusCode || 'SDK') + '（' + requestUrl + '）');
  if (statusCode) {
    wrapped.statusCode = statusCode;
  }
  return wrapped;
}

const SDK_RESPONSE_ENVELOPE_KEYS = new Set([
  'result',
  'data',
  'statusCode',
  'status',
  'header',
  'headers',
  'requestId',
  'request_id',
  'errMsg',
]);

function isSdkResponseEnvelope(value, payloadKey) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return false;
  }
  if (!Object.prototype.hasOwnProperty.call(value, payloadKey)) {
    return false;
  }
  // `from: node-sdk` makes CloudRun preserve the native wx.request response.
  // WeChat may append transport metadata such as cookies/profile/errMsg, so a
  // numeric HTTP status plus data is a stronger and safer envelope signal than
  // requiring an exact key whitelist.
  if (
    payloadKey === 'data' &&
    sdkHttpStatusCode(value.statusCode || value.status)
  ) {
    return true;
  }
  return Object.keys(value).every((key) => SDK_RESPONSE_ENVELOPE_KEYS.has(key));
}

function normalizeSdkResponse(response) {
  // @cloudbase/js-sdk v3.9.0 miniprogram_dist returns `await response.data`,
  // which is normally the FastAPI JSON body itself. Only unwrap documented or
  // previously observed transport envelopes; do not recursively guess through
  // arbitrary business objects that happen to contain a `data`/`result` field.
  if (isSdkResponseEnvelope(response, 'result')) {
    const result = response.result;
    return isSdkResponseEnvelope(result, 'data') ? result.data : result;
  }
  if (isSdkResponseEnvelope(response, 'data')) {
    return response.data;
  }
  return response;
}

function normalizeBusinessToken(token) {
  return typeof token === 'string' ? token.trim() : '';
}

function buildRequestHeader(customHeader, token, cloudbase) {
  const header = {
    'Content-Type': 'application/json',
    ...customHeader,
  };
  const businessToken = normalizeBusinessToken(token);
  if (businessToken) {
    const authorizationHeader = cloudbase.sdkEnabled
      ? 'X-Campus-Authorization'
      : 'Authorization';
    header[authorizationHeader] = 'Bearer ' + businessToken;
  }
  return header;
}

function isDiagnosticRuntime() {
  try {
    if (!wx || typeof wx.getAccountInfoSync !== 'function') {
      return false;
    }
    const account = wx.getAccountInfoSync() || {};
    const envVersion = account.miniProgram && account.miniProgram.envVersion;
    return envVersion === 'develop' || envVersion === 'trial';
  } catch (e) {
    return false;
  }
}

function logCampusAuthDiagnostic(path, header, token) {
  if (!isDiagnosticRuntime()) {
    return;
  }
  const campusAuthorization = header['X-Campus-Authorization'];
  console.info({
    path,
    hasCampusAuthHeader:
      typeof campusAuthorization === 'string' &&
      campusAuthorization.startsWith('Bearer ') &&
      campusAuthorization.length > 'Bearer '.length,
    tokenLength: normalizeBusinessToken(token).length,
  });
}

function missingCampusAuthError(path) {
  const error = new Error('业务登录状态缺失，请重新登录（' + path + '）');
  error.statusCode = 401;
  return error;
}

function request(options) {
  const {
    url,
    method = 'GET',
    data = null,
    header: customHeader = {},
    auth = true,
  } = options;
  const send = (token) =>
    new Promise((resolve, reject) => {
      const cloudbase = config.getCloudbaseConfig();
      const requestUrl = cloudbase.sdkEnabled
        ? 'cloudbase-sdk://' + cloudbase.envId + '/' + cloudbase.serviceName + url
        : cloudbase.enabled
        ? 'cloudbase://' + cloudbase.envId + '/' + cloudbase.serviceName + url
        : config.getApiBaseUrl(cloudbase.mode) + url;
      const header = buildRequestHeader(customHeader, token, cloudbase);
      logCampusAuthDiagnostic(url, header, token);
      // SDK/Gateway 模式没有 FastAPI JWT 时不得发送受保护请求，否则后端只会
      // 收到一个缺少 X-Campus-Authorization 的请求并返回 401。
      if (auth && cloudbase.sdkEnabled && !normalizeBusinessToken(token)) {
        reject(missingCampusAuthError(url));
        return;
      }
      const timeout = url === '/agent/chat' ? 60000 : 30000;
      if (cloudbase.sdkEnabled) {
        const startedAt = Date.now();
        const rejectSdkError = (error) => {
          logSdkFailureDiagnostic(url, error, Date.now() - startedAt);
          reject(sdkError(error, requestUrl, timeout));
        };
        cloudbaseSdk.callCloudbaseContainer(
          cloudbase,
          {
            name: cloudbase.serviceName,
            method,
            path: url,
            header,
            data,
          },
          { timeout }
        ).then(
          (res) => {
            const statusCode = sdkStatusCode(
              sdkErrorValue(res, ['statusCode', 'status'])
            );
            if (statusCode) {
              throw res;
            }
            if (res && res.code) {
              const error = new Error(res.message || String(res.code));
              error.code = res.code;
              error.result = res.result;
              throw error;
            }
            resolve(normalizeSdkResponse(res));
          },
          rejectSdkError
        ).catch(rejectSdkError);
        return;
      }
      const requestOptions = {
        method,
        data,
        header,
        timeout,
        success(res) {
          if (res.statusCode >= 200 && res.statusCode < 300) {
            resolve(res.data);
          } else {
            const detail = res.data && res.data.detail;
            const error = new Error(errorMessage(detail, res.statusCode));
            error.statusCode = res.statusCode;
            reject(error);
          }
        },
        fail(err) {
          reject(new Error((err.errMsg || '网络错误') + '（' + requestUrl + '）'));
        },
      };
      if (cloudbase.enabled) {
        if (!wx.cloud || typeof wx.cloud.callContainer !== 'function') {
          reject(new Error('当前基础库不支持 wx.cloud.callContainer'));
          return;
        }
        wx.cloud.callContainer({
          ...requestOptions,
          config: { env: cloudbase.envId },
          path: url,
          header: {
            ...header,
            'X-WX-SERVICE': cloudbase.serviceName,
          },
        });
        return;
      }
      wx.request({
        ...requestOptions,
        url: requestUrl,
      });
    });
  if (!auth) {
    return send(null);
  }
  const existingToken = getToken();
  // 未登录：先尝试微信登录（失败则按后端 DEV_AUTH_MODE 无 token 放行）。
  const tokenPromise = existingToken
    ? Promise.resolve(existingToken)
    : login().catch(() => null);
  return tokenPromise.then((token) =>
    send(token).catch((error) => {
      if (error.statusCode !== 401 || !token) {
        throw error;
      }
      // Token 过期时只重试一次微信登录；避免所有页面分别处理 401。
      clearToken();
      return login().then(
        (newToken) => send(newToken),
        (loginError) => {
          // In SDK mode a protected API must never be retried without the
          // FastAPI JWT. Surface the login failure instead of replacing it
          // with a second unauthenticated /agent/chat request.
          if (config.getCloudbaseConfig().sdkEnabled) {
            throw loginError;
          }
          return send(null);
        }
      );
    })
  );
}

function wechatLogin(code) {
  return request({ url: '/auth/wechat', method: 'POST', data: { code }, auth: false });
}

let loginPromise = null;

function login() {
  if (!loginPromise) {
    loginPromise = new Promise((resolve, reject) => {
      wx.login({
        success(res) {
          wechatLogin(res.code).then(
            (data) => {
              const token = data && data.access_token;
              if (!token) {
                loginPromise = null;
                reject(new Error('微信登录响应缺少 access_token'));
                return;
              }
              setToken(token);
              loginPromise = null;
              resolve(token);
            },
            (err) => {
              loginPromise = null;
              reject(err);
            }
          );
        },
        fail(err) {
          loginPromise = null;
          reject(new Error(err.errMsg || 'wx.login 失败'));
        },
      });
    });
  }
  return loginPromise;
}

function ensureToken() {
  if (getToken()) {
    return Promise.resolve(getToken());
  }
  return login().catch(() => null);
}

function getMe() {
  return request({ url: '/users/me' });
}

function updateMe(payload) {
  return request({ url: '/users/me', method: 'PATCH', data: payload });
}

function parseProfile(text, apply = true) {
  return request({
    url: '/users/me/profile/parse',
    method: 'POST',
    data: { text, apply },
  });
}

function agentChat(message, limit = 3, sessionId = null) {
  return request({
    url: '/agent/chat',
    method: 'POST',
    data: { message, limit, session_id: sessionId },
    auth: true,
  });
}

function getMatches() {
  return request({ url: '/matches/me' });
}

function getMatchDetail(matchId) {
  return request({ url: '/matches/me/' + matchId });
}

function sendFeedback(candidateId, feedback) {
  return request({
    url: '/feedback',
    method: 'POST',
    data: { candidate_id: candidateId, feedback },
  });
}

function blockUser(blockedUserId) {
  return request({
    url: '/block',
    method: 'POST',
    data: { blocked_user_id: blockedUserId },
  });
}

function reportUser(reportedUserId, reason, category = 'OTHER') {
  return request({
    url: '/report',
    method: 'POST',
    data: {
      reported_user_id: reportedUserId,
      reason,
      category,
    },
  });
}

function getActivities() {
  return request({ url: '/activities' });
}

function analyzePersonality(text) {
  return request({
    url: '/users/me/personality/analyze',
    method: 'POST',
    data: { text, consent: true },
  });
}

function clearPersonality() {
  return request({ url: '/users/me/personality', method: 'DELETE' });
}

function getConversations() {
  return request({ url: '/conversations' });
}

function getMessages(partnerId) {
  return request({ url: '/conversations/' + partnerId + '/messages' });
}

function sendMessage(partnerId, body) {
  return request({
    url: '/conversations/' + partnerId + '/messages',
    method: 'POST',
    data: { body },
  });
}

function markConversationRead(partnerId) {
  return request({
    url: '/conversations/' + partnerId + '/read',
    method: 'POST',
  });
}

function getNotifications(unreadOnly = false) {
  return request({ url: '/notifications?unread_only=' + String(unreadOnly) });
}

function markNotificationRead(notificationId) {
  return request({
    url: '/notifications/' + notificationId + '/read',
    method: 'POST',
  });
}

function getPartnerRequests() {
  return request({ url: '/partner-requests' });
}

function updatePartnerRequest(requestId, status) {
  return request({
    url: '/partner-requests/' + requestId,
    method: 'PATCH',
    data: { status },
  });
}

module.exports = {
  getToken,
  setToken,
  clearToken,
  normalizeSdkResponse,
  wechatLogin,
  ensureToken,
  getMe,
  updateMe,
  parseProfile,
  agentChat,
  getMatches,
  getMatchDetail,
  sendFeedback,
  blockUser,
  reportUser,
  getActivities,
  analyzePersonality,
  clearPersonality,
  getConversations,
  getMessages,
  sendMessage,
  markConversationRead,
  getNotifications,
  markNotificationRead,
  getPartnerRequests,
  updatePartnerRequest,
  getApiBaseUrl: config.getApiBaseUrl,
  getCloudbaseConfig: config.getCloudbaseConfig,
};
