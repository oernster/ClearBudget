"""Credit-card pass-throughs and folds for BudgetService - LOC limit split."""

from datetime import date

from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth


class CardOperationsMixin:
    """Credit-card-related operations for BudgetService."""

    __slots__ = ()

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
            today=_date.today(),  # noqa: DTZ011 (app runs on naive local dates)
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
            today=today or _date.today(),  # noqa: DTZ011 (naive local dates)
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
            today=today or _date.today(),  # noqa: DTZ011 (naive local dates)
        )

    def apply_elapsed_limit_changes(self, *, today: date | None = None) -> None:
        """Fold each card's elapsed scheduled limit changes into its limit."""
        from datetime import date as _date

        from clear_budget.application.services._card_limit_updates import (
            apply_elapsed_limit_changes as _impl,
        )

        _impl(
            self.payment_method_repo,
            today=today or _date.today(),  # noqa: DTZ011 (naive local dates)
        )

    def set_credit_limit_changes(self, *, card_id: int, changes) -> None:
        """Replace a card's scheduled credit limit changes."""
        self.payment_method_repo.set_credit_limit_changes(
            card_id=card_id, changes=tuple(changes)
        )
