"""Domain-level errors and exceptions."""


class BudgetError(Exception):
    """Base exception for all domain errors."""


class InvalidAmountError(BudgetError):
    """Raised when an amount is invalid (negative, etc.)."""


class InvalidYearMonthError(BudgetError):
    """Raised when a year-month string is invalid."""


class InvalidCreditLimitChangeError(BudgetError):
    """Raised when a scheduled credit limit change has an invalid date."""


class InvalidBillAmountChangeError(BudgetError):
    """A scheduled change to a bill's amount is not a real month."""


class BillNotFoundError(BudgetError):
    """Raised when a bill is not found."""


class MonthNotFoundError(BudgetError):
    """Raised when a month is not found."""


class InvalidCommitmentError(BudgetError):
    """Raised when a commitment's fields cannot describe a real obligation."""
