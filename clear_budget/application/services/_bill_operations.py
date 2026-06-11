"""Bill CRUD/override/skip/paid pass-throughs for BudgetService - LOC limit split."""

from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.value_objects.year_month import YearMonth


class BillOperationsMixin:
    """Bill-related pass-through operations for BudgetService."""

    __slots__ = ()

    def add_bill(self, *, bill: Bill) -> Bill:  # pragma: no cover
        return self.bill_repo.add(bill=bill)

    def update_bill(self, *, bill: Bill) -> Bill:  # pragma: no cover
        return self.bill_repo.update(bill=bill)

    def update_bill_for_month(
        self, *, bill: Bill, year_month: YearMonth
    ) -> None:  # pragma: no cover
        from clear_budget.application.services._bill_month_overrides import (
            upsert_bill_month_override,
        )

        upsert_bill_month_override(self.bill_repo.conn, bill, year_month)

    def delete_bill(self, *, bill_id: int) -> None:  # pragma: no cover
        self.bill_repo.hard_delete(bill_id=bill_id)

    def set_bill_active(
        self, *, bill_id: int, active: bool
    ) -> None:  # pragma: no cover
        self.bill_repo.set_active(bill_id=bill_id, active=active)

    def delete_bill_month_override(
        self, *, bill_id: int, year_month: YearMonth
    ) -> None:  # pragma: no cover
        from clear_budget.application.services._bill_month_overrides import (
            delete_bill_month_override as _delete_override,
        )

        _delete_override(self.bill_repo.conn, bill_id, year_month)

    def skip_bill_for_month(
        self, *, bill_id: int, year_month: YearMonth
    ) -> None:  # pragma: no cover
        self.bill_repo.skip_for_month(bill_id=bill_id, year_month=year_month)

    def unskip_bill_for_month(
        self, *, bill_id: int, year_month: YearMonth
    ) -> None:  # pragma: no cover
        self.bill_repo.unskip_for_month(bill_id=bill_id, year_month=year_month)

    def mark_bill_paid_for_month(
        self, *, bill_id: int, year_month: YearMonth
    ) -> None:  # pragma: no cover
        self.bill_repo.mark_paid_for_month(bill_id=bill_id, year_month=year_month)

    def unmark_bill_paid_for_month(
        self, *, bill_id: int, year_month: YearMonth
    ) -> None:  # pragma: no cover
        self.bill_repo.unmark_paid_for_month(bill_id=bill_id, year_month=year_month)
