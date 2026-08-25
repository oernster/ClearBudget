"""What the Reserves page WRITES into the widgets its view builds.

Split from `reserves_view` so that file builds the page and this one fills it,
the same shape the month and solvency pages already have. One concern per
file; this one is the concern that reads the service.

The month block here is deliberately the same block the Recommendations page
carries, on the same walk the Solvency bank page reads: the three pages are
meant to be one system; the only way to be sure of that is for there to be one
simulation behind all of them.
"""

from PySide6.QtWidgets import QTableWidgetItem

from clear_budget.application.formatting import money_from_pence
from clear_budget.ui import theme
from clear_budget.ui.utils.format_helpers import MONTH_NAMES
from clear_budget.ui.utils import reserves_text as copy


def month_name(year: int, month: int) -> str:
    """A month as every line on this page names it."""
    return f"{MONTH_NAMES[month]} {year}"


class ReservesContentMixin:
    """Fills the Reserves page's verdict, month block and table."""

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

    def _fill_where(self) -> None:
        """The months ahead, each against what it has already promised.

        One line per month, on the same figures the Solvency bank page walks,
        so the two pages cannot disagree about a month. A month that cannot
        cover its floor is painted in the danger colour: it is the only
        verdict on the block and the only one worth colouring.
        """
        window = self.budget_service.get_sustainable_window_months()
        lines = self.budget_service.get_reserve_month_lines(months=window)
        colours = theme.colours()
        rendered = []
        for line in lines:
            text = copy.month_line(
                month_name=month_name(line.year_month.year, line.year_month.month),
                low=money_from_pence(line.low_pence),
                day=line.low_day,
                floor=money_from_pence(line.floor_pence),
                clear=money_from_pence(abs(line.clear_pence)),
                short=line.is_short,
            )
            if line.is_short:
                text = f"<span style='color:{colours['danger']};'>{text}</span>"
            rendered.append(text)
        self.where_label.setText("<br>".join(rendered))

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
