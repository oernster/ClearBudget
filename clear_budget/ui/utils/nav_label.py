"""The nav tray's month/year label: class, styling and width guarantees.

Extracted from nav_header.py to keep both under the module cap. The public
names are re-exported by nav_header (and from there by format_helpers), so
the sixty-odd call sites did not move.
"""

# Neutral colour for a nav month/year label before any solvency-driven colour
# is applied. The Solvency tab overrides this with a health colour and
# broadcasts it so every tab's nav label stays consistent.
NAV_LABEL_DEFAULT_COLOR = "#9ca3af"

# Breathing room around the month/year text, applied as a real QLabel margin,
# NOT stylesheet padding. Stylesheet padding on a QLabel is painted but not
# reliably included in its size hints, so a tray under width pressure (a 13in
# laptop at the window's minimum floor) reserved a few pixels less than the
# painted text and clipped the year's last digit. QLabel.setMargin feeds both
# sizeHint and minimumSizeHint, so the layout can never reserve less than the
# text actually needs, whatever the platform's fonts do.
NAV_LABEL_MARGIN_PX = 10

# The widest the signed-in account may be drawn before it is shortened.
# Measured at the window's own width floor (994px): the month cluster and
# the mirrored slot on the other side leave a little under 284px a side, so
# a cap below that can never cost the month its space however long an
# account is named. A name that does not fit is elided and its full form
# put on the tooltip, which is the only way to keep both promises at once.
NAV_USER_MAX_WIDTH_PX = 240


def _nav_label_style(color: str) -> str:
    """Return the standard nav month/year label stylesheet in `color`.

    The base style (size/weight) is fixed; only the colour varies, so a label
    can be recoloured without dropping its other properties. The surrounding
    space comes from QLabel.setMargin (see NAV_LABEL_MARGIN_PX), never from
    stylesheet padding.
    """
    from clear_budget.ui import ui_scale

    return ui_scale.style(f"font-size: 20px; font-weight: bold; color: {color};")


def _sync_nav_label_min_width(label) -> None:
    """Pin the label's minimum width to its current text plus margins.

    A hard minimum, not a hint: when the tray is forced narrower than its
    layout wants (a 13in laptop at the window's width floor), Qt shaves every
    child proportionally and a hint-only label loses a few pixels, clipping
    the year's last digit. An explicit minimum is never violated, so the
    shave lands on the stretch space and the flanking buttons instead of the
    date. Re-run after anything that can change the metrics: the text (every
    month step) and the stylesheet (colour changes repolish the font).
    """
    label.ensurePolished()
    fm = label.fontMetrics()
    label.setMinimumWidth(fm.horizontalAdvance(label.text()) + 2 * label.margin())


class NavLabel:
    """Deferred-import factory for the nav month/year label class.

    The QLabel subclass is created lazily (this module must stay importable
    without Qt); `setText` re-pins the minimum width, so a month step to a
    longer name (May to September) grows the reservation with it.
    """

    _cls = None

    @classmethod
    def create(cls, text: str):
        if cls._cls is None:
            from PySide6.QtWidgets import QLabel

            class _NavLabel(QLabel):
                def setText(self, text: str) -> None:
                    super().setText(text)
                    _sync_nav_label_min_width(self)

            cls._cls = _NavLabel
        return cls._cls(text)


def apply_nav_label_color(label, color: str) -> None:
    """Recolour a nav month/year label, preserving its base style.

    Also (re)applies the margin and re-pins the minimum width, so every nav
    label carries both however it was built and no recolour path can drop
    them.
    """
    from clear_budget.ui import ui_scale

    label.setMargin(ui_scale.px(NAV_LABEL_MARGIN_PX))
    label.setStyleSheet(_nav_label_style(color))
    _sync_nav_label_min_width(label)


class NavUserLabel:
    """Deferred-import factory for the signed-in-account label.

    Built lazily for the same reason as `NavLabel`: this module has to stay
    importable without Qt.

    The label shortens its own text to fit, rather than growing until it
    pushes the month cluster off the middle of the window. When it does
    shorten, the full name goes on the tooltip, so nothing is ever lost, only
    folded away until it is hovered.
    """

    _cls = None

    @classmethod
    def create(cls):
        if cls._cls is None:
            from PySide6.QtCore import Qt
            from PySide6.QtWidgets import QLabel

            class _NavUserLabel(QLabel):
                def __init__(self) -> None:
                    super().__init__("")
                    self._full_text = ""
                    self.setMargin(NAV_LABEL_MARGIN_PX)
                    from clear_budget.ui import ui_scale

                    self.setMaximumWidth(ui_scale.px(NAV_USER_MAX_WIDTH_PX))

                def set_full_text(self, text: str) -> None:
                    """Show `text`, shortened to fit, with the whole of it on hover."""
                    self._full_text = text
                    # The hint is measured from the full text, so the layout
                    # has to be told to ask again before the refit measures
                    # against the width it gets.
                    self.updateGeometry()
                    self._refit()

                def full_text(self) -> str:
                    return self._full_text

                def sizeHint(self):
                    """Ask for the FULL name's width, capped at the maximum.

                    Measured from the full text and never from what is
                    currently drawn. A hint taken from the drawn text is
                    self-reinforcing: the moment the name is elided the hint
                    collapses to the width of an ellipsis, the layout hands
                    back exactly that, so the label can never grow again. It
                    was measured doing precisely that, every name after the
                    first coming out as a lone ellipsis.
                    """
                    from PySide6.QtCore import QSize

                    width = (
                        self.fontMetrics().horizontalAdvance(self._full_text)
                        + 2 * self.margin()
                    )
                    return QSize(
                        min(width, self.maximumWidth()), super().sizeHint().height()
                    )

                def minimumSizeHint(self):
                    """The same width it asks for, so it is never shaved.

                    A hint alone is not enough here for the reason the month
                    label carries an explicit minimum: under width pressure
                    Qt shaves every child proportionally, so a few pixels lost
                    is a few pixels of name lost. Left free to shrink, a
                    two-letter account came out as a lone ellipsis with room
                    to spare either side of it. The cap in sizeHint is what
                    keeps this honest: a long name still yields, at the
                    maximum width and nowhere before it.
                    """
                    return self.sizeHint()

                def resizeEvent(self, event) -> None:
                    super().resizeEvent(event)
                    self._refit()

                def _refit(self) -> None:
                    self.ensurePolished()
                    metrics = self.fontMetrics()
                    available = self.width() - 2 * self.margin()
                    needed = metrics.horizontalAdvance(self._full_text)
                    # The fit is decided HERE rather than left to elidedText,
                    # which treats an exact fit as no fit: the layout hands
                    # this label precisely the width it asked for, so every
                    # name was borderline and even a two-letter one came back
                    # as a lone ellipsis. available <= 0 is the state before
                    # the first layout, where there is nothing to measure
                    # against and the resize that follows will refit anyway.
                    if available <= 0 or needed <= available:
                        shown = self._full_text
                    else:
                        shown = metrics.elidedText(
                            self._full_text, Qt.TextElideMode.ElideRight, available
                        )
                    # Only ever set a CHANGED text: setText re-lays out, which
                    # resizes, which lands back here; an unconditional set
                    # would keep that going round.
                    if shown != self.text():
                        super().setText(shown)
                    self.setToolTip(self._full_text if shown != self._full_text else "")

            cls._cls = _NavUserLabel
        return cls._cls()
