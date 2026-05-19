"""Main application window with tab-based interface."""

from datetime import date as _date

from PySide6.QtWidgets import QMainWindow, QTabWidget, QWidget, QVBoxLayout, QLabel
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt

from clear_budget.ui.dark_theme import get_dark_qss
from clear_budget.ui import ui_scale
from clear_budget.ui.view_models.month_view_model import MonthViewModel
from clear_budget.ui.view_models.solvency_view_model import SolvencyViewModel
from clear_budget.ui.views.month_view import MonthView
from clear_budget.ui.views.solvency_panel import SolvencyPanel
from clear_budget.ui.views.credit_card_view import CreditCardView
from clear_budget.ui.views.archive_view import ArchiveView


class MainWindow(QMainWindow):
    """Application main window with tabbed views."""

    def __init__(
        self,
        month_view_model: MonthViewModel,
        solvency_view_model: SolvencyViewModel,
    ) -> None:
        """Initialize main window and tabs."""
        super().__init__()
        self.month_view_model = month_view_model
        self.solvency_view_model = solvency_view_model
        self.setWindowTitle("ClearBudget - Personal Budget Planner")
        self.setMinimumWidth(ui_scale.px(1400))
        self.init_ui()
        self.apply_theme()

    def init_ui(self) -> None:
        """Build main window with tabs."""
        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        self.tabs.tabBar().setElideMode(Qt.TextElideMode.ElideNone)
        self.tabs.tabBar().setExpanding(False)

        month_view = MonthView(self.month_view_model)
        self.tabs.addTab(month_view, "Monthly Budget")

        solvency_panel = SolvencyPanel(self.solvency_view_model)
        self.tabs.addTab(solvency_panel, "Solvency")

        credit_card_view = CreditCardView(
            self.month_view_model.budget_service,
            self.month_view_model.current_month,
        )
        self.tabs.addTab(credit_card_view, "Credit Cards")

        archive_view = ArchiveView(self.month_view_model.budget_service)
        self.tabs.addTab(archive_view, "Archive")

        layout.addWidget(self.tabs)
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        self.month_view_model.month_changed.connect(self.solvency_view_model.set_month)
        self.month_view_model.month_changed.connect(credit_card_view.set_month)
        self.month_view_model.month_summary_updated.connect(
            self.solvency_view_model.update_month_summary
        )

        # Nav buttons on Solvency and Credit Cards tabs
        solvency_panel.prev_btn.clicked.connect(self.month_view_model.previous_month)
        solvency_panel.next_btn.clicked.connect(self.month_view_model.next_month)
        credit_card_view.prev_btn.clicked.connect(self.month_view_model.previous_month)
        credit_card_view.next_btn.clicked.connect(self.month_view_model.next_month)

        # Keep prev buttons in sync with base_month constraint
        self.month_view_model.month_changed.connect(
            lambda ym: solvency_panel.prev_btn.setEnabled(ym > self.month_view_model.base_month)
        )
        self.month_view_model.month_changed.connect(
            lambda ym: credit_card_view.prev_btn.setEnabled(ym > self.month_view_model.base_month)
        )

        # Initialise disabled state
        at_base = self.month_view_model.current_month <= self.month_view_model.base_month
        solvency_panel.prev_btn.setEnabled(not at_base)
        credit_card_view.prev_btn.setEnabled(not at_base)

        # Ensure solvency has current summary data
        if self.month_view_model.month_summary:
            self.solvency_view_model.update_month_summary(
                self.month_view_model.month_summary
            )

    def _build_status_bar(self) -> None:
        today = _date.today().strftime("%A, %d %B %Y")
        lbl = QLabel(f"  Today: {today}  ")
        lbl.setStyleSheet(
            ui_scale.style("font-size: 18px; font-weight: bold; color: #00d4ff; padding: 2px 8px;")
        )
        self.statusBar().addPermanentWidget(lbl)
        self.statusBar().setStyleSheet(
            "QStatusBar { background-color: #0d0d1a; border-top: 1px solid #1e3a5f; }"
        )

    def apply_theme(self) -> None:
        """Apply dark theme stylesheet."""
        self.setStyleSheet(get_dark_qss())
        self._build_status_bar()
