"""The Recommendations tab: what would make the months ahead survivable.

A reference set, never an actor. Every line names an exact edit (move this
bill to that day; find this much by then) with its measured effect; the user
makes the change in the real world first, then in the bill or income dialog
and this page recomputes. There is deliberately no Apply button: a batch of
auto-applied edits would leave the user digging out what changed and
reconciling it with their actual bank, which is more work than making each
change knowingly. The app follows reality; it does not lead it.

The page is anchored to TODAY, not to the month being viewed: the tray's
arrows still step the shared month like every other tab; the advice is
about the months ahead of now, which it says at the top. It recomputes on
every month-summary change, so an edit made on Monthly Budget lands here the
moment it is saved.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from clear_budget.application.formatting import money_from_pence
from clear_budget.application.services.budget_service import BudgetService
from clear_budget.domain.services.recommendations import KIND_BILL
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.ui import label_roles, ui_scale
from clear_budget.ui.utils.format_helpers import (
    MONTH_NAMES,
    apply_nav_label_color,
    build_centered_nav_header,
    nav_glyph_height,
)
from clear_budget.ui.utils.tab_icons import build_tab_buttons, ring_tab_stops
from clear_budget.ui.widgets._tray_buttons import (
    build_bank_button,
    build_budgets_button,
    build_info_button,
    build_save_load_buttons,
    build_tray_separator,
)

# The buffer field is a short money entry, not a full-width line.
_BUFFER_FIELD_WIDTH_PX = 120


def _month_name(year: int, month: int) -> str:
    return f"{MONTH_NAMES[month]} {year}"


class RecommendationsView(QWidget):
    """Suggestions for surviving the months ahead, computed from today."""

    def __init__(self, budget_service: BudgetService, current_month: YearMonth) -> None:
        super().__init__()
        self.budget_service = budget_service
        self._current_month = current_month
        self._build_ui()
        self.refresh()

    # ---- construction -------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout()

        self.prev_btn = QPushButton("← Previous")
        self.next_btn = QPushButton("Next →")
        _glyph_h = nav_glyph_height(self.prev_btn)
        self.load_btn, self.save_btn = build_save_load_buttons(_glyph_h)
        self.budgets_btn = build_budgets_button(_glyph_h)
        _sep, self.bank_btn = build_bank_button(_glyph_h)
        self.info_btn = build_info_button(_glyph_h)
        self.tab_btns = build_tab_buttons(_glyph_h)
        self.nav_header, self.month_label, self.theme_btn = build_centered_nav_header(
            _month_name(self._current_month.year, self._current_month.month),
            prev_btn=self.prev_btn,
            next_btn=self.next_btn,
            leading=(
                self.load_btn,
                self.save_btn,
                self.budgets_btn,
                _sep,
                self.bank_btn,
            ),
            tabs=self.tab_btns[:-1],
            pre_theme=(build_tray_separator(_glyph_h), self.tab_btns[-1]),
            trailing=(self.info_btn,),
        )

        buffer_row = QHBoxLayout()
        self.buffer_check = QCheckBox("Keep an emergency buffer of")
        self.buffer_check.setToolTip(
            "Ticked, every suggestion aims to leave at least this much clear"
            " at each month's lowest day, on top of surviving. Unticked, the"
            " target is bare survival against your arranged overdraft."
        )
        self.buffer_edit = QLineEdit()
        self.buffer_edit.setFixedWidth(ui_scale.px(_BUFFER_FIELD_WIDTH_PX))
        self.buffer_edit.setPlaceholderText("0.00")
        self.buffer_edit.setToolTip(
            "The emergency cushion, in the display currency. The income asks"
            " below grow by exactly this amount per month it protects."
        )
        buffer_row.addWidget(self.buffer_check)
        buffer_row.addWidget(self.buffer_edit)
        buffer_row.addStretch(1)
        layout.addLayout(buffer_row)

        self.anchor_label = QLabel("")
        self.anchor_label.setObjectName(label_roles.SUBTLE)
        self.anchor_label.setWordWrap(True)
        layout.addWidget(self.anchor_label)

        self.body_label = QLabel("")
        self.body_label.setObjectName(label_roles.NOTE)
        self.body_label.setWordWrap(True)
        self.body_label.setTextFormat(Qt.TextFormat.RichText)
        self.body_label.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        layout.addWidget(self.body_label, 1)

        self.setLayout(layout)

        enabled, amount = self.budget_service.get_recommendation_buffer()
        self.buffer_check.setChecked(enabled)
        self.buffer_edit.setText(f"{amount.pounds:.2f}")
        self.buffer_edit.setEnabled(enabled)
        self.buffer_check.toggled.connect(self._on_buffer_changed)
        self.buffer_edit.editingFinished.connect(self._on_buffer_changed)

    # ---- behaviour ----------------------------------------------------------
    def _on_buffer_changed(self) -> None:
        """Persist the buffer, then recompute against the new target."""
        enabled = self.buffer_check.isChecked()
        self.buffer_edit.setEnabled(enabled)
        try:
            pounds = float(self.buffer_edit.text().strip() or "0")
        except ValueError:
            return
        if pounds < 0:
            return
        self.budget_service.set_recommendation_buffer(
            enabled=enabled, amount=Amount.from_pounds(pounds)
        )
        self.refresh()

    def set_month(self, year_month: YearMonth) -> None:
        """Follow the shared month label; the advice stays anchored to today."""
        self._current_month = year_month
        self.month_label.setText(_month_name(year_month.year, year_month.month))

    def on_month_summary_updated(self, _summary) -> None:
        """An edit anywhere re-answers the question here."""
        self.refresh()

    def set_nav_label_color(self, color: str) -> None:
        apply_nav_label_color(self.month_label, color)

    def refresh(self) -> None:
        """Recompute the suggestions and render them as three plain sections."""
        result, horizon = self.budget_service.get_recommendations()
        first = _month_name(horizon[0].year, horizon[0].month)
        last = _month_name(horizon[-1].year, horizon[-1].month)
        self.anchor_label.setText(
            f"Measured from your months as entered, {first} to {last}."
            " Nothing here is changed for you: make an edit in its own"
            " dialog and this page recomputes."
        )
        self.body_label.setText(self._body_html(result))

    # ---- rendering ----------------------------------------------------------
    def _body_html(self, result) -> str:
        if result.healthy:
            return (
                "<h3>Nothing to recommend</h3>"
                "<p>Every month in the window clears the target as entered.</p>"
            )
        parts = []
        if result.moves:
            parts.append("<h3>Retime what can move</h3>")
            for move in result.moves:
                what = "bill" if move.kind == KIND_BILL else "income"
                parts.append(
                    f"<p>Move the {what} <b>{move.name}</b> from day"
                    f" {move.from_day} to day {move.to_day} in"
                    f" {_month_name(move.year, move.month)}: lifts that"
                    f" month's low from {money_from_pence(move.low_before_pence)}"
                    f" to {money_from_pence(move.low_after_pence)}.</p>"
                )
        if result.asks:
            parts.append("<h3>Extra income needed</h3>")
            for ask in result.asks:
                parts.append(
                    f"<p>Find <b>{money_from_pence(ask.amount_pence)}</b> by day"
                    f" {ask.by_day} of {_month_name(ask.year, ask.month)}."
                    " Each ask assumes the earlier ones arrived, so together"
                    " they are the whole plan.</p>"
                )
        parts.append("<h3>Where that leaves each month</h3>")
        for month in result.outlook:
            parts.append(
                f"<p>{_month_name(month.year, month.month)}: low of"
                f" {money_from_pence(month.low_pence)} on day {month.low_day},"
                f" closing at {money_from_pence(month.close_pence)}.</p>"
            )
        return "".join(parts)

    # ---- keyboard ring ------------------------------------------------------
    def nav_targets(self) -> list:
        """Ordered keyboard-ring stops: trays first, then the page's own."""
        others = ring_tab_stops(self.tab_btns[:-1])
        archive_stop = ring_tab_stops(self.tab_btns[-1:])
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
        ]
