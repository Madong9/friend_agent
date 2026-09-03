from pydantic import BaseModel, ConfigDict, Field, model_validator

from .user import UserRead


class LoginRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    user_id: str | None = Field(default=None, min_length=1, max_length=64)
    school_email: str | None = Field(default=None, min_length=6, max_length=128)
    password: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_identifier(self):
        if not self.user_id and not self.school_email:
            raise ValueError("user_id or school_email is required")
        if self.user_id and self.school_email:
            raise ValueError("provide only one login identifier")
        return self


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserRead


class LogoutResponse(BaseModel):
    revoked: bool = True


class WechatLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=256)
    nickname: str | None = Field(default=None, max_length=64)
