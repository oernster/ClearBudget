"""Solvency panel widget - displays financial health status and warnings."""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar
from PySide6.QtCore import Qt

from clear_budget.ui.view_models.solvency_view_model import SolvencyViewModel


class SolvencyPanel(QWidget):
    """Displays account solvency status and forward projections."""

    def __init__(self, view_model: SolvencyViewModel) -> None:
        """Initialize solvency panel widget."""
        super().__init__()
        self.view_model = view_model
        self.init_ui()
        self.connect_signals()

    def init_ui(self) -> None:
        """Build solvency panel layout."""
        layout = QVBoxLayout()

        self.balance_label = QLabel("Balance: £0.00")
        self.balance_label.setObjectName("BalanceLabel")
        layout.addWidget(self.balance_label)

        self.status_label = QLabel("Status: Unknown")
        self.status_label.setObjectName("StatusLabel")
        layout.addWidget(self.status_label)

        self.deficit_label = QLabel("Deficit: £0.00")
        self.deficit_label.setObjectName("DeficitLabel")
        self.deficit_label.setVisible(False)
        layout.addWidget(self.deficit_label)

        self.forward_label = QLabel("Forward Shortfall: £0.00")
        layout.addWidget(self.forward_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        layout.addWidget(self.progress_bar)

        self.setLayout(layout)

    def connect_signals(self) -> None:
        """Connect ViewModel signals to view updates."""
        self.view_model.solvency_updated.connect(self.update_display)
        self.view_model.danger_warning_triggered.connect(self.on_danger_warning)

    def update_display(self, report) -> None:
        """Update display from solvency report."""
        if not report:
            return

        balance_str = f"£{report.balance_pence / 100:.2f}"
        self.balance_label.setText(f"Balance: {balance_str}")

        if report.is_solvent:
            self.status_label.setText("Status: Solvent ✓")
            self.status_label.setObjectName("SolvencyGood")
        else:
            self.status_label.setText("Status: Deficit ✗")
            self.status_label.setObjectName("SolvencyBad")

        if report.balance_pence < 0:
            deficit_str = f"£{abs(report.balance_pence / 100):.2f}"
            self.deficit_label.setText(f"Deficit: {deficit_str}")
            self.deficit_label.setVisible(True)
        else:
            self.deficit_label.setVisible(False)

        forward_str = f"£{report.forward_shortfall.pounds:.2f}"
        self.forward_label.setText(f"Forward Shortfall: {forward_str}")

        desired_str = f"£{report.desired_acquire.pounds:.2f}"
        self.progress_bar.setValue(min(100, int((report.balance_pence / 100) / 10)))

    def on_danger_warning(self, message: str) -> None:
        """Handle danger warning signal."""
        self.deficit_label.setText(message)
