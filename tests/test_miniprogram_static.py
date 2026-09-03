"""Repeatable checks for the locally verifiable mini-program contract."""

import json
import subprocess
from pathlib import Path

import pytest

from scripts.check_miniprogram import run_all_checks


ROOT = Path(__file__).resolve().parents[1]


def test_miniprogram_manifest_api_and_secret_boundaries():
    assert run_all_checks() == []


def test_release_pack_excludes_backup_and_private_config():
    project_config = json.loads((ROOT / "project.config.json").read_text())
    ignored = {
        item.get("value") for item in project_config["packOptions"]["ignore"]
    }
    assert {"config.js.save", "project.private.config.json"} <= ignored
    assert project_config["packOptions"]["include"] == []
    assert "node_modules" in ignored
    assert "miniprogram_npm" in ignored
    # Vendored modules are ordinary source files, so the release never depends
    # on the uploader discovering a lazy npm require.
    assert project_config["setting"]["ignoreUploadUnusedFiles"] is False
    assert project_config["setting"]["uploadWithSourceMap"] is False

    nested_config = json.loads(
        (ROOT / "miniprogram/project.config.json").read_text()
    )
    assert nested_config["packOptions"] == project_config["packOptions"]


def test_vendored_cloudbase_runtime_is_pinned_and_used():
    import hashlib

    expected = {
        "app.js": "3874f62720b02ee0feb051bf3814ebf7762cf586da9dddf833dd24773a6b1a29",
        "auth.js": "74454489023f2336745eafcd56a6691a604a3143b89ea1e621e6e7f3a19c8703",
        "cloudrun.js": "d62d0fa658770d345036c00a631ec3039cc25393d6ac5aaf963ddc88d26d9cd7",
    }
    vendor = ROOT / "miniprogram/vendor/cloudbase"
    for filename, digest in expected.items():
        assert hashlib.sha256((vendor / filename).read_bytes()).hexdigest() == digest

    adapter = (ROOT / "miniprogram/services/cloudbase-sdk.js").read_text()
    for filename in expected:
        assert f"../vendor/cloudbase/{filename}" in adapter


