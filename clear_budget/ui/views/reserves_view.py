"""The Reserves view: money committed or expected that no month's table shows.

Safe to Spend Today counts everything above the buffer as spendable; the
projection only knows about the bills that have been entered. An annual
premium four months out is invisible until the month it lands in, so the
figure above it confidently offers money that is already spoken for.

A reserve fixes that by ACCRUAL rather than by a longer projection: the
premium is held back across the months before it lands, which makes a distant
bill honest inside the horizon that already exists. Nothing is moved anywhere
and no separate account is assumed; this only changes what the application is
willing to call spendable.

The page reports and never encourages. There is no progress bar, no goal and
no congratulation: a commitment is a bill that has not asked yet.
"""

from datetime import date

from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from clear_budget.application.services.budget_service import BudgetService
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.ui import label_roles, ui_scale
from clear_budget.ui.utils import reserves_text as copy
from clear_budget.application.formatting import money_from_pence
from clear_budget.ui.utils.format_helpers import (
    MONTH_NAMES,
    build_centered_nav_header,
    nav_glyph_height,
)
from clear_budget.ui.utils.table_focus import keyboard_only_focus
from clear_budget.ui.utils.view_buttons import build_view_buttons, ring_view_stops
from clear_budget.ui.widgets._tray_buttons import (
    build_bank_button,
    build_budgets_button,
    build_info_button,
    build_save_load_buttons,
    build_tray_separator,
)
from clear_budget.ui.widgets.commitment_dialog import CommitmentDialog

_BUFFER_FIELD_WIDTH_PX = 120
_TABLE_MIN_HEIGHT_PX = 160
_ACTIVE_COLUMN = 7


def _month_name(year: int, month: int) -> str:
    return f"{MONTH_NAMES[month]} {year}"


