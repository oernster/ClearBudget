"""Bill CRUD/override/skip/paid pass-throughs for BudgetService - LOC limit split."""

from dataclasses import replace

from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.value_objects.year_month import YearMonth


class BillOperationsMixin:
    """Bill-related pass-through operations for BudgetService."""

    __slots__ = ()

    def add_bill(self, *, bill: Bill) -> Bill:  # pragma: no cover
        return self.bill_repo.add(bill=bill)

    def update_bill(self, *, bill: Bill) -> Bill:  # pragma: no cover
        return self.bill_repo.update(bill=bill)

    def set_bill_amount_changes(
        self, *, bill_id: int, changes
    ) -> None:  # pragma: no cover
        """Replace a bill's scheduled amount changes."""
        self.bill_repo.set_amount_changes(bill_id=bill_id, changes=tuple(changes))

    def update_bill_for_month(
        self, *, bill: Bill, year_month: YearMonth
    ) -> None:  # pragma: no cover
        from clear_budget.application.services._bill_month_overrides import (
            upsert_bill_month_override,
        )

        upsert_bill_month_override(self.bill_repo.conn, bill, year_month)

    def delete_bill(self, *, bill_id: int) -> None:
        """Delete a bill entirely, handing back any applied balance amounts."""
        from clear_budget.application.services._balance_application import (
            reverse_applied_for_item,
        )

        reverse_applied_for_item(
            getattr(self.bill_repo, "conn", None), item_type="bill", item_id=bill_id
        )
        self.bill_repo.hard_delete(bill_id=bill_id)

    def end_bill(self, *, bill_id: int, last_active_month: YearMonth) -> None:
        """End a bill so it stops after last_active_month, preserving history.

        Sets the bill's end month, so every earlier month (and any archived
        snapshot) still shows it. Used by the history-safe delete: removing a
        bill while viewing a month ends it the month before, leaving the past
        untouched. Amounts applied to the balance in the months being removed
        are handed back; earlier months keep theirs.
        """
        from clear_budget.application.services._balance_application import (
            reverse_applied_for_item,
        )

        bill = self.bill_repo.get_by_id(bill_id=bill_id)
        if bill is not None:
            reverse_applied_for_item(
                getattr(self.bill_repo, "conn", None),
                item_type="bill",
                item_id=bill_id,
                after=last_active_month,
            )
            self.bill_repo.update(bill=replace(bill, end_ym=last_active_month))

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
