"""Every typed money field reads exact pence; a refusal is shown, never raised.

The README says nothing rounds away between the figure typed and the figure
stored. The Bill and Income dialogs were brought into line first; these are the
rest: the balance, bank-account settings, commitment and credit card dialogs
plus the buffer fields on the Reserves and Recommendations views. Each read its
fields with `float()`, so 0.125 was stored as 12p, `inf` or `nan` raised out of
the OK handler and a negative or unreadable figure was silently ignored or
clamped.

Now each reads through `pence_from_text`. A figure it will not read exactly is
refused through the screen's `_refuse_amount` hook (a warning; the dialog
stays open) and nothing is saved.

Qt-free: each screen's real handler is borrowed onto a plain stand-in whose
"widgets" answer the few calls it makes; the stand-in records the refusal
instead of showing a message box.
"""

from types import SimpleNamespace

import pytest

from clear_budget.domain.value_objects.amount import Amount
from clear_budget.shared.errors import InvalidAmountError
from clear_budget.ui.views.recommendations_view import RecommendationsView
from clear_budget.ui.views.reserves_view import ReservesView
from clear_budget.ui.widgets.balance_dialog import BalanceDialog
from clear_budget.ui.widgets.bank_account_settings_dialog import (
    BankAccountSettingsDialog,
    apr_basis_points_from_text,
)
from clear_budget.ui.widgets.commitment_dialog import CommitmentDialog
from clear_budget.ui.widgets.credit_card_dialog import CreditCardDialog

_REFUSED = ["0.125", "2.675", "nan", "inf", "-5", "1e19", "abc"]
_READ = [("1,500", 150000), ("£0.10", 10), ("12", 1200)]


class _Field:
    def __init__(self, text: str = "") -> None:
        self._text = text

    def text(self) -> str:
        return self._text

    def setEnabled(self, _enabled: bool) -> None:  # noqa: N802 (Qt name)
        pass


def _check(ticked: bool = True):
    return SimpleNamespace(isChecked=lambda: ticked)


class _Screen:
    """What every stand-in shares: it records instead of showing or closing."""

    def __init__(self) -> None:
        self.refusals: list[str] = []
        self.accepted = False

    def _refuse_amount(self, _field, refusal) -> None:
        self.refusals.append(str(refusal))

    def accept(self) -> None:
        self.accepted = True


class _Balance(_Screen):
    on_ok = BalanceDialog.on_ok

    def __init__(self, text: str) -> None:
        super().__init__()
        self.amount_edit = _Field(text)
        self.new_balance_pence = None


class TestTheBalanceDialog:
    @pytest.mark.parametrize(("typed", "pence"), [*_READ, ("-£1,250.50", -125050)])
    def test_reads_exact_signed_pence(self, typed: str, pence: int) -> None:
        """An overdrawn balance is negative; the dialog pre-fills it as such."""
        dialog = _Balance(typed)
        dialog.on_ok()
        assert (dialog.new_balance_pence, dialog.accepted) == (pence, True)

    @pytest.mark.parametrize("typed", ["0.125", "nan", "inf", "1e19", "abc", ""])
    def test_refuses_and_stays_open(self, typed: str) -> None:
        dialog = _Balance(typed)
        dialog.on_ok()
        assert dialog.refusals
        assert not dialog.accepted


class _BankSettings(_Screen):
    _on_save = BankAccountSettingsDialog._on_save
    _read_safe_to_spend_inputs = BankAccountSettingsDialog._read_safe_to_spend_inputs

    def __init__(self, *, limit="0", apr="0", floor="0") -> None:
        super().__init__()
        self._has_overdraft_check = _check()
        self._limit_edit = _Field(limit)
        self._apr_edit = _Field(apr)
        self._floor_edit = _Field(floor)
        self._window_spin = SimpleNamespace(value=lambda: 4)
        self._new_overdraft_limit = None
        self._new_overdraft_apr_basis_points = None
        self._new_safe_to_spend_floor = None
        self._new_sustainable_window_months = None


class TestTheBankAccountSettingsDialog:
    @pytest.mark.parametrize(("typed", "pence"), _READ)
    def test_reads_exact_pence(self, typed: str, pence: int) -> None:
        dialog = _BankSettings(limit=typed, floor=typed, apr="19.9")
        dialog._on_save()
        assert dialog._new_overdraft_limit == Amount(pence=pence)
        assert dialog._new_safe_to_spend_floor == Amount(pence=pence)
        assert dialog._new_overdraft_apr_basis_points == 1990
        assert dialog.accepted

    def test_an_empty_field_is_zero(self) -> None:
        dialog = _BankSettings(limit="", floor="", apr="")
        dialog._on_save()
        assert dialog._new_overdraft_limit == Amount(pence=0)
        assert dialog._new_safe_to_spend_floor == Amount(pence=0)

    @pytest.mark.parametrize("typed", _REFUSED)
    @pytest.mark.parametrize("field", ["limit", "floor"])
    def test_refuses_and_stays_open(self, field: str, typed: str) -> None:
        dialog = _BankSettings(**{field: typed})
        dialog._on_save()
        assert dialog.refusals
        assert not dialog.accepted

    @pytest.mark.parametrize(
        ("typed", "basis_points"), [("19.9%", 1990), ("0", 0), ("1000", 100000)]
    )
    def test_an_apr_is_read_exactly(self, typed: str, basis_points: int) -> None:
        assert apr_basis_points_from_text(typed) == basis_points

    @pytest.mark.parametrize(
        "typed", ["nan", "inf", "-1", "abc", "19.999", "1000.01", "1e999999999"]
    )
    def test_an_apr_that_is_not_a_rate_is_refused(self, typed: str) -> None:
        dialog = _BankSettings(apr=typed)
        dialog._on_save()
        assert dialog.refusals
        assert not dialog.accepted


