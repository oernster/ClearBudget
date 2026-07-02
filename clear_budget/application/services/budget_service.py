"""BudgetService  -  main application orchestrator."""

from dataclasses import dataclass, replace
from datetime import date

from clear_budget.application.dto.month_summary import MonthSummary
from clear_budget.application.dto.solvency_report import SolvencyReport
from clear_budget.application.services.month_generator import MonthGenerator
from clear_budget.application.services._bill_operations import BillOperationsMixin
from clear_budget.application.services._income_operations import (
    IncomeOperationsMixin,
)
from clear_budget.application.services._overdraft_operations import (
    OverdraftOperationsMixin,
)
from clear_budget.application.services._month_mappers import (
    bills_to_month_bills as _bills_to_month_bills,
    income_to_month_income as _income_to_month_income,
)
from clear_budget.domain.interfaces.bill_repository import BillRepository
from clear_budget.domain.interfaces.income_source_repository import (
    IncomeSourceRepository,
)
from clear_budget.domain.interfaces.payment_method_repository import (
    PaymentMethodRepository,
)
from clear_budget.domain.services._prorating import (
    days_in_month,
    prorate_remaining_pence,
)
from clear_budget.domain.services.solvency_calculator import (
    SolvencyCalculatorService,
)
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth


@dataclass(frozen=True, slots=True)
class BudgetService(
    BillOperationsMixin, IncomeOperationsMixin, OverdraftOperationsMixin
):
    bill_repo: BillRepository
    income_repo: IncomeSourceRepository
    payment_method_repo: PaymentMethodRepository
    month_generator: MonthGenerator

    def get_month_summary(self, *, year_month: YearMonth) -> MonthSummary:
        active_bills = self.bill_repo.list_active_for_month(year_month=year_month)
        all_bills = self.bill_repo.list_active_for_month(
            year_month=year_month, include_inactive=True
        )
        extras = self.income_repo.list_extras_for_month(year_month=year_month)
        income = self.income_repo.list_active_for_month(year_month=year_month) + extras
        all_income = (
            self.income_repo.list_active_for_month(
                year_month=year_month, include_inactive=True
            )
            + extras
        )

        total_bills_pence = sum(bill.amount.pence for bill in active_bills)
        bank_bills_pence = sum(
            bill.amount.pence for bill in active_bills if bill.payment_method_id == 1
        )
        total_income_pence = sum(inc.amount.pence for inc in income)
        balance_pence = total_income_pence - bank_bills_pence

        return MonthSummary(
            year_month=year_month,
            total_income=Amount(pence=total_income_pence),
            total_bills=Amount(pence=total_bills_pence),
            bank_bills=Amount(pence=bank_bills_pence),
            balance=(
                Amount(pence=balance_pence) if balance_pence >= 0 else Amount(pence=0)
            ),
            bills=tuple(active_bills),
            all_bills=tuple(all_bills),
            income_sources=tuple(income),
            all_income_sources=tuple(all_income),
        )

    def calculate_solvency_from_summary(
        self,
        *,
        year_month: YearMonth,
        month_summary: "MonthSummary | None",
    ) -> SolvencyReport:
        if month_summary is None:
            return self.calculate_solvency(year_month=year_month)
        from datetime import date as _date

        today = _date.today()
        today_ym = YearMonth(today.year, today.month)
        month_bills, month_income = self._apply_current_month_filters(
            month_summary.bills,
            month_summary.income_sources,
            year_month,
            today_ym,
            today.day,
        )
        return self._build_solvency_report(month_bills, month_income, year_month)

    def calculate_solvency(self, *, year_month: YearMonth) -> SolvencyReport:
        from datetime import date as _date

        today = _date.today()
        today_ym = YearMonth(today.year, today.month)
        summary = self.get_month_summary(year_month=year_month)
        month_bills, month_income = self._apply_current_month_filters(
            summary.bills, summary.income_sources, year_month, today_ym, today.day
        )
        return self._build_solvency_report(month_bills, month_income, year_month)

    def get_remaining_month_items(
        self, *, year_month: YearMonth, summary: MonthSummary
    ) -> tuple[tuple, tuple]:
        """Return (bills, income) still outstanding for year_month.

        For the current month this excludes items already due before today
        (matching the filtering used for the solvency balance projection).
        For other months, returns all bills/income unchanged.
        """
        today = date.today()
        today_ym = YearMonth(today.year, today.month)
        return self._apply_current_month_filters(
            summary.bills, summary.income_sources, year_month, today_ym, today.day
        )

    def _apply_current_month_filters(
        self, bills, income, year_month, today_ym, today_day: int
    ):
        if year_month != today_ym:
            return tuple(bills), tuple(income)
        balance_day = self._get_bank_balance_day()
        total_days = days_in_month(year_month.year, year_month.month)
        filtered_bills = tuple(
            (
                replace(
                    b,
                    amount=Amount(
                        pence=prorate_remaining_pence(
                            b.amount.pence, today_day, total_days
                        )
                    ),
                )
                if b.day_of_month is None
                else b
            )
            for b in bills
            if not b.paid_for_month
            and (b.day_of_month is None or b.day_of_month >= today_day)
        )
        if balance_day > 0:
            filtered_income = tuple(
                i
                for i in income
                if i.day_of_month is None or i.day_of_month > balance_day
            )
        else:
            filtered_income = tuple(
                i
                for i in income
                if i.day_of_month is None or i.day_of_month >= today_day
            )
        return filtered_bills, filtered_income

    def _build_solvency_report(
        self, month_bills, month_income, year_month: YearMonth
    ) -> SolvencyReport:
        m1 = year_month.next_month()
        m2 = m1.next_month()
        s1 = self.get_month_summary(year_month=m1)
        s2 = self.get_month_summary(year_month=m2)
        solvency = SolvencyCalculatorService.calculate(
            month_bills=_bills_to_month_bills(month_bills, 0),
            month_income=_income_to_month_income(month_income, 0),
            next_two_months_bills=[
                _bills_to_month_bills(s1.bills, 1),
                _bills_to_month_bills(s2.bills, 2),
            ],
            next_two_months_income=[
                _income_to_month_income(s1.income_sources, 1),
                _income_to_month_income(s2.income_sources, 2),
            ],
        )
        projected_balance = (
            self._projected_starting_balance_pence(year_month) + solvency.balance
        )
        return SolvencyReport(
            year_month=year_month,
            balance_pence=projected_balance,
            deficit=solvency.deficit,
            buffer=solvency.buffer,
            forward_shortfall=solvency.forward_shortfall,
            desired_acquire=solvency.desired_acquire,
            is_solvent=projected_balance >= 0,
            first_negative_day=None,
        )

    def get_projected_month_end_balance_pence(
        self, *, year_month: YearMonth, summary: "MonthSummary"
    ) -> int:
        """Projected bank balance pence at end of year_month. Signed."""
        from datetime import date as _date
        from clear_budget.application.services._balance_projection import (
            projected_month_end_balance_pence,
        )

        today = _date.today()
        return projected_month_end_balance_pence(
            get_month_summary=self.get_month_summary,
            get_bank_balance_pence=lambda: self.get_bank_balance().pence,
            get_bank_balance_day=self._get_bank_balance_day,
            today_ym=YearMonth(today.year, today.month),
            today_day=today.day,
            year_month=year_month,
            summary=summary,
        )

    def get_card_monthly_states(
        self, *, year_month: YearMonth
    ) -> list:  # pragma: no cover
        from clear_budget.application.services._card_projection import (
            get_card_monthly_states as _impl,
        )

        return _impl(self.payment_method_repo, self.get_month_summary, year_month)

    def get_card_projection_months(
        self, *, start_month: YearMonth, n_months: int
    ) -> list[list]:  # pragma: no cover
        """Return n_months of CardMonthlyState lists starting from start_month."""
        from clear_budget.application.services._card_projection import (
            get_card_projection_months as _impl,
        )

        return _impl(
            self.payment_method_repo,
            self.get_month_summary,
            start_month=start_month,
            n_months=n_months,
        )

    def get_credit_cards(
        self, include_inactive: bool = False
    ) -> list:  # pragma: no cover
        return self.payment_method_repo.get_all_credit_cards(
            include_inactive=include_inactive
        )

    def get_live_card_balance(self, *, card) -> Amount:
        """Return the card's live (pro-rated) balance for the current day."""
        from datetime import date as _date
        from clear_budget.application.services._card_balance_updates import (
            get_live_card_balance as _impl,
        )

        return _impl(
            self.payment_method_repo,
            self.get_month_summary,
            card=card,
            today=_date.today(),
        )

    def save_credit_card_today_balance(
        self, *, card, today_balance: Amount, is_new: bool, today: date | None = None
    ) -> int:
        """Persist a card from its entered live (as-of-today) balance.

        Converts the user-facing "what I owe now" figure into the start-of-month
        opening the projection layer expects, so the displayed balance matches
        what was entered and forward projections stay anchored. Returns the
        persisted card id.
        """
        from datetime import date as _date
        from clear_budget.application.services._card_balance_updates import (
            save_card_with_today_balance as _impl,
        )

        return _impl(
            self.payment_method_repo,
            card=card,
            today_balance_pence=today_balance.pence,
            today=today or _date.today(),
            is_new=is_new,
        )

    def update_card_balances_for_elapsed_dates(
        self, *, today: date | None = None
    ) -> None:
        """Fold each card's closing balance once its payment date has passed."""
        from datetime import date as _date
        from clear_budget.application.services._card_balance_updates import (
            update_card_balances_for_elapsed_dates as _impl,
        )

        _impl(
            self.payment_method_repo,
            self.get_month_summary,
            today=today or _date.today(),
        )

    def apply_elapsed_limit_changes(self, *, today: date | None = None) -> None:
        """Fold each card's elapsed scheduled limit changes into its limit."""
        from datetime import date as _date
        from clear_budget.application.services._card_limit_updates import (
            apply_elapsed_limit_changes as _impl,
        )

        _impl(self.payment_method_repo, today=today or _date.today())

    def set_credit_limit_changes(self, *, card_id: int, changes) -> None:
        """Replace a card's scheduled credit limit changes."""
        self.payment_method_repo.set_credit_limit_changes(
            card_id=card_id, changes=tuple(changes)
        )

    def get_recorded_months(self) -> list[YearMonth]:  # pragma: no cover
        from clear_budget.application.services._archive_helpers import (
            _get_recorded_months,
        )

        return _get_recorded_months(self.bill_repo.conn)

    def archive_month(self, *, year_month: YearMonth) -> None:  # pragma: no cover
        from clear_budget.application.services._archive_helpers import _do_archive_month

        _do_archive_month(self.bill_repo.conn, year_month, self.month_generator)

    def auto_archive_elapsed_months(self, *, current_month: YearMonth) -> None:
        """Archive every elapsed month up to (but excluding) current_month.

        Run at startup so a month is captured into the archive the moment it
        ends, even when the app was not opened for several months (each missing
        month in the gap is filled). The left bound is the earliest month
        already on record; with nothing recorded yet it is the month that just
        ended, so history is never fabricated before the first record. Already
        recorded months are skipped, so it is safe to run on every launch.
        """
        recorded = set(self.get_recorded_months())
        month = min(recorded) if recorded else current_month.previous_month()
        while month < current_month:
            if month not in recorded:
                self.archive_month(year_month=month)
            month = month.next_month()

    def get_projected_starting_balance_pence(self, *, year_month: YearMonth) -> int:
        """Public wrapper: projected bank balance pence at start of year_month."""
        return self._projected_starting_balance_pence(year_month)

    def _projected_starting_balance_pence(self, year_month: YearMonth) -> int:
        from datetime import date as _date
        from clear_budget.application.services._balance_projection import (
            projected_starting_balance_pence,
        )

        today = _date.today()
        return projected_starting_balance_pence(
            get_month_summary=self.get_month_summary,
            get_bank_balance_pence=lambda: self.get_bank_balance().pence,
            get_bank_balance_day=self._get_bank_balance_day,
            today_ym=YearMonth(today.year, today.month),
            today_day=today.day,
            year_month=year_month,
        )

    def get_bank_balance(self) -> Amount:  # pragma: no cover
        from clear_budget.application.services._settings_operations import (
            get_bank_balance_pence,
        )

        return Amount(
            pence=get_bank_balance_pence(getattr(self.bill_repo, "conn", None))
        )

    def _get_bank_balance_day(self) -> int:  # pragma: no cover
        from clear_budget.application.services._settings_operations import (
            get_bank_balance_day,
        )

        return get_bank_balance_day(getattr(self.bill_repo, "conn", None))

    def reset_all_data(self) -> None:
        """Wipe all user data, preserving the Bank Account payment method."""
        from clear_budget.application.services._budget_reset import reset_budget_data

        reset_budget_data(self.bill_repo.conn)

    def set_bank_balance(self, *, amount: Amount) -> None:  # pragma: no cover
        from clear_budget.application.services._settings_operations import (
            set_bank_balance_pence,
        )

        set_bank_balance_pence(self.bill_repo.conn, amount.pence)
