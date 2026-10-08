"""Semantic style roles for widgets, applied by object name.

A widget carries its colour role as an object name (styled by the theme QSS in
`_theme_controls.label_roles_qss`) rather than an inline stylesheet. Two
reasons: no view hardcodes a hex colour; re-applying the app stylesheet on
a theme switch restyles every role at once, which an inline style set at build
time cannot do.

`set_role` swaps a role at runtime (a balance turning from good to danger) and
repolishes, since Qt only re-resolves a stylesheet for a widget when its
object name changes are followed by an unpolish/polish pair.
"""

from __future__ import annotations

# Static roles.
BODY = "LabelBody"
BODY_DETAIL = "LabelBodyDetail"
HINT = "LabelHint"
MUTED = "LabelMuted"
SUBTLE = "LabelSubtle"
DISABLED = "LabelDisabled"
ERROR = "LabelError"
TITLE = "LabelTitle"
SECTION_TITLE = "LabelSectionTitle"
VALUE = "LabelValue"
SEPARATOR = "Separator"
NAV_USER = "NavUserLabel"
ICON_ACTION = "IconAction"

# Severity roles, swapped at runtime by set_role.
GOOD = "LabelGood"
WARN = "LabelWarn"
DANGER = "LabelDanger"

# Compact severity notes (the overdraft warning line).
WARN_NOTE = "WarnNote"
DANGER_NOTE = "DangerNote"

# Dialog roles.
NOTE = "LabelNote"
STRONG_WARN = "LabelStrongWarn"
CHANGE_WARN = "LabelChangeWarn"
LOGIN_TITLE = "LoginTitle"
RECOVERY_CODE_BOX = "RecoveryCodeBox"

# The status bar's date.
STATUS_DATE = "StatusDateLabel"

# Solvency view lines.
SOLVENCY_BANNER = "SolvencyBanner"
SAFE_TO_SPEND_HEADLINE = "SafeToSpendHeadline"
SOLVENCY_MIDMONTH_ALERT = "SolvencyMidmonthAlert"
SOLVENCY_COMMITTED = "SolvencyCommitted"
SOLVENCY_ASSUMED_NOTE = "SolvencyAssumedNote"
SOLVENCY_SHORTFALL = "SolvencyShortfall"
SOLVENCY_REMAINING_BANK = "SolvencyRemainingBank"
SOLVENCY_REMAINING_CARD = "SolvencyRemainingCard"
SOLVENCY_BREAKDOWN = "SolvencyBreakdown"
# A forward-projection month block. Styled inline (its colour is the month's
# state), so the role exists only to carry the block's inset.
SOLVENCY_PROJECTION = "SolvencyProjection"


def set_role(widget, role: str) -> None:
    """Give `widget` a style role and repolish it so the change takes effect."""
    widget.setObjectName(role)
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()
