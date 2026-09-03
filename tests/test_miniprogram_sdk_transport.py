"""CloudBase JS SDK v3 transport contracts for the native Mini Program."""

import json
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _run_node(script: str) -> dict | list:
    try:
        result = subprocess.run(
            ["node", "-e", script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        pytest.skip("node is required for the Mini Program SDK contract tests")
    return json.loads(result.stdout)


def test_sdk_adapter_initializes_v3_with_publishable_key():
    script = r"""
const Module = require('module');
const originalLoad = Module._load;
let initOptions = null;
let authOptions = null;
let initCalls = 0;
let authCalls = 0;
let authRegistrations = 0;
let cloudrunRegistrations = 0;
const fakeAuth = { signInAnonymously() {} };
const fakeApp = {
  auth(options) { authCalls += 1; authOptions = options; return fakeAuth; },
  callContainer() {}
};
const fakeCloudbase = {
  init(options) { initCalls += 1; initOptions = options; return fakeApp; }
};
Module._load = function(request, parent, isMain) {
  if (request === '../vendor/cloudbase/app.js') return fakeCloudbase;
  if (request === '../vendor/cloudbase/auth.js') {
    return { registerAuth(value) {
      if (value !== fakeCloudbase) throw new Error('Wrong Auth registration target');
      authRegistrations += 1;
    } };
  }
  if (request === '../vendor/cloudbase/cloudrun.js') {
    return { registerCloudrun(value) {
      if (value !== fakeCloudbase) throw new Error('Wrong CloudRun registration target');
      cloudrunRegistrations += 1;
    } };
  }
  return originalLoad.call(this, request, parent, isMain);
};
const adapter = require('./miniprogram/services/cloudbase-sdk.js');
const options = {
  envId: 'campus-social-d3gsie43e1ca1bc6c',
  serviceName: 'campus-social-agent',
  publishableKey: 'publishable-test-key'
};
const app = adapter.getCloudbaseSdkApp(options);
const sameApp = adapter.getCloudbaseSdkApp(options);
process.stdout.write(JSON.stringify({
  sameApp: app === fakeApp && sameApp === fakeApp,
  initCalls,
  authCalls,
  authRegistrations,
  cloudrunRegistrations,
  initOptions,
  authOptions
}));
"""
    assert _run_node(script) == {
        "sameApp": True,
        "initCalls": 1,
        "authCalls": 1,
        "authRegistrations": 1,
        "cloudrunRegistrations": 1,
        "initOptions": {
            "env": "campus-social-d3gsie43e1ca1bc6c",
            "accessKey": "publishable-test-key",
            "timeout": 60000,
        },
        "authOptions": {"persistence": "local"},
    }


def test_real_v390_miniprogram_cloudrun_can_preserve_http_response_envelope():
    script = r"""
global.cloudbase = { registerComponent() {} };
global.window = {};
const cloudrun = require(
  './miniprogram/node_modules/@cloudbase/js-sdk/miniprogram_dist/cloudrun/index.js'
);
const sdkPackage = require(
  './miniprogram/node_modules/@cloudbase/js-sdk/package.json'
);
const body = { status: 'ok', source: 'fastapi' };
const fetchOptions = [];
const context = {
  getEndPointWithKey() {
    return { BASE_URL: 'example.invalid', PROTOCOL: 'https://' };
  },
  request: {
    fetch() {
      fetchOptions.push(arguments[0]);
      return Promise.resolve({ data: body, statusCode: 200 });
    }
  }
};
Promise.all([
  cloudrun.requestContainer.call(context, {
    name: 'campus-social-agent', method: 'GET', path: '/health'
  }, { timeout: 60000 }),
  cloudrun.requestContainer.call(context, {
    name: 'campus-social-agent', method: 'GET', path: '/health'
  }, { from: 'node-sdk' })
]).then(([direct, envelope]) => process.stdout.write(JSON.stringify({
  version: sdkPackage.version,
  returnsBodyDirectly: direct === body,
  hasResultWrapper: Boolean(direct && direct.result),
  preservesStatusCode: envelope.statusCode === 200,
  preservedBody: envelope.data === body,
  timeoutIsNested: fetchOptions[0].customReqOpts.timeout === 60000,
  topLevelTimeoutMissing: fetchOptions[0].timeout === undefined
})));
"""
    assert _run_node(script) == {
        "version": "3.9.0",
        "returnsBodyDirectly": True,
        "hasResultWrapper": False,
        "preservesStatusCode": True,
        "preservedBody": True,
        "timeoutIsNested": True,
        "topLevelTimeoutMissing": True,
    }


def test_sdk_adapter_enforces_timeout_and_requests_http_response_envelope():
    script = r"""
const Module = require('module');
const originalLoad = Module._load;
let callArguments = null;
const fakeApp = {
  auth() {
    return { signInAnonymously() {
      return Promise.resolve({
        data: {
          user: { id: 'oauth-user' },
          session: { access_token: 'oauth-token' }
        },
        error: null
      });
    } };
  },
  callContainer() {
    callArguments = Array.from(arguments);
    return new Promise(() => {});
  }
};
const fakeCloudbase = { init() { return fakeApp; } };
Module._load = function(request, parent, isMain) {
  if (request === '../vendor/cloudbase/app.js') return fakeCloudbase;
  if (request === '../vendor/cloudbase/auth.js') return { registerAuth() {} };
  if (request === '../vendor/cloudbase/cloudrun.js') return { registerCloudrun() {} };
  return originalLoad.call(this, request, parent, isMain);
};
const adapter = require('./miniprogram/services/cloudbase-sdk.js');
adapter.callCloudbaseContainer({
  envId: 'campus-social-d3gsie43e1ca1bc6c',
  serviceName: 'campus-social-agent',
  publishableKey: 'publishable-test-key'
}, { name: 'campus-social-agent', path: '/agent/chat' }, { timeout: 5 }).then(
  () => { throw new Error('Expected local timeout guard to reject'); },
  (error) => process.stdout.write(JSON.stringify({
    callArgumentCount: callArguments.length,
    responseMode: callArguments[1],
    code: error.code,
    message: error.message
  }))
);
"""
    result = _run_node(script)
    assert result == {
        "callArgumentCount": 2,
        "responseMode": {"from": "node-sdk"},
        "code": "CAMPUS_SDK_TIMEOUT",
        "message": "CloudBase SDK 请求超时（1 秒）",
    }


def test_sdk_first_concurrent_requests_share_one_anonymous_login():
    script = r"""
const Module = require('module');
const originalLoad = Module._load;
let releaseLogin = null;
let signInCalls = 0;
let containerCalls = 0;
const loginArgumentCounts = [];
const fakeAuth = {
  signInAnonymously() {
    signInCalls += 1;
    loginArgumentCounts.push(arguments.length);
    return new Promise((resolve) => { releaseLogin = resolve; });
  }
};
const fakeApp = {
  auth() { return fakeAuth; },
  callContainer(options) {
    containerCalls += 1;
    return Promise.resolve({ result: { path: options.path } });
  }
};
const fakeCloudbase = { init() { return fakeApp; } };
Module._load = function(request, parent, isMain) {
  if (request === '../vendor/cloudbase/app.js') return fakeCloudbase;
  if (request === '../vendor/cloudbase/auth.js') return { registerAuth() {} };
  if (request === '../vendor/cloudbase/cloudrun.js') return { registerCloudrun() {} };
  return originalLoad.call(this, request, parent, isMain);
};
const adapter = require('./miniprogram/services/cloudbase-sdk.js');
const config = {
  envId: 'campus-social-d3gsie43e1ca1bc6c',
  serviceName: 'campus-social-agent',
  publishableKey: 'publishable-test-key'
};
const first = adapter.callCloudbaseContainer(
  config, { name: config.serviceName, path: '/users/me' }, { timeout: 30000 }
);
const second = adapter.callCloudbaseContainer(
  config, { name: config.serviceName, path: '/activities' }, { timeout: 30000 }
);
setTimeout(() => {
  const beforeLogin = { signInCalls, containerCalls };
  releaseLogin({
    data: { user: { id: 'oauth-user' }, session: { access_token: 'oauth-token' } },
    error: null
  });
  Promise.all([first, second]).then((responses) => {
    process.stdout.write(JSON.stringify({
      beforeLogin,
      signInCalls,
      containerCalls,
      loginArgumentCounts,
      responses
    }));
  });
}, 0);
"""
    result = _run_node(script)
    assert result["beforeLogin"] == {"signInCalls": 1, "containerCalls": 0}
    assert result["signInCalls"] == 1
    assert result["containerCalls"] == 2
    assert result["loginArgumentCounts"] == [0]
    assert result["responses"] == [
        {"result": {"path": "/users/me"}},
        {"result": {"path": "/activities"}},
    ]


def test_sdk_auth_failure_stops_before_container_call():
    script = r"""
const Module = require('module');
const originalLoad = Module._load;
let containerCalls = 0;
const authFailure = new Error('anonymous login rejected');
const fakeApp = {
  auth() {
    return { signInAnonymously() {
      return Promise.resolve({
        data: { user: null, session: null },
        error: authFailure
      });
    } };
  },
  callContainer() { containerCalls += 1; return Promise.resolve({}); }
};
const fakeCloudbase = { init() { return fakeApp; } };
Module._load = function(request, parent, isMain) {
  if (request === '../vendor/cloudbase/app.js') return fakeCloudbase;
  if (request === '../vendor/cloudbase/auth.js') return { registerAuth() {} };
  if (request === '../vendor/cloudbase/cloudrun.js') return { registerCloudrun() {} };
  return originalLoad.call(this, request, parent, isMain);
};
const adapter = require('./miniprogram/services/cloudbase-sdk.js');
adapter.callCloudbaseContainer({
  envId: 'campus-social-d3gsie43e1ca1bc6c',
  serviceName: 'campus-social-agent',
  publishableKey: 'publishable-test-key'
}, { name: 'campus-social-agent', path: '/health' }, { timeout: 30000 }).then(
  () => { throw new Error('Expected CloudBase Auth to fail'); },
  (error) => process.stdout.write(JSON.stringify({
    message: error.message,
    sameError: error === authFailure,
    containerCalls
  }))
);
"""
    result = _run_node(script)
    assert result == {
        "message": "anonymous login rejected",
        "sameError": True,
        "containerCalls": 0,
    }


def test_sdk_expired_session_reauthenticates_once_then_retries():
    script = r"""
const Module = require('module');
const originalLoad = Module._load;
let signInCalls = 0;
let containerCalls = 0;
const fakeAuth = {
  signInAnonymously() {
    signInCalls += 1;
    return Promise.resolve({
      data: {
        user: { id: 'oauth-user' },
        session: { access_token: 'oauth-token-' + signInCalls }
      },
      error: null
    });
  }
};
const fakeApp = {
  auth() { return fakeAuth; },
  callContainer() {
    containerCalls += 1;
    if (containerCalls === 1) {
      return Promise.reject({ statusCode: 401, code: 'TOKEN_EXPIRED' });
    }
    return Promise.resolve({ result: { status: 'ok' } });
  }
};
const fakeCloudbase = { init() { return fakeApp; } };
Module._load = function(request, parent, isMain) {
  if (request === '../vendor/cloudbase/app.js') return fakeCloudbase;
  if (request === '../vendor/cloudbase/auth.js') return { registerAuth() {} };
  if (request === '../vendor/cloudbase/cloudrun.js') return { registerCloudrun() {} };
  return originalLoad.call(this, request, parent, isMain);
};
const adapter = require('./miniprogram/services/cloudbase-sdk.js');
adapter.callCloudbaseContainer({
  envId: 'campus-social-d3gsie43e1ca1bc6c',
  serviceName: 'campus-social-agent',
  publishableKey: 'publishable-test-key'
}, { name: 'campus-social-agent', path: '/health' }, { timeout: 30000 }).then(
  (response) => process.stdout.write(JSON.stringify({
    response,
    signInCalls,
    containerCalls
  }))
);
"""
    result = _run_node(script)
    assert result == {
        "response": {"result": {"status": "ok"}},
        "signInCalls": 2,
        "containerCalls": 2,
    }


def test_sdk_fastapi_401_does_not_reauthenticate_cloudbase_session():
    script = r"""
const Module = require('module');
const originalLoad = Module._load;
let signInCalls = 0;
let containerCalls = 0;
const businessError = {
  statusCode: 401,
  data: { detail: 'valid bearer token required' }
};
const fakeApp = {
  auth() {
    return { signInAnonymously() {
      signInCalls += 1;
      return Promise.resolve({
        data: {
          user: { id: 'oauth-user' },
          session: { access_token: 'oauth-token' }
        },
        error: null
      });
    } };
  },
  callContainer() {
    containerCalls += 1;
    return Promise.resolve(businessError);
  }
};
const fakeCloudbase = { init() { return fakeApp; } };
Module._load = function(request, parent, isMain) {
  if (request === '../vendor/cloudbase/app.js') return fakeCloudbase;
  if (request === '../vendor/cloudbase/auth.js') return { registerAuth() {} };
  if (request === '../vendor/cloudbase/cloudrun.js') return { registerCloudrun() {} };
  return originalLoad.call(this, request, parent, isMain);
};
const adapter = require('./miniprogram/services/cloudbase-sdk.js');
adapter.callCloudbaseContainer({
  envId: 'campus-social-d3gsie43e1ca1bc6c',
  serviceName: 'campus-social-agent',
  publishableKey: 'publishable-test-key'
}, { name: 'campus-social-agent', path: '/users/me' }, { timeout: 30000 }).then(
  (response) => process.stdout.write(JSON.stringify({
    sameResponse: response === businessError,
    signInCalls,
    containerCalls
  })),
  () => { throw new Error('FastAPI response must be handled by api.js'); }
);
"""
    result = _run_node(script)
    assert result == {
        "sameResponse": True,
        "signInCalls": 1,
        "containerCalls": 1,
    }


def test_sdk_config_requires_publishable_key_and_is_the_default_mode():
    script = r"""
global.wx = {
  getStorageSync() { return ''; },
  getExtConfigSync() { return {}; }
};
const config = require('./miniprogram/config.js');
let missingKeyError = '';
try {
  config.getCloudbaseConfig('sdk', '');
} catch (error) {
  missingKeyError = error.message;
}
const sdk = config.getCloudbaseConfig('sdk', 'publishable-test-key');
process.stdout.write(JSON.stringify({
  defaultMode: config.API_MODE,
  missingKeyError,
  sdk
}));
"""
    result = _run_node(script)
    assert result["defaultMode"] == "sdk"
    assert "Publishable Key" in result["missingKeyError"]
    assert result["sdk"] == {
        "enabled": False,
        "sdkEnabled": True,
        "envId": "campus-social-d3gsie43e1ca1bc6c",
        "serviceName": "campus-social-agent",
        "publishableKey": "publishable-test-key",
        "mode": "sdk",
    }


def test_default_sdk_mode_ignores_stale_http_transport_storage():
    script = r"""
const storage = {
  apiMode: 'local',
  apiBaseUrl: 'http://100.64.158.53:8000',
  token: 'fake-business-jwt'
};
let sdkCalls = 0;
let wxRequestCalls = 0;
let wxCloudCalls = 0;
global.wx = {
  getStorageSync(key) { return storage[key] || ''; },
  getExtConfigSync() {
    return { apiMode: 'public', apiBaseUrl: 'http://127.0.0.1:8000' };
  },
  setStorageSync() {},
  removeStorageSync() {},
  login() { throw new Error('Existing business token should avoid wx.login'); },
  request() { wxRequestCalls += 1; },
  cloud: { callContainer() { wxCloudCalls += 1; } }
};
const config = require('./miniprogram/config.js');
const adapter = require('./miniprogram/services/cloudbase-sdk.js');
adapter.callCloudbaseContainer = (cloudbase, options) => {
  sdkCalls += 1;
  return Promise.resolve({ id: 'sdk-user', path: options.path });
};
const api = require('./miniprogram/services/api.js');
api.getMe().then((response) => process.stdout.write(JSON.stringify({
  configuredMode: config.API_MODE,
  resolvedMode: config.getCloudbaseConfig().mode,
  sdkCalls,
  wxRequestCalls,
  wxCloudCalls,
  responsePath: response.path
})));
"""
    assert _run_node(script) == {
        "configuredMode": "sdk",
        "resolvedMode": "sdk",
        "sdkCalls": 1,
        "wxRequestCalls": 0,
        "wxCloudCalls": 0,
        "responsePath": "/users/me",
    }


def test_sdk_transport_login_jwt_paths_and_timeouts():
    script = r"""
const storage = {};
const calls = [];
const setTokenCalls = [];
global.wx = {
  getStorageSync(key) { return storage[key] || ''; },
  getExtConfigSync() { return {}; },
  setStorageSync(key, value) {
    storage[key] = value;
    if (key === 'token') setTokenCalls.push(value);
  },
  removeStorageSync(key) { delete storage[key]; },
  login(options) { options.success({ code: 'wx-sdk-code' }); },
  request() { throw new Error('SDK mode must not call wx.request'); },
  cloud: {
    callContainer() { throw new Error('SDK mode must not call wx.cloud.callContainer'); }
  }
};
const config = require('./miniprogram/config.js');
config.getCloudbaseConfig = () => ({
  enabled: false,
  sdkEnabled: true,
  mode: 'sdk',
  envId: 'campus-social-d3gsie43e1ca1bc6c',
  serviceName: 'campus-social-agent',
  publishableKey: 'publishable-test-key'
});
const adapter = require('./miniprogram/services/cloudbase-sdk.js');
adapter.callCloudbaseContainer = (cloudbase, options, requestOptions) => {
  calls.push({ cloudbase, options, requestOptions });
  if (options.path === '/auth/wechat') {
    return Promise.resolve({ access_token: 'fake-fastapi-jwt', token_type: 'bearer' });
  }
  if (options.path === '/users/me') {
    return Promise.resolve({ id: 'sdk-user', interests: ['羽毛球'] });
  }
  return Promise.resolve({ ok: true, path: options.path });
};
const api = require('./miniprogram/services/api.js');
let meResponse = null;
api.getMe().then((me) => {
  meResponse = me;
  return api.agentChat('找羽毛球搭子', 3, 'sdk-session');
}).then(
  (agent) => process.stdout.write(JSON.stringify({
    calls,
    tokenStored: storage.token === 'fake-fastapi-jwt',
    setTokenCallCount: setTokenCalls.length,
    meResponse,
    agent
  })),
  (error) => {
    process.stderr.write(error.stack || String(error));
    process.exitCode = 1;
  }
);
"""
    flow = _run_node(script)
    assert flow["tokenStored"] is True
    assert flow["setTokenCallCount"] == 1
    assert flow["meResponse"] == {"id": "sdk-user", "interests": ["羽毛球"]}
    assert flow["agent"] == {"ok": True, "path": "/agent/chat"}
    calls = flow["calls"]
    assert [call["options"]["path"] for call in calls] == [
        "/auth/wechat",
        "/users/me",
        "/agent/chat",
    ]
    assert all(
        call["options"]["name"] == "campus-social-agent" for call in calls
    )
    assert calls[0]["options"]["method"] == "POST"
    assert calls[0]["options"]["data"] == {"code": "wx-sdk-code"}
    assert calls[1]["options"]["method"] == "GET"
    assert calls[2]["options"]["method"] == "POST"
    assert [call["requestOptions"]["timeout"] for call in calls] == [
        30000,
        30000,
        60000,
    ]
    for call in calls:
        assert "Authorization" not in call["options"]["header"]
    assert "X-Campus-Authorization" not in calls[0]["options"]["header"]
    assert calls[1]["options"]["header"]["X-Campus-Authorization"] == (
        "Bearer fake-fastapi-jwt"
    )
    assert calls[2]["options"]["header"]["X-Campus-Authorization"] == (
        "Bearer fake-fastapi-jwt"
    )


def test_sdk_agent_chat_uses_shared_campus_auth_header_and_safe_diagnostic():
    script = r"""
const storage = { token: 'diagnostic-fake-jwt' };
const calls = [];
const diagnostics = [];
console.info = (value) => diagnostics.push(value);
global.wx = {
  getStorageSync(key) { return storage[key] || ''; },
  getExtConfigSync() { return {}; },
  getAccountInfoSync() { return { miniProgram: { envVersion: 'trial' } }; },
  setStorageSync(key, value) { storage[key] = value; },
  removeStorageSync(key) { delete storage[key]; },
  login() { throw new Error('Existing token should avoid wx.login'); },
  request() { throw new Error('SDK mode must not call wx.request'); },
  cloud: { callContainer() { throw new Error('Wrong transport'); } }
};
const config = require('./miniprogram/config.js');
config.getCloudbaseConfig = () => ({
  enabled: false,
  sdkEnabled: true,
  mode: 'sdk',
  envId: 'campus-social-d3gsie43e1ca1bc6c',
  serviceName: 'campus-social-agent',
  publishableKey: 'publishable-test-key'
});
const adapter = require('./miniprogram/services/cloudbase-sdk.js');
adapter.callCloudbaseContainer = (cloudbase, options) => {
  calls.push({ path: options.path, header: options.header });
  return Promise.resolve({ ok: true });
};
const api = require('./miniprogram/services/api.js');
Promise.all([
  api.getMe(),
  api.agentChat('找飞盘搭子', 3, 'diagnostic-session'),
  api.sendMessage('partner-id', '你好')
]).then(
  () => process.stdout.write(JSON.stringify({ calls, diagnostics })),
  (error) => {
    process.stderr.write(error.stack || String(error));
    process.exitCode = 1;
  }
);
"""
    result = _run_node(script)
    assert [call["path"] for call in result["calls"]] == [
        "/users/me",
        "/agent/chat",
        "/conversations/partner-id/messages",
    ]
    for call in result["calls"]:
        assert call["header"]["X-Campus-Authorization"] == (
            "Bearer diagnostic-fake-jwt"
        )
        assert "Authorization" not in call["header"]
    assert result["diagnostics"] == [
        {
            "path": "/users/me",
            "hasCampusAuthHeader": True,
            "tokenLength": len("diagnostic-fake-jwt"),
        },
        {
            "path": "/agent/chat",
            "hasCampusAuthHeader": True,
            "tokenLength": len("diagnostic-fake-jwt"),
        },
        {
            "path": "/conversations/partner-id/messages",
            "hasCampusAuthHeader": True,
            "tokenLength": len("diagnostic-fake-jwt"),
        },
    ]
    assert "diagnostic-fake-jwt" not in json.dumps(result["diagnostics"])


def test_sdk_http_401_envelope_refreshes_fastapi_jwt_then_retries_agent():
    script = r"""
const storage = { token: 'expired-fastapi-jwt' };
const calls = [];
let loginCalls = 0;
global.wx = {
  getStorageSync(key) { return storage[key] || ''; },
  getExtConfigSync() { return {}; },
  setStorageSync(key, value) { storage[key] = value; },
  removeStorageSync(key) { delete storage[key]; },
  login(options) {
    loginCalls += 1;
    options.success({ code: 'fresh-wx-code' });
  },
  request() { throw new Error('SDK mode must not call wx.request'); },
  cloud: { callContainer() { throw new Error('Wrong transport'); } }
};
const config = require('./miniprogram/config.js');
config.getCloudbaseConfig = () => ({
  enabled: false,
  sdkEnabled: true,
  mode: 'sdk',
  envId: 'campus-social-d3gsie43e1ca1bc6c',
  serviceName: 'campus-social-agent',
  publishableKey: 'publishable-test-key'
});
const adapter = require('./miniprogram/services/cloudbase-sdk.js');
adapter.callCloudbaseContainer = (cloudbase, options) => {
  calls.push({ path: options.path, header: options.header });
  if (options.path === '/auth/wechat') {
    return Promise.resolve({
      statusCode: 200,
      data: { access_token: 'fresh-fastapi-jwt', token_type: 'bearer' },
      header: { 'content-type': 'application/json' },
      cookies: [],
      profile: { redirectStart: 1 },
      errMsg: 'request:ok'
    });
  }
  if (calls.filter((call) => call.path === '/agent/chat').length === 1) {
    return Promise.resolve({
      statusCode: 401,
      data: { detail: 'valid bearer token required' }
    });
  }
  return Promise.resolve({
    statusCode: 200,
    data: { message: '找到飞盘搭子', matches: [], session_id: 'session-1' }
  });
};
const api = require('./miniprogram/services/api.js');
api.agentChat('高新区下午找飞盘搭子', 3, null).then(
  (result) => process.stdout.write(JSON.stringify({
    result,
    loginCalls,
    storedFreshToken: storage.token === 'fresh-fastapi-jwt',
    calls
  })),
  (error) => {
    process.stderr.write(error.stack || String(error));
    process.exitCode = 1;
  }
);
"""
    result = _run_node(script)
    assert result["result"]["message"] == "找到飞盘搭子"
    assert result["loginCalls"] == 1
    assert result["storedFreshToken"] is True
    calls = result["calls"]
    assert [call["path"] for call in calls] == [
        "/agent/chat",
        "/auth/wechat",
        "/agent/chat",
    ]
    assert calls[0]["header"]["X-Campus-Authorization"] == (
        "Bearer expired-fastapi-jwt"
    )
    assert "X-Campus-Authorization" not in calls[1]["header"]
    assert calls[2]["header"]["X-Campus-Authorization"] == (
        "Bearer fresh-fastapi-jwt"
    )


def test_sdk_failed_jwt_refresh_does_not_retry_agent_without_token():
    script = r"""
const storage = { token: 'expired-fastapi-jwt' };
const paths = [];
global.wx = {
  getStorageSync(key) { return storage[key] || ''; },
  getExtConfigSync() { return {}; },
  setStorageSync(key, value) { storage[key] = value; },
  removeStorageSync(key) { delete storage[key]; },
  login(options) { options.success({ code: 'wx-code' }); },
  request() { throw new Error('SDK mode must not call wx.request'); },
  cloud: { callContainer() { throw new Error('Wrong transport'); } }
};
const config = require('./miniprogram/config.js');
config.getCloudbaseConfig = () => ({
  enabled: false,
  sdkEnabled: true,
  mode: 'sdk',
  envId: 'campus-social-d3gsie43e1ca1bc6c',
  serviceName: 'campus-social-agent',
  publishableKey: 'publishable-test-key'
});
const adapter = require('./miniprogram/services/cloudbase-sdk.js');
adapter.callCloudbaseContainer = (cloudbase, options) => {
  paths.push(options.path);
  if (options.path === '/auth/wechat') {
    return Promise.resolve({
      statusCode: 503,
      data: { detail: 'wechat login temporarily unavailable' }
    });
  }
  return Promise.resolve({
    statusCode: 401,
    data: { detail: 'valid bearer token required' }
  });
};
const api = require('./miniprogram/services/api.js');
api.agentChat('找飞盘搭子').then(
  () => { throw new Error('Expected login refresh to fail'); },
  (error) => process.stdout.write(JSON.stringify({
    paths,
    statusCode: error.statusCode,
    tokenExists: Boolean(storage.token)
  }))
);
"""
    result = _run_node(script)
    assert result == {
        "paths": ["/agent/chat", "/auth/wechat"],
        "statusCode": 503,
        "tokenExists": False,
    }


def test_sdk_protected_request_without_jwt_is_not_sent_to_fastapi():
    script = r"""
const diagnostics = [];
let containerCalls = 0;
console.info = (value) => diagnostics.push(value);
global.wx = {
  getStorageSync() { return ''; },
  getExtConfigSync() { return {}; },
  getAccountInfoSync() { return { miniProgram: { envVersion: 'develop' } }; },
  setStorageSync() {},
  removeStorageSync() {},
  login(options) { options.fail({ errMsg: 'test login unavailable' }); },
  request() { throw new Error('SDK mode must not call wx.request'); },
  cloud: { callContainer() { throw new Error('Wrong transport'); } }
};
const config = require('./miniprogram/config.js');
config.getCloudbaseConfig = () => ({
  enabled: false,
  sdkEnabled: true,
  mode: 'sdk',
  envId: 'campus-social-d3gsie43e1ca1bc6c',
  serviceName: 'campus-social-agent',
  publishableKey: 'publishable-test-key'
});
const adapter = require('./miniprogram/services/cloudbase-sdk.js');
adapter.callCloudbaseContainer = () => {
  containerCalls += 1;
  return Promise.resolve({ ok: true });
};
const api = require('./miniprogram/services/api.js');
api.agentChat('找飞盘搭子').then(
  () => { throw new Error('Missing JWT must reject'); },
  (error) => process.stdout.write(JSON.stringify({
    containerCalls,
    statusCode: error.statusCode,
    diagnostics
  }))
);
"""
    result = _run_node(script)
    assert result == {
        "containerCalls": 0,
        "statusCode": 401,
        "diagnostics": [
            {
                "path": "/agent/chat",
                "hasCampusAuthHeader": False,
                "tokenLength": 0,
            }
        ],
    }


def test_sdk_response_normalizer_uses_known_envelopes_only():
    script = r"""
global.wx = {
  getStorageSync() { return ''; },
  getExtConfigSync() { return {}; }
};
const api = require('./miniprogram/services/api.js');
const body = { access_token: 'fake-token', token_type: 'bearer' };
const profile = { id: 'user-1', interests: ['跑步'] };
const normalized = {
  direct: api.normalizeSdkResponse(body),
  result: api.normalizeSdkResponse({ result: profile }),
  data: api.normalizeSdkResponse({ statusCode: 200, data: profile }),
  wxNative: api.normalizeSdkResponse({
    statusCode: 200,
    data: profile,
    header: { 'content-type': 'application/json' },
    cookies: [],
    profile: { redirectStart: 1 },
    errMsg: 'request:ok'
  }),
  resultData: api.normalizeSdkResponse({
    result: { statusCode: 200, data: profile },
    requestId: 'fake-request-id'
  }),
  businessData: api.normalizeSdkResponse({
    id: 'business-object',
    data: { preference: 'quiet' }
  })
};
process.stdout.write(JSON.stringify({
  directHasToken: normalized.direct.access_token === 'fake-token',
  resultId: normalized.result.id,
  dataId: normalized.data.id,
  wxNativeId: normalized.wxNative.id,
  resultDataId: normalized.resultData.id,
  businessDataPreserved: normalized.businessData.id === 'business-object'
    && normalized.businessData.data.preference === 'quiet'
}));
"""
    assert _run_node(script) == {
        "directHasToken": True,
        "resultId": "user-1",
        "dataId": "user-1",
        "wxNativeId": "user-1",
        "resultDataId": "user-1",
        "businessDataPreserved": True,
    }


def test_sdk_failure_becomes_existing_error_shape():
    script = r"""
const storage = { token: 'fastapi-jwt' };
global.wx = {
  getStorageSync(key) { return storage[key] || ''; },
  getExtConfigSync() { return {}; },
  setStorageSync() {},
  removeStorageSync() {},
  login() { throw new Error('Existing token should avoid wx.login'); },
  request() { throw new Error('SDK mode must not call wx.request'); },
  cloud: { callContainer() { throw new Error('Wrong transport'); } }
};
const config = require('./miniprogram/config.js');
config.getCloudbaseConfig = () => ({
  enabled: false,
  sdkEnabled: true,
  mode: 'sdk',
  envId: 'campus-social-d3gsie43e1ca1bc6c',
  serviceName: 'campus-social-agent',
  publishableKey: 'publishable-test-key'
});
const adapter = require('./miniprogram/services/cloudbase-sdk.js');
adapter.callCloudbaseContainer = () => Promise.reject({
  statusCode: 403,
  data: { detail: 'campus access forbidden' }
});
const api = require('./miniprogram/services/api.js');
api.getMe().then(
  () => { throw new Error('Expected SDK request to fail'); },
  (error) => process.stdout.write(JSON.stringify({
    isError: error instanceof Error,
    message: error.message,
    statusCode: error.statusCode
  }))
);
"""
    failure = _run_node(script)
    assert failure["isError"] is True
    assert failure["statusCode"] == 403
    assert "campus access forbidden" in failure["message"]


def test_sdk_wx_timeout_has_actionable_message_and_safe_diagnostic():
    script = r"""
const storage = { token: 'timeout-test-jwt' };
const diagnostics = [];
console.info = (value) => diagnostics.push(value);
global.wx = {
  getStorageSync(key) { return storage[key] || ''; },
  getExtConfigSync() { return {}; },
  getAccountInfoSync() { return { miniProgram: { envVersion: 'trial' } }; },
  setStorageSync() {},
  removeStorageSync() {},
  login() { throw new Error('Existing token should avoid wx.login'); },
  request() { throw new Error('SDK mode must not call wx.request'); },
  cloud: { callContainer() { throw new Error('Wrong transport'); } }
};
const config = require('./miniprogram/config.js');
config.getCloudbaseConfig = () => ({
  enabled: false,
  sdkEnabled: true,
  mode: 'sdk',
  envId: 'campus-social-d3gsie43e1ca1bc6c',
  serviceName: 'campus-social-agent',
  publishableKey: 'publishable-test-key'
});
const adapter = require('./miniprogram/services/cloudbase-sdk.js');
adapter.callCloudbaseContainer = () => Promise.reject({
  errMsg: 'request:fail timeout'
});
const api = require('./miniprogram/services/api.js');
api.agentChat('找飞盘搭子', 3, 'timeout-session').then(
  () => { throw new Error('Expected SDK timeout'); },
  (error) => process.stdout.write(JSON.stringify({
    message: error.message,
    diagnostics
  }))
);
"""
    result = _run_node(script)
    assert "CloudBase SDK 请求超时（60 秒）" in result["message"]
    assert result["diagnostics"][0] == {
        "path": "/agent/chat",
        "hasCampusAuthHeader": True,
        "tokenLength": len("timeout-test-jwt"),
    }
    failure = result["diagnostics"][1]
    assert failure["path"] == "/agent/chat"
    assert failure["errorType"] == "timeout"
    assert failure["statusCode"] is None
    assert failure["code"] is None
    assert failure["hasDetail"] is False
    assert isinstance(failure["elapsedMs"], int)
    assert "timeout-test-jwt" not in json.dumps(result["diagnostics"])
