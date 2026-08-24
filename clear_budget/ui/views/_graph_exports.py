"""The Graph page's two HTML exports, kept out of the page itself.

Split off so `graph_view` stays a page rather than a page plus a reporting
module (`tests/structural/test_loc_limits.py`). The behaviour is carried over
unchanged from the graph dialog these replaced.

"Export HTML" writes the VIEWED month as a standalone page carrying both
renderings at once, since a page has room for both where the view has room
for one. It is offered whatever is plotted, because it exports whatever is
plotted.

"Export projection HTML" asks for a range of months and writes the BANK
balance across them, so it is offered only while the bank is what is on
screen. Offered beside a graph of card balances it would claim to project
what is shown and would not.
"""

from __future__ import annotations

from PySide6.QtWidgets import QFileDialog, QMessageBox

from clear_budget.application.reporting.month_report import month_report_html
from clear_budget.application.reporting.projection_report import (
    projection_report_html,
)
from clear_budget.ui.ui_paths import default_downloads_dir
from clear_budget.ui.widgets.month_range_dialog import MonthRangeDialog

_HTML_FILTER = "Web page (*.html)"
_HTML_SUFFIX = ".html"


class GraphExportsMixin:
    """The two export actions for `GraphView`."""

    def _export_month(self) -> None:
        html = month_report_html(
            title=self._title,
            subtitle=f"Projected day by day across {self._month_label_text()}.",
            series=self._series,
            floor_pence=self._floor_pence(),
        )
        self._write(html, suggested=f"{self._slug(self._title)}{_HTML_SUFFIX}")

    def _export_projection(self) -> None:
        dialog = MonthRangeDialog(self, anchor=self.current_month)
        if dialog.exec() != MonthRangeDialog.Accepted:
            return
        start, end = dialog.selected_range()
        months = self.budget_service.get_projection_months(start=start, end=end)
        if not months:
            QMessageBox.information(
                self, "Nothing to export", "That range contains no months."
            )
            return
        html = projection_report_html(
            title="Bank balance projection",
            subtitle=f"{months[0].label} to {months[-1].label}.",
            months=months,
            recorded_balance_pence=self.budget_service.get_bank_balance().pence,
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
        """A filename-safe version of the plotted title."""
        kept = [c if c.isalnum() else "-" for c in text.lower()]
        return "-".join(part for part in "".join(kept).split("-") if part) or "graph"
