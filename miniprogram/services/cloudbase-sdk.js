// CloudBase JS SDK v3 adapter. Modules and OAuth are loaded lazily so the
// existing public/local fallback does not initialize CloudBase at startup.

let cachedApp = null;
let cachedAuth = null;
let cachedIdentity = '';
let modulesRegistered = false;
let authenticated = false;
let loginPromise = null;
let authGeneration = 0;

// CloudBase JS SDK v3.9.0 accepts customReqOpts in callContainer(), but its
// CloudRun implementation passes that value to the Mini Program request
// adapter as a nested field. The adapter only reads the timeout configured at
// app initialization. Keep the underlying request open for the longest API
// budget; invokeContainer() below enforces the per-request budget.
const MAX_CONTAINER_TIMEOUT_MS = 60000;

function loadCloudbase() {
  // Keep the three v3.9.0 Mini Program bundles in fixed vendor paths. The
  // WeChat uploader can otherwise prune these lazily loaded npm modules as
  // "unused", producing a package that compiles but fails on-device.
  const appModule = require('../vendor/cloudbase/app.js');
  const cloudbase = appModule.default || appModule;
  if (!modulesRegistered) {
    const authModule = require('../vendor/cloudbase/auth.js');
    const cloudrunModule = require('../vendor/cloudbase/cloudrun.js');
    authModule.registerAuth(cloudbase);
    cloudrunModule.registerCloudrun(cloudbase);
    modulesRegistered = true;
  }
  return cloudbase;
}

function sdkIdentity(options) {
  return [options.envId, options.serviceName, options.publishableKey].join(':');
}

function getCloudbaseSdkApp(options) {
  const identity = sdkIdentity(options);
  if (cachedApp && cachedIdentity === identity) {
    return cachedApp;
  }
  const cloudbase = loadCloudbase();
  const app = cloudbase.init({
    env: options.envId,
    accessKey: options.publishableKey,
    timeout: MAX_CONTAINER_TIMEOUT_MS,
  });
  if (!app || typeof app.auth !== 'function') {
    throw new Error('CloudBase Auth 模块初始化失败');
  }
  const auth = app.auth({ persistence: 'local' });
  cachedApp = app;
  cachedAuth = auth;
  cachedIdentity = identity;
  authenticated = false;
  loginPromise = null;
  authGeneration = 0;
  return cachedApp;
}

function validateLoginResult(result) {
  if (result && result.error) {
    throw result.error;
  }
  const session = result && result.data && result.data.session;
  if (!session || !session.access_token) {
    throw new Error('CloudBase Auth 登录未返回有效 OAuth session');
  }
}

function ensureCloudbaseAuth(options, force = false) {
  const app = getCloudbaseSdkApp(options);
  if (authenticated && !force) {
    return Promise.resolve({ app, generation: authGeneration });
  }
  if (loginPromise) {
    return loginPromise;
  }
  if (force) {
    authenticated = false;
  }
  const pending = Promise.resolve()
    .then(() => cachedAuth.signInAnonymously())
    .then((result) => {
      validateLoginResult(result);
      authenticated = true;
      authGeneration += 1;
      loginPromise = null;
      return { app, generation: authGeneration };
    })
    .catch((error) => {
      authenticated = false;
      loginPromise = null;
      throw error;
    });
  loginPromise = pending;
  return pending;
}

function nestedValue(error, key) {
  if (!error || typeof error !== 'object') {
    return undefined;
  }
  return (
    error[key] ||
    (error.result && error.result[key]) ||
    (error.data && error.data[key])
  );
}

function isCloudbaseSessionError(error) {
  // FastAPI application 401 contains detail and belongs to the campus JWT
  // retry path in api.js, not the CloudBase OAuth retry path here.
  if (nestedValue(error, 'detail')) {
    return false;
  }
  const status = Number(
    nestedValue(error, 'statusCode') || nestedValue(error, 'status')
  );
  if (status === 401) {
    return true;
  }
  const code = String(
    nestedValue(error, 'code') || nestedValue(error, 'error_code') || ''
  ).toUpperCase();
  const message = String(nestedValue(error, 'message') || '').toUpperCase();
  const diagnostic = code + ' ' + message;
  return [
    'TOKEN_EXPIRED',
    'SESSION_EXPIRED',
    'LOGIN_STATE_EXPIRED',
    'INVALID_TOKEN',
    'INVALID_GRANT',
    'INVALID_CREDENTIAL',
    'CREDENTIALS_ERROR',
    'REFRESH_TOKEN',
    'AUTHENTICATION_FAILED',
    'MISSING_CREDENTIAL',
    "YOU CAN'T REQUEST WITHOUT AUTH",
  ].some((marker) => diagnostic.includes(marker));
}

function containerTimeoutError(timeout) {
  const seconds = Math.max(1, Math.round(timeout / 1000));
  const error = new Error('CloudBase SDK 请求超时（' + seconds + ' 秒）');
  error.code = 'CAMPUS_SDK_TIMEOUT';
  return error;
}

function withRequestTimeout(promise, timeout) {
  const timeoutMs = Number(timeout);
  if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) {
    return promise;
  }
  return new Promise((resolve, reject) => {
    const timer = setTimeout(
      () => reject(containerTimeoutError(timeoutMs)),
      timeoutMs
    );
    Promise.resolve(promise).then(
      (value) => {
        clearTimeout(timer);
        resolve(value);
      },
      (error) => {
        clearTimeout(timer);
        reject(error);
      }
    );
  });
}

function invokeContainer(app, requestOptions, transportOptions) {
  const request = Promise.resolve().then(() =>
    // The SDK-level timeout comes from cloudbase.init(). The second argument is
    // used only to preserve the HTTP response envelope. v3.9.0 otherwise
    // returns response.data directly and loses statusCode on Mini Programs.
    // Do not put timeout here: v3.9.0 does not propagate it to wx.request.
    app.callContainer(requestOptions, { from: 'node-sdk' })
  );
  return withRequestTimeout(request, transportOptions && transportOptions.timeout)
    .then((response) => {
      if (isCloudbaseSessionError(response)) {
        throw response;
      }
      return response;
    });
}

function callCloudbaseContainer(options, requestOptions, transportOptions) {
  return ensureCloudbaseAuth(options).then(({ app, generation }) =>
    invokeContainer(app, requestOptions, transportOptions).catch((error) => {
      if (!isCloudbaseSessionError(error)) {
        throw error;
      }
      // If another request already refreshed this generation, reuse it rather
      // than starting another anonymous login for the stale failure.
      const refresh = generation === authGeneration
        ? ensureCloudbaseAuth(options, true)
        : ensureCloudbaseAuth(options);
      return refresh.then(() =>
        invokeContainer(app, requestOptions, transportOptions)
      );
    })
  );
}

module.exports = {
  callCloudbaseContainer,
  ensureCloudbaseAuth,
  getCloudbaseSdkApp,
  isCloudbaseSessionError,
  withRequestTimeout,
};
