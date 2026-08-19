from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.auth import get_current_user
from backend.app.database import get_db
from backend.app.dependencies import require_admin
from backend.app.models import User
from backend.app.repositories import update_user_plan
from backend.app.responses import user_response
from backend.app.schemas import UpdateUserPlanRequest, UserResponse

router = APIRouter(prefix="/v1/admin", tags=["admin"])


@router.patch("/users/{user_id}/plan", response_model=UserResponse)
def set_user_plan(
    user_id: str,
    request: UpdateUserPlanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    require_admin(current_user)
    user = update_user_plan(db, user_id, request.plan)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user_response(user)
