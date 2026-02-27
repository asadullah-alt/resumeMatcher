from fastapi import APIRouter, HTTPException, status, Query
from app.services.billing_service import BillingService
from app.schemas.pydantic.user import UserPreferences, UserPreferencesUpdate
from app.models.user import User

user_router = APIRouter()

@user_router.get("/preferences", response_model=UserPreferences)
async def get_preferences(token: str = Query(..., description="User token")):
    billing_service = BillingService()
    user = await billing_service.get_user_by_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    return UserPreferences(
        salary_min=user.salary_min,
        salary_max=user.salary_max,
        visa_sponsorship=user.visa_sponsorship,
        remote_friendly=user.remote_friendly,
        country=user.country
    )

@user_router.patch("/preferences", response_model=UserPreferences)
async def update_preferences(payload: UserPreferencesUpdate):
    billing_service = BillingService()
    user = await billing_service.get_user_by_token(payload.token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    if payload.salary_min is not None:
        user.salary_min = payload.salary_min
    if payload.salary_max is not None:
        user.salary_max = payload.salary_max
    if payload.visa_sponsorship is not None:
        user.visa_sponsorship = payload.visa_sponsorship
    if payload.remote_friendly is not None:
        user.remote_friendly = payload.remote_friendly
    if payload.country is not None:
        user.country = payload.country
        
    await user.save()
    
    return UserPreferences(
        salary_min=user.salary_min,
        salary_max=user.salary_max,
        visa_sponsorship=user.visa_sponsorship,
        remote_friendly=user.remote_friendly,
        country=user.country
    )
