"""The Recommendations page's suggestion sections, built as widget rows.

Split from `recommendations_view` for the LOC limit and because the rows are
interactive: each suggestion carries a try-it-on checkbox. The WORDING all
comes from `ui.utils.recommendation_text`; this module only wraps it in
checkboxes, labels and each row's tray panel.

Ticking never rewrites the page. The sections are built once per data
refresh from the UNTRIALLED result and stay put; a tick only opens the inset
tray panel under its own row, where the view writes that change's measured
marginal effect. That is what makes multi-select natural: every checkbox is
independent, so trying three changes at once is three open panels, with the
copy above them never moving.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from clear_budget.ui import label_roles, ui_scale
from clear_budget.ui._theme_labels import BODY_PADDING_PX
from clear_budget.ui.utils.recommendation_text import (
    ask_html,
    headroom_rows,
    move_rows,
    outlook_html,
    sooner_note_html,
)

_TRY_TOOLTIP = (
    "Tick to preview this change in a panel below. Nothing is applied: your"
    " bills and incomes stay exactly as entered."
)
# The panel indents to the text it annotates, past the checkbox column.
_PANEL_INDENT_PX = 28
_PANEL_PAD_PX = 8


class SuggestionRow:
    """One suggestion: its trial, its checkbox and its tray panel."""

    def __init__(self, trial, layout, html, on_toggle) -> None:
        self.trial = trial
        row = QHBoxLayout()
        self.check = QCheckBox()
        self.check.setToolTip(_TRY_TOOLTIP)
        self.check.toggled.connect(on_toggle)
        text = _label(_unwrapped(html))
        self.text_label = text
        # Centre the box's indicator on the sentence's FIRST line, derived
        # rather than eyeballed: the label's padding puts its first line
        # down from the row top, then half the difference between the line
        # and the indicator centres one on the other. The sentences drop
        # their <p> wrapper too, whose rich-text margin defeats any offset.
        text.ensurePolished()
        self.check.ensurePolished()
        indicator = self.check.style().pixelMetric(
            QStyle.PixelMetric.PM_IndicatorHeight, None, self.check
        )
        drop = ui_scale.px(BODY_PADDING_PX) + max(
            0, (text.fontMetrics().height() - indicator) // 2
        )
        check_col = QVBoxLayout()
        check_col.setContentsMargins(0, drop, 0, 0)
        check_col.addWidget(self.check)
        check_col.addStretch(1)
        row.addLayout(check_col)
        row.addWidget(text, 1)
        layout.addLayout(row)

        self.panel = QWidget()
        self.panel.setObjectName("TrialPanel")
        pad = ui_scale.px(_PANEL_PAD_PX)
        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(pad, pad, pad, pad)
        self._panel_label = _label("")
        panel_layout.addWidget(self._panel_label)
        holder = QHBoxLayout()
        holder.setContentsMargins(ui_scale.px(_PANEL_INDENT_PX), 0, 0, 0)
        holder.addWidget(self.panel)
        layout.addLayout(holder)
        self.panel.hide()

    def show_panel(self, html: str) -> None:
        # Raw, never through _unwrapped: the panel carries a bullet list
        # whose structure the <p>-stripper would mangle and its alignment
        # concern does not apply inside the padded tray.
        self._panel_label.setText(html)
        self.panel.show()

    def hide_panel(self) -> None:
        self.panel.hide()


def _unwrapped(html: str) -> str:
    """The sentence without its outer <p>, whose margin misaligns rows."""
    inner = html.strip()
    if inner.startswith("<p>"):
        inner = inner[len("<p>") :]
    if inner.endswith("</p>"):
        inner = inner[: -len("</p>")]
    return inner.replace("</p><p>", "<br>")


def _label(html: str, role: str = label_roles.BODY) -> QLabel:
    label = QLabel(html)
    label.setObjectName(role)
    label.setWordWrap(True)
    label.setTextFormat(Qt.TextFormat.RichText)
    return label


def build_sections(*, result, horizon, month_name, on_toggle) -> tuple[QWidget, list]:
    """The page body below the anchor line, rebuilt on each DATA refresh.

    Built from the untrialled result and left alone by ticking. Returns the
    container plus the suggestion rows in reading order; the view owns the
    tick state and writes each row's panel. `on_toggle(row)` fires on any
    checkbox change.
    """
    box = QWidget()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    rows: list[SuggestionRow] = []

    def _add_row(trial, html) -> None:
        rows.append(SuggestionRow(trial, layout, html, lambda _on: on_toggle()))

    if result.healthy:
        layout.addWidget(_label("<h3>Nothing needed</h3>"))
        layout.addWidget(
            _label("Every month in the window clears the target as entered.")
        )
    if result.moves:
        layout.addWidget(_label("<h3>Retime what can move</h3>"))
        for trial, html in move_rows(result.moves, month_name):
            _add_row(trial, html)
        note = sooner_note_html(result.moves, result.extras, horizon[0], month_name)
        if note is not None:
            layout.addWidget(_label(note))
    if result.asks:
        layout.addWidget(_label("<h3>Extra income needed</h3>"))
        for ask in result.asks:
            layout.addWidget(_label(ask_html(ask, month_name)))
    layout.addWidget(_label("<h3>Where that leaves each month</h3>"))
    for month in result.outlook:
        layout.addWidget(_label(outlook_html(month, month_name)))
    optional = headroom_rows(result.extras, result.moves, month_name)
    if optional:
        layout.addWidget(_label("<h3>More headroom, if you want it</h3>"))
        layout.addWidget(
            _label(
                "Solvency does not need these. Each one buys slack against"
                " surprises; tick any to see them tried, alone or together."
            )
        )
        for trial, html in optional:
            _add_row(trial, html)
    layout.addStretch(1)
    return box, rows
