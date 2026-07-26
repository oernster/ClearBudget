"""MonthGraphDialog - bar/line graph of the month, opened from the nav icon.

Shows the viewed month's day-by-day series for the page it was opened from
(the bank balance on Monthly Budget, one series per card on Credit Cards).
A pilot button switches between bar and line rendering. Neutral start,
Escape closes, and the ring is Tab/Right forward with the pilot and Close
buttons as the stops.
"""

from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout

from clear_budget.ui import ui_scale
from clear_budget.ui.widgets._line_bar_chart import MODE_BAR, MODE_LINE, LineBarChart
from clear_budget.ui.widgets.neutral_dialog import NeutralDialog

_DIALOG_MIN_WIDTH = 760
_DIALOG_MIN_HEIGHT = 440

_PILOT_TO_LINE = "Switch to line graph"
_PILOT_TO_BAR = "Switch to bar graph"


class MonthGraphDialog(NeutralDialog):
    """Displays one month's series as a bar or line graph."""

    def __init__(self, parent=None, *, title: str, series) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumSize(
            ui_scale.px(_DIALOG_MIN_WIDTH), ui_scale.px(_DIALOG_MIN_HEIGHT)
        )
        self._series = list(series)
        self._mode = MODE_BAR

        layout = QVBoxLayout(self)
        self.chart = LineBarChart(self)
        self.chart.set_data(self._series, self._mode)
        layout.addWidget(self.chart, 1)

        button_row = QHBoxLayout()
        self.pilot_btn = QPushButton(_PILOT_TO_LINE)
        self.pilot_btn.clicked.connect(self._toggle_mode)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_row.addWidget(self.pilot_btn)
        button_row.addStretch()
        button_row.addWidget(close_btn)
        layout.addLayout(button_row)

    def _toggle_mode(self) -> None:
        self._mode = MODE_LINE if self._mode == MODE_BAR else MODE_BAR
        self.pilot_btn.setText(
            _PILOT_TO_LINE if self._mode == MODE_BAR else _PILOT_TO_BAR
        )
        self.chart.set_data(self._series, self._mode)
