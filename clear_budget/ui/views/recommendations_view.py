"""The Recommendations view: what would make the months ahead survivable.

A reference set, never an actor. Every line names an exact edit (move this
bill to that day; find this much by then) with its measured effect; the user
makes the change in the real world first, then in the bill or income dialog
and this page recomputes. There is deliberately no Apply button: a batch of
auto-applied edits would leave the user digging out what changed and
reconciling it with their actual bank, which is more work than making each
change knowingly. The app follows reality; it does not lead it.

Each suggestion carries a try-it-on checkbox instead. A tick never rewrites
the page (a body that reshuffles under a click is jarring): it opens an
inset tray panel under that row alone, stating the change's measured
marginal effect beside whatever else is ticked, so several changes can be
tried together. Simulation only, nothing stored; every panel says so. The
tick state lives here on the view and survives data-driven rebuilds.

The page is anchored to TODAY, not to the month being viewed: the tray's
arrows still step the shared month like every other view; the advice is
about the months ahead of now, which it says at the top. It recomputes on
every month-summary change, so an edit made on Monthly Budget lands here the
moment it is saved.
"""

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
from clear_budget.ui.utils.view_buttons import build_view_buttons, ring_view_stops
from clear_budget.ui.utils.recommendation_text import panel_html
from clear_budget.ui.views._recommendation_sections import build_sections
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
        # The try-it-on state: (kind, name) -> TrialDay for every ticked
        # row. Held here so ticks survive a data-driven rebuild of the
        # rows; nothing in it is ever written anywhere.
        self._tried: dict = {}
        self._rows: list = []
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
        self.view_btns = build_view_buttons(_glyph_h)
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
            views=self.view_btns[:-1],
            pre_theme=(build_tray_separator(_glyph_h), self.view_btns[-1]),
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

        # The suggestion sections are rebuilt on every DATA refresh (never
        # on a tick); this box is the slot they land in.
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
        """Rebuild the sections from the data as entered; re-tick survivors.

        Runs on data changes only, never on a tick: a tick touches nothing
        but its own row's panel. A trial whose suggestion no longer exists
        after a data edit is dropped rather than silently simulated.
        """
        result, horizon = self.budget_service.get_recommendations()
        first = _month_name(horizon[0].year, horizon[0].month)
        last = _month_name(horizon[-1].year, horizon[-1].month)
        self.anchor_label.setText(
            f"Measured from your months as entered, {first} to {last}."
            " Nothing here is changed for you: make an edit in its own"
            " dialog and this page recomputes."
        )
        while self._sections_box.count():
            item = self._sections_box.takeAt(0)
            widget = item.widget()
            if widget is not None:
                # Detach BEFORE deleteLater: the deferred delete waits for
                # the event loop, so a still-parented widget would keep
                # painting under the rebuilt sections until it fires.
                widget.setParent(None)
                widget.deleteLater()
        sections, self._rows = build_sections(
            result=result,
            horizon=horizon,
            month_name=_month_name,
            on_toggle=self._on_toggle,
        )
        self._sections_box.addWidget(sections)
        keys = {self._trial_key(row.trial) for row in self._rows}
        self._tried = {k: t for k, t in self._tried.items() if k in keys}
        for row in self._rows:
            if self._trial_key(row.trial) in self._tried:
                row.check.blockSignals(True)
                row.check.setChecked(True)
                row.check.blockSignals(False)
        self._update_panels()

    @staticmethod
    def _trial_key(trial) -> tuple[str, str]:
        return (trial.kind, trial.name)

    def _on_toggle(self) -> None:
        """Re-read every checkbox, then repaint only the panels."""
        self._tried = {
            self._trial_key(row.trial): row.trial
            for row in self._rows
            if row.check.isChecked()
        }
        self._update_panels()

    def _update_panels(self) -> None:
        """Each ticked row's panel: its marginal effect beside the others.

        With-versus-without on the full ticked set, so however many boxes
        are ticked and in whatever order, every panel states what its own
        change still contributes. Simulation only; nothing is written.
        """

        # Pinned runs throughout: the normal outlook assumes the engine's
        # whole plan, which would hide a tick that does what the plan
        # proposed anyway. Pinning isolates the user's own ticks.
        def _pinned(trials):
            result, _ = self.budget_service.get_recommendations(
                trial=trials, pinned=True
            )
            return result

        everything = tuple(self._tried.values())
        with_all = None
        baseline = None
        for row in self._rows:
            if not row.check.isChecked():
                row.hide_panel()
                continue
            if with_all is None:
                with_all = _pinned(everything)
                baseline = _pinned(())
            without = _pinned(
                tuple(
                    t for k, t in self._tried.items() if k != self._trial_key(row.trial)
                )
            )
            row.show_panel(
                panel_html(
                    with_all,
                    without,
                    _month_name,
                    solo=_pinned((row.trial,)),
                    baseline=baseline,
                    price=row.price_html,
                )
            )

    # ---- keyboard ring ------------------------------------------------------
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
            *(row.check for row in self._rows),
        ]
