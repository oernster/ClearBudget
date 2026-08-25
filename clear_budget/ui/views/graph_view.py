"""The Graph view: the month plotted, as a PAGE rather than a dialog.

This used to be a modal dialog opened from an icon in the tray; it was the
one control in the application that behaved that way. Every other icon in
that row shows you a page; this one opened a window on top of the one you
were reading, which is what made it grate.

The dialog gave itself away in its own code. It built ← Previous and Next →
buttons that stepped months "exactly as the tray's own arrows step the page",
so it carried a working copy of the tray it had been launched from. As a page
it simply uses the real tray, so that duplicate pair goes, along with the
Close button a page has no need of.

WHAT IS PLOTTED IS CHOSEN HERE, not inherited from wherever you came from.
The dialog took its series from the view that opened it: the bank balance from
Monthly Budget and Solvency, one series per card from Credit Cards. Folding
those into one page could have kept that by remembering which view you arrived
from; that would have been the same invisible state in a new place. The
page carries a switch instead and names what it is showing in a heading above
the chart, so it answers the question rather than depending on how it was
reached.

The projection export follows the switch rather than the page: it writes a
BANK balance projection, so it is offered while the bank is on screen and
withdrawn while the cards are. Offered beside a graph of card balances it
would claim to project what is shown and would not.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from clear_budget.application.services.budget_service import BudgetService
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.ui.utils.format_helpers import (
    MONTH_NAMES,
    apply_nav_label_color,
    build_centered_nav_header,
    nav_glyph_height,
)
from clear_budget.ui.utils.icon_buttons import (
    apply_glyph_face,
    apply_image_face,
    build_tray_icon_button,
)
from clear_budget.ui.utils.view_buttons import build_view_buttons, ring_view_stops
from clear_budget.ui.views._graph_exports import GraphExportsMixin
from clear_budget.ui.views._graph_package_export import (
    GraphPackageExportMixin,
)
from clear_budget.ui.widgets._line_bar_chart import MODE_BAR, MODE_LINE, LineBarChart
from clear_budget.ui.widgets._tray_buttons import (
    build_budgets_button,
    build_info_button,
    build_save_load_buttons,
    build_tray_separator,
    build_bank_button,
)

# What the two switches say. Each names what a press will DO rather than what
# is currently shown, matching the rendering switch this page inherited from
# the dialog; the heading above the chart is what states the current mode.
#
# The source switch says it in a PICTURE, with the words as its hover. It
# shows what a press will give you: the bank, else the cards. The card picture
# is the Credit Cards view's own, so the switch names its destination in the
# same artwork the destination wears everywhere else.
_TO_CARDS_LABEL = "Show card balances"
_TO_BANK_LABEL = "Show bank balance"
# The switch's two faces. Deliberately NOT the pictures the tray and the
# Credit Cards button wear: those two open an account's settings and a view, while
# these plot a balance; a control that repeats another control's picture
# reads as the same control in a second place.
_BANK_ICON = "bank-icon2.png"
_CARDS_ICON = "creditcards2.png"
# The switch's picture is sized from the BUTTONS BESIDE IT rather than from a
# number of its own, so the row keeps one height whatever the display's UI
# scale does to the text. A fixed 18 was tried and came out 13px tall on a
# 0.72 scale, a stamp in a button twice its height.
# The rendering switch, in pictures like the rest of the row. Each face is
# what a press will DRAW: a rising line, else bars.
_PILOT_TO_LINE = "Switch to line graph"
_PILOT_TO_BAR = "Switch to bar graph"
_LINE_GLYPH = "📈"
_BAR_GLYPH = "📊"
_EXPORT_LABEL = "Export HTML…"
_EXPORT_ICON = "exporttohtml.png"
_PACKAGE_LABEL = "Export a folder of months…"
_PACKAGE_ICON = "exportpackage.png"

_SOURCE_BANK = "bank"
_SOURCE_CARDS = "cards"


class GraphView(QWidget, GraphExportsMixin, GraphPackageExportMixin):
    """Plots the viewed month, bank or cards, with the tray driving the month."""

    def __init__(
        self,
        budget_service: BudgetService,
        current_month: YearMonth,
    ) -> None:
        super().__init__()
        self.budget_service = budget_service
        self.current_month = current_month
        self._source = _SOURCE_BANK
        self._mode = MODE_BAR
        self._series: list = []
        self._title = ""
        self.init_ui()
        self.replot()

    def init_ui(self) -> None:
        """Build the page: the shared tray, a heading, the chart, its controls."""
        layout = QVBoxLayout()

        self.prev_btn = QPushButton("← Previous")
        self.next_btn = QPushButton("Next →")
        _glyph_h = nav_glyph_height(self.prev_btn)
        self.load_btn, self.save_btn = build_save_load_buttons(_glyph_h)
        self.budgets_btn = build_budgets_button(_glyph_h)
        _sep, self.bank_btn = build_bank_button(_glyph_h)
        self.info_btn = build_info_button(_glyph_h)
        # Every view builds its own set of the buttons; MainWindow wires
        # them and keeps the current-view mark in step across all of them.
        self.view_btns = build_view_buttons(_glyph_h)
        (
            self.nav_header,
            self.month_label,
            self.theme_btn,
        ) = build_centered_nav_header(
            "",
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
        self._refresh_month_label()

        # The page's own controls, ABOVE the chart rather than under it,
        # drawn at the tray's icon size so the two rows read as one band of
        # controls with the page beneath them. Underneath they sat below the
        # fold on a short window, so the chart's own switches were the part
        # you had to go looking for.
        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        self.source_btn = build_tray_icon_button(_TO_CARDS_LABEL)
        self.source_btn.clicked.connect(self._toggle_source)
        button_row.addWidget(self.source_btn)

        self.pilot_btn = build_tray_icon_button(_PILOT_TO_LINE)
        self.pilot_btn.clicked.connect(self._toggle_mode)
        button_row.addWidget(self.pilot_btn)

        self.export_btn = build_tray_icon_button(_EXPORT_LABEL)
        self.export_btn.clicked.connect(self._export_month)
        apply_image_face(self.export_btn, _EXPORT_ICON, _EXPORT_LABEL, _glyph_h)
        button_row.addWidget(self.export_btn)

        self.package_btn = build_tray_icon_button(_PACKAGE_LABEL)
        self.package_btn.clicked.connect(self._export_package)
        apply_image_face(self.package_btn, _PACKAGE_ICON, _PACKAGE_LABEL, _glyph_h)
        button_row.addWidget(self.package_btn)

        button_row.addStretch()
        layout.addLayout(button_row)
        self._glyph_height = _glyph_h
        self._apply_source_face()
        self._apply_pilot_face()

        # The heading the dialog put in its title bar. A page has no title bar,
        # and it is the only thing naming which series is on screen, so it is
        # a label rather than being left out with the window frame.
        self.title_label = QLabel("")
        self.title_label.setObjectName("GraphTitle")
        layout.addWidget(self.title_label)

        self.chart = LineBarChart(self)
        layout.addWidget(self.chart, 1)

        self.setLayout(layout)

    # ---- what is plotted ----------------------------------------------------
    def _month_label_text(self) -> str:
        return f"{MONTH_NAMES[self.current_month.month]} {self.current_month.year}"

    def _showing_bank(self) -> bool:
        return self._source == _SOURCE_BANK

    def _floor_pence(self) -> int:
        """The overdraft limit for a bank plot; zero for anything else.

        Zero means no facility, so a below-zero bar reads red. A bank plot
        passes the arranged limit and the bars inside it read amber instead.
        A card plot never has one.
        """
        if not self._showing_bank():
            return 0
        return self.budget_service.get_overdraft_limit().pence

    def _reserve_floor_values(self) -> list[int]:
        """The reserve floor across the viewed month; empty for a card plot.

        A card carries its own limit rather than a reserve, so nothing is set
        aside against it and the chart is given no line to read the bars
        against, which is how it drew before reserves existed.
        """
        if not self._showing_bank():
            return []
        return self.budget_service.get_bank_graph_floor_values(
            year_month=self.current_month
        )

    def _current_series(self):
        """Return (title, series) for the viewed month under the switch.

        Derived fresh on every call rather than cached, so stepping the month
        or editing a bill on another view always plots what is true now.
        """
        month = self._month_label_text()
        if self._showing_bank():
            summary = self.budget_service.get_month_summary(
                year_month=self.current_month
            )
            series = self.budget_service.get_bank_graph_series(
                year_month=self.current_month, summary=summary
            )
            return f"{month}: bank balance by day", [series]
        return (
            f"{month}: card balances by day",
            self.budget_service.get_card_graph_series(year_month=self.current_month),
        )

    def replot(self) -> None:
        """Re-derive the series and redraw, keeping the heading in step."""
        self._title, series = self._current_series()
        self._series = list(series)
        self.title_label.setText(self._title)
        self.chart.set_overdraft_limit_pence(self._floor_pence())
        self.chart.set_reserve_floor_values(self._reserve_floor_values())
        self.chart.set_data(self._series, self._mode)
        # A bank-balance projection offered beside a graph of cards would name
        # something other than what is on screen, so it goes with the switch.
        self.package_btn.setVisible(self._showing_bank())

    def _apply_source_face(self) -> None:
        """Show the picture of what a press will PLOT, words in the tooltip."""
        showing_bank = self._showing_bank()
        apply_image_face(
            self.source_btn,
            _CARDS_ICON if showing_bank else _BANK_ICON,
            _TO_CARDS_LABEL if showing_bank else _TO_BANK_LABEL,
            self._glyph_height,
        )

    def _apply_pilot_face(self) -> None:
        """Show the shape a press will DRAW, words in the tooltip."""
        drawing_bars = self._mode == MODE_BAR
        apply_glyph_face(
            self.pilot_btn,
            _LINE_GLYPH if drawing_bars else _BAR_GLYPH,
            _PILOT_TO_LINE if drawing_bars else _PILOT_TO_BAR,
            self._glyph_height,
        )

    def _toggle_source(self) -> None:
        self._source = _SOURCE_CARDS if self._showing_bank() else _SOURCE_BANK
        self._apply_source_face()
        self.replot()

    def _toggle_mode(self) -> None:
        self._mode = MODE_LINE if self._mode == MODE_BAR else MODE_BAR
        self._apply_pilot_face()
        self.chart.set_data(self._series, self._mode)

    # ---- the tray drives the month ------------------------------------------
    def set_month(self, year_month: YearMonth) -> None:
        """Follow the tray's month, exactly as every other page does."""
        self.current_month = year_month
        self._refresh_month_label()
        self.replot()

    def on_month_summary_updated(self, _summary) -> None:
        """Redraw when the month's data changes on another view."""
        self.replot()

    def _refresh_month_label(self) -> None:
        self.month_label.setText(self._month_label_text())

    def set_nav_label_color(self, color: str) -> None:
        """Recolour the nav month label to match the Solvency view."""
        apply_nav_label_color(self.month_label, color)

    def nav_targets(self) -> list:
        """Ordered keyboard-ring stops for this view.

        READING order: the top tray first, then the lower one left to right as
        drawn, then the page's own controls. The chart itself is not a stop;
        it takes no focus and offers nothing to activate, exactly as it did
        inside the dialog.
        """
        others = ring_view_stops(self.view_btns[:-1])
        archive_stop = ring_view_stops(self.view_btns[-1:])
        page_stops = [self.source_btn, self.pilot_btn, self.export_btn]
        if self.package_btn.isVisible():
            page_stops.append(self.package_btn)
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
            *page_stops,
        ]