def test_app_launch_initializes_configured_cloudbase_environment():
    script = r"""
const storage = {
  apiMode: 'cloud',
  cloudbaseEnvId: 'campus-social-test-123',
  cloudbaseServiceName: 'campus-social-agent',
  token: 'existing-token'
};
let application = null;
let cloudInitOptions = null;
global.App = (definition) => { application = definition; };
global.wx = {
  getStorageSync(key) { return storage[key] || ''; },
  getExtConfigSync() { return {}; },
  setStorageSync(key, value) { storage[key] = value; },
  removeStorageSync(key) { delete storage[key]; },
  cloud: {
    init(options) { cloudInitOptions = options; }
  }
};
const config = require('./miniprogram/config.js');
const getCloudbaseConfig = config.getCloudbaseConfig;
config.getCloudbaseConfig = () => getCloudbaseConfig('cloud');
require('./miniprogram/app.js');
application.onLaunch();
process.stdout.write(JSON.stringify(cloudInitOptions));
"""
    try:
        result = subprocess.run(
            ["node", "-e", script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        pytest.skip("node is required for the mini-program app launch contract test")
    assert json.loads(result.stdout) == {
        "env": "campus-social-test-123",
        "traceUser": True,
    }


def test_profile_update_helper_sends_only_backend_writable_fields():
    script = r"""
const helper = require('./miniprogram/utils/profile.js');
const payload = helper.buildProfileUpdate({
  id: 'internal-id',
  nickname: '同学',
  school: '中国科学技术大学',
  campus: '西区',
  grade: '研一',
  major: '计算机',
  bio: '你好',
  is_mock: false,
  created_at: 'private-read-only-value',
  interests: [], social_goals: [], activities: [], availability: [], avoidances: []
}, {
  interestsText: '羽毛球，跑步',
  goalsText: '运动搭子',
  activitiesText: '夜跑',
  availabilityText: '周六下午',
  avoidancesText: '高强度竞技'
});
process.stdout.write(JSON.stringify(payload));
"""
    try:
        result = subprocess.run(
            ["node", "-e", script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        pytest.skip("node is required for the mini-program helper contract test")
    payload = json.loads(result.stdout)
    assert "id" not in payload
    assert "is_mock" not in payload
    assert "created_at" not in payload
    assert payload["interests"] == ["羽毛球", "跑步"]
    assert payload["activities"] == ["夜跑"]
    assert payload["avoidances"] == ["高强度竞技"]


def test_profile_load_failure_sets_visible_error_without_reading_user_fields():
    script = r"""
const Module = require('module');
const originalLoad = Module._load;
const loadError = new Error('登录已失效');
Module._load = function(request, parent, isMain) {
  if (request === '../../services/api.js') {
    return { getMe() { return Promise.reject(loadError); } };
  }
  return originalLoad.call(this, request, parent, isMain);
};
let page = null;
const toastCalls = [];
global.Page = (definition) => { page = definition; };
global.wx = {
  showToast(options) { toastCalls.push(options); }
};
require('./miniprogram/pages/profile/profile.js');
const state = { ...page.data };
const context = {
  data: state,
  setData(values) {
    Object.assign(state, values);
    this.data = state;
  }
};
page.load.call(context).then(() => {
  process.stdout.write(JSON.stringify({
    formIsEmpty: Object.keys(state.form).length === 0,
    loading: state.loading,
    loadError: state.loadError,
    toastTitle: toastCalls[0] && toastCalls[0].title
  }));
});
"""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout) == {
        "formIsEmpty": True,
        "loading": False,
        "loadError": "登录已失效",
        "toastTitle": "登录已失效",
    }


def test_profile_exposes_notification_entry_with_unread_badge():
    script = r"""
const Module = require('module');
const originalLoad = Module._load;
let unreadOnly = null;
Module._load = function(request, parent, isMain) {
  if (request === '../../services/api.js') {
    return {
      getNotifications(value) {
        unreadOnly = value;
        return Promise.resolve([{ id: 1 }, { id: 2 }]);
      }
    };
  }
  return originalLoad.call(this, request, parent, isMain);
};
let page = null;
let navigationUrl = '';
global.Page = (definition) => { page = definition; };
global.wx = {
  navigateTo(options) { navigationUrl = options.url; }
};
require('./miniprogram/pages/profile/profile.js');
const state = { ...page.data };
const context = {
  data: state,
  setData(values) {
    Object.assign(state, values);
    this.data = state;
  }
};
page.loadNotificationSummary.call(context).then(() => {
  page.goNotifications.call(context);
  process.stdout.write(JSON.stringify({
    unreadOnly,
    unreadNotificationCount: state.unreadNotificationCount,
    navigationUrl
  }));
});
"""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout) == {
        "unreadOnly": True,
        "unreadNotificationCount": 2,
        "navigationUrl": "/pages/notifications/notifications",
    }


def test_notifications_page_distinguishes_loading_failure_and_empty_state():
    script = r"""
const Module = require('module');
const originalLoad = Module._load;
Module._load = function(request, parent, isMain) {
  if (request === '../../services/api.js') {
    return {
      getNotifications() { return Promise.reject(new Error('通知接口暂时不可用')); },
      getPartnerRequests() {
        return Promise.resolve([{ id: 8, status: 'OPEN', intent: { activity: '飞盘', availability: ['下午'] } }]);
      }
    };
  }
  return originalLoad.call(this, request, parent, isMain);
};
let page = null;
global.Page = (definition) => { page = definition; };
global.wx = {};
require('./miniprogram/pages/notifications/notifications.js');
const state = { ...page.data };
const context = {
  data: state,
  setData(values) {
    Object.assign(state, values);
    this.data = state;
  }
};
page.load.call(context).then(() => {
  process.stdout.write(JSON.stringify({
    loading: state.loading,
    notificationsLoaded: state.notificationsLoaded,
    notificationError: state.notificationError,
    requestsLoaded: state.requestsLoaded,
    requestCount: state.requests.length,
    requestAvailability: state.requests[0].availabilityText
  }));
});
"""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout) == {
        "loading": False,
        "notificationsLoaded": False,
        "notificationError": "通知接口暂时不可用",
        "requestsLoaded": True,
        "requestCount": 1,
        "requestAvailability": "下午",
    }


def test_match_detail_exposes_and_submits_normal_candidate_feedback():
    script = r"""
const Module = require('module');
const originalLoad = Module._load;
const feedbackCalls = [];
const removed = [];
Module._load = function(request, parent, isMain) {
  if (request === '../../services/api.js') {
    return {
      sendFeedback(candidateId, feedback) {
        feedbackCalls.push({ candidateId, feedback });
        return Promise.resolve({ matched: false, demo_match: false });
      }
    };
  }
  if (request === '../../services/recommendations.js') {
    return { removeCandidate(candidateId) { removed.push(candidateId); } };
  }
  return originalLoad.call(this, request, parent, isMain);
};
let page = null;
const toastCalls = [];
let navigateBackCalls = 0;
const candidate = { id: 'candidate-safe-id', nickname: '测试候选', total: 0.44 };
global.Page = (definition) => { page = definition; };
global.wx = {
  getStorageSync(key) { return key === 'matchDetailCandidate' ? candidate : ''; },
  showToast(options) { toastCalls.push(options); },
  navigateBack() { navigateBackCalls += 1; }
};
require('./miniprogram/pages/match-detail/match-detail.js');
const state = { ...page.data };
const context = {
  data: state,
  setData(values) { Object.assign(state, values); this.data = state; },
  submitFeedback: page.submitFeedback
};
page.onLoad.call(context);
page.onLike.call(context).then(() => {
  process.stdout.write(JSON.stringify({
    feedbackCalls,
    removed,
    feedbackLoading: state.feedbackLoading,
    toastTitle: toastCalls[0] && toastCalls[0].title,
    navigateBackCalls
  }));
});
"""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout) == {
        "feedbackCalls": [
            {"candidateId": "candidate-safe-id", "feedback": "LIKE"}
        ],
        "removed": ["candidate-safe-id"],
        "feedbackLoading": False,
        "toastTitle": "已表达兴趣",
        "navigateBackCalls": 1,
    }

    template = (
        ROOT / "miniprogram/pages/match-detail/match-detail.wxml"
    ).read_text()
    assert 'bindtap="onLike"' in template
    assert 'bindtap="onPass"' in template
    assert 'bindtap="onNotRelevant"' in template


