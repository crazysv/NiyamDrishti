import uuid

import pytest
from fastapi import HTTPException

from app.api.deps import (
    get_current_active_admin,
    get_current_active_officer,
    get_current_active_supervisor,
    get_current_active_user,
)
from app.models.base import User


@pytest.mark.asyncio
async def test_rbac_roles():
    officer = User(id=uuid.uuid4(), email="o@test.gov.in", role="officer", is_active=True, full_name="Officer")
    supervisor = User(id=uuid.uuid4(), email="s@test.gov.in", role="supervisor", is_active=True, full_name="Supervisor")
    admin = User(id=uuid.uuid4(), email="a@test.gov.in", role="admin", is_active=True, full_name="Admin")
    inactive = User(id=uuid.uuid4(), email="i@test.gov.in", role="officer", is_active=False, full_name="Inactive")

    # Inactive check
    with pytest.raises(HTTPException) as exc_info:
        await get_current_active_user(inactive)
    assert exc_info.value.status_code == 400

    # Officer dependency checks
    assert (await get_current_active_officer(officer)).id == officer.id
    assert (await get_current_active_officer(supervisor)).id == supervisor.id
    assert (await get_current_active_officer(admin)).id == admin.id

    # Supervisor dependency checks
    assert (await get_current_active_supervisor(supervisor)).id == supervisor.id
    assert (await get_current_active_supervisor(admin)).id == admin.id
    with pytest.raises(HTTPException) as exc_info:
        await get_current_active_supervisor(officer)
    assert exc_info.value.status_code == 403

    # Admin dependency checks
    assert (await get_current_active_admin(admin)).id == admin.id
    with pytest.raises(HTTPException) as exc_info:
        await get_current_active_admin(officer)
    assert exc_info.value.status_code == 403

    with pytest.raises(HTTPException) as exc_info:
        await get_current_active_admin(supervisor)
    assert exc_info.value.status_code == 403
