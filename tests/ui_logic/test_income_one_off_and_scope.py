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
    _is_promotion = IncomeDialog._is_promotion
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
    def test_a_narrow_edit_says_other_months_are_untouched(self):
        entry = _entry(one_off=False)
        text = _text(entry, wants_one_off=False, scope_only=True)
        assert "June 2026 only" in text
        assert "Other months are unchanged" in text

    def test_a_wide_edit_says_it_reaches_every_month(self):
        entry = _entry(one_off=False)
        text = _text(entry, wants_one_off=False, scope_only=False)
        assert text == "Changes saved for every month."

    def test_demoting_is_not_something_the_dialog_can_ask_for(self):
        """The one control that could erase history does not exist here.

        A regular income never offers the one-off box, so this combination is
        unreachable through the UI. It is pinned anyway: were the box ever
        reinstated, this says the dialog must not treat it as a conversion.
        """
        entry = _entry(one_off=False)
        assert _role(entry, wants_one_off=True) == label_roles.NOTE


class _FakeViewModel:
    def __init__(self) -> None:
        self.current_month = _JUNE
        self.calls: list[tuple[str, dict]] = []

    def convert_income_extra_to_source(self, **kwargs):
        self.calls.append(("to_source", kwargs))
        return _entry(one_off=False, entry_id=99)


class _Converter(MonthViewIncomeConvertMixin):
    """The mixin with its confirmation replaced by a recorded answer."""

    def __init__(self, *, answer: bool) -> None:
        self.view_model = _FakeViewModel()
        self._answer = answer
        self.asked: list[dict] = []

    def _confirm_income_promotion(self, *, name: str) -> bool:
        self.asked.append({"name": name})
        return self._answer


class TestPromotionRouting:
    def test_declining_promotes_nothing_and_reports_it(self):
        converter = _Converter(answer=False)
        result = converter._promote_income(
            before=_entry(one_off=True), after=_entry(one_off=False)
        )
        assert result is None
        assert converter.view_model.calls == []

    def test_a_one_off_becomes_a_regular_income_by_its_extra_id(self):
        converter = _Converter(answer=True)
        before = _entry(one_off=True, entry_id=5)
        after = _entry(one_off=False, entry_id=5)
        persisted = converter._promote_income(before=before, after=after)
        kind, kwargs = converter.view_model.calls[0]
        assert kind == "to_source"
        assert kwargs == {"extra_id": 5, "income": after}
        assert persisted.is_month_only is False

    def test_the_confirmation_names_the_entry(self):
        converter = _Converter(answer=True)
        converter._promote_income(
            before=_entry(one_off=True, name="Wages"),
            after=_entry(one_off=False, name="Wages"),
        )
        assert converter.asked == [{"name": "Wages"}]

    def test_there_is_no_route_that_demotes(self):
        """The mixin exposes promotion alone, so nothing can erase history."""
        assert not hasattr(_Converter(answer=True), "_convert_income")
        assert not hasattr(
            _Converter(answer=True).view_model, "convert_income_source_to_extra"
        )

    def test_the_month_is_named_rather_than_numbered(self):
        converter = _Converter(answer=True)
        assert converter._convert_month_label() == "June 2026"
