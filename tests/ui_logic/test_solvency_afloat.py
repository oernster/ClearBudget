"""Each forecast month names the money that would keep it afloat.

The Forward Projection blocks used to close on the hold-flat gap, a whole
month's bills and reserves against its income. That figure ignores the
opening balance by design, so it was never the sum that would rescue the
month: a month opening with a cushion was told it needed hundreds when it
needed nothing; a month going under was told a number unrelated to how
far under it went.

Qt-free: the builder is a method over plain data, so these run without a
QApplication (see this package's docstring).
"""

from types import SimpleNamespace

from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.entities.income_source import IncomeSource
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.ui.utils.format_helpers import fmt
from clear_budget.ui.views._solvency_panel_narratives import (
    SolvencyPanelNarrativeMixin,
)

_BANK = 1
_CARD = 2


def _bank_bill(pence: int, day: int) -> Bill:
    return Bill(
        id=day,
        name=f"bill-{day}",
        amount=Amount(pence=pence),
        payment_method_id=_BANK,
        category="x",
        bill_type="fixed",
        day_of_month=day,
        start_ym=YearMonth(2026, 1),
        end_ym=None,
    )


def _income(pence: int, day: int) -> IncomeSource:
    return IncomeSource(
        id=day,
        name=f"income-{day}",
        amount=Amount(pence=pence),
        is_reliable=True,
        day_of_month=day,
    )


def _summary(bills, incomes) -> SimpleNamespace:
    return SimpleNamespace(
        bills=tuple(bills),
        income_sources=tuple(incomes),
        total_income=Amount(pence=sum(i.amount.pence for i in incomes)),
    )


class TestTheClause:
    """The wording, in isolation from the block it closes."""

    def test_a_breaching_month_names_the_sum_that_rescues_it(self):
        mix = SolvencyPanelNarrativeMixin()
        assert mix._afloat_clause(-26813, 0) == f"needs {fmt(26813)} to stay afloat"

    def test_a_safe_month_names_its_margin_instead(self):
        mix = SolvencyPanelNarrativeMixin()
        clause = mix._afloat_clause(55416, 0)
        assert clause == f"stays afloat, {fmt(55416)} clear at its lowest"

    def test_a_month_inside_its_facility_is_reported_as_safe(self):
        """Borrowing the bank agreed to is not a shortfall."""
        mix = SolvencyPanelNarrativeMixin()
        assert "stays afloat" in mix._afloat_clause(-26813, 50000)

    def test_a_month_past_its_facility_names_the_facility(self):
        """Staying afloat and staying out of the red differ once borrowing
        is arranged, so the limit is named."""
        mix = SolvencyPanelNarrativeMixin()
        clause = mix._afloat_clause(-109042, 50000)
        assert clause == (
            f"needs {fmt(59042)} to stay within your {fmt(50000)} overdraft"
        )


class TestTheForecastBlock:
    """The clause as it lands at the foot of a Forward Projection month."""

    def test_the_block_states_the_rescue_figure_not_the_hold_flat_gap(self):
        """The case from the reported defect, in the shape it was reported.

        The month opens with a cushion, runs a heavy monthly loss and ends up
        a little under. The old line named the whole loss; the sum that keeps
        the account out of the red is a fraction of it.
        """
        mix = SolvencyPanelNarrativeMixin()
        summary = _summary([_bank_bill(204629, 28)], [_income(122400, 20)])
        monthly_shortfall = 204629 - 122400

        text, _, _ = mix._build_month_cashflow_summary(
            55416, summary, monthly_shortfall, overdraft_limit_pence=0
        )

        assert f"Needs {fmt(26813)} to stay afloat" in text
        assert "hold flat" not in text
        assert fmt(monthly_shortfall) not in text

    def test_the_figure_agrees_with_the_low_point_printed_above_it(self):
        """Both come from one walk, so a reader can check one against the other."""
        mix = SolvencyPanelNarrativeMixin()
        summary = _summary([_bank_bill(204629, 28)], [_income(122400, 20)])

        text, _, _ = mix._build_month_cashflow_summary(
            55416, summary, 82229, overdraft_limit_pence=0
        )

        assert f"Low point: -{fmt(26813)} on day 28" in text
        assert f"Needs {fmt(26813)} to stay afloat" in text

    def test_a_month_that_never_goes_under_reports_its_margin(self):
        mix = SolvencyPanelNarrativeMixin()
        summary = _summary([_bank_bill(5000, 28)], [_income(5000, 20)])

        text, _, _ = mix._build_month_cashflow_summary(
            200000, summary, 0, overdraft_limit_pence=0
        )

        # The low is the opening itself: the month only ever rises from there.
        assert f"Stays afloat, {fmt(200000)} clear at its lowest" in text

    def test_a_month_rescued_by_payday_is_still_measured_at_its_low(self):
        """It closes positive and had payments refused on the way; the close
        cannot be the measure."""
        mix = SolvencyPanelNarrativeMixin()
        summary = _summary([_bank_bill(170000, 1)], [_income(170000, 20)])

        text, _, _ = mix._build_month_cashflow_summary(
            50000, summary, 0, overdraft_limit_pence=0
        )

        assert "Closes: £500.00" in text
        assert f"Needs {fmt(120000)} to stay afloat" in text

    def test_card_bills_never_move_the_figure(self):
        """Card spending does not leave the bank account, so it cannot sink it."""
        mix = SolvencyPanelNarrativeMixin()
        card = Bill(
            id=99,
            name="card",
            amount=Amount(pence=300000),
            payment_method_id=_CARD,
            category="x",
            bill_type="fixed",
            day_of_month=15,
            start_ym=YearMonth(2026, 1),
            end_ym=None,
        )
        summary = _summary([_bank_bill(204629, 28), card], [_income(122400, 20)])

        text, _, _ = mix._build_month_cashflow_summary(
            55416, summary, 82229, overdraft_limit_pence=0
        )

        assert f"Needs {fmt(26813)} to stay afloat" in text


class TestEachMonthIsMeasuredAsProjected:
    """A forecast month is measured on the chain as it stands, never on a
    hypothetical where the month before it was rescued.

    Otherwise the figure would contradict the "Opens" line at the top of its
    own block, which is the one number in the block a reader trusts absolutely.
    """

    def test_the_second_forecast_month_carries_the_first_ones_damage(self):
        mix = SolvencyPanelNarrativeMixin()
        summary = _summary([_bank_bill(204629, 28)], [_income(122400, 20)])

        first, _, _ = mix._build_month_cashflow_summary(
            55416, summary, 82229, overdraft_limit_pence=0
        )
        second, _, _ = mix._build_month_cashflow_summary(
            -26813, summary, 82229, overdraft_limit_pence=0
        )

        assert f"Opens: -{fmt(26813)}" in second
        assert f"Needs {fmt(26813)} to stay afloat" in first
        assert f"Needs {fmt(109042)} to stay afloat" in second