def test_matches_page_uses_card_layout_and_opens_candidate_detail():
    script = r"""
const Module = require('module');
const originalLoad = Module._load;
Module._load = function(request, parent, isMain) {
  if (request === '../../services/api.js') return {};
  if (request === '../../services/recommendations.js') return {};
  return originalLoad.call(this, request, parent, isMain);
};
let page = null;
const storageWrites = [];
const navigations = [];
global.Page = (definition) => { page = definition; };
global.wx = {
  setStorageSync(key, value) { storageWrites.push({ key, value }); },
  navigateTo(options) { navigations.push(options); }
};
require('./miniprogram/pages/matches/matches.js');
const candidate = { id: 'candidate-layout', nickname: '候选人' };
page.goCandidateDetail.call(
  { data: { queue: [candidate] } },
  { detail: { candidateId: candidate.id } }
);
process.stdout.write(JSON.stringify({ storageWrites, navigations }));
"""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout) == {
        "storageWrites": [
            {
                "key": "matchDetailCandidate",
                "value": {"id": "candidate-layout", "nickname": "候选人"},
            }
        ],
        "navigations": [{"url": "/pages/match-detail/match-detail"}],
    }

    page_template = (ROOT / "miniprogram/pages/matches/matches.wxml").read_text()
    page_styles = (ROOT / "miniprogram/pages/matches/matches.wxss").read_text()
    card_template = (
        ROOT / "miniprogram/components/match-card/match-card.wxml"
    ).read_text()
    card_styles = (
        ROOT / "miniprogram/components/match-card/match-card.wxss"
    ).read_text()
    assert 'class="section-panel mutual-section"' in page_template
    assert 'class="section-panel queue-section"' in page_template
    assert 'class="compact-empty"' in page_template
    assert 'bind:detail="goCandidateDetail"' in page_template
    assert ".section-panel" in page_styles
    assert 'class="score-block" bindtap="onDetail"' in card_template
    assert ".card" in card_styles and "background: #ffffff" in card_styles
    assert ".mock-badge" in card_styles

    wxml = (ROOT / "miniprogram/pages/notifications/notifications.wxml").read_text(
        encoding="utf-8"
    )
    assert "loading && !notificationsLoaded" in wxml
    assert (
        "notificationsLoaded && !notificationError && notifications.length === 0"
        in wxml
    )


