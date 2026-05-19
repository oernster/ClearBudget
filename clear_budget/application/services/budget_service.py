"""BudgetService  -  main application orchestrator."""

from dataclasses import dataclass

from clear_budget.application.dto.month_summary import MonthSummary
from clear_budget.application.dto.solvency_report import SolvencyReport
from clear_budget.application.services.month_generator import MonthGenerator
from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.entities.month_bill import MonthBill
from clear_budget.domain.entities.month_income import MonthIncome
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


def _bills_to_month_bills(bills, month_id: int) -> list[MonthBill]:  # pragma: no cover
    return [
        MonthBill(
            id=bill.id,
            month_id=month_id,
            bill_template_id=bill.id,
            name=bill.name,
            amount=bill.amount,
            payment_method_id=bill.payment_method_id,
            category=bill.category,
            day_of_month=bill.day_of_month,
            is_ad_hoc=False,
        )
        for bill in bills
    ]


def _income_to_month_income(income_sources, month_id: int) -> list[MonthIncome]:  # pragma: no cover
    return [
        MonthIncome(
            id=inc.id,
            month_id=month_id,
            income_source_id=inc.id,
            name=inc.name,
            amount=inc.amount,
            is_reliable=inc.is_reliable,
            day_of_month=inc.day_of_month,
        )
        for inc in income_sources
    ]

