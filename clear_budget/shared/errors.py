"""Domain-level errors and exceptions."""


class BudgetError(Exception):
    """Base exception for all domain errors."""

    pass


class InvalidAmountError(BudgetError):
    """Raised when an amount is invalid (negative, etc.)."""

    pass


class InvalidYearMonthError(BudgetError):
    """Raised when a year-month string is invalid."""

    pass


class InvalidCreditLimitChangeError(BudgetError):
    """Raised when a scheduled credit limit change has an invalid date."""

    pass


class BillNotFoundError(BudgetError):
    """Raised when a bill is not found."""

    pass


class MonthNotFoundError(BudgetError):
    """Raised when a month is not found."""

    pass
