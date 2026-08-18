"""Solvency panel widget - displays financial health status and warnings."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from clear_budget.ui.utils.format_helpers import (
    build_centered_nav_header,
    nav_glyph_height,
)
from clear_budget.ui.view_models.solvency_view_model import SolvencyViewModel
from clear_budget.ui.widgets._save_load_flow import (
    build_info_button,
    build_save_load_buttons,
    build_settings_bank_buttons,
)
from clear_budget.ui.views._solvency_panel_assumed import SolvencyPanelAssumedMixin
from clear_budget.ui.views._solvency_panel_card_bars import (
    SolvencyPanelCardBarsMixin,
)
from clear_budget.ui.views._solvency_panel_display import SolvencyPanelDisplayMixin
from clear_budget.ui.views._solvency_panel_layout import SolvencyPanelLayoutMixin
from clear_budget.ui.views._solvency_panel_forward import SolvencyPanelForwardMixin
from clear_budget.ui.views._solvency_panel_narratives import (
    SolvencyPanelNarrativeMixin,
)
from clear_budget.ui.views._solvency_panel_safe_to_spend import (
    SolvencyPanelSafeToSpendMixin,
)

# The pilot button names the page it goes TO, never the page you are on, the
# same convention the month graph's pilot button uses.
_PILOT_TO_CARDS = "Switch to credit cards"
_PILOT_TO_BANK = "Switch to bank view"

# Stack order. The bank page opens first: it answers "does the account hold",
# which is the question the tab exists for.
_PAGE_BANK = 0
_PAGE_CARDS = 1


class SolvencyPanel(
    SolvencyPanelAssumedMixin,
    SolvencyPanelCardBarsMixin,
    SolvencyPanelDisplayMixin,
    SolvencyPanelLayoutMixin,
    SolvencyPanelForwardMixin,
    SolvencyPanelNarrativeMixin,
    SolvencyPanelSafeToSpendMixin,
    QWidget,
):
    """Displays account solvency status with three critical sections."""

    # Broadcasts the health colour applied to the month label so the other tabs'
    # nav labels can match it (Solvency is the single source of truth).
    month_label_color_changed = Signal(str)

    def __init__(self, view_model: SolvencyViewModel, read_only: bool = False) -> None:
        """Initialize solvency panel widget."""
        super().__init__()
        self.view_model = view_model
        self.read_only = read_only
        self.init_ui()
        self.connect_signals()

    def init_ui(self) -> None:
        """Build solvency panel layout with three sections."""
        layout = QVBoxLayout()

        self.prev_btn = QPushButton("← Previous")
        self.next_btn = QPushButton("Next →")
        _glyph_h = nav_glyph_height(self.prev_btn)
        self.load_btn, self.save_btn = build_save_load_buttons(self.read_only, _glyph_h)
        _sep, self.settings_btn, self.bank_btn = build_settings_bank_buttons(
            self.read_only, _glyph_h
        )
        self.info_btn = build_info_button(_glyph_h)
        self.nav_header, self.month_label, _, self.theme_btn = (
            build_centered_nav_header(
                "May 2026",
                prev_btn=self.prev_btn,
                next_btn=self.next_btn,
                leading=(
                    self.load_btn,
                    self.save_btn,
                    _sep,
                    self.settings_btn,
                    self.bank_btn,
                ),
                trailing=(self.info_btn,),
            )
        )

        self.pilot_btn = QPushButton(_PILOT_TO_CARDS)
        self.pilot_btn.setObjectName("SolvencyPilot")
        self.pilot_btn.clicked.connect(self._toggle_page)
        pilot_row = QHBoxLayout()
        pilot_row.addWidget(self.pilot_btn)
        pilot_row.addStretch(1)
        layout.addLayout(pilot_row)

        # Both pages are built once and kept alive, so switching is a turn of
        # the page rather than a rebuild that would drop scroll position.
        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_bank_page())
        self.pages.addWidget(self._build_cards_page())
        layout.addWidget(self.pages)

        layout.addStretch()
        self.setLayout(layout)

    def _toggle_page(self) -> None:
        """Swap the two readings, relabelling the button with its destination."""
        showing_bank = self.pages.currentIndex() == _PAGE_BANK
        self.pages.setCurrentIndex(_PAGE_CARDS if showing_bank else _PAGE_BANK)
        self.pilot_btn.setText(_PILOT_TO_BANK if showing_bank else _PILOT_TO_CARDS)

    def nav_targets(self) -> list:
        """Ordered keyboard-ring stops for this tab."""
        return [
            self.load_btn,
            self.save_btn,
            self.settings_btn,
            self.bank_btn,
            self.prev_btn,
            self.next_btn,
            self.theme_btn,
            self.info_btn,
            self.pilot_btn,
        ]

    def connect_signals(self) -> None:
        """Connect ViewModel signals to view updates."""
        self.view_model.solvency_updated.connect(self.update_display)

    def _simulate_runway(self, starting_balance_pence: int, from_month) -> tuple:
        """Step forward month by month until balance goes negative.

        Returns (overdrawn_month_or_None, months_solvent_count).
        Caps at 24 months to avoid infinite loops on perpetually-solvent scenarios.
        """
        balance = starting_balance_pence
        month = from_month.next_month()
        for i in range(24):
            s = self.view_model.budget_service.get_month_summary(year_month=month)
            bank_bills = sum(
                b.amount.pence for b in s.bills if b.payment_method_id == 1
            )
            income = s.total_income.pence
            balance += income - bank_bills
            if balance < 0:
                return month, i + 1
            month = month.next_month()
        return None, 24