@dataclass(frozen=True, slots=True)
class BudgetService:
    bill_repo: BillRepository
    income_repo: IncomeSourceRepository
    payment_method_repo: PaymentMethodRepository
    month_generator: MonthGenerator

    def get_month_summary(self, *, year_month: YearMonth) -> MonthSummary:
        active_bills = self.bill_repo.list_active_for_month(year_month=year_month)
        all_bills = self.bill_repo.list_active_for_month(year_month=year_month, include_inactive=True)
        income = self.income_repo.list_active()
        all_income = self.income_repo.list_all()

        total_bills_pence = sum(bill.amount.pence for bill in active_bills)
        bank_bills_pence = sum(bill.amount.pence for bill in active_bills if bill.payment_method_id == 1)
        total_income_pence = sum(inc.amount.pence for inc in income)
        balance_pence = total_income_pence - bank_bills_pence

        return MonthSummary(
            year_month=year_month,
            total_income=Amount(pence=total_income_pence),
            total_bills=Amount(pence=total_bills_pence),
            bank_bills=Amount(pence=bank_bills_pence),
            balance=Amount(pence=balance_pence)
            if balance_pence >= 0
            else Amount(pence=0),
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

        month_bills = month_summary.bills
        month_income = month_summary.income_sources

        if year_month == today_ym:
            month_bills = tuple(
                b for b in month_bills
                if b.day_of_month is None or b.day_of_month >= today.day
            )
            month_income = tuple(
                i for i in month_income
                if i.day_of_month is None or i.day_of_month >= today.day
            )

        next_month = year_month.next_month()
        next_next_month = next_month.next_month()

        next_summary = self.get_month_summary(year_month=next_month)
        next_bills = next_summary.bills
        next_income = next_summary.income_sources

        next_next_summary = self.get_month_summary(year_month=next_next_month)
        next_next_bills = next_next_summary.bills
        next_next_income = next_next_summary.income_sources

        solvency = SolvencyCalculatorService.calculate(
            month_bills=_bills_to_month_bills(month_bills, 0),
            month_income=_income_to_month_income(month_income, 0),
            next_two_months_bills=[
                _bills_to_month_bills(next_bills, 1),
                _bills_to_month_bills(next_next_bills, 2),
            ],
            next_two_months_income=[
                _income_to_month_income(next_income, 1),
                _income_to_month_income(next_next_income, 2),
            ],
        )

        projected_balance = self._projected_starting_balance_pence(year_month) + solvency.balance
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

    def calculate_solvency(
        self,
        *,
        year_month: YearMonth,
    ) -> SolvencyReport:
        from datetime import date as _date
        today = _date.today()
        today_ym = YearMonth(today.year, today.month)

        summary = self.get_month_summary(year_month=year_month)
        month_bills = summary.bills
        month_income = summary.income_sources

        if year_month == today_ym:
            month_bills = tuple(
                b for b in month_bills
                if b.day_of_month is None or b.day_of_month >= today.day
            )
            month_income = tuple(
                i for i in month_income
                if i.day_of_month is None or i.day_of_month >= today.day
            )

        next_month = year_month.next_month()
        next_next_month = next_month.next_month()

        next_summary = self.get_month_summary(year_month=next_month)
        next_bills = next_summary.bills
        next_income = next_summary.income_sources

        next_next_summary = self.get_month_summary(year_month=next_next_month)
        next_next_bills = next_next_summary.bills
        next_next_income = next_next_summary.income_sources

        solvency = SolvencyCalculatorService.calculate(
            month_bills=_bills_to_month_bills(month_bills, 0),
            month_income=_income_to_month_income(month_income, 0),
            next_two_months_bills=[
                _bills_to_month_bills(next_bills, 1),
                _bills_to_month_bills(next_next_bills, 2),
            ],
            next_two_months_income=[
                _income_to_month_income(next_income, 1),
                _income_to_month_income(next_next_income, 2),
            ],
        )

        projected_balance = self._projected_starting_balance_pence(year_month) + solvency.balance
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

    def update_bill_for_month(self, *, bill: Bill, year_month: YearMonth) -> None:  # pragma: no cover
        cursor = self.bill_repo.conn.cursor()
        cursor.execute(
            """
            INSERT INTO bill_month_overrides (bill_id, year, month, amount_pence, payment_method_id, day_of_month)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(bill_id, year, month) DO UPDATE SET
                amount_pence = excluded.amount_pence,
                payment_method_id = excluded.payment_method_id,
                day_of_month = excluded.day_of_month
            """,
            (bill.id, year_month.year, year_month.month, bill.amount.pence, bill.payment_method_id, bill.day_of_month),
        )
        self.bill_repo.conn.commit()

    def delete_bill(self, *, bill_id: int) -> None:  # pragma: no cover
        self.bill_repo.hard_delete(bill_id=bill_id)

    def set_bill_active(self, *, bill_id: int, active: bool) -> None:  # pragma: no cover
        self.bill_repo.set_active(bill_id=bill_id, active=active)

    def get_card_monthly_states(self, *, year_month: YearMonth) -> list:  # pragma: no cover
        from datetime import datetime
        from clear_budget.domain.services.card_monthly_calculator import calculate_card_monthly_state
        cards = self.payment_method_repo.get_all_credit_cards(include_inactive=False)
        summary = self.get_month_summary(year_month=year_month)
        all_bills = list(summary.all_bills)
        today_ym = YearMonth(datetime.now().year, datetime.now().month)
        results = []
        for card in cards:
            balance_pence = card.current_balance_used.pence
            cursor = today_ym
            while cursor < year_month:
                s = self.get_month_summary(year_month=cursor)
                interim = calculate_card_monthly_state(
                    card=card, opening_balance_pence=balance_pence, bills=list(s.all_bills)
                )
                balance_pence = interim.closing_balance.pence
                cursor = cursor.next_month()
            results.append(calculate_card_monthly_state(
                card=card, opening_balance_pence=balance_pence, bills=all_bills
            ))
        return results

    def add_income(self, *, income: "IncomeSource") -> "IncomeSource":  # pragma: no cover
        from clear_budget.domain.entities.income_source import IncomeSource
        return self.income_repo.add(income=income)

    def update_income(self, *, income: "IncomeSource") -> "IncomeSource":  # pragma: no cover
        from clear_budget.domain.entities.income_source import IncomeSource
        return self.income_repo.update(income=income)

    def delete_income(self, *, income_id: int) -> None:  # pragma: no cover
        self.income_repo.hard_delete(income_id=income_id)

    def get_credit_cards(self, include_inactive: bool = False) -> list:  # pragma: no cover
        return self.payment_method_repo.get_all_credit_cards(include_inactive=include_inactive)

    def get_recorded_months(self) -> list[YearMonth]:
        cursor = self.bill_repo.conn.cursor()
        cursor.execute("""
            SELECT DISTINCT m.year, m.month
            FROM months m
            WHERE m.id IN (
                SELECT DISTINCT month_id FROM month_bills
                UNION
                SELECT DISTINCT month_id FROM month_income
            )
            ORDER BY m.year ASC, m.month ASC
        """)
        rows = cursor.fetchall()
        return [YearMonth(row['year'], row['month']) for row in rows]

    def archive_month(self, *, year_month: YearMonth) -> None:
        cursor = self.bill_repo.conn.cursor()

        cursor.execute(
            "SELECT id FROM months WHERE year = ? AND month = ?",
            (year_month.year, year_month.month),
        )
        existing = cursor.fetchone()

        if existing:
            month_id = existing['id']
            cursor.execute("DELETE FROM month_bills WHERE month_id = ?", (month_id,))
            cursor.execute("DELETE FROM month_income WHERE month_id = ?", (month_id,))
        else:
            cursor.execute(
                "INSERT INTO months (year, month) VALUES (?, ?)",
                (year_month.year, year_month.month),
            )
            month_id = cursor.lastrowid

        month_bills = self.month_generator.generate_month_bills(
            year_month=year_month,
            month_id=month_id,
        )
        month_income = self.month_generator.generate_month_income(
            year_month=year_month,
            month_id=month_id,
        )

        for bill in month_bills:
            cursor.execute(
                """
                INSERT INTO month_bills
                (month_id, bill_template_id, name, amount_pence, payment_method_id, category, day_of_month, is_ad_hoc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    bill.month_id,
                    bill.bill_template_id,
                    bill.name,
                    bill.amount.pence,
                    bill.payment_method_id,
                    bill.category,
                    bill.day_of_month,
                    1 if bill.is_ad_hoc else 0,
                ),
            )

        for inc in month_income:
            cursor.execute(
                """
                INSERT INTO month_income
                (month_id, income_source_id, name, amount_pence, is_reliable, day_of_month)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    inc.month_id,
                    inc.income_source_id,
                    inc.name,
                    inc.amount.pence,
                    1 if inc.is_reliable else 0,
                    inc.day_of_month,
                ),
            )

        self.bill_repo.conn.commit()

    def auto_archive_previous_month_if_needed(self, *, current_month: YearMonth) -> None:
        prev_month = current_month.previous_month()
        recorded = self.get_recorded_months()
        if prev_month not in recorded:
            self.archive_month(year_month=prev_month)

    def _projected_starting_balance_pence(self, year_month: YearMonth) -> int:
        from datetime import datetime, date as _date
        today = _date.today()
        today_ym = YearMonth(today.year, today.month)
        pence = self.get_bank_balance().pence
        cursor = today_ym
        while cursor < year_month:
            s = self.get_month_summary(year_month=cursor)
            if cursor == today_ym:
                income = sum(
                    i.amount.pence for i in s.income_sources
                    if i.day_of_month is None or i.day_of_month >= today.day
                )
                bills = sum(
                    b.amount.pence for b in s.bills
                    if b.payment_method_id == 1 and (b.day_of_month is None or b.day_of_month >= today.day)
                )
            else:
                income = sum(i.amount.pence for i in s.income_sources)
                bills = sum(b.amount.pence for b in s.bills if b.payment_method_id == 1)
            pence += income - bills
            cursor = cursor.next_month()
        return pence

    def get_bank_balance(self) -> Amount:  # pragma: no cover
        if not hasattr(self.bill_repo, 'conn'): return Amount.zero()
        cursor = self.bill_repo.conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", ("bank_balance",))
        row = cursor.fetchone()
        return Amount(pence=int(row["value"]) if row else 0)

    def set_bank_balance(self, *, amount: Amount) -> None:  # pragma: no cover
        cursor = self.bill_repo.conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ("bank_balance", str(amount.pence)),
        )
        self.bill_repo.conn.commit()
