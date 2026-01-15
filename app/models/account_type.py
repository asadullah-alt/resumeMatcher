from enum import Enum


class AccountType(str, Enum):
    """User account types with different monthly credit allocations."""
    
    JOB_TRACKER = "jobTracker"  # 5 applications per month
    CASUALLY_LOOKING = "causallyLooking"  # 25 applications per month
    I_NEED_A_JOB = "iNeedAJob"  # 50 applications per month
    ARE_YOU_SERIOUS = "areYouSerious"  # 150 applications per month

    @property
    def monthly_credits(self) -> int:
        """Returns monthly credit allocation for this account type."""
        credit_map = {
            AccountType.JOB_TRACKER: 5,
            AccountType.CASUALLY_LOOKING: 25,
            AccountType.I_NEED_A_JOB: 50,
            AccountType.ARE_YOU_SERIOUS: 150,
        }
        return credit_map[self]
