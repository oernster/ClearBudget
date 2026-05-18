"""SolvencyCalculator  -  pure domain service for solvency calculations."""

from dataclasses import dataclass

from clear_budget.domain.entities.month_bill import MonthBill
from clear_budget.domain.entities.month_income import MonthIncome
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.solvency_result import SolvencyResult


@dataclass(frozen=True, slots=True)
class SolvencyCalculatorService:
    """Pure service for calculating solvency (balance, deficit, acquire targets).

    Takes month data in, returns solvency result. No I/O, deterministic.
    """

    @staticmethod
    def calculate(
        *,
        month_bills: list[MonthBill],
        month_income: list[MonthIncome],
        next_two_months_bills: list[list[MonthBill]],
        next_two_months_income: list[list[MonthIncome]],
        buffer: Amount = None,
    ) -> SolvencyResult:
        """Calculate solvency for a month.

        Args:
            month_bills: Bills for the current month
            month_income: Income for the current month
            next_two_months_bills: Bills for the next 2 months
            next_two_months_income: Income for the next 2 months (reliable only)
            buffer: Safety cushion (default £600)

        Returns:
            SolvencyResult with balance, deficit, forward_shortfall, desired_acquire
        """
        if buffer is None:
            buffer = Amount.from_pounds(600)

        # Calculate current month balance (bank account only)
        total_in = sum((inc.amount.pence for inc in month_income), 0)
        total_out = sum((bill.amount.pence for bill in month_bills if bill.payment_method_id == 1), 0)
        balance = total_in - total_out

        # Calculate deficit if negative
        deficit = Amount(pence=abs(balance)) if balance < 0 else Amount.zero()

        # Calculate forward shortfall (next 2 months reliable income vs bank bills)
        forward_shortfall_pence = 0
        for month_idx in range(len(next_two_months_bills)):
            future_out = sum(
                (bill.amount.pence for bill in next_two_months_bills[month_idx] if bill.payment_method_id == 1),
                0,
            )
            future_in_reliable = sum(
                (inc.amount.pence for inc in next_two_months_income[month_idx]),
                0,
            )
            month_shortfall = max(0, future_out - future_in_reliable)
            forward_shortfall_pence += month_shortfall

        forward_shortfall = Amount(pence=forward_shortfall_pence)

        # Desired acquire = deficit + buffer + forward shortfall
        desired_pence = deficit.pence + buffer.pence + forward_shortfall.pence
        desired_acquire = Amount(pence=desired_pence)

        return SolvencyResult(
            balance=balance,
            deficit=deficit,
            buffer=buffer,
            forward_shortfall=forward_shortfall,
            desired_acquire=desired_acquire,
        )
