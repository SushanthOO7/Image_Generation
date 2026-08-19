from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.auth import create_api_key_secret, get_current_user
from backend.app.database import get_db
from backend.app.models import User
from backend.app.rate_limits import get_generation_rate_limit_status
from backend.app.repositories import (
    count_active_generation_jobs,
    create_api_key,
    get_monthly_generation_usage,
    list_api_keys,
    next_usage_month_start,
    revoke_api_key,
)
from backend.app.responses import api_key_response
from backend.app.schemas import (
    ApiKeyCreateRequest,
    ApiKeyCreateResponse,
    ApiKeyListResponse,
    ApiKeyRevokeResponse,
    GenerationLimitsResponse,
)
from backend.app.settings import limits_for_plan, load_settings

router = APIRouter(prefix="/v1/me", tags=["account"])
settings = load_settings()


@router.get("/api-keys", response_model=ApiKeyListResponse)
def get_api_keys(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiKeyListResponse:
    return ApiKeyListResponse(api_keys=[api_key_response(key) for key in list_api_keys(db, current_user.id)])


@router.post("/api-keys", response_model=ApiKeyCreateResponse, status_code=status.HTTP_201_CREATED)
def create_user_api_key(
    request: ApiKeyCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiKeyCreateResponse:
    if not request.name.strip():
        raise HTTPException(status_code=400, detail="API key name is required")
    secret = create_api_key_secret()
    key = create_api_key(db, current_user.id, request.name, secret)
    response = api_key_response(key)
    return ApiKeyCreateResponse(**response.model_dump(), api_key=secret)


@router.delete("/api-keys/{key_id}", response_model=ApiKeyRevokeResponse)
def revoke_user_api_key(
    key_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiKeyRevokeResponse:
    key = revoke_api_key(db, current_user.id, key_id)
    if key is None:
        raise HTTPException(status_code=404, detail="API key not found")
    if key.revoked_at is None:
        raise HTTPException(status_code=500, detail="API key revoke failed")
    return ApiKeyRevokeResponse(id=key.id, revoked_at=key.revoked_at)


@router.get("/limits", response_model=GenerationLimitsResponse)
def generation_limits(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GenerationLimitsResponse:
    plan_limits = limits_for_plan(settings, current_user.plan)
    active_jobs = count_active_generation_jobs(db, current_user.id)
    rate_limit = get_generation_rate_limit_status(settings, current_user.id, plan_limits.rate_limit_per_minute)
    monthly_used = get_monthly_generation_usage(db, current_user.id)
    monthly_remaining = (
        max(plan_limits.monthly_generation_quota - monthly_used, 0)
        if plan_limits.monthly_generation_quota >= 0
        else -1
    )
    return GenerationLimitsResponse(
        rate_limit_per_minute=plan_limits.rate_limit_per_minute,
        rate_limit_remaining=rate_limit.remaining,
        rate_limit_reset_seconds=rate_limit.reset_seconds,
        concurrent_limit=plan_limits.concurrent_generation_limit,
        active_jobs=active_jobs,
        monthly_quota=plan_limits.monthly_generation_quota,
        monthly_used=monthly_used,
        monthly_remaining=monthly_remaining,
        monthly_reset_at=next_usage_month_start(),
    )
