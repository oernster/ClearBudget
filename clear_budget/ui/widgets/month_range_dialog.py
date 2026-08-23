"""MonthRangeDialog - pick the first and last month of a projected export.

Two month pickers and nothing else. It opens focused on the first month's
picker, ready to type; Escape closes; the ring is the dialog's own tab
order (the application navigator hands a modal its own arrows). Export stays
disabled while the range runs backwards, so an impossible range cannot be
submitted rather than being reported afterwards.
"""

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.ui import ui_scale
from clear_budget.ui.widgets.first_stop_dialog import FirstStopDialog

_MONTH_NAMES = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
_DIALOG_MIN_WIDTH = 380
# How far either side of the anchor month a range may be picked. Wide enough
# for a mortgage-length view, bounded so the picker stays usable.
_YEARS_EITHER_SIDE = 10
# Default span when the dialog opens: a year reads as a plan without being a
# wall of months.
_DEFAULT_SPAN_MONTHS = 11
_MONTHS_IN_YEAR = 12


def _shift(year_month: YearMonth, months: int) -> YearMonth:
    """`year_month` moved on by `months`, carrying the year over."""
    index = (year_month.year * _MONTHS_IN_YEAR) + (year_month.month - 1) + months
    return YearMonth(index // _MONTHS_IN_YEAR, (index % _MONTHS_IN_YEAR) + 1)


class MonthRangeDialog(FirstStopDialog):
    """Asks for the first and last month of a projection."""

    def __init__(self, parent=None, *, anchor: YearMonth) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export projection")
        self.setModal(True)
        self.setMinimumWidth(ui_scale.px(_DIALOG_MIN_WIDTH))
        self._anchor = anchor

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Project the bank balance across a range of months."))
        form = QFormLayout()
        self.from_month, self.from_year = self._picker(anchor)
        self.to_month, self.to_year = self._picker(_shift(anchor, _DEFAULT_SPAN_MONTHS))
        form.addRow("First month", self._row(self.from_month, self.from_year))
        form.addRow("Last month", self._row(self.to_month, self.to_year))
        layout.addLayout(form)

        self.warning = QLabel("")
        self.warning.setWordWrap(True)
        layout.addWidget(self.warning)

        buttons = QHBoxLayout()
        self.export_btn = QPushButton("Export…")
        self.export_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons.addStretch()
        buttons.addWidget(cancel_btn)
        buttons.addWidget(self.export_btn)
        layout.addLayout(buttons)

        for combo in (self.from_month, self.to_month):
            combo.currentIndexChanged.connect(self._refresh)
        for spin in (self.from_year, self.to_year):
            spin.valueChanged.connect(self._refresh)
        self._refresh()

    def _picker(self, at: YearMonth) -> tuple:
        month = QComboBox()
        month.addItems(_MONTH_NAMES)
        month.setCurrentIndex(at.month - 1)
        year = QSpinBox()
        year.setRange(
            self._anchor.year - _YEARS_EITHER_SIDE,
            self._anchor.year + _YEARS_EITHER_SIDE,
        )
        year.setValue(at.year)
        return month, year

    @staticmethod
    def _row(month: QComboBox, year: QSpinBox) -> QWidget:
        """Month and year side by side as one form row."""
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(month, 1)
        row.addWidget(year)
        return container

    def selected_range(self) -> tuple[YearMonth, YearMonth]:
        """The chosen (first, last) months."""
        return (
            YearMonth(self.from_year.value(), self.from_month.currentIndex() + 1),
            YearMonth(self.to_year.value(), self.to_month.currentIndex() + 1),
        )

    def _refresh(self) -> None:
        start, end = self.selected_range()
        backwards = (end.year, end.month) < (start.year, start.month)
        self.export_btn.setEnabled(not backwards)
        self.warning.setText("The last month is before the first." if backwards else "")
