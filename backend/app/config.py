"""Environment based application configuration (no secrets are hard coded)."""

from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict


load_dotenv()


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)

    app_env: str = "development"
    data_backend: str = "sqlite"
    database_url: str = "sqlite:///./campus_social.db"
    cloudbase_env_id: str = ""
    cloudbase_api_key: str = ""
    cloudbase_pg_api_url: str = ""
    cloudbase_http_timeout_seconds: float = 15.0
    llm_provider: str = "mock"
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_timeout_seconds: float = 30.0
    llm_response_format: str = "auto"
    llm_fallback_to_mock: bool = True
    outbound_http_trust_env: bool = False
    debug_agent_trace: bool = True
    agent_session_ttl_minutes: int = 1440
    agent_trace_ttl_days: int = 7
    agent_trace_max_entries: int = 1000
    agent_turn_lock_seconds: int = 120
    jwt_secret: str = "change-this-development-secret-at-least-32-bytes"
    jwt_access_token_minutes: int = 120
    jwt_issuer: str = "campus-social-agent"
    school_email_domains: tuple[str, ...] = ("ustc.edu.cn",)
    require_campus_verification: bool = False
    frontend_base_url: str = "http://127.0.0.1:5173"
    ustc_cas_login_url: str = "https://id.ustc.edu.cn/cas/login"
    ustc_cas_validate_url: str = "https://id.ustc.edu.cn/cas/serviceValidate"

    dev_auth_mode: bool = False
    dev_user_id: str = "user001"
    show_mock_users: bool = True
    allow_mock_verification: bool = True
    wechat_app_id: str = ""
    wechat_app_secret: str = ""
    wechat_code2session_url: str = "https://api.weixin.qq.com/sns/jscode2session"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            app_env=os.getenv("APP_ENV", "development"),
            data_backend=os.getenv("DATA_BACKEND", "sqlite").lower(),
            database_url=os.getenv("DATABASE_URL", "sqlite:///./campus_social.db"),
            cloudbase_env_id=os.getenv("CLOUDBASE_ENV_ID", ""),
            cloudbase_api_key=os.getenv("CLOUDBASE_API_KEY", ""),
            cloudbase_pg_api_url=os.getenv("CLOUDBASE_PG_API_URL", ""),
            cloudbase_http_timeout_seconds=float(
                os.getenv("CLOUDBASE_HTTP_TIMEOUT_SECONDS", "15")
            ),
            llm_provider=os.getenv("LLM_PROVIDER", "mock"),
            llm_base_url=os.getenv("LLM_BASE_URL", ""),
            llm_api_key=os.getenv("LLM_API_KEY", ""),
            llm_model=os.getenv("LLM_MODEL", ""),
            llm_timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "30")),
            llm_response_format=os.getenv("LLM_RESPONSE_FORMAT", "auto"),
            llm_fallback_to_mock=os.getenv("LLM_FALLBACK_TO_MOCK", "true").lower()
            in {"1", "true", "yes", "on"},
            outbound_http_trust_env=os.getenv(
                "OUTBOUND_HTTP_TRUST_ENV", "false"
            ).lower()
            in {"1", "true", "yes", "on"},
            debug_agent_trace=os.getenv("DEBUG_AGENT_TRACE", "true").lower()
            in {"1", "true", "yes", "on"},
            agent_session_ttl_minutes=int(
                os.getenv("AGENT_SESSION_TTL_MINUTES", "1440")
            ),
            agent_trace_ttl_days=int(os.getenv("AGENT_TRACE_TTL_DAYS", "7")),
            agent_trace_max_entries=int(os.getenv("AGENT_TRACE_MAX_ENTRIES", "1000")),
            agent_turn_lock_seconds=int(os.getenv("AGENT_TURN_LOCK_SECONDS", "120")),
            jwt_secret=os.getenv(
                "JWT_SECRET", "change-this-development-secret-at-least-32-bytes"
            ),
            jwt_access_token_minutes=int(os.getenv("JWT_ACCESS_TOKEN_MINUTES", "120")),
            jwt_issuer=os.getenv("JWT_ISSUER", "campus-social-agent"),
            school_email_domains=tuple(
                domain.strip()
                for domain in os.getenv("SCHOOL_EMAIL_DOMAINS", "ustc.edu.cn").split(
                    ","
                )
                if domain.strip()
            ),
            require_campus_verification=os.getenv(
                "REQUIRE_CAMPUS_VERIFICATION", "false"
            ).lower()
            in {"1", "true", "yes", "on"},
            frontend_base_url=os.getenv("FRONTEND_BASE_URL", "http://127.0.0.1:5173"),
            ustc_cas_login_url=os.getenv(
                "USTC_CAS_LOGIN_URL", "https://id.ustc.edu.cn/cas/login"
            ),
            ustc_cas_validate_url=os.getenv(
                "USTC_CAS_VALIDATE_URL",
                "https://id.ustc.edu.cn/cas/serviceValidate",
            ),
            dev_auth_mode=os.getenv("DEV_AUTH_MODE", "false").lower()
            in {"1", "true", "yes", "on"},
            dev_user_id=os.getenv("DEV_USER_ID", "user001"),
            show_mock_users=os.getenv("SHOW_MOCK_USERS", "true").lower()
            in {"1", "true", "yes", "on"},
            allow_mock_verification=os.getenv("ALLOW_MOCK_VERIFICATION", "true").lower()
            in {"1", "true", "yes", "on"},
            wechat_app_id=os.getenv("WECHAT_APP_ID", ""),
            wechat_app_secret=os.getenv("WECHAT_APP_SECRET", ""),
            wechat_code2session_url=os.getenv(
                "WECHAT_CODE2SESSION_URL",
                "https://api.weixin.qq.com/sns/jscode2session",
            ),
        )

    def validate_runtime(self) -> None:
        if self.data_backend not in {"sqlite", "cloudbase_http"}:
            raise ValueError("DATA_BACKEND must be sqlite or cloudbase_http")
        if self.data_backend == "cloudbase_http":
            if not self.cloudbase_env_id:
                raise ValueError("CLOUDBASE_ENV_ID is required for cloudbase_http")
            if not self.cloudbase_api_key:
                raise ValueError("CLOUDBASE_API_KEY is required for cloudbase_http")
        if self.cloudbase_http_timeout_seconds <= 0:
            raise ValueError("CLOUDBASE_HTTP_TIMEOUT_SECONDS must be positive")
        if not self.llm_timeout_seconds > 0:
            raise ValueError("LLM_TIMEOUT_SECONDS must be positive")
        if len(self.jwt_secret.encode()) < 32:
            raise ValueError("JWT_SECRET must contain at least 32 bytes")
        if self.app_env.lower() == "production" and self.jwt_secret.startswith(
            "change-this-development"
        ):
            raise ValueError("JWT_SECRET must be changed in production")
        if self.jwt_access_token_minutes <= 0:
            raise ValueError("JWT_ACCESS_TOKEN_MINUTES must be positive")
        if self.agent_session_ttl_minutes <= 0:
            raise ValueError("AGENT_SESSION_TTL_MINUTES must be positive")
        if self.agent_trace_ttl_days <= 0:
            raise ValueError("AGENT_TRACE_TTL_DAYS must be positive")
        if self.agent_trace_max_entries <= 0:
            raise ValueError("AGENT_TRACE_MAX_ENTRIES must be positive")
        if self.agent_turn_lock_seconds <= 0:
            raise ValueError("AGENT_TURN_LOCK_SECONDS must be positive")
        if not self.school_email_domains:
            raise ValueError("SCHOOL_EMAIL_DOMAINS must contain at least one domain")
        if self.dev_auth_mode and self.app_env.lower() == "production":
            raise ValueError("DEV_AUTH_MODE cannot be enabled in production")
        if self.llm_fallback_to_mock and self.app_env.lower() == "production":
            raise ValueError("LLM_FALLBACK_TO_MOCK cannot be enabled in production")
        if self.llm_response_format not in {"auto", "json_schema", "json_object"}:
            raise ValueError(
                "LLM_RESPONSE_FORMAT must be auto, json_schema, or json_object"
            )


@lru_cache
def get_settings() -> Settings:
    return Settings.from_env()
