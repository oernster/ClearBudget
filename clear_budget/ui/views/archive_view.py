"""Archive view widget - displays historical month data and trends."""

from PySide6.QtWidgets import (
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from clear_budget.application.services.budget_service import BudgetService
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.ui.utils.format_helpers import (
    apply_nav_label_color,
    build_centered_nav_header,
    nav_glyph_height,
)
from clear_budget.ui.utils.tab_icons import (
    build_tab_buttons,
    ring_tab_stops,
)
from clear_budget.ui.widgets._save_load_flow import (
    build_info_button,
    build_save_load_buttons,
    build_settings_bank_buttons,
)
from clear_budget.ui.widgets.archive_detail_dialog import ArchiveDetailDialog


class ArchiveView(QWidget):
    """Displays historical month summaries and solvency trends."""

    def __init__(self, budget_service: BudgetService, read_only: bool = False) -> None:
        """Initialize archive view widget."""
        super().__init__()
        self.budget_service = budget_service
        self.read_only = read_only
        self.current_year: int = 0
        self.available_years: list[int] = []
        self.months_by_row: dict = {}
        self.init_ui()
        self.on_load_history()

    def init_ui(self) -> None:
        """Build archive view layout."""
        layout = QVBoxLayout()

        self.prev_year_btn = QPushButton("← Previous")
        self.next_year_btn = QPushButton("Next →")
        _glyph_h = nav_glyph_height(self.prev_year_btn)
        self.load_btn, self.save_btn = build_save_load_buttons(self.read_only, _glyph_h)
        _sep, self.settings_btn, self.bank_btn = build_settings_bank_buttons(
            self.read_only, _glyph_h
        )
        self.info_btn = build_info_button(_glyph_h)
        # The four primary tabs live in this tray, so every view builds its
        # own set; MainWindow wires them and keeps the current-tab mark in
        # step across all four.
        self.tab_btns = build_tab_buttons(_glyph_h)
        self.nav_header, self.year_label, _, self.theme_btn = build_centered_nav_header(
            "",
            prev_btn=self.prev_year_btn,
            next_btn=self.next_year_btn,
            leading=(
                self.load_btn,
                self.save_btn,
                self.settings_btn,
                self.bank_btn,
                _sep,
            ),
            tabs=self.tab_btns,
            trailing=(self.info_btn,),
        )

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
        # The row-header pencil colour comes from the app stylesheet
        # (QHeaderView::section:vertical), so it follows the theme.
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
        recorded_months = self._past_recorded_months()
        self.available_years = sorted({m.year for m in recorded_months})
        if self.available_years:
            if self.current_year not in self.available_years:
                self.current_year = self.available_years[-1]
        else:
            self.current_year = 0
        self._refresh_year_view(recorded_months)

    def _past_recorded_months(self) -> list[YearMonth]:
        """Recorded months that are fully complete (excludes current/future)."""
        current = YearMonth.today()
        return [m for m in self.budget_service.get_recorded_months() if m < current]

    def _refresh_year_view(self, all_months: list[YearMonth] | None = None) -> None:
        """Filter table to current_year and update nav state."""
        if all_months is None:
            all_months = self._past_recorded_months()
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

    def nav_targets(self) -> list:
        """Ordered keyboard-ring stops for this tab.

        READING order, which with two stacked trays means the TOP tray first
        and the lower one after it, each left to right as drawn. A ring that
        disagrees with the drawing does not present as a wrong order, it
        presents as a SKIPPED control: the user tabs past where a button
        visibly is and lands somewhere else entirely.

        The tab being shown is not in the list. It is a stop that could do
        nothing, and it is dropped here rather than disabled, because a
        disabled control paints the permanent red ring and would read as
        broken rather than as current.
        """
        others = ring_tab_stops(self.tab_btns)
        return [
            self.prev_year_btn,
            self.next_year_btn,
            self.load_btn,
            self.save_btn,
            self.settings_btn,
            self.bank_btn,
            *others,
            self.theme_btn,
            self.info_btn,
            self.archive_table,
        ]

    def set_nav_label_color(self, color: str) -> None:
        """Recolour the nav year label to match the Solvency tab."""
        apply_nav_label_color(self.year_label, color)

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