class _Commitment(_Screen):
    accept_checked = CommitmentDialog.accept
    _typed_commitment_pence = getattr(CommitmentDialog, "_typed_commitment_pence", None)

    def __init__(self, *, amount="10", held="") -> None:
        super().__init__()
        self.amount_edit = _Field(amount)
        self.held_edit = _Field(held)


class TestTheCommitmentDialog:
    @pytest.mark.parametrize(("typed", "pence"), _READ)
    def test_reads_exact_pence(self, typed: str, pence: int) -> None:
        dialog = _Commitment(amount=typed, held=typed)
        assert dialog._typed_commitment_pence() == (pence, pence)

    def test_nothing_put_by_is_zero(self) -> None:
        assert _Commitment(amount="10", held="")._typed_commitment_pence() == (
            1000,
            0,
        )

    @pytest.mark.parametrize("typed", _REFUSED)
    @pytest.mark.parametrize("field", ["amount", "held"])
    def test_refuses_and_stays_open(self, field: str, typed: str) -> None:
        dialog = _Commitment(**{field: typed})
        dialog.accept_checked()
        assert dialog.refusals
        assert not dialog.accepted


class _Card(_Screen):
    accept_checked = CreditCardDialog.accept
    _typed_card_pence = getattr(CreditCardDialog, "_typed_card_pence", None)

    def __init__(self, *, limit="100", balance="", minimum="") -> None:
        super().__init__()
        self.limit_edit = _Field(limit)
        self.balance_edit = _Field(balance)
        self.min_payment_edit = _Field(minimum)


class TestTheCreditCardDialog:
    @pytest.mark.parametrize(("typed", "pence"), _READ)
    def test_reads_exact_pence(self, typed: str, pence: int) -> None:
        card = _Card(limit=typed, balance=typed, minimum=typed)
        assert card._typed_card_pence() == (pence, pence, pence)

    def test_optional_fields_left_empty(self) -> None:
        """No balance used is zero; no minimum payment is no minimum at all."""
        assert _Card(limit="100")._typed_card_pence() == (10000, 0, None)

    @pytest.mark.parametrize("typed", [*_REFUSED, ""])
    def test_a_limit_is_required(self, typed: str) -> None:
        dialog = _Card(limit=typed)
        dialog.accept_checked()
        assert dialog.refusals
        assert not dialog.accepted

    @pytest.mark.parametrize("typed", _REFUSED)
    @pytest.mark.parametrize("field", ["balance", "minimum"])
    def test_refuses_and_stays_open(self, field: str, typed: str) -> None:
        dialog = _Card(**{field: typed})
        dialog.accept_checked()
        assert dialog.refusals
        assert not dialog.accepted


class _BufferService:
    def __init__(self) -> None:
        self.saved: list[tuple[bool, Amount]] = []

    def set_recommendation_buffer(self, *, enabled: bool, amount: Amount) -> None:
        self.saved.append((enabled, amount))


class _Buffer(_Screen):
    def __init__(self, text: str) -> None:
        super().__init__()
        self.buffer_edit = _Field(text)
        self.buffer_check = _check()
        self.budget_service = _BufferService()

    def refresh(self) -> None:
        pass


class _ReservesBuffer(_Buffer):
    save = ReservesView._save_buffer


class _RecommendationsBuffer(_Buffer):
    save = RecommendationsView._on_buffer_changed


@pytest.mark.parametrize("view", [_ReservesBuffer, _RecommendationsBuffer])
class TestTheBufferFields:
    @pytest.mark.parametrize(("typed", "pence"), [*_READ, ("", 0)])
    def test_saves_exact_pence(self, view, typed: str, pence: int) -> None:
        screen = view(typed)
        screen.save()
        assert screen.budget_service.saved == [(True, Amount(pence=pence))]

    @pytest.mark.parametrize("typed", _REFUSED)
    def test_refuses_and_saves_nothing(self, view, typed: str) -> None:
        screen = view(typed)
        screen.save()
        assert screen.refusals
        assert screen.budget_service.saved == []


def test_refusals_name_the_problem() -> None:
    """The refusal text is the parser's own, so every screen says the same."""
    dialog = _Balance("0.125")
    dialog.on_ok()
    with pytest.raises(InvalidAmountError) as caught:
        from clear_budget.application.formatting import pence_from_text

        pence_from_text("0.125")
    assert str(caught.value) in dialog.refusals[0]
