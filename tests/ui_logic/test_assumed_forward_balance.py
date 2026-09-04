"""Qt-free guard: a reserve must not drain either forward projection.

Both `_render_forward_projection` and its assumed twin walk two months,
carrying the closing balance of the first into the second. What each month
must FIND now includes its reserve, because that drives the month's sentence
and its colour. What actually LEAVES the account does not, because money set
aside stays in the account until the commitment is paid.

Those two figures sit two lines apart in that loop and are easy to confuse.
Carrying the wrong one forward would walk the projection down by money that
never moved and report an overdraft that cannot happen, silently: every
figure still looks plausible. This test exists because the mistake was
planted and the rest of the suite passed.
"""

from types import SimpleNamespace

import pytest

from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.entities.income_source import IncomeSource
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.ui.views._solvency_panel_assumed import SolvencyPanelAssumedMixin
from clear_budget.ui.views._solvency_panel_display import SolvencyPanelDisplayMixin
from clear_budget.ui.views._solvency_panel_forward import SolvencyPanelForwardMixin
from clear_budget.ui.views._solvency_panel_narratives import (
    SolvencyPanelNarrativeMixin,
)

_BANK = 1
_MONTH = YearMonth(year=2026, month=9)
_OPENING_PENCE = 500000
_BILLS_PENCE = 150000
_INCOME_PENCE = 160000
# Large enough to flip the month's traffic light on its own, which is how the
# guard below proves the reserve is not being ignored outright. A reserve the
# month can comfortably absorb would leave the colour unchanged and the guard
# would then pass for the wrong reason.
_RESERVE_PENCE = 200000
# What the month actually does to the balance: income in, bills out. The
# reserve is deliberately absent, which is the whole point of the test.
_NET_EFFECT_PENCE = _INCOME_PENCE - _BILLS_PENCE


def _summary() -> SimpleNamespace:
    bill = Bill(
        id=1,
        name="rent",
        amount=Amount(pence=_BILLS_PENCE),
        payment_method_id=_BANK,
        category="x",
        bill_type="fixed",
        day_of_month=1,
        start_ym=YearMonth(2026, 1),
        end_ym=None,
    )
    income = IncomeSource(
        id=1,
        name="salary",
        amount=Amount(pence=_INCOME_PENCE),
        is_reliable=True,
        day_of_month=20,
    )
    return SimpleNamespace(
        bills=(bill,),
        income_sources=(income,),
        total_income=Amount(pence=_INCOME_PENCE),
    )


class _Label:
    def __init__(self) -> None:
        self.text = None

    def setText(self, text) -> None:  # noqa: N802 (Qt's own spelling)
        self.text = text

    def setStyleSheet(self, style) -> None:  # noqa: N802 (Qt's own spelling)
        pass

    def setMargin(self, margin) -> None:  # noqa: N802 (Qt's own spelling)
        pass


@pytest.fixture(autouse=True)
def _no_nav_label_styling(monkeypatch):
    """Silence the nav label's own styling, which wants real Qt metrics.

    It measures the polished font to size the label, so it cannot run without
    a QApplication and it is not what these tests are about: they are about
    which balance each month is walked from.
    """
    monkeypatch.setattr(
        "clear_budget.ui.views._solvency_panel_forward.apply_nav_label_color",
        lambda label, colour: None,
    )


class _Panel(
    SolvencyPanelNarrativeMixin,
    SolvencyPanelAssumedMixin,
    SolvencyPanelDisplayMixin,
    SolvencyPanelForwardMixin,
):
    """Records the openings each month was walked from."""

    def __init__(self, reserve_pence: int) -> None:
        self.openings = []
        self.m1_assumed_projection_label = _Label()
        self.m2_assumed_projection_label = _Label()
        self.m1_projection_label = _Label()
        self.m2_projection_label = _Label()
        self.month_label = _Label()
        self.month_label_color_changed = SimpleNamespace(emit=lambda colour: None)
        summary = _summary()
        service = SimpleNamespace(
            get_month_summary=(lambda *, year_month: summary),
            get_overdraft_limit=(lambda: Amount(pence=0)),
            get_projected_starting_balance_pence=(lambda *, year_month: _OPENING_PENCE),
            get_assumed_month_summary=(lambda *, year_month: summary),
            get_month_reserve_cost_pence=(lambda *, year_month: reserve_pence),
        )
        self.view_model = SimpleNamespace(budget_service=service)

    def _walk_month(self, opening_pence, summary, floor_pence=0):
        self.openings.append(opening_pence)
        return SolvencyPanelNarrativeMixin._walk_month(
            opening_pence, summary, floor_pence
        )

    @staticmethod
    def _set_projection_label(label, *, heading, body, colour, clarion) -> None:
        label.setText(f"{heading}\n{body}")
        label.colour = colour


def _run(panel, *, assumed: bool):
    report = SimpleNamespace(balance_pence=_OPENING_PENCE, year_month=_MONTH)
    if assumed:
        panel._render_assumed_forward(report, 0)
    else:
        panel.view_model.current_summary = _summary()
        panel._render_forward_projection(report, 0, False)


def _openings(reserve_pence: int, *, assumed: bool = True) -> list[int]:
    """The opening balance each rendered month was walked from."""
    panel = _Panel(reserve_pence)
    _run(panel, assumed=assumed)
    # One walk per month for the summary, one more for its state; the openings
    # repeat, so the distinct sequence in order is what is being asserted.
    seen = []
    for opening in panel.openings:
        if not seen or seen[-1] != opening:
            seen.append(opening)
    return seen


def _assumed_colour(reserve_pence: int) -> str:
    """The colour the first assumed forward month was painted."""
    panel = _Panel(reserve_pence)
    _run(panel, assumed=True)
    return panel.m1_assumed_projection_label.colour


def _entered_colour(reserve_pence: int) -> str:
    """The colour the first entered forward month was painted."""
    panel = _Panel(reserve_pence)
    _run(panel, assumed=False)
    return panel.m1_projection_label.colour


class TestTheChainCarriesTheBalance:
    def test_the_second_month_opens_where_the_first_closed(self):
        """Bills out and income in; nothing else."""
        openings = _openings(0)
        assert openings[1] == openings[0] + _NET_EFFECT_PENCE

    def test_a_reserve_does_not_move_the_chain(self):
        """The planted regression: subtracting what is merely held back."""
        assert _openings(_RESERVE_PENCE) == _openings(0)

    def test_the_reserve_still_reaches_the_month_s_own_colour(self):
        """Proves the test above is not passing because the reserve is ignored.

        The proof used to read the month's closing sentence, which named the
        hold-flat gap. That sentence now names the sum that would keep the
        month afloat instead, a figure the reserve is correctly absent from,
        so the traffic light is where the reserve is read back.
        """
        assert _assumed_colour(_RESERVE_PENCE) != _assumed_colour(0)


class TestTheEnteredChainCarriesTheBalanceToo:
    """The same two figures, the same two lines apart, in the entered months."""

    def test_the_second_month_opens_where_the_first_closed(self):
        openings = _openings(0, assumed=False)
        assert openings[1] == openings[0] + _NET_EFFECT_PENCE

    def test_a_reserve_does_not_move_the_chain(self):
        assert _openings(_RESERVE_PENCE, assumed=False) == _openings(0, assumed=False)

    def test_the_reserve_still_reaches_the_month_s_own_colour(self):
        assert _entered_colour(_RESERVE_PENCE) != _entered_colour(0)
