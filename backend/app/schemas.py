"""Pydantic request/response models. Chat/document schemas are added in later steps."""
from pydantic import BaseModel, EmailStr, Field, SecretStr, field_validator

from app.models import User


def _strip(value):
    return value.strip() if isinstance(value, str) else value


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    # SecretStr: shows as '**********' in logs/reprs instead of the real value.
    gemini_api_key: SecretStr = Field(min_length=20, max_length=256)

    _strip_key = field_validator("gemini_api_key", mode="before")(_strip)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class GeminiKeyRequest(BaseModel):
    api_key: SecretStr = Field(min_length=20, max_length=256)

    _strip_key = field_validator("api_key", mode="before")(_strip)


class UserOut(BaseModel):
    id: str
    email: EmailStr
    has_gemini_key: bool
    gemini_key_hint: str | None = None  # last 4 chars only; the full key is never returned

    @classmethod
    def from_user(cls, user: User) -> "UserOut":
        return cls(
            id=user.id,
            email=user.email,
            has_gemini_key=user.gemini_key_encrypted is not None,
            gemini_key_hint=user.gemini_key_hint,
        )