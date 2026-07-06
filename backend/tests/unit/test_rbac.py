from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.deps import require_role


async def test_require_role_allows_matching_role():
    dependency = require_role("admin", "reviewer")
    fake_admin = SimpleNamespace(role=SimpleNamespace(value="reviewer"))

    result = await dependency(admin=fake_admin)

    assert result is fake_admin


async def test_require_role_rejects_non_matching_role():
    dependency = require_role("admin")
    fake_admin = SimpleNamespace(role=SimpleNamespace(value="reviewer"))

    with pytest.raises(HTTPException) as exc_info:
        await dependency(admin=fake_admin)

    assert exc_info.value.status_code == 403
