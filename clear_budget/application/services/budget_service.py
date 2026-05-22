"""BudgetService  -  main application orchestrator."""

from dataclasses import dataclass

from clear_budget.application.dto.month_summary import MonthSummary
from clear_budget.application.dto.solvency_report import SolvencyReport
from clear_budget.application.services.month_generator import MonthGenerator
from clear_budget.application.services._month_mappers import (
    bills_to_month_bills as _bills_to_month_bills,
    income_to_month_income as _income_to_month_income,
)
from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.entities.income_source import IncomeSource
from clear_budget.domain.interfaces.bill_repository import BillRepository
from clear_budget.domain.interfaces.income_source_repository import (
    IncomeSourceRepository,
)
from clear_budget.domain.interfaces.payment_method_repository import (
    PaymentMethodRepository,
)
from clear_budget.domain.services.solvency_calculator import (
    SolvencyCalculatorService,
)
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth


@dataclass(frozen=True, slots=True)
class BudgetService:
    bill_repo: BillRepository
    income_repo: IncomeSourceRepository
    payment_method_repo: PaymentMethodRepository
    month_generator: MonthGenerator

    def get_month_summary(self, *, year_month: YearMonth) -> MonthSummary:
        active_bills = self.bill_repo.list_active_for_month(year_month=year_month)
        all_bills = self.bill_repo.list_active_for_month(
            year_month=year_month, include_inactive=True
        )
        income = self.income_repo.list_active()
        all_income = self.income_repo.list_all()

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

    def _apply_current_month_filters(
        self, bills, income, year_month, today_ym, today_day: int
    ):
        if year_month != today_ym:
            return tuple(bills), tuple(income)
        balance_day = self._get_bank_balance_day()
        filtered_bills = tuple(
            b for b in bills if b.day_of_month is None or b.day_of_month >= today_day
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

    def add_bill(self, *, bill: Bill) -> Bill:  # pragma: no cover
        return self.bill_repo.add(bill=bill)

    def update_bill(self, *, bill: Bill) -> Bill:  # pragma: no cover
        return self.bill_repo.update(bill=bill)

    def update_bill_for_month(
        self, *, bill: Bill, year_month: YearMonth
    ) -> None:  # pragma: no cover
        cursor = self.bill_repo.conn.cursor()
        cursor.execute(
            """
            INSERT INTO bill_month_overrides (
                bill_id, year, month, amount_pence, payment_method_id, day_of_month
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(bill_id, year, month) DO UPDATE SET
                amount_pence = excluded.amount_pence,
                payment_method_id = excluded.payment_method_id,
                day_of_month = excluded.day_of_month
            """,
            (
                bill.id,
                year_month.year,
                year_month.month,
                bill.amount.pence,
                bill.payment_method_id,
                bill.day_of_month,
            ),
        )
        self.bill_repo.conn.commit()

    def delete_bill(self, *, bill_id: int) -> None:  # pragma: no cover
        self.bill_repo.hard_delete(bill_id=bill_id)

    def set_bill_active(
        self, *, bill_id: int, active: bool
    ) -> None:  # pragma: no cover
        self.bill_repo.set_active(bill_id=bill_id, active=active)

    def delete_bill_month_override(
        self, *, bill_id: int, year_month: YearMonth
    ) -> None:  # pragma: no cover
        cursor = self.bill_repo.conn.cursor()
        cursor.execute(
            "DELETE FROM bill_month_overrides"
            " WHERE bill_id = ? AND year = ? AND month = ?",
            (bill_id, year_month.year, year_month.month),
        )
        self.bill_repo.conn.commit()

    def skip_bill_for_month(
        self, *, bill_id: int, year_month: YearMonth
    ) -> None:  # pragma: no cover
        self.bill_repo.skip_for_month(bill_id=bill_id, year_month=year_month)

    def unskip_bill_for_month(
        self, *, bill_id: int, year_month: YearMonth
    ) -> None:  # pragma: no cover
        self.bill_repo.unskip_for_month(bill_id=bill_id, year_month=year_month)

    def get_projected_month_end_balance_pence(
        self, *, year_month: YearMonth, summary: "MonthSummary"
    ) -> int:
        """Projected bank balance pence at end of year_month.

        Signed - can be negative.
        """
        from datetime import date as _date

        today = _date.today()
        today_ym = YearMonth(today.year, today.month)
        starting = self._projected_starting_balance_pence(year_month)
        if year_month == today_ym:
            balance_day = self._get_bank_balance_day()
            if balance_day > 0:
                income = sum(
                    i.amount.pence
                    for i in summary.income_sources
                    if i.day_of_month is None or i.day_of_month > balance_day
                )
            else:
                income = sum(
                    i.amount.pence
                    for i in summary.income_sources
                    if i.day_of_month is None or i.day_of_month >= today.day
                )
            bills = sum(
                b.amount.pence
                for b in summary.bills
                if b.payment_method_id == 1
                and (b.day_of_month is None or b.day_of_month >= today.day)
            )
        else:
            income = sum(i.amount.pence for i in summary.income_sources)
            bills = sum(
                b.amount.pence for b in summary.bills if b.payment_method_id == 1
            )
        return starting + income - bills

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

    def add_income(self, *, income: IncomeSource) -> IncomeSource:  # pragma: no cover
        return self.income_repo.add(income=income)

    def update_income(
        self, *, income: IncomeSource
    ) -> IncomeSource:  # pragma: no cover
        return self.income_repo.update(income=income)

    def delete_income(self, *, income_id: int) -> None:  # pragma: no cover
        self.income_repo.hard_delete(income_id=income_id)

    def get_credit_cards(
        self, include_inactive: bool = False
    ) -> list:  # pragma: no cover
        return self.payment_method_repo.get_all_credit_cards(
            include_inactive=include_inactive
        )

    def get_recorded_months(self) -> list[YearMonth]:  # pragma: no cover
        from clear_budget.application.services._archive_helpers import (
            _get_recorded_months,
        )

        return _get_recorded_months(self.bill_repo.conn)

    def archive_month(self, *, year_month: YearMonth) -> None:  # pragma: no cover
        from clear_budget.application.services._archive_helpers import _do_archive_month

        _do_archive_month(self.bill_repo.conn, year_month, self.month_generator)

    def auto_archive_previous_month_if_needed(
        self, *, current_month: YearMonth
    ) -> None:
        prev_month = current_month.previous_month()
        recorded = self.get_recorded_months()
        if prev_month not in recorded:
            self.archive_month(year_month=prev_month)

    def _projected_starting_balance_pence(self, year_month: YearMonth) -> int:
        from datetime import date as _date

        today = _date.today()
        today_ym = YearMonth(today.year, today.month)
        pence = self.get_bank_balance().pence
        cursor = today_ym
        while cursor < year_month:
            s = self.get_month_summary(year_month=cursor)
            if cursor == today_ym:
                balance_day = self._get_bank_balance_day()
                if balance_day > 0:
                    income = sum(
                        i.amount.pence
                        for i in s.income_sources
                        if i.day_of_month is None or i.day_of_month > balance_day
                    )
                else:
                    income = sum(
                        i.amount.pence
                        for i in s.income_sources
                        if i.day_of_month is None or i.day_of_month >= today.day
                    )
                bills = sum(
                    b.amount.pence
                    for b in s.bills
                    if b.payment_method_id == 1
                    and (b.day_of_month is None or b.day_of_month >= today.day)
                )
            else:
                income = sum(i.amount.pence for i in s.income_sources)
                bills = sum(b.amount.pence for b in s.bills if b.payment_method_id == 1)
            pence += income - bills
            cursor = cursor.next_month()
        return pence

    def get_bank_balance(self) -> Amount:  # pragma: no cover
        if not hasattr(self.bill_repo, "conn"):
            return Amount.zero()
        cursor = self.bill_repo.conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", ("bank_balance",))
        row = cursor.fetchone()
        return Amount(pence=int(row["value"]) if row else 0)

    def _get_bank_balance_day(self) -> int:  # pragma: no cover
        if not hasattr(self.bill_repo, "conn"):
            return 0
        cursor = self.bill_repo.conn.cursor()
        cursor.execute(
            "SELECT value FROM settings WHERE key = ?", ("bank_balance_day",)
        )
        row = cursor.fetchone()
        return int(row["value"]) if row else 0

    def reset_all_data(self) -> None:
        """Wipe all user data, preserving the Bank Account payment method."""
        from clear_budget.application.services._budget_reset import reset_budget_data

        reset_budget_data(self.bill_repo.conn)

    def get_discretionary_buffer(self) -> int:  # pragma: no cover
        """Return discretionary buffer in pence (default 5000 = £50)."""
        if not hasattr(self.bill_repo, "conn"):
            return 5000
        cursor = self.bill_repo.conn.cursor()
        cursor.execute(
            "SELECT value FROM settings WHERE key = ?", ("discretionary_buffer",)
        )
        row = cursor.fetchone()
        return int(row["value"]) if row else 5000

    def set_discretionary_buffer(self, *, pence: int) -> None:  # pragma: no cover
        """Save discretionary buffer in pence."""
        cursor = self.bill_repo.conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ("discretionary_buffer", str(pence)),
        )
        self.bill_repo.conn.commit()

    def set_bank_balance(self, *, amount: Amount) -> None:  # pragma: no cover
        from datetime import date as _date

        cursor = self.bill_repo.conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ("bank_balance", str(amount.pence)),
        )
        cursor.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ("bank_balance_day", str(_date.today().day)),
        )
        self.bill_repo.conn.commit()
