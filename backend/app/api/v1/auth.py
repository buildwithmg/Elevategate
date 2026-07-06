from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_db
from app.config import get_settings
from app.core.rate_limit import limiter
from app.core.security import create_access_token, hash_secret, verify_secret
from app.models.admin_user import AdminUser
from app.repositories import admin_user_repository
from app.schemas.auth import LoginRequest, LoginResponse, MeResponse

router = APIRouter(prefix="/auth", tags=["auth"])

# A fixed, valid Argon2id hash with no corresponding real account, used purely so that looking up
# a nonexistent email still costs roughly the same wall-clock time as verifying a real password -
# otherwise "unknown email" (fast) vs "wrong password" (slow, real Argon2id verify) would be
# distinguishable from response timing alone.
_DUMMY_HASH = hash_secret("dummy-password-for-timing-equalization")


@router.post("/login", response_model=LoginResponse)
@limiter.limit(lambda: get_settings().rate_limit_login)
async def login(
    request: Request, body: LoginRequest, session: AsyncSession = Depends(get_db)
) -> LoginResponse:
    admin = await admin_user_repository.get_by_email(session, body.email)

    if admin is None:
        verify_secret(body.password, _DUMMY_HASH)  # timing equalization only; result discarded
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")

    if not admin.is_active or not verify_secret(body.password, admin.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")

    token = create_access_token(subject=str(admin.id), role=admin.role.value)
    return LoginResponse(access_token=token)


@router.get("/me", response_model=MeResponse)
async def me(admin: AdminUser = Depends(get_current_admin)) -> MeResponse:
    return MeResponse.model_validate(admin)
