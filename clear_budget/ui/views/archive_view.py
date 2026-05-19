"""Archive view widget - displays historical month data and trends."""

import shutil
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QFileDialog,
    QMessageBox,
)
from PySide6.QtCore import Qt

from clear_budget.application.services.budget_service import BudgetService
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.ui.widgets.archive_detail_dialog import ArchiveDetailDialog
from clear_budget.shared.config import Config


class ArchiveView(QWidget):
    """Displays historical month summaries and solvency trends."""

    def __init__(self, budget_service: BudgetService) -> None:
        """Initialize archive view widget."""
        super().__init__()
        self.budget_service = budget_service
        self.init_ui()
        self.on_load_history()

    def init_ui(self) -> None:
        """Build archive view layout."""
        layout = QVBoxLayout()

        self.archive_table = QTableWidget()
        self.archive_table.setColumnCount(5)
        self.archive_table.setHorizontalHeaderLabels(
            ["Month", "Income", "Bills", "Balance", "Status"]
        )
        self.archive_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.archive_table.verticalHeader().setStyleSheet("QHeaderView::section { color: #34d399; }")
        self.archive_table.verticalHeader().sectionClicked.connect(self.on_row_header_click)
        layout.addWidget(self.archive_table)

        btn_layout = QHBoxLayout()
        export_db_btn = QPushButton("Export Database")
        import_db_btn = QPushButton("Import Database")
        btn_layout.addWidget(export_db_btn)
        btn_layout.addWidget(import_db_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

        export_db_btn.clicked.connect(self.on_export_database)
        import_db_btn.clicked.connect(self.on_import_database)
        self.months_by_row = {}

    def on_row_header_click(self, row: int) -> None:
        """Handle pencil icon click on row header to show details."""
        if row in self.months_by_row:
            month, summary = self.months_by_row[row]
            dialog = ArchiveDetailDialog(self, month, summary)
            dialog.exec()

    def on_load_history(self) -> None:
        """Load recorded months from database."""
        recorded_months = self.budget_service.get_recorded_months()
        self.load_history(recorded_months)

    _REQUIRED_SCHEMA: dict[str, set[str]] = {
        "bills": {"amount_pence", "payment_method_id", "category", "bill_type", "active"},
        "income_sources": {"amount_pence", "is_reliable", "day_of_month", "active"},
        "credit_cards": {"credit_limit_pence", "current_balance_used_pence", "payment_due_day", "active"},
        "payment_methods": {"name", "type"},
        "settings": {"key", "value"},
        "bill_month_overrides": {"bill_id", "year", "month", "amount_pence"},
        "bill_month_skips": {"bill_id", "year", "month"},
    }

    def _validate_db(self, path: Path) -> str | None:
        """Return an error string if path is not a valid ClearBudget database, else None."""
        import sqlite3
        try:
            conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {r["name"] for r in cursor.fetchall()}

            missing_tables = set(self._REQUIRED_SCHEMA) - tables
            if missing_tables:
                conn.close()
                return f"Not a ClearBudget database — missing tables: {', '.join(sorted(missing_tables))}"

            for table, required_cols in self._REQUIRED_SCHEMA.items():
                cursor.execute(f"PRAGMA table_info({table})")
                present_cols = {r["name"] for r in cursor.fetchall()}
                missing_cols = required_cols - present_cols
                if missing_cols:
                    conn.close()
                    return (
                        f"Not a ClearBudget database — table '{table}' missing columns: "
                        f"{', '.join(sorted(missing_cols))}"
                    )

            conn.close()
        except sqlite3.DatabaseError as exc:
            return f"Not a valid SQLite database: {exc}"
        except Exception as exc:
            return f"Could not open file: {exc}"
        return None

    def on_export_database(self) -> None:
        """Copy the active database to a user-chosen backup location."""
        db_path = Config.default().db_path
        dest, _ = QFileDialog.getSaveFileName(
            self,
            "Export Database",
            str(Path.home() / "clearbudget_backup.db"),
            "ClearBudget Database (*.db)",
        )
        if not dest:
            return
        dest_path = Path(dest)
        if dest_path.suffix.lower() != ".db":
            dest_path = dest_path.with_suffix(".db")
        try:
            shutil.copy2(db_path, dest_path)
            QMessageBox.information(
                self,
                "Export Successful",
                f"Database exported to:\n{dest_path}",
            )
        except OSError as exc:
            QMessageBox.critical(self, "Export Failed", str(exc))

    def on_import_database(self) -> None:
        """Replace the active database with a user-chosen backup file."""
        db_path = Config.default().db_path
        src, _ = QFileDialog.getOpenFileName(
            self,
            "Import Database",
            str(Path.home()),
            "ClearBudget Database (*.db)",
        )
        if not src:
            return
        src_path = Path(src)
        if src_path.resolve() == db_path.resolve():
            QMessageBox.warning(self, "Import", "Selected file is the active database — nothing to import.")
            return

        has_data = False
        if db_path.exists():
            try:
                cursor = self.budget_service.bill_repo.conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM bills")
                has_data = cursor.fetchone()[0] > 0
            except Exception:
                has_data = True

        if has_data:
            reply = QMessageBox.question(
                self,
                "Overwrite Existing Data?",
                "The active database already contains data.\n\n"
                "Importing will permanently replace all bills, income sources, credit cards, "
                "overrides and settings with the contents of the selected file.\n\n"
                "This cannot be undone. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        validation_error = self._validate_db(src_path)
        if validation_error:
            QMessageBox.critical(self, "Invalid Database", f"Cannot import — file is not a valid ClearBudget database.\n\n{validation_error}")
            return

        try:
            shutil.copy2(src_path, db_path)
            QMessageBox.information(
                self,
                "Import Successful",
                "Database imported successfully.\n\nPlease restart ClearBudget to load the new data.",
            )
        except OSError as exc:
            QMessageBox.critical(self, "Import Failed", str(exc))

    def load_history(self, months: list[YearMonth]) -> None:
        """Load historical months into table."""
        self.archive_table.setRowCount(0)
        self.months_by_row = {}

        for month in months:
            summary = self.budget_service.get_month_summary(year_month=month)

            row = self.archive_table.rowCount()
            self.archive_table.insertRow(row)
            self.archive_table.setVerticalHeaderItem(row, QTableWidgetItem("📝"))
            self.months_by_row[row] = (month, summary)

            self.archive_table.setItem(row, 0, QTableWidgetItem(str(month)))
            self.archive_table.setItem(row, 1, QTableWidgetItem(str(summary.total_income)))
            self.archive_table.setItem(row, 2, QTableWidgetItem(str(summary.total_bills)))
            self.archive_table.setItem(row, 3, QTableWidgetItem(str(summary.balance)))

            status = "✓ Solvent" if summary.balance.pence >= 0 else "✗ Deficit"
            self.archive_table.setItem(row, 4, QTableWidgetItem(status))