class ReservesView(QWidget):
    """What is being held back, with the obligations it is held for."""

    def __init__(self, budget_service: BudgetService, current_month: YearMonth) -> None:
        super().__init__()
        self.budget_service = budget_service
        self._current_month = current_month
        self._rows: list = []
        self._build_ui()
        self.refresh()

    # ---- construction -------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout()

        self.prev_btn = QPushButton("← Previous")
        self.next_btn = QPushButton("Next →")
        glyph_h = nav_glyph_height(self.prev_btn)
        self.load_btn, self.save_btn = build_save_load_buttons(glyph_h)
        self.budgets_btn = build_budgets_button(glyph_h)
        separator, self.bank_btn = build_bank_button(glyph_h)
        self.info_btn = build_info_button(glyph_h)
        self.view_btns = build_view_buttons(glyph_h)
        self.nav_header, self.month_label, self.theme_btn = build_centered_nav_header(
            _month_name(self._current_month.year, self._current_month.month),
            prev_btn=self.prev_btn,
            next_btn=self.next_btn,
            leading=(
                self.load_btn,
                self.save_btn,
                self.budgets_btn,
                separator,
                self.bank_btn,
            ),
            views=self.view_btns[:-1],
            pre_theme=(build_tray_separator(glyph_h), self.view_btns[-1]),
            trailing=(self.info_btn,),
        )

        buffer_row = QHBoxLayout()
        self.buffer_check = QCheckBox(copy.BUFFER_LABEL)
        self.buffer_check.setToolTip(copy.BUFFER_TOOLTIP)
        self.buffer_edit = QLineEdit()
        self.buffer_edit.setFixedWidth(ui_scale.px(_BUFFER_FIELD_WIDTH_PX))
        self.buffer_edit.setPlaceholderText("0.00")
        buffer_row.addWidget(self.buffer_check)
        buffer_row.addWidget(self.buffer_edit)
        buffer_row.addStretch(1)
        layout.addLayout(buffer_row)
        self.buffer_check.toggled.connect(self._save_buffer)
        self.buffer_edit.editingFinished.connect(self._save_buffer)

        self.verdict_label = QLabel("")
        self.verdict_label.setObjectName(label_roles.BODY)
        self.verdict_label.setWordWrap(True)
        layout.addWidget(self.verdict_label)

        self.cost_label = QLabel("")
        self.cost_label.setObjectName(label_roles.BODY)
        self.cost_label.setWordWrap(True)
        layout.addWidget(self.cost_label)

        self.empty_label = QLabel("")
        self.empty_label.setObjectName(label_roles.BODY_DETAIL)
        self.empty_label.setWordWrap(True)
        layout.addWidget(self.empty_label)

        self.section_label = QLabel(copy.SECTION_WHAT_FOR)
        self.section_label.setObjectName(label_roles.SECTION_TITLE)
        layout.addWidget(self.section_label)

        self.table = QTableWidget()
        self.table.setColumnCount(len(copy.TABLE_HEADINGS))
        self.table.setHorizontalHeaderLabels(list(copy.TABLE_HEADINGS))
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setMinimumHeight(ui_scale.px(_TABLE_MIN_HEIGHT_PX))
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        keyboard_only_focus(self.table)
        layout.addWidget(self.table)

        button_row = QHBoxLayout()
        self.add_btn = QPushButton(copy.ADD_BUTTON)
        self.edit_btn = QPushButton(copy.EDIT_BUTTON)
        self.delete_btn = QPushButton(copy.DELETE_BUTTON)
        self.add_btn.clicked.connect(self._on_add)
        self.edit_btn.clicked.connect(self._on_edit)
        self.delete_btn.clicked.connect(self._on_delete)
        button_row.addWidget(self.add_btn)
        button_row.addWidget(self.edit_btn)
        button_row.addWidget(self.delete_btn)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        self.everyday_title = QLabel(copy.SECTION_EVERYDAY)
        self.everyday_title.setObjectName(label_roles.SECTION_TITLE)
        layout.addWidget(self.everyday_title)
        self.everyday_label = QLabel(copy.EVERYDAY_UNSET)
        self.everyday_label.setObjectName(label_roles.BODY_DETAIL)
        self.everyday_label.setWordWrap(True)
        layout.addWidget(self.everyday_label)
        self.everyday_btn = QPushButton(copy.EVERYDAY_BUTTON)
        # Present but not yet wired: the mechanism lands in a later release
        # and the section is shown anyway, because its absence IS the
        # assumption every other figure rests on.
        self.everyday_btn.setEnabled(False)
        self.everyday_btn.setToolTip(copy.EVERYDAY_LATER)
        everyday_row = QHBoxLayout()
        everyday_row.addWidget(self.everyday_btn)
        everyday_row.addStretch(1)
        layout.addLayout(everyday_row)

        self.footer_label = QLabel(copy.FOOTER)
        self.footer_label.setObjectName(label_roles.BODY_DETAIL)
        self.footer_label.setWordWrap(True)
        layout.addWidget(self.footer_label)
        layout.addStretch(1)
        self.setLayout(layout)

    # ---- data ---------------------------------------------------------------
    def refresh(self) -> None:
        """Rebuild every figure from the service."""
        enabled, buffer_amount = self.budget_service.get_recommendation_buffer()
        self.buffer_check.setChecked(enabled)
        self.buffer_edit.setText(f"{buffer_amount.pence / 100:.2f}")
        self.buffer_edit.setEnabled(enabled)

        self._rows = self.budget_service.get_reserve_rows()
        self._fill_table()
        self._fill_verdict()

    def _fill_verdict(self) -> None:
        """The two lines that say what is held back and what it costs."""
        count = len(self._rows)
        if count == 0:
            self.verdict_label.setText(copy.EMPTY_HEADING)
            self.cost_label.setText("")
            self.empty_label.setText(f"{copy.EMPTY_BODY}\n\n{copy.EMPTY_PROMPT}")
            self.empty_label.setVisible(True)
            self.table.setVisible(False)
            self.section_label.setVisible(False)
            self.edit_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            return
        total = self.budget_service.get_reserved_today_pence()
        self.verdict_label.setText(
            copy.verdict_line(total=money_from_pence(total), count=count)
        )
        self.cost_label.setText(
            copy.cost_line(
                amount=money_from_pence(self.budget_service.get_reserve_cost_pence())
            )
        )
        self.empty_label.setVisible(False)
        self.table.setVisible(True)
        self.section_label.setVisible(True)
        self.edit_btn.setEnabled(True)
        self.delete_btn.setEnabled(True)

    def _fill_table(self) -> None:
        """One row per commitment, in the order the service gave them."""
        self.table.setRowCount(len(self._rows))
        for index, row in enumerate(self._rows):
            commitment = row.commitment
            due = commitment.due_date
            values = (
                commitment.name,
                money_from_pence(commitment.amount.pence),
                f"{due.day} {MONTH_NAMES[due.month][:3]} {due.year}",
                copy.repeats_label(months=commitment.recurrence.months),
                money_from_pence(row.monthly_pence),
                money_from_pence(row.held_pence),
                money_from_pence(row.outstanding_pence),
                "Yes" if commitment.active else "No",
            )
            for column, text in enumerate(values):
                item = QTableWidgetItem(text)
                self.table.setItem(index, column, item)
            if row.is_steep:
                note = copy.steep_note(
                    monthly=money_from_pence(row.monthly_pence),
                    natural=money_from_pence(row.natural_pence),
                    month_name=MONTH_NAMES[due.month],
                )
                self.table.item(index, 4).setToolTip(note)

    # ---- actions ------------------------------------------------------------
    def _save_buffer(self) -> None:
        """Store the buffer as typed; an unreadable figure is left alone."""
        self.buffer_edit.setEnabled(self.buffer_check.isChecked())
        try:
            pence = round(float(self.buffer_edit.text() or 0) * 100)
        except ValueError:
            return
        self.budget_service.set_recommendation_buffer(
            enabled=self.buffer_check.isChecked(), amount=Amount(pence=max(pence, 0))
        )

    def _selected_row(self):
        """The highlighted commitment; None when nothing is selected."""
        index = self.table.currentRow()
        if index < 0 or index >= len(self._rows):
            return None
        return self._rows[index]

    def _on_add(self) -> None:
        dialog = CommitmentDialog(self)
        if dialog.exec():
            self.budget_service.add_commitment(commitment=dialog.commitment())
            self.refresh()

    def _on_edit(self) -> None:
        row = self._selected_row()
        if row is None:
            return
        dialog = CommitmentDialog(self, commitment=row.commitment)
        if dialog.exec():
            self.budget_service.update_commitment(commitment=dialog.commitment())
            self.refresh()

    def _on_delete(self) -> None:
        """Removing is destructive, so it is named and confirmed first."""
        row = self._selected_row()
        if row is None:
            return
        answer = QMessageBox.question(
            self,
            copy.DELETE_BUTTON,
            copy.delete_question(name=row.commitment.name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.budget_service.delete_commitment(commitment_id=row.commitment.id)
            self.refresh()

    # ---- navigation ---------------------------------------------------------
    def set_month(self, year_month: YearMonth) -> None:
        """Follow the shared month label like every other view."""
        self._current_month = year_month
        self.month_label.setText(_month_name(year_month.year, year_month.month))

    def on_month_summary_updated(self, *_args) -> None:
        """Recompute when a bill or income changes on another view."""
        self.refresh()

    def nav_targets(self) -> list:
        """Ordered keyboard-ring stops: trays first, then the page's own."""
        others = ring_view_stops(self.view_btns[:-1])
        archive_stop = ring_view_stops(self.view_btns[-1:])
        return [
            self.prev_btn,
            self.next_btn,
            self.load_btn,
            self.save_btn,
            self.budgets_btn,
            self.bank_btn,
            *others,
            *archive_stop,
            self.theme_btn,
            self.info_btn,
            self.buffer_check,
            self.buffer_edit,
            self.table,
            self.add_btn,
            self.edit_btn,
            self.delete_btn,
        ]

    def restyle(self) -> None:
        """Recompute after a theme switch; the figures carry no colours."""
        self.refresh()


def _today() -> date:
    """Local today, kept here so the view never reads a clock inline."""
    return date.today()  # noqa: DTZ011
