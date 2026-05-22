"""Archive view widget - displays historical month data and trends."""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)
from PySide6.QtCore import Qt

from clear_budget.application.services.budget_service import BudgetService
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.ui.widgets.archive_detail_dialog import ArchiveDetailDialog
from clear_budget.ui.utils.format_helpers import build_nav_month_widget


class ArchiveView(QWidget):
    """Displays historical month summaries and solvency trends."""

    def __init__(self, budget_service: BudgetService) -> None:
        """Initialize archive view widget."""
        super().__init__()
        self.budget_service = budget_service
        self.current_year: int = 0
        self.available_years: list[int] = []
        self.months_by_row: dict = {}
        self.init_ui()
        self.on_load_history()

    def init_ui(self) -> None:
        """Build archive view layout."""
        layout = QVBoxLayout()

        nav_layout = QHBoxLayout()
        self.prev_year_btn = QPushButton("← Previous")
        self.prev_year_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.next_year_btn = QPushButton("Next →")
        self.next_year_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._nav_center, self.year_label = build_nav_month_widget("")

        left_group = QWidget()
        left_lo = QHBoxLayout(left_group)
        left_lo.setContentsMargins(0, 0, 0, 0)
        left_lo.addWidget(self.prev_year_btn)
        left_lo.addStretch()

        right_group = QWidget()
        right_lo = QHBoxLayout(right_group)
        right_lo.setContentsMargins(0, 0, 0, 0)
        right_lo.addStretch()
        right_lo.addWidget(self.next_year_btn)

        nav_layout.addWidget(left_group, 1)
        nav_layout.addWidget(self._nav_center, 0)
        nav_layout.addWidget(right_group, 1)
        layout.addLayout(nav_layout)

        self.archive_table = QTableWidget()
        self.archive_table.setColumnCount(5)
        self.archive_table.setHorizontalHeaderLabels(
            ["Month", "Income", "Bills", "Balance", "Status"]
        )
        self.archive_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.archive_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.archive_table.horizontalHeader().setStretchLastSection(False)
        self.archive_table.verticalHeader().setStyleSheet(
            "QHeaderView::section { color: #34d399; }"
        )
        self.archive_table.verticalHeader().sectionClicked.connect(
            self.on_row_header_click
        )
        layout.addWidget(self.archive_table)

        self.setLayout(layout)

        self.prev_year_btn.clicked.connect(self._on_prev_year)
        self.next_year_btn.clicked.connect(self._on_next_year)

    def on_row_header_click(self, row: int) -> None:
        """Handle pencil icon click on row header to show details."""
        if row in self.months_by_row:
            month, summary = self.months_by_row[row]
            dialog = ArchiveDetailDialog(self, month, summary)
            dialog.exec()

    def on_load_history(self) -> None:
        """Load recorded months from database and initialise year navigation."""
        recorded_months = self.budget_service.get_recorded_months()
        self.available_years = sorted({m.year for m in recorded_months})
        if self.available_years:
            if self.current_year not in self.available_years:
                self.current_year = self.available_years[-1]
        else:
            self.current_year = 0
        self._refresh_year_view(recorded_months)

    def _refresh_year_view(self, all_months: list[YearMonth] | None = None) -> None:
        """Filter table to current_year and update nav state."""
        if all_months is None:
            all_months = self.budget_service.get_recorded_months()
        year_months = [m for m in all_months if m.year == self.current_year]
        self.year_label.setText(str(self.current_year) if self.current_year else "")
        idx = (
            self.available_years.index(self.current_year)
            if self.current_year in self.available_years
            else -1
        )
        self.prev_year_btn.setEnabled(idx > 0)
        self.next_year_btn.setEnabled(0 <= idx < len(self.available_years) - 1)
        self.load_history(year_months)

    def _on_prev_year(self) -> None:
        idx = self.available_years.index(self.current_year)
        self.current_year = self.available_years[idx - 1]
        self._refresh_year_view()

    def _on_next_year(self) -> None:
        idx = self.available_years.index(self.current_year)
        self.current_year = self.available_years[idx + 1]
        self._refresh_year_view()

    def load_history(self, months: list[YearMonth]) -> None:
        """Load historical months into table."""
        self.archive_table.setRowCount(0)
        self.months_by_row.clear()

        for month in months:
            summary = self.budget_service.get_month_summary(year_month=month)

            row = self.archive_table.rowCount()
            self.archive_table.insertRow(row)
            self.archive_table.setVerticalHeaderItem(row, QTableWidgetItem("📝"))
            self.months_by_row[row] = (month, summary)

            self.archive_table.setItem(row, 0, QTableWidgetItem(str(month)))
            self.archive_table.setItem(
                row, 1, QTableWidgetItem(str(summary.total_income))
            )
            self.archive_table.setItem(
                row, 2, QTableWidgetItem(str(summary.total_bills))
            )
            self.archive_table.setItem(row, 3, QTableWidgetItem(str(summary.balance)))

            status = "✓ Solvent" if summary.balance.pence >= 0 else "✗ Deficit"
            self.archive_table.setItem(row, 4, QTableWidgetItem(status))
