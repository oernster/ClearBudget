"""Qt-free guard: showing the Reserves page must not erase its own buffer.

`refresh` puts the stored emergency buffer back on screen. Ticking the box in
code fires the same handler a user's tick fires. On the first build it fired
BEFORE the amount beside it had been filled in: the handler read an
empty field, made it zero and wrote that over the stored setting. Opening the
page destroyed the figure it had come to display, silently; every reading that
rests on the buffer moved with it.

The fix is one blockSignals pair, which is exactly the kind of line a later
edit removes without noticing. Hence this test.
"""

from clear_budget.domain.value_objects.amount import Amount
from clear_budget.ui.views.reserves_view import ReservesView

_STORED_PENCE = 15000


class _Check:
    """A checkbox that only runs its handler when signals are live."""

    def __init__(self) -> None:
        self._checked = False
        self._blocked = False
        self._on_toggled = None
        self.writes = 0

    def blockSignals(self, blocked) -> None:  # noqa: N802 (Qt's own spelling)
        self._blocked = blocked

    def setChecked(self, checked) -> None:  # noqa: N802 (Qt's own spelling)
        self._checked = checked
        if not self._blocked and self._on_toggled is not None:
            self._on_toggled()

    def isChecked(self) -> bool:  # noqa: N802 (Qt's own spelling)
        return self._checked


class _Edit:
    def __init__(self) -> None:
        self._text = ""

    def setText(self, text) -> None:  # noqa: N802 (Qt's own spelling)
        self._text = text

    def text(self) -> str:
        return self._text

    def setEnabled(self, enabled) -> None:  # noqa: N802 (Qt's own spelling)
        pass


class _Service:
    """Records what the page writes back, with the store as the truth."""

    def __init__(self) -> None:
        self.enabled = True
        self.amount = Amount(pence=_STORED_PENCE)
        self.writes = 0

    def get_recommendation_buffer(self):
        return self.enabled, self.amount

    def set_recommendation_buffer(self, *, enabled, amount):
        self.writes += 1
        self.enabled = enabled
        self.amount = amount

    def get_reserve_rows(self):
        return []


class _Page(ReservesView):
    """`refresh`'s buffer half alone, with no Qt underneath it."""

    def __init__(self, service) -> None:
        self.budget_service = service
        self.buffer_check = _Check()
        self.buffer_check._on_toggled = self._save_buffer
        self.buffer_edit = _Edit()
        self._rows = []

    def _fill_table(self) -> None:
        pass

    def _fill_verdict(self) -> None:
        pass

    def _fill_where(self) -> None:
        pass


def _page():
    service = _Service()
    return _Page(service), service


class TestShowingThePage:
    def test_the_stored_buffer_is_still_there_afterwards(self):
        page, service = _page()
        page.refresh()
        assert service.amount == Amount(pence=_STORED_PENCE)

    def test_it_writes_nothing_back_at_all(self):
        """Displaying a setting is a read; a write here can only lose data."""
        page, service = _page()
        page.refresh()
        assert service.writes == 0

    def test_it_survives_being_shown_repeatedly(self):
        page, service = _page()
        for _ in range(3):
            page.refresh()
        assert service.amount == Amount(pence=_STORED_PENCE)

    def test_the_figure_reaches_the_field(self):
        """Proves the test above is not passing because nothing ran."""
        page, _service = _page()
        page.refresh()
        assert page.buffer_edit.text() == "150.00"


class TestAUserStillChangesIt:
    def test_a_real_tick_writes_the_typed_figure(self):
        """The guard must silence the refresh, never the user."""
        page, service = _page()
        page.refresh()
        page.buffer_edit.setText("20.00")
        page.buffer_check.setChecked(True)
        assert service.writes == 1
        assert service.amount == Amount(pence=2000)