def test_cloudbase_transport_calls_configured_container_service():
    script = r"""
const storage = {
  apiMode: 'cloud',
  cloudbaseEnvId: 'campus-social-test-123',
  cloudbaseServiceName: 'campus-social-agent',
  token: 'test-token'
};
let capturedRequest = null;
global.wx = {
  getStorageSync(key) { return storage[key] || ''; },
  getExtConfigSync() { return {}; },
  cloud: {
    callContainer(options) {
      capturedRequest = {
        env: options.config.env,
        path: options.path,
        method: options.method,
        service: options.header['X-WX-SERVICE'],
        authorization: options.header.Authorization,
        data: options.data
      };
      options.success({ statusCode: 200, data: { ok: true, source: 'fastapi' } });
    }
  },
  request() { throw new Error('CloudBase mode must not call wx.request'); },
  login() { throw new Error('Existing token should avoid wx.login'); },
  setStorageSync() {},
  removeStorageSync() {}
};
const config = require('./miniprogram/config.js');
const getCloudbaseConfig = config.getCloudbaseConfig;
config.getCloudbaseConfig = () => getCloudbaseConfig('cloud');
const api = require('./miniprogram/services/api.js');
api.agentChat('找西区考研搭子', 3, 'session-1').then(
  (response) => process.stdout.write(JSON.stringify({ request: capturedRequest, response })),
  (error) => {
    process.stderr.write(error.stack || String(error));
    process.exitCode = 1;
  }
);
"""
    try:
        result = subprocess.run(
            ["node", "-e", script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        pytest.skip("node is required for the mini-program transport contract test")
    result_data = json.loads(result.stdout)
    assert result_data["request"] == {
        "env": "campus-social-test-123",
        "path": "/agent/chat",
        "method": "POST",
        "service": "campus-social-agent",
        "authorization": "Bearer test-token",
        "data": {
            "message": "找西区考研搭子",
            "limit": 3,
            "session_id": "session-1",
        },
    }
    assert result_data["response"] == {"ok": True, "source": "fastapi"}


def test_local_transport_remains_available_when_cloud_config_exists():
    script = r"""
const storage = {
  apiMode: 'local',
  apiBaseUrl: 'http://127.0.0.1:8000',
  cloudbaseEnvId: 'campus-social-test-123',
  cloudbaseServiceName: 'campus-social-agent',
  token: 'local-token'
};
global.wx = {
  getStorageSync(key) { return storage[key] || ''; },
  getExtConfigSync() { return {}; },
  cloud: {
    callContainer() { throw new Error('Local mode must not call CloudBase'); }
  },
  request(options) {
    options.success({ statusCode: 200, data: { id: 'local-user' } });
    process.stdout.write(JSON.stringify({
      url: options.url,
      method: options.method,
      authorization: options.header.Authorization
    }));
  },
  login() { throw new Error('Existing token should avoid wx.login'); },
  setStorageSync() {},
  removeStorageSync() {}
};
const config = require('./miniprogram/config.js');
const getCloudbaseConfig = config.getCloudbaseConfig;
config.getCloudbaseConfig = () => getCloudbaseConfig('local');
const api = require('./miniprogram/services/api.js');
api.getMe().catch((error) => {
  process.stderr.write(error.stack || String(error));
  process.exitCode = 1;
});
"""
    try:
        result = subprocess.run(
            ["node", "-e", script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        pytest.skip("node is required for the mini-program transport contract test")
    request = json.loads(result.stdout)
    assert request == {
        "url": "http://127.0.0.1:8000/users/me",
        "method": "GET",
        "authorization": "Bearer local-token",
    }


@pytest.mark.parametrize("mode", ["public", "http"])
def test_public_http_modes_ignore_stale_local_storage_and_use_wx_request(mode):
    script = rf"""
const storage = {{
  apiMode: 'local',
  apiBaseUrl: 'http://100.64.158.53:8000',
  cloudbaseEnvId: 'unassociated-pg-environment',
  cloudbaseServiceName: 'campus-social-agent',
  token: 'public-token'
}};
global.wx = {{
  getStorageSync(key) {{ return storage[key] || ''; }},
  getExtConfigSync() {{ return {{}}; }},
  cloud: {{
    callContainer() {{ throw new Error('Public HTTP mode must not call CloudBase'); }}
  }},
  request(options) {{
    options.success({{ statusCode: 200, data: {{ id: 'public-user' }} }});
    process.stdout.write(JSON.stringify({{
      url: options.url,
      authorization: options.header.Authorization
    }}));
  }},
  login() {{ throw new Error('Existing token should avoid wx.login'); }},
  setStorageSync() {{}},
  removeStorageSync() {{}}
}};
const config = require('./miniprogram/config.js');
const getCloudbaseConfig = config.getCloudbaseConfig;
if ('{mode}' !== config.API_MODE) {{
  config.getCloudbaseConfig = () => getCloudbaseConfig('{mode}');
}}
const api = require('./miniprogram/services/api.js');
api.getMe().catch((error) => {{
  process.stderr.write(error.stack || String(error));
  process.exitCode = 1;
}});
"""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout) == {
        "url": (
            "https://campus-social-agent-304566-11-1476699034.sh.run."
            "tcloudbase.com/users/me"
        ),
        "authorization": "Bearer public-token",
    }


def test_wx_request_timeout_is_30_seconds_except_agent_chat():
    script = r"""
const storage = { token: 'timeout-test-token' };
const requests = [];
global.wx = {
  getStorageSync(key) { return storage[key] || ''; },
  getExtConfigSync() { return {}; },
  request(options) {
    requests.push({ url: options.url, timeout: options.timeout });
    options.success({ statusCode: 200, data: { ok: true } });
  },
  login() { throw new Error('Existing token should avoid wx.login'); },
  setStorageSync() {},
  removeStorageSync() {}
};
const config = require('./miniprogram/config.js');
const getCloudbaseConfig = config.getCloudbaseConfig;
config.getCloudbaseConfig = () => getCloudbaseConfig('public');
const api = require('./miniprogram/services/api.js');
Promise.all([
  api.getMe(),
  api.agentChat('找羽毛球搭子', 3, 'timeout-session')
]).then(
  () => process.stdout.write(JSON.stringify(requests)),
  (error) => {
    process.stderr.write(error.stack || String(error));
    process.exitCode = 1;
  }
);
"""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout) == [
        {
            "url": (
                "https://campus-social-agent-304566-11-1476699034.sh.run."
                "tcloudbase.com/users/me"
            ),
            "timeout": 30000,
        },
        {
            "url": (
                "https://campus-social-agent-304566-11-1476699034.sh.run."
                "tcloudbase.com/agent/chat"
            ),
            "timeout": 60000,
        },
    ]


def test_wechat_login_stores_jwt_and_uses_it_for_follow_up_request():
    script = r"""
const storage = {
  apiMode: 'cloud',
  cloudbaseEnvId: 'campus-social-test-123',
  cloudbaseServiceName: 'campus-social-agent'
};
const requests = [];
global.wx = {
  getStorageSync(key) { return storage[key] || ''; },
  getExtConfigSync() { return {}; },
  setStorageSync(key, value) { storage[key] = value; },
  removeStorageSync(key) { delete storage[key]; },
  login(options) { options.success({ code: 'wx-login-code' }); },
  request() { throw new Error('CloudBase mode must not call wx.request'); },
  cloud: {
    callContainer(options) {
      requests.push({
        path: options.path,
        method: options.method,
        service: options.header['X-WX-SERVICE'],
        authorization: options.header.Authorization || null,
        data: options.data
      });
      if (options.path === '/auth/wechat') {
        options.success({
          statusCode: 200,
          data: { access_token: 'jwt-from-fastapi', token_type: 'bearer' }
        });
        return;
      }
      options.success({ statusCode: 200, data: { id: 'wechat-user' } });
    }
  }
};
const config = require('./miniprogram/config.js');
const getCloudbaseConfig = config.getCloudbaseConfig;
config.getCloudbaseConfig = () => getCloudbaseConfig('cloud');
const api = require('./miniprogram/services/api.js');
api.getMe().then(
  (me) => process.stdout.write(JSON.stringify({ requests, token: storage.token, me })),
  (error) => {
    process.stderr.write(error.stack || String(error));
    process.exitCode = 1;
  }
);
"""
    try:
        result = subprocess.run(
            ["node", "-e", script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        pytest.skip("node is required for the mini-program auth contract test")
    flow = json.loads(result.stdout)
    assert flow == {
        "requests": [
            {
                "path": "/auth/wechat",
                "method": "POST",
                "service": "campus-social-agent",
                "authorization": None,
                "data": {"code": "wx-login-code"},
            },
            {
                "path": "/users/me",
                "method": "GET",
                "service": "campus-social-agent",
                "authorization": "Bearer jwt-from-fastapi",
                "data": None,
            },
        ],
        "token": "jwt-from-fastapi",
        "me": {"id": "wechat-user"},
    }
