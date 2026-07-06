from pydantic import BaseModel


class DashboardSummary(BaseModel):
    pending_requests: int
    approved_today: int
    denied_today: int
    active_devices: int
    offline_devices: int
