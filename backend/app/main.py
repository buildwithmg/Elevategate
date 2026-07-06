import logging

from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1.router import api_router
from app.core.rate_limit import limiter

# Uvicorn's default access log only records method/path/status - never headers or bodies - so
# it never sees an Authorization header, JWT, password, or device secret. No app code in this
# project logs a request body or an Authorization header; see docs/BACKEND_THREAT_MODEL.md.
logging.basicConfig(level=logging.INFO)


def create_app() -> FastAPI:
    app = FastAPI(
        title="ElevateGate Backend",
        description=(
            "Endpoint privilege-approval backend. Issues structured, signed, single-use "
            "elevation approvals to enrolled Windows agents; never arbitrary commands."
        ),
        version="1.0.0",
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    app.include_router(api_router)

    @app.get("/healthz", tags=["health"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
