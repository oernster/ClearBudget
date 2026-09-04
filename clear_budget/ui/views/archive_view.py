"""Archive view widget - displays historical month data and trends.

A budget that sets money aside gets one more column, stating the reserve each
completed month really carried at its own last day. It appears only when there
is something to report, so an archive that has never had a commitment reads
exactly as it always did.
"""

from PySide6.QtWidgets import (
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from clear_budget.application.services.budget_service import BudgetService
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.ui.utils.format_helpers import (
    apply_nav_label_color,
    build_centered_nav_header,
    nav_glyph_height,
)
from clear_budget.ui.utils.view_buttons import (
    build_view_buttons,
    ring_view_stops,
)
from clear_budget.ui.widgets._tray_buttons import (
    build_budgets_button,
    build_info_button,
    build_save_load_buttons,
    build_tray_separator,
    build_bank_button,
)
from clear_budget.ui.widgets.archive_detail_dialog import ArchiveDetailDialog
from clear_budget.ui.utils import reserves_text
from clear_budget.ui.utils.table_focus import keyboard_only_focus
from clear_budget.ui.utils.text_metrics import apply_comfortable_rows


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

        self.prev_year_btn = QPushButton("← Previous")
        self.next_year_btn = QPushButton("Next →")
        _glyph_h = nav_glyph_height(self.prev_year_btn)
        self.load_btn, self.save_btn = build_save_load_buttons(_glyph_h)
        self.budgets_btn = build_budgets_button(_glyph_h)
        _sep, self.bank_btn = build_bank_button(_glyph_h)
        self.info_btn = build_info_button(_glyph_h)
        # The primary view buttons live in this tray, so every view builds its
        # own set; MainWindow wires them and keeps the current-view mark in
        # step across all four.
        self.view_btns = build_view_buttons(_glyph_h)
        self.nav_header, self.year_label, self.theme_btn = build_centered_nav_header(
            "",
            prev_btn=self.prev_year_btn,
            next_btn=self.next_year_btn,
            leading=(
                self.load_btn,
                self.save_btn,
                self.budgets_btn,
                _sep,
                self.bank_btn,
            ),
            views=self.view_btns[:-1],
            pre_theme=(build_tray_separator(_glyph_h), self.view_btns[-1]),
            trailing=(self.info_btn,),
        )

        self.archive_table = QTableWidget()
        apply_comfortable_rows(self.archive_table)
        keyboard_only_focus(self.archive_table)
        headings = ["Month", "Income", "Bills", "Balance", "Status"]
        if self._shows_reserves():
            headings.insert(-1, reserves_text.ARCHIVE_COLUMN)
        self.archive_table.setColumnCount(len(headings))
        self.archive_table.setHorizontalHeaderLabels(headings)
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
            reserved = (
                Amount(
                    pence=self.budget_service.get_reserve_held_pence(year_month=month)
                )
                if self._shows_reserves()
                else None
            )
            dialog = ArchiveDetailDialog(self, month, summary, reserved)
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
        """Ordered keyboard-ring stops for this view.

        READING order, which with two stacked trays means the TOP tray first
        and the lower one after it, each left to right as drawn. A ring that
        disagrees with the drawing does not present as a wrong order, it
        presents as a SKIPPED control: the user views past where a button
        visibly is and lands somewhere else entirely.

        The button for the view being shown is not in the list. It is a stop
        that could do nothing, dropped here rather than disabled, because a
        disabled control paints the permanent red ring and would read as
        broken rather than as current.
        """
        # Archive was moved out of the button run to the right-hand group,
        # so the ring has to walk it there. A ring that disagrees with the
        # drawing reads as a SKIPPED control, not as a wrong order.
        others = ring_view_stops(self.view_btns[:-1])
        archive_stop = ring_view_stops(self.view_btns[-1:])
        return [
            self.prev_year_btn,
            self.next_year_btn,
            self.load_btn,
            self.save_btn,
            self.budgets_btn,
            self.bank_btn,
            *others,
            *archive_stop,
            self.theme_btn,
            self.info_btn,
            self.archive_table,
        ]

    def set_nav_label_color(self, color: str) -> None:
        """Recolour the nav year label to match the Solvency view."""
        apply_nav_label_color(self.year_label, color)

    def _on_prev_year(self) -> None:
        idx = self.available_years.index(self.current_year)
        self.current_year = self.available_years[idx - 1]
        self._refresh_year_view()

    def _on_next_year(self) -> None:
        idx = self.available_years.index(self.current_year)
        self.current_year = self.available_years[idx + 1]
        self._refresh_year_view()

    def _shows_reserves(self) -> bool:
        """Whether this budget sets anything aside at all.

        Decided once for the whole table rather than per month, so the columns
        do not change shape as the years are stepped through.
        """
        return bool(self.budget_service.list_commitments())

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

            column = 4
            if self._shows_reserves():
                held = self.budget_service.get_reserve_held_pence(year_month=month)
                self.archive_table.setItem(
                    row, column, QTableWidgetItem(str(Amount(pence=held)))
                )
                column += 1
            status = "✓ Solvent" if summary.balance.pence >= 0 else "✗ Deficit"
            self.archive_table.setItem(row, column, QTableWidgetItem(status))
