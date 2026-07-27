"""MonthGraphDialog - bar/line graph of the month, opened from the nav icon.

Shows the viewed month's day-by-day series for the page it was opened from
(the bank balance on Monthly Budget, one series per card on Credit Cards).
A pilot button switches between bar and line rendering. It opens focused on
the pilot button (the chart itself takes no focus), Escape closes, and the
ring is Tab/Right forward with the pilot, the export buttons and Close as
the stops.

"Export HTML" writes THIS month as a standalone page carrying both renderings
at once, since a page has room for both where the dialog has room for one. It
is offered wherever the graph is, because it exports whatever is plotted.

"Export projection HTML" asks for a range of months and writes the BANK
balance across them. It appears only when the caller supplies a
`budget_service` and an `anchor_month`, which the Monthly Budget page does and
the Credit Cards page deliberately does not: a bank-balance projection offered
from a graph of card balances would claim to project what is on screen and
would not.
"""

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from clear_budget.application.reporting.month_report import month_report_html
from clear_budget.application.reporting.projection_report import (
    projection_report_html,
)
from clear_budget.ui import ui_scale
from clear_budget.ui.ui_paths import default_downloads_dir
from clear_budget.ui.widgets._line_bar_chart import MODE_BAR, MODE_LINE, LineBarChart
from clear_budget.ui.widgets.first_stop_dialog import FirstStopDialog
from clear_budget.ui.widgets.month_range_dialog import MonthRangeDialog

_DIALOG_MIN_WIDTH = 760
_DIALOG_MIN_HEIGHT = 440

_PILOT_TO_LINE = "Switch to line graph"
_PILOT_TO_BAR = "Switch to bar graph"
# Pairs with "Export HTML" so the two read as a set. What it projects is kept
# unambiguous by WHERE it is offered (Monthly Budget only) and by the report
# itself, which is titled and captioned as a bank balance projection.
_PROJECTION_LABEL = "Export projection HTML…"
_HTML_FILTER = "Web page (*.html)"
_HTML_SUFFIX = ".html"


class MonthGraphDialog(FirstStopDialog):
    """Displays one month's series as a bar or line graph, and exports both."""

    def __init__(
        self,
        parent=None,
        *,
        title: str,
        series,
        month_label: str = "",
        budget_service=None,
        anchor_month=None,
    ) -> None:
        """Build the dialog.

        `budget_service` and `anchor_month` are what the projection export
        needs; without them that button is not offered, so a caller that has
        only a series still gets a working graph.
        """
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumSize(
            ui_scale.px(_DIALOG_MIN_WIDTH), ui_scale.px(_DIALOG_MIN_HEIGHT)
        )
        self._series = list(series)
        self._mode = MODE_BAR
        self._title = title
        self._month_label = month_label or title
        self._budget_service = budget_service
        self._anchor_month = anchor_month

        layout = QVBoxLayout(self)
        self.chart = LineBarChart(self)
        self.chart.set_data(self._series, self._mode)
        layout.addWidget(self.chart, 1)

        button_row = QHBoxLayout()
        self.pilot_btn = QPushButton(_PILOT_TO_LINE)
        self.pilot_btn.clicked.connect(self._toggle_mode)
        button_row.addWidget(self.pilot_btn)

        self.export_btn = QPushButton("Export HTML…")
        self.export_btn.clicked.connect(self._export_month)
        button_row.addWidget(self.export_btn)

        if self._can_project():
            self.projection_btn = QPushButton(_PROJECTION_LABEL)
            self.projection_btn.clicked.connect(self._export_projection)
            button_row.addWidget(self.projection_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_row.addStretch()
        button_row.addWidget(close_btn)
        layout.addLayout(button_row)

    def _can_project(self) -> bool:
        return self._budget_service is not None and self._anchor_month is not None

    def _toggle_mode(self) -> None:
        self._mode = MODE_LINE if self._mode == MODE_BAR else MODE_BAR
        self.pilot_btn.setText(
            _PILOT_TO_LINE if self._mode == MODE_BAR else _PILOT_TO_BAR
        )
        self.chart.set_data(self._series, self._mode)

    # ---- exports ------------------------------------------------------------
    def _export_month(self) -> None:
        html = month_report_html(
            title=self._title,
            subtitle=f"Projected day by day across {self._month_label}.",
            series=self._series,
        )
        self._write(html, suggested=f"{self._slug(self._title)}{_HTML_SUFFIX}")

    def _export_projection(self) -> None:
        dialog = MonthRangeDialog(self, anchor=self._anchor_month)
        if dialog.exec() != MonthRangeDialog.Accepted:
            return
        start, end = dialog.selected_range()
        months = self._budget_service.get_projection_months(start=start, end=end)
        if not months:
            QMessageBox.information(
                self, "Nothing to export", "That range contains no months."
            )
            return
        html = projection_report_html(
            title="Bank balance projection",
            subtitle=f"{months[0].label} to {months[-1].label}.",
            months=months,
            recorded_balance_pence=self._budget_service.get_bank_balance().pence,
        )
        self._write(html, suggested=f"bank-balance-projection{_HTML_SUFFIX}")

    def _write(self, html: str, *, suggested: str) -> None:
        """Ask where to put the report, then write it."""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export HTML",
            str(default_downloads_dir() / suggested),
            _HTML_FILTER,
        )
        if not path:
            return
        if not path.lower().endswith(_HTML_SUFFIX):
            path += _HTML_SUFFIX
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(html)
        except OSError as exc:
            QMessageBox.critical(self, "Export Failed", str(exc))
            return
        QMessageBox.information(self, "Export Successful", f"Saved to:\n{path}")

    @staticmethod
    def _slug(text: str) -> str:
        """A filename-safe version of the dialog title."""
        kept = [c if c.isalnum() else "-" for c in text.lower()]
        return "-".join(part for part in "".join(kept).split("-") if part) or "graph"
