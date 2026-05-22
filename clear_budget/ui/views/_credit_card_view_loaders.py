"""Loader mixin for CreditCardView — load_cards and projection strip extracted."""

from datetime import date as _date

from PySide6.QtWidgets import QTableWidgetItem
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.ui.utils.format_helpers import MONTH_NAMES

_PROJECTION_MONTHS = 6


class CreditCardViewLoaderMixin:
    """load_cards and _build_projection_strip for CreditCardView."""

    def load_cards(self) -> None:
        self.cards_table.blockSignals(True)
        self.cards_table.setRowCount(0)
        self.cards_table.blockSignals(False)

        cards = self.budget_service.get_credit_cards(include_inactive=True)
        if not cards:
            empty_item = QTableWidgetItem("No credit cards configured")
            empty_item.setForeground(Qt.GlobalColor.gray)
            self.cards_table.insertRow(0)
            self.cards_table.setItem(0, 0, empty_item)
            return

        monthly_states = {
            s.card.id: s
            for s in self.budget_service.get_card_monthly_states(
                year_month=self.current_month
            )
        }

        _today = _date.today()
        _today_ym = YearMonth(_today.year, _today.month)
        self.cards_table.blockSignals(True)
        for card in cards:
            row = self.cards_table.rowCount()
            self.cards_table.insertRow(row)
            self.cards_table.setVerticalHeaderItem(row, QTableWidgetItem("📝"))

            _editable = (
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsEditable
            )
            name_item = QTableWidgetItem(card.name)
            name_item.setData(Qt.ItemDataRole.UserRole, card.id)
            name_item.setFlags(_editable)
            self.cards_table.setItem(row, 0, name_item)
            limit_item = QTableWidgetItem(str(card.credit_limit))
            limit_item.setFlags(_editable)
            self.cards_table.setItem(row, 1, limit_item)
            state_snapshot = monthly_states.get(card.id)
            if state_snapshot and self.current_month > _today_ym:
                display_used = state_snapshot.closing_balance
                display_util = (
                    state_snapshot.closing_balance.pence / card.credit_limit.pence * 100
                    if card.credit_limit.pence
                    else 0.0
                )
            else:
                display_used = card.current_balance_used
                display_util = card.utilization_percent
            display_available = Amount(
                pence=max(0, card.credit_limit.pence - display_used.pence)
            )

            used_item = QTableWidgetItem(str(display_used))
            used_item.setFlags(_editable)
            self.cards_table.setItem(row, 2, used_item)
            self.cards_table.setItem(row, 3, QTableWidgetItem(str(display_available)))

            util_item = QTableWidgetItem(f"{display_util:.1f}%")
            self.cards_table.setItem(row, 4, util_item)

            due_item = QTableWidgetItem(str(card.payment_due_day))
            due_item.setFlags(_editable)
            if self.current_month == _today_ym:
                d, t = card.payment_due_day, _today.day
                if d < t:
                    due_item.setForeground(QColor("#9ca3af"))
                elif d == t:
                    due_item.setForeground(QColor("#f87171"))
                else:
                    due_item.setForeground(QColor("#34d399"))
            self.cards_table.setItem(row, 5, due_item)

            interest_str = (
                f"{card.interest_rate_apr:.2f}%" if card.interest_rate_apr else " - "
            )
            interest_item = QTableWidgetItem(interest_str)
            interest_item.setFlags(_editable)
            self.cards_table.setItem(row, 6, interest_item)

            if card.minimum_payment_pence is not None:
                min_pmt_str = str(Amount(pence=card.minimum_payment_pence))
            else:
                min_pmt_str = " - "
            min_item = QTableWidgetItem(min_pmt_str)
            min_item.setFlags(_editable)
            self.cards_table.setItem(row, 7, min_item)

            if card.card_expiry_month and card.card_expiry_year:
                expiry_str = (
                    f"{card.card_expiry_month:02d}/{card.card_expiry_year % 100:02d}"
                )
            else:
                expiry_str = " - "
            expiry_item = QTableWidgetItem(expiry_str)
            expiry_item.setFlags(_editable)
            self.cards_table.setItem(row, 8, expiry_item)

            status = self._get_status_text(display_util)
            status_item = QTableWidgetItem(status)
            status_color = self._get_status_color(status)
            status_item.setForeground(Qt.GlobalColor.white)
            status_item.setBackground(status_color)
            self.cards_table.setItem(row, 9, status_item)

            active_item = QTableWidgetItem()
            active_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsUserCheckable
            )
            active_item.setCheckState(
                Qt.CheckState.Checked if card.active == 1 else Qt.CheckState.Unchecked
            )
            active_item.setData(Qt.ItemDataRole.UserRole, card.id)
            self.cards_table.setItem(row, 10, active_item)

            state = monthly_states.get(card.id)
            if state:
                pdate = (
                    f" (paid day {state.payment_date})" if state.payment_date else ""
                )
                self.cards_table.setItem(row, 11, QTableWidgetItem(str(state.charges)))
                self.cards_table.setItem(
                    row, 12, QTableWidgetItem(f"{state.payment_received}{pdate}")
                )
                self.cards_table.setItem(
                    row, 13, QTableWidgetItem(str(state.monthly_interest))
                )
                min_due_item = QTableWidgetItem(str(state.minimum_payment))
                min_due_item.setFlags(_editable)
                self.cards_table.setItem(row, 14, min_due_item)
            else:
                for col in (11, 12, 13, 14):
                    self.cards_table.setItem(row, col, QTableWidgetItem("-"))

        self.cards_table.blockSignals(False)
        self._build_projection_strip()

    def _build_projection_strip(self) -> None:
        _today = _date.today()
        today_ym = YearMonth(_today.year, _today.month)
        month_states_list = self.budget_service.get_card_projection_months(
            start_month=today_ym, n_months=_PROJECTION_MONTHS
        )
        if not month_states_list or not month_states_list[0]:
            self.projection_table.setRowCount(0)
            self.projection_table.setColumnCount(0)
            return

        cards_in_strip = [ms.card for ms in month_states_list[0]]
        self.projection_table.setColumnCount(len(cards_in_strip))
        self.projection_table.setHorizontalHeaderLabels(
            [c.name for c in cards_in_strip]
        )
        self.projection_table.setRowCount(_PROJECTION_MONTHS)

        month_labels = []
        cursor = today_ym
        for _ in range(_PROJECTION_MONTHS):
            month_labels.append(f"{MONTH_NAMES[cursor.month][:3]} {cursor.year}")
            cursor = cursor.next_month()
        self.projection_table.setVerticalHeaderLabels(month_labels)

        _red_threshold_pence = 10_000
        _amber_threshold_pence = 25_000
        for row_idx, month_states in enumerate(month_states_list):
            for col_idx, state in enumerate(month_states):
                closing = state.closing_balance.pence
                available = state.card.credit_limit.pence - closing
                cell = QTableWidgetItem(str(state.closing_balance))
                cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if available <= _red_threshold_pence:
                    cell.setBackground(QColor("#7f1d1d"))
                elif available <= _amber_threshold_pence:
                    cell.setBackground(QColor("#f59e0b"))
                else:
                    cell.setBackground(QColor("#14532d"))
                self.projection_table.setItem(row_idx, col_idx, cell)
