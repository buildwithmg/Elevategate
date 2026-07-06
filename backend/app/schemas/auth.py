from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import AdminRole


class LoginRequest(BaseModel):
    email: EmailStr
    # Bounded like every other free-text field in this codebase: Argon2id's cost scales with
    # input size, and this is a public, unauthenticated endpoint - without a cap, a caller could
    # submit a multi-megabyte password on every request to inflate CPU cost per attempt.
    password: str = Field(min_length=1, max_length=128)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str
    role: AdminRole
    is_active: bool
    created_at: datetime
