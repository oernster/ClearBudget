"""ScrollableTab - QScrollArea wrapper with up/down scroll indicators beside it."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QPushButton,
    QScrollArea,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from clear_budget.ui import ui_scale

_INDICATOR_SIZE = 32
_INDICATOR_MARGIN = 10
_SCROLL_STEP = 120

_INDICATOR_STYLE = (
    "QPushButton {"
    "  background-color: rgba(56, 189, 248, 200);"
    "  color: white;"
    "  border: none;"
    "  border-radius: 14px;"
    "  font-size: 20px;"
    "  font-weight: bold;"
    "}"
    "QPushButton:hover {"
    "  background-color: rgba(56, 189, 248, 255);"
    "  border: 2px solid white;"
    "}"
)


class ScrollableTab(QWidget):
    """Wraps a content widget in a QScrollArea with ▲/▼ indicators beside it."""

    def __init__(self, content: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # A content view may expose a `nav_header` widget (the month/year
        # navigation row). Hoist it ABOVE the scroll area so it spans the full
        # tab width and centres identically on every tab, unaffected by this
        # tab's vertical/horizontal scrollbar gutter or content overflow.
        nav_header = getattr(content, "nav_header", None)
        if nav_header is not None:
            outer.addWidget(nav_header)
            # The nav header owns the vertical gap above the content: zero the
            # content layout's TOP margin so the nav header's symmetric padding
            # is the ONLY space between the line below the tabs and the first
            # content line. That leaves the nav cluster vertically centred in
            # that tray (region = vpad + cluster + vpad, so the cluster centre
            # sits at half the region regardless of the padding value).
            content_layout = content.layout()
            if content_layout is not None:
                cm = content_layout.contentsMargins()
                content_layout.setContentsMargins(cm.left(), 0, cm.right(), cm.bottom())

        self._scroll = QScrollArea()
        self._scroll.setObjectName("TabScrollArea")
        self._scroll.setWidget(content)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        # The page body is a keyboard stop when it has something to scroll, so
        # Up and Down can read down a long page. Qt scrolls a focused
        # QAbstractScrollArea on the vertical arrows by itself; the ring only
        # has to be able to land here, which needs an explicit focus policy
        # (a QScrollArea does not take tab focus by default).
        self._scroll.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        sz = ui_scale.px(_INDICATOR_SIZE)
        _style = QApplication.style()
        self._up_btn = QPushButton()
        self._up_btn.setIcon(_style.standardIcon(QStyle.StandardPixmap.SP_ArrowUp))
        self._up_btn.setFixedSize(sz, sz)
        self._up_btn.setStyleSheet(_INDICATOR_STYLE)
        self._up_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._up_btn.hide()

        self._down_btn = QPushButton()
        self._down_btn.setIcon(_style.standardIcon(QStyle.StandardPixmap.SP_ArrowDown))
        self._down_btn.setFixedSize(sz, sz)
        self._down_btn.setStyleSheet(_INDICATOR_STYLE)
        self._down_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._down_btn.hide()

        # The indicators live in a COLUMN of their own beside the page, not
        # floating on top of it. Floating put them over whatever happened to be
        # under them: on a narrow window the down indicator landed on the
        # Delete Income button, and a click there scrolled instead of reaching
        # the button. A column cannot overlap anything, and it costs the
        # layout, not a `move()` call, which is the same reason the up
        # indicator once ended up in the navigation tray.
        #
        # The column is ALWAYS present, even while the buttons are hidden.
        # Showing and hiding it would change the page width, which can change
        # whether the page overflows, which decides whether the buttons show:
        # a loop that flickers on content sitting near the boundary.
        self._indicators = QWidget()
        self._indicators.setFixedWidth(sz + ui_scale.px(_INDICATOR_MARGIN))
        margin = ui_scale.px(_INDICATOR_MARGIN)
        column = QVBoxLayout(self._indicators)
        column.setContentsMargins(0, margin, 0, margin)
        column.setSpacing(0)
        column.addWidget(self._up_btn)
        column.addStretch()
        column.addWidget(self._down_btn)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._scroll)
        body.addWidget(self._indicators)
        outer.addLayout(body)

        vbar = self._scroll.verticalScrollBar()
        vbar.valueChanged.connect(self._refresh)
        vbar.rangeChanged.connect(self._refresh)

        self._up_btn.clicked.connect(
            lambda: vbar.setValue(vbar.value() - ui_scale.px(_SCROLL_STEP))
        )
        self._down_btn.clicked.connect(
            lambda: vbar.setValue(vbar.value() + ui_scale.px(_SCROLL_STEP))
        )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # Nothing to place: the indicators are laid out, not positioned. The
        # refresh stands because a resize changes whether the page overflows.
        self._refresh()

    def _refresh(self, *_) -> None:
        vbar = self._scroll.verticalScrollBar()
        has_range = vbar.maximum() > vbar.minimum()
        self._up_btn.setVisible(has_range and vbar.value() > vbar.minimum())
        self._down_btn.setVisible(has_range and vbar.value() < vbar.maximum())

    def scroll_area(self) -> QScrollArea:
        return self._scroll

    def nav_scroll_stop(self) -> QScrollArea | None:
        """The page body as a ring stop, or None when there is nothing to scroll.

        A stop has to be ACTIONABLE. A page that fits its tab scrolls nowhere,
        so landing on it would spend a keypress and do nothing; a page that
        overflows is the one thing on the tab the keyboard otherwise cannot
        reach. The ring is rebuilt on every move, so the same page counts as a
        stop or not according to the window size at that moment.
        """
        vbar = self._scroll.verticalScrollBar()
        return self._scroll if vbar.maximum() > vbar.minimum() else None
