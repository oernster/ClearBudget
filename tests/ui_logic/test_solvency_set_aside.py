"""Qt-free tests for the Solvency breakdown's "Set aside this month" row.

The row states a WHOLE-MONTH figure, so it sits with "Committed this month"
and the gap line rather than with anything about today. It is hidden outright
while nothing is set aside, because the Reserves page is opt-in and a budget
that never opens it should keep the breakdown it has always had.

Qt-free like the other tests in this package: the method touches one label and
one service, so both are stood in for and the rule is read back directly.
"""

from types import SimpleNamespace

from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.ui.utils import reserves_text
from clear_budget.ui.views._solvency_panel_display import SolvencyPanelDisplayMixin

_MONTH = YearMonth(year=2026, month=8)


class _Label:
    """Records what the panel did to the row, in place of a QLabel."""

    def __init__(self) -> None:
        self.text = None
        self.visible = None

    def setText(self, text) -> None:  # noqa: N802 (Qt's own spelling)
        self.text = text

    def show(self) -> None:
        self.visible = True

    def hide(self) -> None:
        self.visible = False


class _Service:
    def __init__(self, *, commitments, cost_pence: int = 0) -> None:
        self._commitments = commitments
        self._cost_pence = cost_pence

    def list_commitments(self):
        return self._commitments

    def get_month_reserve_cost_pence(self, *, year_month):
        assert year_month is _MONTH
        return self._cost_pence


class _Panel(SolvencyPanelDisplayMixin):
    def __init__(self, service) -> None:
        self.set_aside_label = _Label()
        self.view_model = SimpleNamespace(budget_service=service)


def _row(*, commitments, cost_pence=0) -> _Label:
    panel = _Panel(_Service(commitments=commitments, cost_pence=cost_pence))
    panel._update_set_aside(_MONTH)
    return panel.set_aside_label


class TestNothingSetAside:
    def test_the_row_is_hidden(self):
        assert _row(commitments=[]).visible is False

    def test_it_says_nothing_at_all(self):
        """Not a zero: a budget not using the page gets no row to read."""
        assert _row(commitments=[]).text is None


class TestSomethingSetAside:
    def test_the_row_is_shown(self):
        assert _row(commitments=["one"], cost_pence=12345).visible is True

    def test_it_states_the_month_s_own_figure(self):
        row = _row(commitments=["one"], cost_pence=12345)
        assert row.text == reserves_text.solvency_set_aside_line(amount="£123.45")

    def test_a_commitment_costing_the_month_nothing_still_shows_the_row(self):
        """Ended or fully held: the row reports zero rather than vanishing.

        Hiding it here would be a different claim, that nothing is set aside
        at all, which is not what a fully funded commitment means.
        """
        row = _row(commitments=["one"], cost_pence=0)
        assert row.visible is True
        assert "£0.00" in row.text
