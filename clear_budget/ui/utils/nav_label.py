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
