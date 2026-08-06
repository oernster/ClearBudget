"""The six-month credit headroom strip shown beneath the card list.

Split out of `_credit_card_view_loaders.py`, which was at 399 lines and so one
edit away from failing the size cap. The strip is a cohesive concern: it reads
only the projection table and the budget service, and it owns the headroom
banding that colours each cell.
"""

from datetime import date as _date

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QTableWidgetItem

from clear_budget.domain.services.credit_limit_schedule import (
    month_end_effective_limit_pence,
)
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.ui import theme
from clear_budget.ui.utils.format_helpers import MONTH_NAMES

_PROJECTION_MONTHS = 6

# Remaining headroom (pence) banding a projection cell: tight, worth watching,
# or ample. The colours themselves come from the theme's cell_* tokens.
_HEADROOM_TIGHT_PENCE = 10_000
_HEADROOM_WATCH_PENCE = 25_000


class CreditCardProjectionStripMixin:
    """_build_projection_strip for CreditCardView."""

    def _build_projection_strip(self) -> None:
        _today = _date.today()  # noqa: DTZ011 (local date)
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

        colours = theme.colours()
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
                if available <= _HEADROOM_TIGHT_PENCE:
                    band = "tight"
                elif available <= _HEADROOM_WATCH_PENCE:
                    band = "watch"
                else:
                    band = "ample"
                cell.setBackground(QColor(colours[f"cell_{band}_bg"]))
                cell.setForeground(QColor(colours[f"cell_{band}_fg"]))
                self.projection_table.setItem(row_idx, col_idx, cell)
