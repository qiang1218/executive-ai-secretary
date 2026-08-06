from __future__ import annotations

from fastapi import APIRouter

from api.deps import HealthServiceDep

router = APIRouter(tags=["health"])


@router.get("/health/live", include_in_schema=False)
async def live(service: HealthServiceDep) -> dict[str, str]:
    return service.liveness()


@router.get("/health/ready", include_in_schema=False)
async def ready(service: HealthServiceDep) -> dict[str, str]:
    return await service.readiness()
