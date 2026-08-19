"""The two income checkboxes: what each says; what a conversion does.

One "This month only" box used to carry two unrelated jobs, so it had to mean
different things in different contexts and was greyed out in the one context it
could not express at all. These tests pin the split: `one_off_check` says what
the entry IS, `scope_check` says how far THIS EDIT reaches. The wording
under them states the consequence before OK is pressed.

Qt-free: the wording and the routing are decided by plain functions over plain
data, called on the class rather than on an instance (see this package's
docstring), so no QApplication is needed.
"""

from types import SimpleNamespace

from clear_budget.ui import label_roles
from clear_budget.ui.views._month_view_income_convert import (
    MonthViewIncomeConvertMixin,
)
from clear_budget.ui.widgets.income_dialog import IncomeDialog

_JUNE = SimpleNamespace(year=2026, month=6)


class _Wording:
    """The dialog's wording decisions, lifted off the QDialog that hosts them.

    Borrowing the real attributes keeps this a test of the shipped functions
    rather than a copy of them, while leaving Qt out of the picture.
    """

    _month_label = IncomeDialog._month_label
    _is_conversion = IncomeDialog._is_conversion
    _status_role = IncomeDialog._status_role
    _status_text = IncomeDialog._status_text

    def __init__(self, income) -> None:
        self.income = income
        self.current_month = _JUNE


def _dialog(income):
    return _Wording(income)


def _entry(*, one_off: bool, name: str = "Salary", entry_id: int = 7):
    return SimpleNamespace(id=entry_id, name=name, is_month_only=one_off)


def _text(income, *, wants_one_off: bool, scope_only: bool = False) -> str:
    return _dialog(income)._status_text(wants_one_off, scope_only)


def _role(income, *, wants_one_off: bool) -> str:
    return _dialog(income)._status_role(wants_one_off)


class TestMonthLabel:
    def test_the_dialog_names_its_month_rather_than_numbering_it(self):
        assert _Wording(None)._month_label == "June 2026"


class TestAddingIncome:
    def test_a_ticked_one_off_box_names_the_month_it_is_confined_to(self):
        assert _text(None, wants_one_off=True) == (
            "Added as a one-off for June 2026 only."
        )

    def test_an_unticked_box_says_the_income_recurs(self):
        assert "every month" in _text(None, wants_one_off=False)

    def test_adding_is_never_a_conversion(self):
        assert _role(None, wants_one_off=True) == label_roles.NOTE
        assert _role(None, wants_one_off=False) == label_roles.NOTE


class TestEditingAOneOff:
    def test_leaving_it_a_one_off_states_the_month_without_warning(self):
        entry = _entry(one_off=True, name="Car sale")
        assert (
            _text(entry, wants_one_off=True) == "A one-off entry, in June 2026 alone."
        )
        assert _role(entry, wants_one_off=True) == label_roles.NOTE

    def test_unticking_promises_a_regular_income_and_warns(self):
        entry = _entry(one_off=True, name="Car sale")
        text = _text(entry, wants_one_off=False)
        assert "regular income" in text
        assert "every month" in text
        assert _role(entry, wants_one_off=False) == label_roles.STRONG_WARN


class TestEditingARegularIncome:
    def test_ticking_one_off_warns_that_other_months_lose_it(self):
        entry = _entry(one_off=False)
        text = _text(entry, wants_one_off=True)
        assert "'Salary'" in text
        assert "every other month, past and future" in text
        assert _role(entry, wants_one_off=True) == label_roles.STRONG_WARN

    def test_a_narrow_edit_says_other_months_are_untouched(self):
        entry = _entry(one_off=False)
        text = _text(entry, wants_one_off=False, scope_only=True)
        assert "June 2026 only" in text
        assert "Other months are unchanged" in text

    def test_a_wide_edit_says_it_reaches_every_month(self):
        entry = _entry(one_off=False)
        text = _text(entry, wants_one_off=False, scope_only=False)
        assert text == "Changes saved for every month."

    def test_the_scope_wording_is_ignored_once_one_off_is_ticked(self):
        """Scope has no meaning on a one-off, so it must not leak into the text."""
        entry = _entry(one_off=False)
        assert _text(entry, wants_one_off=True, scope_only=True) == _text(
            entry, wants_one_off=True, scope_only=False
        )


class _FakeViewModel:
    def __init__(self) -> None:
        self.current_month = _JUNE
        self.calls: list[tuple[str, dict]] = []

    def convert_income_source_to_extra(self, **kwargs):
        self.calls.append(("to_extra", kwargs))
        return _entry(one_off=True, entry_id=99)

    def convert_income_extra_to_source(self, **kwargs):
        self.calls.append(("to_source", kwargs))
        return _entry(one_off=False, entry_id=99)


class _Converter(MonthViewIncomeConvertMixin):
    """The mixin with its confirmation replaced by a recorded answer."""

    def __init__(self, *, answer: bool) -> None:
        self.view_model = _FakeViewModel()
        self._answer = answer
        self.asked: list[dict] = []

    def _confirm_income_conversion(self, *, name: str, to_one_off: bool) -> bool:
        self.asked.append({"name": name, "to_one_off": to_one_off})
        return self._answer


class TestConversionRouting:
    def test_declining_converts_nothing_and_reports_it(self):
        converter = _Converter(answer=False)
        result = converter._convert_income(
            before=_entry(one_off=False), after=_entry(one_off=True)
        )
        assert result is None
        assert converter.view_model.calls == []

    def test_a_regular_income_becomes_a_one_off_by_its_source_id(self):
        converter = _Converter(answer=True)
        before = _entry(one_off=False, entry_id=3)
        after = _entry(one_off=True, entry_id=3)
        persisted = converter._convert_income(before=before, after=after)
        kind, kwargs = converter.view_model.calls[0]
        assert kind == "to_extra"
        assert kwargs == {"income_id": 3, "income": after}
        assert persisted.is_month_only is True

    def test_a_one_off_becomes_a_regular_income_by_its_extra_id(self):
        converter = _Converter(answer=True)
        before = _entry(one_off=True, entry_id=5)
        after = _entry(one_off=False, entry_id=5)
        persisted = converter._convert_income(before=before, after=after)
        kind, kwargs = converter.view_model.calls[0]
        assert kind == "to_source"
        assert kwargs == {"extra_id": 5, "income": after}
        assert persisted.is_month_only is False

    def test_the_confirmation_is_asked_in_the_direction_being_taken(self):
        converter = _Converter(answer=True)
        converter._convert_income(
            before=_entry(one_off=False, name="Wages"),
            after=_entry(one_off=True, name="Wages"),
        )
        assert converter.asked == [{"name": "Wages", "to_one_off": True}]

    def test_the_month_is_named_rather_than_numbered(self):
        converter = _Converter(answer=True)
        assert converter._convert_month_label() == "June 2026"
