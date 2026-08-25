"""The Recommendations page's suggestion sections, built as widget rows.

Split from `recommendations_view` for the LOC limit and because the rows
became interactive: each suggestion carries a try-it-on checkbox, so the body
stopped being one rich-text label and became real widgets. The WORDING all
comes from `ui.utils.recommendation_text`; this module only wraps it in
checkboxes and labels.

The checkbox previews, never applies: ticking hands a `TrialDay` back to the
view, which recomputes the whole page with that retiming simulated. The row
for a ticked suggestion is rendered from the view's trial registry (checked,
with a "nothing is applied" caption), because the recomputed result no longer
proposes what the trial already contains.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from clear_budget.ui import label_roles
from clear_budget.ui.utils.recommendation_text import (
    ask_html,
    headroom_rows,
    move_rows,
    outlook_html,
    sooner_note_html,
    tried_caption,
)

_TRY_TOOLTIP = (
    "Tick to preview this change on this page. Nothing is applied: your"
    " bills and incomes stay exactly as entered."
)
_UNTRY_TOOLTIP = "Untick to take this preview back out of the picture."


def _label(html: str, role: str = label_roles.BODY) -> QLabel:
    label = QLabel(html)
    label.setObjectName(role)
    label.setWordWrap(True)
    label.setTextFormat(Qt.TextFormat.RichText)
    return label


def _check_row(layout, html, *, checked, tooltip, on_toggle) -> QCheckBox:
    """One suggestion row: the try-it-on checkbox beside its sentence."""
    row = QHBoxLayout()
    check = QCheckBox()
    check.setChecked(checked)
    check.setToolTip(tooltip)
    check.toggled.connect(on_toggle)
    row.addWidget(check, 0, Qt.AlignmentFlag.AlignTop)
    row.addWidget(_label(html), 1)
    layout.addLayout(row)
    return check


def build_sections(
    *, result, horizon, tried, month_name, on_try, on_untry
) -> tuple[QWidget, list]:
    """The page body below the anchor line, rebuilt on every recompute.

    `tried` maps each active trial's (kind, name) to (TrialDay, caption
    html). Returns the container plus its checkboxes in reading order, so
    the view can put them on the keyboard ring.
    """
    box = QWidget()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    checks: list = []

    if tried:
        layout.addWidget(_label("<h3>Being tried, nothing applied</h3>"))
        for key in sorted(tried):
            trial, caption = tried[key]
            checks.append(
                _check_row(
                    layout,
                    caption,
                    checked=True,
                    tooltip=_UNTRY_TOOLTIP,
                    on_toggle=lambda _on, k=key: on_untry(k),
                )
            )

    if result.healthy:
        layout.addWidget(_label("<h3>Nothing needed</h3>"))
        layout.addWidget(
            _label(
                "<p>Every month in the window clears the target"
                + (" with these changes tried" if tried else " as entered")
                + ".</p>"
            )
        )
    if result.moves:
        layout.addWidget(_label("<h3>Retime what can move</h3>"))
        for trial, html in move_rows(result.moves, month_name):
            checks.append(
                _check_row(
                    layout,
                    html,
                    checked=False,
                    tooltip=_TRY_TOOLTIP,
                    on_toggle=lambda _on, t=trial, h=html: on_try(t, h),
                )
            )
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
    optional = [
        (trial, html)
        for trial, html in optional
        if (trial.kind, trial.name) not in tried
    ]
    if optional:
        layout.addWidget(_label("<h3>More headroom, if you want it</h3>"))
        layout.addWidget(
            _label(
                "<p>Solvency does not need these. Each one buys slack against"
                " surprises; tick one to see it tried.</p>"
            )
        )
        for trial, html in optional:
            checks.append(
                _check_row(
                    layout,
                    html,
                    checked=False,
                    tooltip=_TRY_TOOLTIP,
                    on_toggle=lambda _on, t=trial, h=html: on_try(t, h),
                )
            )
    layout.addStretch(1)
    return box, checks


def trial_key(trial) -> tuple[str, str]:
    """How the view's registry identifies a trial: the item, not the day."""
    return (trial.kind, trial.name)


def trial_entry(trial, moves_and_extras) -> tuple:
    """(trial, caption) for the registry, naming the day it was entered as."""
    from_day = next(
        (
            m.from_day
            for m in moves_and_extras
            if (m.kind, m.name) == (trial.kind, trial.name)
        ),
        trial.to_day,
    )
    return trial, tried_caption(trial.kind, trial.name, from_day, trial.to_day)
