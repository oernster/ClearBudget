"""Solvency panel widget - displays financial health status and warnings."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from clear_budget.ui import label_roles, ui_scale
from clear_budget.ui.utils.format_helpers import (
    build_centered_nav_header,
    fmt,
    nav_glyph_height,
)
from clear_budget.ui.view_models.solvency_view_model import SolvencyViewModel
from clear_budget.ui.widgets._save_load_flow import (
    build_info_button,
    build_save_load_buttons,
    build_settings_bank_buttons,
)
from clear_budget.ui.views._solvency_panel_card_bars import (
    SolvencyPanelCardBarsMixin,
)
from clear_budget.ui.views._solvency_panel_display import SolvencyPanelDisplayMixin
from clear_budget.ui.views._solvency_panel_forward import SolvencyPanelForwardMixin
from clear_budget.ui.views._solvency_panel_narratives import (
    SolvencyPanelNarrativeMixin,
)
from clear_budget.ui.views._solvency_panel_safe_to_spend import (
    SolvencyPanelSafeToSpendMixin,
)

# Section headings on this tab share one QSS role (see _theme_controls).
_HEADING_ROLE = "SolvencySectionHeading"


class SolvencyPanel(
    SolvencyPanelCardBarsMixin,
    SolvencyPanelDisplayMixin,
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

        # SECTION 0: SAFE TO SPEND TODAY (Headline - the actionable number)
        sts_heading = QLabel("Safe to Spend Today")
        sts_heading.setObjectName(_HEADING_ROLE)
        layout.addWidget(sts_heading)

        self.sts_banner = QLabel("")
        self.sts_banner.setObjectName("SolvencyBanner")
        layout.addWidget(self.sts_banner)

        self.sts_detail = QLabel("")
        self.sts_detail.setWordWrap(True)
        self.sts_detail.setObjectName("SolvencyCommitted")
        layout.addWidget(self.sts_detail)

        # How the figure moves as money lands later in the month. Hidden when
        # it never moves, so a flat month says nothing rather than repeating
        # the headline.
        self.sts_capacity = QLabel("")
        self.sts_capacity.setWordWrap(True)
        self.sts_capacity.setObjectName("SolvencyBreakdown")
        self.sts_capacity.hide()
        layout.addWidget(self.sts_capacity)

        # SECTION 1: OVERDRAFT ALERT (Top - Prominent)
        alert_label = QLabel("Overdraft Status")
        alert_label.setObjectName(_HEADING_ROLE)
        layout.addWidget(alert_label)

        self.overdraft_alert = QLabel(f"SAFE: {fmt(0)} buffer")
        self.overdraft_alert.setObjectName("SolvencyBanner")
        layout.addWidget(self.overdraft_alert)

        self.midmonth_alert = QLabel("")
        self.midmonth_alert.setWordWrap(True)
        self.midmonth_alert.setObjectName("SolvencyMidmonthAlert")
        self.midmonth_alert.hide()
        layout.addWidget(self.midmonth_alert)

        # SECTION 2: OVERALL HEALTH (Middle)
        health_label = QLabel("Overall Health")
        health_label.setObjectName(_HEADING_ROLE)
        layout.addWidget(health_label)

        self.balance_label = QLabel(f"Bank Balance: {fmt(0)}")
        self.balance_label.setObjectName(label_roles.VALUE)
        layout.addWidget(self.balance_label)

        self.committed_label = QLabel("Committed this month: -")
        self.committed_label.setObjectName("SolvencyCommitted")
        layout.addWidget(self.committed_label)

        self.remaining_bank_label = QLabel("Still due this month (bank): -")
        self.remaining_bank_label.setWordWrap(True)
        self.remaining_bank_label.setObjectName("SolvencyRemainingBank")
        layout.addWidget(self.remaining_bank_label)

        self.remaining_card_label = QLabel("Still due this month (cards): -")
        self.remaining_card_label.setObjectName("SolvencyRemainingCard")
        layout.addWidget(self.remaining_card_label)

        self.month_breakdown_label = QLabel("")
        self.month_breakdown_label.setWordWrap(True)
        self.month_breakdown_label.setObjectName("SolvencyBreakdown")
        layout.addWidget(self.month_breakdown_label)

        cards_header = QLabel("Credit Card Status")
        cards_header.setObjectName(_HEADING_ROLE)
        layout.addWidget(cards_header)

        self.card_bars_container = QWidget()
        self.card_bars_layout = QVBoxLayout(self.card_bars_container)
        self.card_bars_layout.setSpacing(ui_scale.px(3))
        self.card_bars_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.card_bars_container)

        # SECTION 3: FORWARD PROJECTION (Bottom)
        forward_label = QLabel("Forward Projection")
        forward_label.setObjectName(_HEADING_ROLE)
        layout.addWidget(forward_label)

        self.m1_projection_label = QLabel("")
        self.m1_projection_label.setWordWrap(True)
        self.m1_projection_label.setStyleSheet(
            ui_scale.style("font-size: 17px; padding: 5px;")
        )
        layout.addWidget(self.m1_projection_label)

        self.m2_projection_label = QLabel("")
        self.m2_projection_label.setWordWrap(True)
        self.m2_projection_label.setStyleSheet(
            ui_scale.style("font-size: 17px; padding: 5px;")
        )
        layout.addWidget(self.m2_projection_label)

        layout.addStretch()
        self.setLayout(layout)

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
