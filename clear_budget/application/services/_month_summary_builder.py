"""Month summary construction for BudgetService - LOC limit split.

Owns one concern: turning a month's bills and income into the MonthSummary
every other calculation reads. The reliable/assumed split lives here because
this is the single place the counted income set is decided, so no downstream
projection can disagree about what it was built from.
"""

from clear_budget.application.dto.month_summary import MonthSummary
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth

# Bills paid from the bank account rather than from a card.
_BANK_PAYMENT_METHOD_ID = 1


class MonthSummaryBuilderMixin:
    """Builds the MonthSummary a month's figures are read from."""

    __slots__ = ()

    def get_month_summary(
        self, *, year_month: YearMonth, include_assumed: bool = False
    ) -> MonthSummary:
        """One month's figures, built from reliable income by default.

        Income marked NOT reliable is money the user expects rather than money
        they have. It is excluded from every figure unless `include_assumed`
        asks for it, so nothing in the app is quietly propped up by income
        that may not arrive. It is always carried separately on the summary as
        the gap specification.
        """
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
            bill.amount.pence
            for bill in active_bills
            if bill.payment_method_id == _BANK_PAYMENT_METHOD_ID
        )
        assumed = [inc for inc in income if not inc.is_reliable]
        counted = income if include_assumed else [i for i in income if i.is_reliable]

        total_income_pence = sum(inc.amount.pence for inc in counted)
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
            income_sources=tuple(counted),
            all_income_sources=tuple(all_income),
            assumed_income_sources=tuple(assumed),
        )
