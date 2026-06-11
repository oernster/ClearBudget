"""Loader mixin for CreditCardView - load_cards, card frames and projection strip."""

from datetime import date as _date

from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
    QLabel,
    QCheckBox,
    QPushButton,
    QTableWidgetItem,
    QSizePolicy,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.ui import ui_scale
from clear_budget.ui.utils.format_helpers import MONTH_NAMES

_PROJECTION_MONTHS = 6


class CreditCardViewLoaderMixin:
    """load_cards, _build_card_frame and _build_projection_strip for CreditCardView."""

    def load_cards(self) -> None:
        while self.cards_layout.count():
            taken = self.cards_layout.takeAt(0)
            widget = taken.widget()
            if widget is not None:
                widget.deleteLater()

        cards = self.budget_service.get_credit_cards(include_inactive=True)
        if not cards:
            empty_label = QLabel("No credit cards configured")
            empty_label.setStyleSheet("color: #6b7280;")
            self.cards_layout.addWidget(empty_label)
            self.cards_layout.addStretch(1)
            self._build_projection_strip()
            return

        monthly_states = {
            s.card.id: s
            for s in self.budget_service.get_card_monthly_states(
                year_month=self.current_month
            )
        }

        _today = _date.today()
        _today_ym = YearMonth(_today.year, _today.month)
        for card in cards:
            state = monthly_states.get(card.id)
            if state and self.current_month > _today_ym:
                display_used = state.closing_balance
                display_util = (
                    state.closing_balance.pence / card.credit_limit.pence * 100
                    if card.credit_limit.pence
                    else 0.0
                )
            elif self.current_month == _today_ym:
                display_used = self.budget_service.get_live_card_balance(card=card)
                display_util = (
                    display_used.pence / card.credit_limit.pence * 100
                    if card.credit_limit.pence
                    else 0.0
                )
            else:
                display_used = card.current_balance_used
                display_util = card.utilization_percent
            display_available = Amount(
                pence=max(0, card.credit_limit.pence - display_used.pence)
            )

            due_color = None
            if self.current_month == _today_ym:
                d, t = card.payment_due_day, _today.day
                if d < t:
                    due_color = "#9ca3af"
                elif d == t:
                    due_color = "#f87171"
                else:
                    due_color = "#34d399"

            status = self._get_status_text(display_util)
            status_color = self._get_status_color(status)

            frame = self._build_card_frame(
                card=card,
                state=state,
                display_used=display_used,
                display_available=display_available,
                display_util=display_util,
                due_color=due_color,
                status=status,
                status_color=status_color,
            )
            self.cards_layout.addWidget(frame)

        self.cards_layout.addStretch(1)
        self._build_projection_strip()

    def _field_widget(
        self, label: str, value: str, color: str | None = None
    ) -> QWidget:
        container = QWidget()
        col = QVBoxLayout(container)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        label_widget = QLabel(label)
        label_widget.setStyleSheet(ui_scale.style("font-size: 13px; color: #9ca3af;"))
        value_widget = QLabel(value)
        value_style = "font-size: 16px; font-weight: 600;"
        if color:
            value_style += f" color: {color};"
        value_widget.setStyleSheet(ui_scale.style(value_style))
        col.addWidget(label_widget)
        col.addWidget(value_widget)
        return container

    def _build_card_frame(
        self,
        *,
        card,
        state,
        display_used: Amount,
        display_available: Amount,
        display_util: float,
        due_color: str | None,
        status: str,
        status_color: QColor,
    ) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame { background-color: #242938; border: 1px solid #3a4156;"
            " border-radius: 8px; }"
        )
        outer = QVBoxLayout(frame)

        header = QHBoxLayout()
        active_cb = QCheckBox()
        active_cb.setToolTip("Active")
        active_cb.setChecked(card.active == 1)
        active_cb.setEnabled(not self.read_only)
        active_cb.toggled.connect(
            lambda checked, cid=card.id: self._on_card_active_toggled(cid, checked)
        )
        header.addWidget(active_cb)

        name_label = QLabel(card.name)
        name_label.setStyleSheet(ui_scale.style("font-size: 16px; font-weight: 700;"))
        header.addWidget(name_label)
        header.addStretch(1)

        status_label = QLabel(status)
        status_label.setStyleSheet(
            ui_scale.style(
                f"background-color: {status_color.name()}; color: white;"
                " padding: 2px 10px; border-radius: 4px; font-weight: 600;"
                " font-size: 12px;"
            )
        )
        header.addWidget(status_label)

        edit_btn = QPushButton("Edit")
        edit_btn.setEnabled(not self.read_only)
        edit_btn.clicked.connect(
            lambda _checked=False, cid=card.id: self.on_edit_card(cid)
        )
        header.addWidget(edit_btn)

        delete_btn = QPushButton("Delete")
        delete_btn.setEnabled(not self.read_only)
        delete_btn.setObjectName("DangerButton")
        delete_btn.clicked.connect(
            lambda _checked=False, cid=card.id, name=card.name: self.on_delete_card(
                cid, name
            )
        )
        header.addWidget(delete_btn)

        outer.addLayout(header)

        if card.interest_rate_apr:
            interest_str = f"{card.interest_rate_apr:.2f}%"
        else:
            interest_str = " - "

        if card.minimum_payment_pence is not None:
            fixed_min_str = str(Amount(pence=card.minimum_payment_pence))
        else:
            fixed_min_str = " - "

        if card.card_expiry_month and card.card_expiry_year:
            expiry_str = (
                f"{card.card_expiry_month:02d}/{card.card_expiry_year % 100:02d}"
            )
        else:
            expiry_str = " - "

        overview_grid = QGridLayout()
        overview_grid.setHorizontalSpacing(ui_scale.px(24))
        overview_fields = [
            ("Limit", str(card.credit_limit), None),
            ("Used", str(display_used), None),
            ("Available", str(display_available), None),
            ("Util %", f"{display_util:.1f}%", None),
            ("Due Day", str(card.payment_due_day), due_color),
            ("Interest %", interest_str, None),
            ("Fixed Min", fixed_min_str, None),
            ("Expiry", expiry_str, None),
        ]
        for idx, (label, value, color) in enumerate(overview_fields):
            overview_grid.addWidget(self._field_widget(label, value, color), 0, idx)
        overview_grid.setColumnStretch(len(overview_fields), 1)
        outer.addLayout(overview_grid)

        if state:
            pdate = f" (paid day {state.payment_date})" if state.payment_date else ""
            month_fields = [
                ("Month Charges", str(state.charges)),
                ("Payment Received", f"{state.payment_received}{pdate}"),
                ("Month Interest", str(state.monthly_interest)),
                ("Min Payment Due", str(state.minimum_payment)),
            ]
        else:
            month_fields = [
                ("Month Charges", "-"),
                ("Payment Received", "-"),
                ("Month Interest", "-"),
                ("Min Payment Due", "-"),
            ]

        month_grid = QGridLayout()
        month_grid.setHorizontalSpacing(ui_scale.px(24))
        for idx, (label, value) in enumerate(month_fields):
            month_grid.addWidget(self._field_widget(label, value), 0, idx)
        month_grid.setColumnStretch(len(month_fields), 1)
        outer.addLayout(month_grid)

        frame.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        return frame

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
