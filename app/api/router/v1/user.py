from datetime import timezone
from datetime import datetime
import logging
from fastapi import APIRouter, HTTPException, status, Query
from pydantic import BaseModel, Field, validator
from app.services.billing_service import BillingService
from app.schemas.pydantic.user import UserPreferences, UserPreferencesUpdate
from app.models.user import User

user_router = APIRouter()
logger = logging.getLogger(__name__)

class UserFeedback(BaseModel):
    token: str
    rating: int = Field(..., ge=1, le=10, description="Rating between 1 and 10")
    description: str = Field(..., min_length=0, max_length=1000)

@user_router.post("/feedback", status_code=status.HTTP_201_CREATED)
async def submit_feedback(feedback: UserFeedback):
    logger.info(f"Received feedback from token: {feedback.token[:10]}...")
    billing_service = BillingService()

    user = await billing_service.get_user_by_token(feedback.token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    user.feedback.append({
        "rating": feedback.rating,
        "description": feedback.description,
        "timestamp": datetime.now(timezone.utc)
    })
    
    await user.save()
    
    return {"message": "Feedback submitted successfully"}

@user_router.get("/preferences", response_model=UserPreferences)
async def get_preferences(token: str = Query(..., description="User token")):
    logger.info(f"Received request to get preferences for token: {token[:10]}...")
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
        country=user.country,
        city=user.city,
        experience=user.experience
    )

@user_router.patch("/preferences", response_model=UserPreferences)
async def update_preferences(payload: UserPreferencesUpdate):
    logger.info(f"Received request to update preferences for token: {payload.token[:10]}...")
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
    if payload.city is not None:
        user.city = payload.city
    if payload.experience is not None:
        user.experience = payload.experience
        
    await user.save()
    
    return UserPreferences(
        salary_min=user.salary_min,
        salary_max=user.salary_max,
        visa_sponsorship=user.visa_sponsorship,
        remote_friendly=user.remote_friendly,
        country=user.country
    )
