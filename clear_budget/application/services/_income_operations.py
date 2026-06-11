"""Income CRUD/override/skip/received pass-throughs for BudgetService - LOC limit split."""

from clear_budget.domain.entities.income_source import IncomeSource
from clear_budget.domain.value_objects.year_month import YearMonth


class IncomeOperationsMixin:
    """Income-related pass-through operations for BudgetService."""

    __slots__ = ()

    def add_income(self, *, income: IncomeSource) -> IncomeSource:  # pragma: no cover
        return self.income_repo.add(income=income)

    def update_income(
        self, *, income: IncomeSource
    ) -> IncomeSource:  # pragma: no cover
        return self.income_repo.update(income=income)

    def delete_income(self, *, income_id: int) -> None:  # pragma: no cover
        self.income_repo.hard_delete(income_id=income_id)

    def add_income_month_extra(
        self, *, income: IncomeSource, year_month: YearMonth
    ) -> IncomeSource:  # pragma: no cover
        return self.income_repo.add_month_extra(year_month=year_month, income=income)

    def update_income_month_extra(
        self, *, income: IncomeSource, year_month: YearMonth
    ) -> IncomeSource:  # pragma: no cover
        return self.income_repo.update_month_extra(year_month=year_month, income=income)

    def delete_income_month_extra(self, *, extra_id: int) -> None:  # pragma: no cover
        self.income_repo.delete_month_extra(extra_id=extra_id)

    def update_income_for_month(
        self, *, income: IncomeSource, year_month: YearMonth
    ) -> None:  # pragma: no cover
        from clear_budget.application.services._income_month_overrides import (
            upsert_income_month_override,
        )

        upsert_income_month_override(self.income_repo.conn, income, year_month)

    def delete_income_month_override(
        self, *, income_id: int, year_month: YearMonth
    ) -> None:  # pragma: no cover
        from clear_budget.application.services._income_month_overrides import (
            delete_income_month_override as _delete_override,
        )

        _delete_override(self.income_repo.conn, income_id, year_month)

    def skip_income_for_month(
        self, *, income_id: int, year_month: YearMonth
    ) -> None:  # pragma: no cover
        self.income_repo.skip_for_month(income_id=income_id, year_month=year_month)

    def unskip_income_for_month(
        self, *, income_id: int, year_month: YearMonth
    ) -> None:  # pragma: no cover
        self.income_repo.unskip_for_month(income_id=income_id, year_month=year_month)

    def mark_income_received_for_month(
        self, *, income_id: int, year_month: YearMonth
    ) -> None:  # pragma: no cover
        self.income_repo.mark_received_for_month(
            income_id=income_id, year_month=year_month
        )

    def unmark_income_received_for_month(
        self, *, income_id: int, year_month: YearMonth
    ) -> None:  # pragma: no cover
        self.income_repo.unmark_received_for_month(
            income_id=income_id, year_month=year_month
        )

    def mark_income_extra_received(self, *, extra_id: int) -> None:  # pragma: no cover
        self.income_repo.mark_extra_received(extra_id=extra_id)

    def unmark_income_extra_received(
        self, *, extra_id: int
    ) -> None:  # pragma: no cover
        self.income_repo.unmark_extra_received(extra_id=extra_id)
