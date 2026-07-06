from fastapi import APIRouter

from app.api.v1 import (
    agent,
    agent_compat,
    approvals,
    audit_logs,
    auth,
    dashboard,
    devices,
    elevation_requests,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(devices.router)
api_router.include_router(elevation_requests.router)
api_router.include_router(agent.router)
api_router.include_router(agent_compat.router)
api_router.include_router(approvals.router)
api_router.include_router(audit_logs.router)
api_router.include_router(dashboard.router)
