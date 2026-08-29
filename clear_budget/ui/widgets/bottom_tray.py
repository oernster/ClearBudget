"""The strip along the foot of the window, holding the donate button.

Its own strip rather than a place in the navigation tray above, because the
donate button belongs to nothing on screen. Every control in that tray acts on
the budget, the account or the view being looked at; this one leaves the
application entirely, so it sits where nothing else is reached by accident.

There is ONE of these for the window, not one per view. The navigation tray is
built afresh by each of the seven views and kept in step by
`tests/structural/test_tray_switch_invariants.py`; a control that belongs to
none of them has no business being copied seven times and held in agreement.

Its glyph is two thirds of the tray's, taken from that tray's own measurement
through `footer_glyph_height` rather than written again here. The tray above is
deliberately the heaviest band on the window (`NAV_GLYPH_SCALE` is over 1.0
for that reason), so a footer matching it would weigh the layout down at both
ends; two thirds reads as subordinate while leaving the artwork big enough to
recognise.

The button carries a picture of a beer and a coffee, which on its own tells
nobody that pressing it leaves the application, so the tooltip says so outright.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from clear_budget.ui import ui_scale
from clear_budget.ui.utils.icon_buttons import build_tray_image_button

# The bundled master, cropped and scaled at runtime like every other picture
# in the trays. Listed in `resources._VIEW_ICON_NAMES`, which is what makes the
# delivery scripts carry it.
DONATE_ICON = "donate.png"

# Said in the tooltip because pressing it leaves the application, which a
# picture of a beer and a coffee does not on its own tell anybody.
DONATE_TOOLTIP = "Buy the author a drink (opens your browser)"

# The strip's own padding. Half the tray's, for the same reason its glyph is
# two thirds: it is the lighter of the two bands.
_EDGE_PADDING = 6
_V_PADDING = 3


class BottomTray(QWidget):
    """The window's footer: the donate button, held apart from everything else."""

    def __init__(
        self,
        parent: QWidget | None,
        tray_glyph_px: int,
        open_donation: Callable[[], None] = lambda: None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("bottomTray")
        # A plain QWidget paints a stylesheet background only when told to, the
        # same reason the nav tray sets it.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # A container is never a focus stop, so it is said rather than assumed.
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.donate_button: QPushButton = build_tray_image_button(
            DONATE_ICON, DONATE_TOOLTIP, tray_glyph_px
        )
        self.donate_button.clicked.connect(open_donation)
        row = QHBoxLayout(self)
        edge, vertical = ui_scale.px(_EDGE_PADDING), ui_scale.px(_V_PADDING)
        row.setContentsMargins(edge, vertical, edge, vertical)
        row.addWidget(self.donate_button)
        # Everything the application might later put at this end goes after the
        # stretch; the donate button stays alone at the left.
        row.addStretch()

    def ring_stops(self) -> tuple[QPushButton, ...]:
        """This strip's controls, left to right as they are drawn."""
        return (self.donate_button,)
