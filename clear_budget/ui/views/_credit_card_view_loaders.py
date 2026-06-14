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

from clear_budget.domain.services.credit_limit_schedule import (
    effective_credit_limit_pence,
    month_end_effective_limit_pence,
)
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.ui import ui_scale
from clear_budget.ui.utils.format_helpers import MONTH_NAMES

_PROJECTION_MONTHS = 6

# The native Windows 11 style draws a rounded frame around any styled QLabel; on the
# dark card those frame corners show through as ugly "black notches". A stylesheet set
# on the *parent* container outranks the app-global stylesheet, so cascading these
# declarations down from the field container reliably suppresses the frame on its
# labels (a global QLabel rule does not). The card-name label sits directly on the
# card, so it carries the declarations itself.
_FLAT_DECLS = "background: transparent; border: none;"
_FLAT_LABEL = " " + _FLAT_DECLS  # append to a label's own style
_FLAT_CONTAINER = "QWidget { " + _FLAT_DECLS + " }"  # cascades to child labels


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
            empty_label.setStyleSheet("color: #6b7280;" + _FLAT_LABEL)
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
                # The limit a card carries entering a future month is its
                # start-of-month effective limit; a mid-month change is flagged
                # by the pill rather than applied to the whole month.
                display_limit_pence = effective_credit_limit_pence(
                    card=card,
                    as_of=_date(self.current_month.year, self.current_month.month, 1),
                )
            elif self.current_month == _today_ym:
                display_used = self.budget_service.get_live_card_balance(card=card)
                display_limit_pence = card.credit_limit.pence
            else:
                display_used = card.current_balance_used
                display_limit_pence = card.credit_limit.pence
            display_util = (
                display_used.pence / display_limit_pence * 100
                if display_limit_pence
                else 0.0
            )
            display_available = Amount(
                pence=max(0, display_limit_pence - display_used.pence)
            )
            display_limit = Amount(pence=display_limit_pence)

            # Flag a still-upcoming change on any month it has not yet taken
            # effect by, measured from today on the live month and from the
            # first of the month on a future month, so the month it lands on
            # shows the pill too.
            upcoming_changes = []
            if self.current_month == _today_ym:
                ref_key = (_today.year, _today.month, _today.day)
                upcoming_changes = [
                    c for c in card.scheduled_limit_changes if c.sort_key > ref_key
                ]
            elif self.current_month > _today_ym:
                ref_key = (self.current_month.year, self.current_month.month, 1)
                upcoming_changes = [
                    c for c in card.scheduled_limit_changes if c.sort_key > ref_key
                ]

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
                display_limit=display_limit,
                display_available=display_available,
                display_util=display_util,
                upcoming_changes=upcoming_changes,
                due_color=due_color,
                status=status,
                status_color=status_color,
            )
            self.cards_layout.addWidget(frame)

        self.cards_layout.addStretch(1)
        self._build_projection_strip()

    def _field_widget(
        self,
        label: str,
        value: str,
        color: str | None = None,
        pills: list | None = None,
    ) -> QWidget:
        container = QWidget()
        container.setStyleSheet(_FLAT_CONTAINER)
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
        for pill_text, pill_color in pills or []:
            pill = QLabel(pill_text)
            pill.setStyleSheet(
                ui_scale.style(
                    "font-size: 11px; font-weight: 600; color: #ffffff;"
                    f" background-color: {pill_color};"
                    " border-radius: 4px; padding: 1px 6px;"
                )
            )
            pill.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
            pill_row = QHBoxLayout()
            pill_row.setContentsMargins(0, 3, 0, 0)
            pill_row.addWidget(pill)
            pill_row.addStretch(1)
            col.addLayout(pill_row)
        return container

    def _limit_change_pills(self, reference_limit_pence, upcoming_changes):
        """Return a list of (text, color) pills, one per upcoming limit change,
        each arrow judged against the running limit. Blue for an increase, amber
        for a decrease."""
        running = reference_limit_pence
        pills = []
        for change in upcoming_changes:
            increase = change.new_limit.pence >= running
            arrow = "↑" if increase else "↓"
            month_abbr = MONTH_NAMES[change.effective_month][:3]
            pills.append(
                (
                    f"{arrow} {change.new_limit} · "
                    f"{change.effective_day} {month_abbr}",
                    "#1e3a8a" if increase else "#78350f",
                )
            )
            running = change.new_limit.pence
        return pills

    def _build_card_frame(
        self,
        *,
        card,
        state,
        display_used: Amount,
        display_limit: Amount,
        display_available: Amount,
        display_util: float,
        upcoming_changes: list,
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
        name_label.setStyleSheet(
            ui_scale.style("font-size: 16px; font-weight: 700;" + _FLAT_LABEL)
        )
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

        limit_pills = self._limit_change_pills(display_limit.pence, upcoming_changes)

        overview_grid = QGridLayout()
        overview_grid.setHorizontalSpacing(ui_scale.px(24))
        overview_fields = [
            ("Limit", str(display_limit), None, limit_pills),
            ("Used", str(display_used), None, None),
            ("Available", str(display_available), None, None),
            ("Util %", f"{display_util:.1f}%", None, None),
            ("Due Day", str(card.payment_due_day), due_color, None),
            ("Interest %", interest_str, None, None),
            ("Fixed Min", fixed_min_str, None, None),
            ("Expiry", expiry_str, None, None),
        ]
        for idx, (label, value, color, pills) in enumerate(overview_fields):
            overview_grid.addWidget(
                self._field_widget(label, value, color, pills), 0, idx
            )
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
        row_months = []
        cursor = today_ym
        for _ in range(_PROJECTION_MONTHS):
            month_labels.append(f"{MONTH_NAMES[cursor.month][:3]} {cursor.year}")
            row_months.append(cursor)
            cursor = cursor.next_month()
        self.projection_table.setVerticalHeaderLabels(month_labels)
        # Lock the strip to exactly its rows now the columns exist, so the header
        # height is real. It then shows every month with no scrollbar and stays
        # compact beneath the card list.
        _row_h = self.projection_table.verticalHeader().defaultSectionSize()
        _hdr_h = self.projection_table.horizontalHeader().sizeHint().height()
        _frame = self.projection_table.frameWidth() * 2
        self.projection_table.setFixedHeight(
            _hdr_h + _row_h * _PROJECTION_MONTHS + _frame
        )

        _red_threshold_pence = 10_000
        _amber_threshold_pence = 25_000
        for row_idx, month_states in enumerate(month_states_list):
            row_ym = row_months[row_idx]
            for col_idx, state in enumerate(month_states):
                closing = state.closing_balance.pence
                limit_pence = month_end_effective_limit_pence(
                    card=state.card, year=row_ym.year, month=row_ym.month
                )
                available = limit_pence - closing
                cell = QTableWidgetItem(str(state.closing_balance))
                cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if available <= _red_threshold_pence:
                    cell.setBackground(QColor("#7f1d1d"))
                elif available <= _amber_threshold_pence:
                    cell.setBackground(QColor("#f59e0b"))
                else:
                    cell.setBackground(QColor("#14532d"))
                self.projection_table.setItem(row_idx, col_idx, cell)
