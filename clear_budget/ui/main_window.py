"""Main application window with tab-based interface."""

from PySide6.QtWidgets import QMainWindow, QTabWidget, QWidget, QVBoxLayout
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt

from clear_budget.ui.dark_theme import DARK_QSS
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
        self.setGeometry(100, 100, 1200, 800)
        self.init_ui()
        self.apply_theme()

    def init_ui(self) -> None:
        """Build main window with tabs."""
        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()

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

        self.month_view_model.month_changed.connect(
            self.solvency_view_model.set_month
        )
        self.month_view_model.month_changed.connect(credit_card_view.set_month)

    def apply_theme(self) -> None:
        """Apply dark theme stylesheet."""
        self.setStyleSheet(DARK_QSS)
