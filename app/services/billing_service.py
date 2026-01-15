from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from app.models.user import User
from app.models.account_type import AccountType

logger = logging.getLogger(__name__)


class InsufficientCreditsError(Exception):
    """Raised when user has insufficient credits for an operation."""
    pass


class BillingService:
    """Handles credit management and billing operations for users."""

    async def check_and_reset_credits(self, user: User) -> User:
        """
        Check if credits need to be reset (monthly - 30 day rolling window).
        If 30+ days have passed since last reset, reset credits with rollover.
        
        Args:
            user: User document to check and potentially reset
            
        Returns:
            Updated user document (saved to database if reset occurred)
        """
        now = datetime.utcnow()
        days_since_reset = (now - user.last_credit_reset).days
        
        if days_since_reset >= 30:
            # Calculate rollover from unused credits
            rollover = user.credits_remaining
            monthly_allocation = user.account_type.monthly_credits
            new_credits = monthly_allocation + rollover
            
            # Update user
            user.credits_remaining = new_credits
            user.credits_used_this_period = 0
            user.last_credit_reset = now
            
            await user.save()
            
            logger.info(
                f"Reset credits for user {user.id}: "
                f"rolled over {rollover} credits, "
                f"new total: {new_credits} "
                f"(base: {monthly_allocation})"
            )
        
        return user

    async def has_available_credits(self, user: User) -> bool:
        """
        Check if user has credits available.
        
        Args:
            user: User document to check
            
        Returns:
            True if user has at least 1 credit remaining
        """
        return user.credits_remaining > 0

    async def consume_credit(self, user: User) -> bool:
        """
        Deduct one credit from user's account.
        
        Args:
            user: User document to deduct credit from
            
        Returns:
            True if successful
            
        Raises:
            InsufficientCreditsError: If user has no credits remaining
        """
        if user.credits_remaining <= 0:
            raise InsufficientCreditsError("All credits used for this month")
        
        user.credits_remaining -= 1
        user.credits_used_this_period += 1
        user.total_credits_lifetime += 1
        
        await user.save()
        
        logger.info(
            f"Consumed 1 credit for user {user.id}. "
            f"Remaining: {user.credits_remaining}, "
            f"Used this period: {user.credits_used_this_period}"
        )
        
        return True

    async def get_user_by_token(self, token: str) -> Optional[User]:
        """
        Helper to get user by extension token.
        
        Args:
            token: Extension token to look up user
            
        Returns:
            User document if found, None otherwise
        """
        user = await self.db.users.find_one({
            "$or": [
                {"local.token": token},
                {"google.token": token},
                {"linkedin.token": token},
            ]
        })
        return user
    
    async def get_user_by_extension_or_local_token(self, token: str) -> Optional[User]:
        """
        Helper to get user by either extension_token or by validating JWT token.
        
        Args:
            token: Token to look up user (could be extension_token or JWT)
            
        Returns:
            User document if found, None otherwise
        """
        # First try extension token
        user = await User.find_one(User.extension_token == token)
        if user:
            return user
        
        # If not found, could be a JWT token (for local auth)
        # For now, just return None - JWT validation can be added later if needed
        return None
