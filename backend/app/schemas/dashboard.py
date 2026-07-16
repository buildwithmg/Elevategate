from pydantic import BaseModel


class DashboardSummary(BaseModel):
    pending_requests: int
    approved_today: int
    denied_today: int
    active_devices: int
    offline_devices: int


class EnrollmentInfo(BaseModel):
    """Admin-only (require_role("admin") - not "reviewer", unlike most of this API) - the
    enrollment key gates who can create a device identity at all, so it's treated more sensitively
    than ordinary read access. `install_command` is just the same one-liner from docs/INSTALL.md,
    included so the dashboard never hardcodes a URL that could drift from the real one."""

    enrollment_key: str
    install_command: str
