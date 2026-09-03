#!/usr/bin/env python3
"""Static acceptance checks for the native WeChat mini program.

This cannot replace the WeChat developer tools or a real phone. It makes the
locally verifiable part repeatable: manifest paths, JSON, JavaScript syntax,
component references, API facade exports, secret scanning and backend routes.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MINIPROGRAM = ROOT / "miniprogram"
GENERATED_JS_DIRS = {"node_modules", "miniprogram_npm"}
PINNED_THIRD_PARTY_DIR = MINIPROGRAM / "vendor" / "cloudbase"

REQUIRED_API_EXPORTS = {
    "getMe",
    "updateMe",
    "parseProfile",
    "agentChat",
    "getMatches",
    "getMatchDetail",
    "sendFeedback",
    "blockUser",
    "reportUser",
    "analyzePersonality",
    "clearPersonality",
    "getConversations",
    "getMessages",
    "sendMessage",
    "markConversationRead",
    "getNotifications",
    "markNotificationRead",
    "getPartnerRequests",
    "updatePartnerRequest",
}
REQUIRED_ROUTES = {
    ("POST", "/auth/wechat"),
    ("GET", "/users/me"),
    ("PATCH", "/users/me"),
    ("POST", "/users/me/profile/parse"),
    ("POST", "/agent/chat"),
    ("GET", "/matches/me"),
    ("POST", "/feedback"),
    ("POST", "/block"),
    ("POST", "/report"),
    ("POST", "/users/me/personality/analyze"),
    ("DELETE", "/users/me/personality"),
    ("GET", "/conversations"),
    ("GET", "/conversations/{partner_id}/messages"),
    ("POST", "/conversations/{partner_id}/messages"),
    ("POST", "/conversations/{partner_id}/read"),
    ("GET", "/notifications"),
    ("POST", "/notifications/{notification_id}/read"),
    ("GET", "/partner-requests"),
    ("PATCH", "/partner-requests/{request_id}"),
}
FORBIDDEN_SECRET_PATTERNS = {
    "LLM_API_KEY": re.compile(r"LLM_API_KEY"),
    "WECHAT_APP_SECRET": re.compile(r"WECHAT_APP_SECRET"),
    "JWT signing secret": re.compile(r"\bJWT_SECRET\b"),
    "CloudBase service role": re.compile(r"\bservice_role\b", re.IGNORECASE),
    "Tencent Cloud secret env": re.compile(
        r"\b(?:TENCENT_)?SECRET_(?:ID|KEY)\b"
    ),
    "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "common API token": re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    "CloudBase service API key": re.compile(
        r"\b(?:const|let|var)\s+CLOUDBASE_API_KEY\b"
    ),
    "Tencent Cloud secret ID": re.compile(r"\bsecretId\s*:"),
    "Tencent Cloud secret key": re.compile(r"\bsecretKey\s*:"),
}


def _load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def _is_generated(path: Path) -> bool:
    return any(part in GENERATED_JS_DIRS for part in path.parts)


def validate_manifest() -> list[str]:
    errors: list[str] = []
    app_config = _load_json(MINIPROGRAM / "app.json")
    for page in app_config.get("pages", []):
        for suffix in (".js", ".json", ".wxml", ".wxss"):
            path = MINIPROGRAM / f"{page}{suffix}"
            if not path.is_file():
                errors.append(f"missing page file: {path.relative_to(ROOT)}")
    for json_path in MINIPROGRAM.rglob("*.json"):
        if _is_generated(json_path):
            continue
        config = _load_json(json_path)
        for component in config.get("usingComponents", {}).values():
            component_path = MINIPROGRAM / component.lstrip("/")
            if not component_path.with_suffix(".js").is_file():
                errors.append(
                    f"missing component: {component} referenced by "
                    f"{json_path.relative_to(ROOT)}"
                )
    return errors


def validate_assets() -> list[str]:
    errors: list[str] = []
    for path in MINIPROGRAM.rglob("*.wxml"):
        if _is_generated(path):
            continue
        text = path.read_text(encoding="utf-8")
        if "<" not in text or text.count("{{") != text.count("}}"):
            errors.append(f"invalid WXML structure: {path.relative_to(ROOT)}")
    for path in MINIPROGRAM.rglob("*.wxss"):
        if _is_generated(path):
            continue
        text = path.read_text(encoding="utf-8")
        if text.count("{") != text.count("}"):
            errors.append(f"unbalanced WXSS braces: {path.relative_to(ROOT)}")
    return errors


def validate_javascript() -> list[str]:
    node = shutil.which("node")
    if node is None:
        return ["node is unavailable; JavaScript syntax was not checked"]
    errors: list[str] = []
    for path in MINIPROGRAM.rglob("*.js"):
        if _is_generated(path):
            continue
        result = subprocess.run(
            [node, "--check", str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            errors.append(
                f"JavaScript syntax error in {path.relative_to(ROOT)}: "
                f"{result.stderr.strip()}"
            )
    return errors


def validate_api_facade() -> list[str]:
    api_source = (MINIPROGRAM / "services" / "api.js").read_text(encoding="utf-8")
    config_source = (MINIPROGRAM / "config.js").read_text(encoding="utf-8")
    errors = []
    missing = sorted(
        name
        for name in REQUIRED_API_EXPORTS
        if not re.search(rf"\b{name}\s*,", api_source)
    )
    if missing:
        errors.append(f"API facade does not export: {', '.join(missing)}")
    if "127.0.0.1" in api_source or "localhost" in api_source:
        errors.append("services/api.js hard-codes a local endpoint")
    if "wx.cloud.callContainer" not in api_source:
        errors.append("services/api.js does not support CloudBase callContainer")
    if "X-WX-SERVICE" not in api_source:
        errors.append("services/api.js does not select a CloudBase service")
    if not re.search(r"const API_MODE\s*=\s*['\"]sdk['\"]", config_source):
        errors.append("experience build must use API_MODE='sdk'")
    if re.search(r"getStorageSync\(\s*['\"]apiMode['\"]", config_source) or re.search(
        r"extConfig\s*\.\s*apiMode", config_source
    ):
        errors.append("persistent runtime config must not override release API_MODE")
    if "getApiBaseUrl(cloudbase.mode)" not in api_source:
        errors.append("API facade does not bind base URL selection to transport mode")
    package = _load_json(MINIPROGRAM / "package.json")
    sdk_version = package.get("dependencies", {}).get("@cloudbase/js-sdk", "")
    if not re.fullmatch(r"3(?:\.\d+){2}", sdk_version):
        errors.append("Mini Program must pin @cloudbase/js-sdk to a v3 release")
    if (
        "callCloudbaseContainer" not in api_source
        or "X-Campus-Authorization" not in api_source
    ):
        errors.append("API facade does not implement the CloudBase JS SDK transport")
    sdk_adapter = (MINIPROGRAM / "services" / "cloudbase-sdk.js").read_text(
        encoding="utf-8"
    )
    for contract in (
        "registerAuth(cloudbase)",
        "registerCloudrun(cloudbase)",
        "app.auth({ persistence: 'local' })",
        "signInAnonymously()",
        "app.callContainer(requestOptions, { from: 'node-sdk' })",
        "timeout: MAX_CONTAINER_TIMEOUT_MS",
        "withRequestTimeout(request, transportOptions && transportOptions.timeout)",
    ):
        if contract not in sdk_adapter:
            errors.append(f"CloudBase SDK adapter is missing contract: {contract}")
    if not re.search(
        r"const\s+timeout\s*=\s*url\s*===\s*['\"]/agent/chat['\"]"
        r"\s*\?\s*60000\s*:\s*30000",
        api_source,
    ):
        errors.append("API facade must use 60s agent and 30s ordinary request timeouts")
    return errors


def validate_secret_boundary() -> list[str]:
    errors: list[str] = []
    for path in MINIPROGRAM.rglob("*"):
        if not path.is_file():
            continue
        if _is_generated(path):
            continue
        # These unmodified v3.9.0 bundles contain SDK option names such as
        # secretId/secretKey, but no configured credentials. Their exact
        # hashes are pinned by test_vendored_cloudbase_runtime_is_pinned_and_used.
        if PINNED_THIRD_PARTY_DIR in path.parents:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for label, pattern in FORBIDDEN_SECRET_PATTERNS.items():
            if pattern.search(text):
                errors.append(f"possible {label} in {path.relative_to(ROOT)}")
    return errors


def validate_backend_routes() -> list[str]:
    from backend.app.main import app

    actual = {
        (method, route.path)
        for route in app.routes
        for method in getattr(route, "methods", set())
    }
    missing = sorted(REQUIRED_ROUTES - actual)
    return [f"backend route missing: {method} {path}" for method, path in missing]


def run_all_checks() -> list[str]:
    return [
        *validate_manifest(),
        *validate_assets(),
        *validate_javascript(),
        *validate_api_facade(),
        *validate_secret_boundary(),
        *validate_backend_routes(),
    ]


def main() -> int:
    errors = run_all_checks()
    if errors:
        print("Mini program static validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Mini program static validation passed.")
    print("Checked manifests, page/component files, JS syntax, WXML/WXSS basics,")
    print("API facade exports, backend routes, and client-side secret boundaries.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
