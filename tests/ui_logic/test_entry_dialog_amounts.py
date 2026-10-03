"""What the Bill and Income dialogs do with a typed amount; where a new income
starts.

The dialogs read amounts with `float()`: 2.675 was stored as 268p, `inf`
raised an OverflowError out of the OK handler and "1,500" (as the app itself
prints it) was refused silently. They now read through `pence_from_text` and
refuse, with the parser's own message, anything it will not read exactly.

A new income was saved with no start month, so it appeared in every month
before it was added (measured in January 2019). It now starts at the month
being viewed, as a new bill does.

Qt-free: the dialogs' real methods are borrowed onto a plain stand-in whose
"widgets" answer the few calls those methods make (see this package's
docstring), so no QApplication is needed.
"""

from types import SimpleNamespace

import pytest

from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.ui.widgets._entry_dialog_rules import EntryDialogRulesMixin
from clear_budget.ui.widgets.bill_dialog import BillDialog
from clear_budget.ui.widgets.income_dialog import IncomeDialog

_VIEWED = YearMonth(2019, 1)
_REFUSED = ["", "abc", "nan", "inf", "-5", "0.125", "2.675", "1e19"]


def _text(value: str):
    return SimpleNamespace(text=lambda: value)


def _check(ticked: bool = False):
    return SimpleNamespace(isChecked=lambda: ticked)


def _spin(value: int = 0):
    return SimpleNamespace(value=lambda: value)


def _combo(text: str, data=None):
    return SimpleNamespace(currentText=lambda: text, currentData=lambda: data)


class _IncomeForm(EntryDialogRulesMixin):
    get_income = IncomeDialog.get_income
    _chosen_end_month = IncomeDialog._chosen_end_month

    def __init__(self, amount: str, income=None) -> None:
        self.income = income
        self.current_month = _VIEWED
        self.name_edit = _text("New job")
        self.amount_edit = _text(amount)
        self.due_day_spinbox = _spin(25)
        self.ends_check = _check()
        self.one_off_check = _check()
        self.day_fixed_check = _check()


class _BillForm(EntryDialogRulesMixin):
    get_bill = BillDialog.get_bill
    _internal_category = staticmethod(BillDialog._internal_category)

    def __init__(self, amount: str) -> None:
        self.bill = None
        self.current_month = _VIEWED
        self.payment_method_repo = None
        self.name_edit = _text("Rent")
        self.amount_edit = _text(amount)
        self.category_combo = _combo("Housing")
        self.type_combo = _combo("fixed")
        self.day_spin = _spin(1)
        self.payment_method_combo = _combo("Bank Account", 1)
        self.pays_card_combo = _combo("(none)")
        self.month_only_check = _check()
        self.ends_check = _check()
        self.day_fixed_check = _check()


class TestTheAmountIsReadExactly:
    @pytest.mark.parametrize(("typed", "pence"), [("1,500", 150000), ("12.34", 1234)])
    def test_an_income(self, typed: str, pence: int) -> None:
        assert _IncomeForm(typed).get_income().amount == Amount(pence=pence)

    @pytest.mark.parametrize(("typed", "pence"), [("£1,500", 150000), ("0.10", 10)])
    def test_a_bill(self, typed: str, pence: int) -> None:
        assert _BillForm(typed).get_bill().amount == Amount(pence=pence)


class TestARefusedAmountNeverEscapesTheDialog:
    @pytest.mark.parametrize("typed", _REFUSED)
    def test_it_comes_back_as_a_message_to_show(self, typed: str) -> None:
        assert _IncomeForm(typed)._amount_refusal()
        assert _BillForm(typed)._amount_refusal()

    @pytest.mark.parametrize("typed", _REFUSED)
    def test_nothing_is_built_from_it(self, typed: str) -> None:
        assert _IncomeForm(typed).get_income() is None
        assert _BillForm(typed).get_bill() is None

    def test_a_readable_amount_has_no_refusal(self) -> None:
        assert _IncomeForm("1,500")._amount_refusal() is None


class TestWhereANewIncomeStarts:
    def test_at_the_month_being_viewed(self) -> None:
        assert _IncomeForm("10").get_income().start_ym == _VIEWED

    def test_an_edit_keeps_the_start_it_had(self) -> None:
        for start in (None, YearMonth(2018, 6)):
            existing = SimpleNamespace(id=4, start_ym=start)
            assert _IncomeForm("10", existing).get_income().start_ym == start

    def test_a_new_bill_still_starts_there_too(self) -> None:
        assert _BillForm("10").get_bill().start_ym == _VIEWED
