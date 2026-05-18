"""BudgetService — main application orchestrator."""

from dataclasses import dataclass

from clear_budget.application.dto.month_summary import MonthSummary
from clear_budget.application.dto.solvency_report import SolvencyReport
from clear_budget.application.services.month_generator import MonthGenerator
from clear_budget.domain.interfaces.bill_repository import BillRepository
from clear_budget.domain.interfaces.income_source_repository import (
    IncomeSourceRepository,
)
from clear_budget.domain.interfaces.payment_method_repository import (
    PaymentMethodRepository,
)
from clear_budget.domain.services.bank_cashflow import (
    BankCashflowService,
    DailyCashflowEvent,
)
from clear_budget.domain.services.card_exhaustion import CardExhaustionService
from clear_budget.domain.services.solvency_calculator import (
    SolvencyCalculatorService,
)
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth


from clear_budget.domain.entities.bill import Bill

@dataclass(frozen=True, slots=True)
class BudgetService:
    """Main application service orchestrating domain services and repositories."""

    bill_repo: BillRepository
    income_repo: IncomeSourceRepository
    payment_method_repo: PaymentMethodRepository
    month_generator: MonthGenerator

    def get_month_summary(self, *, year_month: YearMonth) -> MonthSummary:
        """Get summary of bills and income for a month.

        Args:
            year_month: The month to summarize

        Returns:
            MonthSummary with totals, balance, and bill/income lists
        """
        bills = self.bill_repo.list_active_for_month(year_month=year_month)
        income = self.income_repo.list_active()

        total_bills_pence = sum(bill.amount.pence for bill in bills)
        total_income_pence = sum(inc.amount.pence for inc in income)
        balance_pence = total_income_pence - total_bills_pence

        return MonthSummary(
            year_month=year_month,
            total_income=Amount(pence=total_income_pence),
            total_bills=Amount(pence=total_bills_pence),
            balance=Amount(pence=balance_pence)
            if balance_pence >= 0
            else Amount(pence=0),  # Store as non-negative
            bills=tuple(bills),
            income_sources=tuple(income),
        )

    def calculate_solvency(
        self,
        *,
        year_month: YearMonth,
    ) -> SolvencyReport:
        """Calculate complete solvency analysis for a month.

        Analyzes current month and projects forward 2 months for shortfalls.

        Args:
            year_month: The month to analyze

        Returns:
            SolvencyReport with balance, deficit, forward shortfall, acquire target
        """
        # Generate month data from templates
        month_bills = self.month_generator.generate_month_bills(
            year_month=year_month,
            month_id=0,  # Placeholder
        )
        month_income = self.month_generator.generate_month_income(
            year_month=year_month,
            month_id=0,
        )

        # Generate next 2 months for forward projections
        next_month = year_month.next_month()
        next_next_month = next_month.next_month()

        next_bills = self.month_generator.generate_month_bills(
            year_month=next_month,
            month_id=0,
        )
        next_income = self.month_generator.generate_month_income(
            year_month=next_month,
            month_id=0,
        )

        next_next_bills = self.month_generator.generate_month_bills(
            year_month=next_next_month,
            month_id=0,
        )
        next_next_income = self.month_generator.generate_month_income(
            year_month=next_next_month,
            month_id=0,
        )

        # Calculate solvency
        solvency = SolvencyCalculatorService.calculate(
            month_bills=month_bills,
            month_income=month_income,
            next_two_months_bills=[next_bills, next_next_bills],
            next_two_months_income=[next_income, next_next_income],
        )

        # Check for overdraft (for now, return None)
        # In a real implementation, would calculate daily events
        first_negative = None

        return SolvencyReport(
            year_month=year_month,
            balance_pence=solvency.balance,
            deficit=solvency.deficit,
            buffer=solvency.buffer,
            forward_shortfall=solvency.forward_shortfall,
            desired_acquire=solvency.desired_acquire,
            is_solvent=solvency.is_solvent,
            first_negative_day=first_negative,
        )

    def add_bill(self, *, bill: Bill) -> Bill:
        """Create a new bill."""
        return self.bill_repo.add(bill=bill)

    def update_bill(self, *, bill: Bill) -> Bill:
        """Update an existing bill."""
        return self.bill_repo.update(bill=bill)

    def delete_bill(self, *, bill_id: int) -> None:
        """Deactivate a bill."""
        self.bill_repo.deactivate(bill_id=bill_id)

    def add_income(self, *, income: "IncomeSource") -> "IncomeSource":
        """Create a new income source."""
        from clear_budget.domain.entities.income_source import IncomeSource
        return self.income_repo.add(income=income)

    def update_income(self, *, income: "IncomeSource") -> "IncomeSource":
        """Update an existing income source."""
        from clear_budget.domain.entities.income_source import IncomeSource
        return self.income_repo.update(income=income)

    def delete_income(self, *, income_id: int) -> None:
        """Deactivate an income source."""
        self.income_repo.deactivate(income_id=income_id)

    def get_credit_cards(self, include_inactive: bool = False) -> list:
        """Get all credit cards."""
        return self.payment_method_repo.get_all_credit_cards(include_inactive=include_inactive)

    def _log_debug(self, msg: str) -> None:
        """Write debug message to log file."""
        from pathlib import Path
        log_file = Path.home() / ".clearbudget" / "debug.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, "a") as f:
            f.write(f"{msg}\n")

    def get_bank_balance(self) -> Amount:
        """Get current bank account balance."""
        cursor = self.bill_repo.conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", ("bank_balance",))
        row = cursor.fetchone()
        pence = int(row["value"]) if row else 0
        self._log_debug(f"[GET_BALANCE] Loaded {pence} pence from database (row exists: {row is not None})")
        return Amount(pence=pence)

    def set_bank_balance(self, *, amount: Amount) -> None:
        """Set current bank account balance."""
        cursor = self.bill_repo.conn.cursor()
        self._log_debug(f"[SET_BALANCE] Saving {amount.pence} pence to database")
        cursor.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ("bank_balance", str(amount.pence)),
        )
        self.bill_repo.conn.commit()
        self._log_debug(f"[SET_BALANCE] Committed to database successfully")

        # Verify it was saved
        cursor.execute("SELECT value FROM settings WHERE key = ?", ("bank_balance",))
        verify_row = cursor.fetchone()
        self._log_debug(f"[SET_BALANCE] Verification - value in DB: {verify_row['value'] if verify_row else 'NOT FOUND'}")
