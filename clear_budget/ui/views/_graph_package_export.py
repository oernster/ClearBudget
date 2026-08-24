"""The Graph page's third export: a FOLDER of months rather than one page.

Kept apart from `_graph_exports` because it is a different act. Those two
write one file through a Save dialog; this one asks for a directory, creates a
folder inside it and writes a page per month plus an index. The difference
shows up in everything that follows: what has to be confirmed, what can
already be there and what a failure half way through leaves behind.

The range comes from the same `MonthRangeDialog` the projection export uses,
so the two never disagree about how a range is picked; only the wording
differs, which is what the dialog's title and prompt arguments are for.

Offered only while the BANK is what is plotted, on the same grounds as the
projection export: offered beside a graph of card balances it would claim to
project what is shown and would not.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMessageBox

from clear_budget.application.reporting.package_report import (
    INDEX_NAME,
    build_package,
    package_folder_name,
)
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.ui.ui_paths import default_downloads_dir
from clear_budget.ui.widgets.month_range_dialog import MonthRangeDialog

_TITLE = "Export a web package"
_PROMPT = "Write a folder holding one page per month, plus an index linking them."
_PACKAGE_TITLE = "Bank balance projection"
_CHOOSE_FOLDER = "Choose where to put the package"


class GraphPackageExportMixin:
    """The multi-month package export for `GraphView`."""

    def _export_package(self) -> None:
        dialog = MonthRangeDialog(
            self, anchor=self.current_month, title=_TITLE, prompt=_PROMPT
        )
        if dialog.exec() != MonthRangeDialog.Accepted:
            return
        start, end = dialog.selected_range()
        months = self.budget_service.get_projection_months(start=start, end=end)
        if not months:
            QMessageBox.information(
                self, "Nothing to export", "That range contains no months."
            )
            return

        files = build_package(
            title=_PACKAGE_TITLE,
            months=months,
            series_by_month=self._series_by_month(months),
            recorded_balance_pence=self.budget_service.get_bank_balance().pence,
        )
        folder = self._chosen_folder(package_folder_name(months))
        if folder is None:
            return
        self._write_package(folder, files)

    def _series_by_month(self, months) -> dict:
        """The day-by-day bank series for each month, keyed by (year, month).

        Derived here rather than inside the report because the report layer
        holds no service: it is given figures and turns them into markup, which
        is what lets it be tested without a database.
        """
        series = {}
        for month in months:
            year_month = YearMonth(month.year, month.month)
            summary = self.budget_service.get_month_summary(year_month=year_month)
            series[(month.year, month.month)] = [
                self.budget_service.get_bank_graph_series(
                    year_month=year_month, summary=summary
                )
            ]
        return series

    def _chosen_folder(self, suggested: str):
        """Ask where the package goes; None when the user backs out.

        A folder that already exists is confirmed rather than silently written
        into, because the pages carry dated names and an older export of an
        overlapping range would be partly overwritten and partly left, which
        is a folder describing two different exports at once.
        """
        parent = QFileDialog.getExistingDirectory(
            self, _CHOOSE_FOLDER, str(default_downloads_dir())
        )
        if not parent:
            return None
        folder = Path(parent) / suggested
        if folder.exists():
            existing = len(list(folder.glob("*.html")))
            reply = QMessageBox.question(
                self,
                "Folder Already Exists",
                f"{folder.name} is already there, holding {existing} page(s).\n\n"
                "Writing this package will replace any page it covers and "
                "leave the rest. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return None
        return folder

    def _write_package(self, folder: Path, files) -> None:
        """Write every page, then say where the index is."""
        try:
            folder.mkdir(parents=True, exist_ok=True)
            for file in files:
                (folder / file.name).write_text(file.html, encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, "Export Failed", str(exc))
            return
        QMessageBox.information(
            self,
            "Export Successful",
            f"{len(files)} page(s) written to:\n{folder}\n\n"
            f"Open {INDEX_NAME} to start.",
        )
