"""The Recommendations tab: what would make the months ahead survivable.

A reference set, never an actor. Every line names an exact edit (move this
bill to that day; find this much by then) with its measured effect; the user
makes the change in the real world first, then in the bill or income dialog
and this page recomputes. There is deliberately no Apply button: a batch of
auto-applied edits would leave the user digging out what changed and
reconciling it with their actual bank, which is more work than making each
change knowingly. The app follows reality; it does not lead it.

Each suggestion carries a try-it-on checkbox instead: ticking SIMULATES that
retiming across the horizon and recomputes the whole page (remaining moves,
asks, outlook, headroom), nothing stored anywhere. The trial registry lives
here on the view and survives data-driven refreshes, so a tick holds while
the user edits elsewhere; the copy says plainly that nothing is applied.

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

from clear_budget.application.services.budget_service import BudgetService
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
from clear_budget.ui.views._recommendation_sections import (
    build_sections,
    trial_entry,
    trial_key,
)
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
        # The try-it-on registry: (kind, name) -> (TrialDay, caption html).
        # Held here rather than in the rebuilt rows so a tick survives every
        # data-driven refresh; nothing in it is ever written anywhere.
        self._tried: dict = {}
        self._section_checks: list = []
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
        self.anchor_label.setObjectName(label_roles.BODY_DETAIL)
        self.anchor_label.setWordWrap(True)
        layout.addWidget(self.anchor_label)

        self.trial_label = QLabel(
            "<p><b>Trying it on.</b> Nothing is applied: your bills and"
            " incomes stay exactly as entered until you change them in their"
            " own dialogs. Untick to put the picture back.</p>"
        )
        self.trial_label.setObjectName(label_roles.BODY)
        self.trial_label.setWordWrap(True)
        self.trial_label.setTextFormat(Qt.TextFormat.RichText)
        self.trial_label.hide()
        layout.addWidget(self.trial_label)

        # The suggestion sections are rebuilt wholesale on every recompute;
        # this box is the slot they land in.
        self._sections_box = QVBoxLayout()
        layout.addLayout(self._sections_box, 1)

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
        """Recompute (trials included) and rebuild the suggestion sections."""
        result, horizon = self.budget_service.get_recommendations(
            trial=tuple(trial for trial, _caption in self._tried.values())
        )
        first = _month_name(horizon[0].year, horizon[0].month)
        last = _month_name(horizon[-1].year, horizon[-1].month)
        self.anchor_label.setText(
            f"Measured from your months as entered, {first} to {last}."
            " Nothing here is changed for you: make an edit in its own"
            " dialog and this page recomputes."
        )
        self.trial_label.setVisible(bool(self._tried))
        while self._sections_box.count():
            item = self._sections_box.takeAt(0)
            widget = item.widget()
            if widget is not None:
                # Detach BEFORE deleteLater: the deferred delete waits for
                # the event loop, so a still-parented widget would keep
                # painting under the rebuilt sections until it fires.
                widget.setParent(None)
                widget.deleteLater()
        sections, self._section_checks = build_sections(
            result=result,
            horizon=horizon,
            tried=self._tried,
            month_name=_month_name,
            on_try=self._on_try,
            on_untry=self._on_untry,
        )
        self._sections_box.addWidget(sections)

    def _on_try(self, trial, _html) -> None:
        """Add one suggestion to the trial and recompute; nothing is applied.

        The caption remembers the day the item is entered as, read from the
        CURRENT result before the trial absorbs it.
        """
        result, _ = self.budget_service.get_recommendations(
            trial=tuple(t for t, _c in self._tried.values())
        )
        self._tried[trial_key(trial)] = trial_entry(
            trial, list(result.moves) + list(result.extras)
        )
        self.refresh()

    def _on_untry(self, key) -> None:
        """Take one trial back out and recompute."""
        self._tried.pop(key, None)
        self.refresh()

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
            *self._section_checks,
        ]
