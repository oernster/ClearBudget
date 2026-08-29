"""The main window's view pages and the wiring that keeps them in step.

Split out of `main_window` as one cohesive concern: building the six pages,
connecting the signals that keep their month and their data together, then
mapping every tray's copy of the view buttons onto the pages. Together they
were what pushed that module into the LOC danger band
(`tests/structural/test_loc_limits.py`).

The pages are POSITIONAL. `_wire_view_buttons` hands button index `i` to
`setCurrentIndex(i)`, so the order the pages are added here must match
`view_buttons.VIEW_SPECS` exactly; `tests/structural/test_tray_switch_invariants`
asserts the two lists against each other, because a page in the wrong slot
sends every tray to the wrong page and looks entirely normal doing it.
"""

from __future__ import annotations

from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from clear_budget.ui.utils.nav_header import set_nav_user
from clear_budget.ui.utils.view_buttons import mark_current_view
from clear_budget.ui.views.archive_view import ArchiveView
from clear_budget.ui.views.credit_card_view import CreditCardView
from clear_budget.ui.views.graph_view import GraphView
from clear_budget.ui.views.month_view import MonthView
from clear_budget.ui.views.recommendations_view import RecommendationsView
from clear_budget.ui.views.reserves_view import ReservesView
from clear_budget.ui.views.solvency_panel import SolvencyPanel
from clear_budget.ui.utils.nav_glyph_size import footer_glyph_height, nav_glyph_height
from clear_budget.ui.widgets.bottom_tray import BottomTray
from clear_budget.ui.widgets.scrollable_view import ScrollableView


class MainWindowViewsMixin:
    """Builds the view pages and keeps every tray's view buttons in step."""

    def _report_view(self, index: int, name: str) -> None:
        """Say which view is being built, so the sign-in screen can show it.

        Reported BEFORE the view is constructed rather than after: the label
        names what is happening now; the bar's position is what says how
        much is done.
        """
        self._progress(self._first_stage + index, self._total_stages, name)

    def init_ui(self) -> None:
        """Build main window with its views."""
        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self.views = QTabWidget()
        # The bar is HIDDEN and stays that way. The views are reached by icon buttons
        # in each view's navigation tray, so a strip above them would be a
        # second, empty copy of the same control. The QTabWidget is kept for
        # what it is actually good at, owning the pages and switching between
        # them; nothing styles or navigates the bar, because nobody sees it.
        self.views.tabBar().hide()

        self._report_view(0, "Monthly Budget")
        month_view = MonthView(self.month_view_model)
        self.views.addTab(self._scrollable(month_view), "Monthly Budget")

        self._report_view(1, "Solvency")
        solvency_panel = SolvencyPanel(
            self.solvency_view_model,
            base_month=self.month_view_model.base_month,
        )
        self.views.addTab(self._scrollable(solvency_panel), "Solvency")

        self._report_view(2, "Credit Cards")
        credit_card_view = CreditCardView(
            self.month_view_model.budget_service,
            self.month_view_model.current_month,
            base_month=self.month_view_model.base_month,
        )
        self.views.addTab(self._scrollable(credit_card_view), "Credit Cards")

        # Right of Credit Cards, matching VIEW_SPECS: what is held back for a
        # bill that has not asked yet, which is the money the pages either
        # side of it would otherwise call spendable.
        self._report_view(3, "Reserves")
        reserves_view = ReservesView(
            self.month_view_model.budget_service,
            self.month_view_model.current_month,
        )
        self.views.addTab(self._scrollable(reserves_view), "Reserves")

        # Between Reserves and Archive, which is where the graph icon has
        # always been drawn. It was an icon button opening a modal dialog; it
        # is a page now, so the tray looks the same and behaves like the rest
        # of it.
        self._report_view(4, "Graph")
        graph_view = GraphView(
            self.month_view_model.budget_service,
            self.month_view_model.current_month,
        )
        self.views.addTab(self._scrollable(graph_view), "Graph")

        # Right of Graph, left of Archive, matching VIEW_SPECS. The advice is
        # anchored to today whatever month the tray shows.
        self._report_view(5, "Recommendations")
        recommendations_view = RecommendationsView(
            self.month_view_model.budget_service,
            self.month_view_model.current_month,
        )
        self.views.addTab(self._scrollable(recommendations_view), "Recommendations")

        self._report_view(6, "Archive")
        archive_view = ArchiveView(self.month_view_model.budget_service)
        self.views.addTab(self._scrollable(archive_view), "Archive")

        # Every tray carries the same icon shortcuts; all of them drive the
        # same window-level flows their menu items do.
        for _tray_view in (
            month_view,
            solvency_panel,
            credit_card_view,
            reserves_view,
            graph_view,
            recommendations_view,
            archive_view,
        ):
            _tray_view.save_btn.clicked.connect(self._on_save_database)
            _tray_view.load_btn.clicked.connect(self._on_load_database)
            _tray_view.budgets_btn.clicked.connect(self._on_manage_budgets)
            _tray_view.bank_btn.clicked.connect(self._on_bank_account_settings)
            _tray_view.info_btn.clicked.connect(self._on_how_it_works)
            set_nav_user(
                _tray_view.nav_header,
                self.current_user.username,
            )

        layout.addWidget(self.views)
        # One footer for the WINDOW, under the stacked views rather than inside
        # each of them. Its glyph is two thirds of the tray's, measured from the
        # tray's own Previous button rather than from a second control built to
        # look like it, so the two can never report different heights.
        self.bottom_tray = BottomTray(
            central_widget,
            footer_glyph_height(nav_glyph_height(month_view.prev_btn)),
            open_donation=self.open_donation,
        )
        layout.addWidget(self.bottom_tray)
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        self.month_view_model.month_changed.connect(self.solvency_view_model.set_month)
        self.month_view_model.month_changed.connect(credit_card_view.set_month)
        self.month_view_model.month_changed.connect(reserves_view.set_month)
        self.month_view_model.month_changed.connect(graph_view.set_month)
        self.month_view_model.month_changed.connect(recommendations_view.set_month)
        self.month_view_model.month_summary_updated.connect(
            self.solvency_view_model.update_month_summary
        )
        # The card panels and the six-month strip are driven by the month's
        # bills, which are edited on a DIFFERENT view, so they need the same
        # summary signal Solvency already takes. Without it the Credit Cards
        # view showed whatever was true when the window was built.
        self.month_view_model.month_summary_updated.connect(
            credit_card_view.on_month_summary_updated
        )
        # The graph plots the same bills, edited on a different view, so it
        # needs the same signal for the same reason.
        self.month_view_model.month_summary_updated.connect(
            graph_view.on_month_summary_updated
        )
        # A reserve is measured against the same months, so an edit that
        # changes a summary changes what is being held back.
        self.month_view_model.month_summary_updated.connect(
            reserves_view.on_month_summary_updated
        )
        # The advice is computed from the months as entered, so any edit that
        # changes a summary re-answers the question this page asks.
        self.month_view_model.month_summary_updated.connect(
            recommendations_view.on_month_summary_updated
        )

        solvency_panel.prev_btn.clicked.connect(self.month_view_model.previous_month)
        solvency_panel.next_btn.clicked.connect(self.month_view_model.next_month)
        credit_card_view.prev_btn.clicked.connect(self.month_view_model.previous_month)
        credit_card_view.next_btn.clicked.connect(self.month_view_model.next_month)
        graph_view.prev_btn.clicked.connect(self.month_view_model.previous_month)
        graph_view.next_btn.clicked.connect(self.month_view_model.next_month)
        recommendations_view.prev_btn.clicked.connect(
            self.month_view_model.previous_month
        )
        recommendations_view.next_btn.clicked.connect(self.month_view_model.next_month)

        for _nav in (
            solvency_panel,
            credit_card_view,
            graph_view,
            recommendations_view,
        ):
            self.month_view_model.month_changed.connect(
                lambda ym, b=_nav.prev_btn: b.setEnabled(
                    ym > self.month_view_model.base_month
                )
            )

        at_base = (
            self.month_view_model.current_month <= self.month_view_model.base_month
        )
        solvency_panel.prev_btn.setEnabled(not at_base)
        credit_card_view.prev_btn.setEnabled(not at_base)
        graph_view.prev_btn.setEnabled(not at_base)
        recommendations_view.prev_btn.setEnabled(not at_base)

        # Solvency owns the nav-label health colour; mirror it onto every view.
        for _view in (
            month_view,
            credit_card_view,
            graph_view,
            recommendations_view,
            archive_view,
        ):
            solvency_panel.month_label_color_changed.connect(_view.set_nav_label_color)

        if self.month_view_model.month_summary:
            self.solvency_view_model.update_month_summary(
                self.month_view_model.month_summary
            )

        # POSITIONAL, matching the addTab order above and VIEW_SPECS. It feeds
        # both the view-button wiring and the keyboard ring, which are indexed
        # by page position, so a view missing here is a page whose buttons do
        # nothing and whose ring belongs to another view. Reserves was missing
        # exactly that way.
        _views = [
            month_view,
            solvency_panel,
            credit_card_view,
            reserves_view,
            graph_view,
            recommendations_view,
            archive_view,
        ]
        self._wire_view_buttons(_views)
        self._setup_keyboard_nav(_views)

    @staticmethod
    def _scrollable(widget: QWidget) -> ScrollableView:
        return ScrollableView(widget)

    def _wire_view_buttons(self, views: list) -> None:
        """Point every view's buttons at the pages and keep them in step.

        Every view carries its OWN four buttons, because every view builds its
        own tray. They all drive the one QTabWidget; every set is marked
        together on each switch, so the view you are on is marked whichever
        tray you happen to be looking at.
        """
        for view in views:
            for index, button in enumerate(view.view_btns):
                button.clicked.connect(
                    lambda _checked=False, target=index: self.views.setCurrentIndex(
                        target
                    )
                )
        self._view_button_sets = [view.view_btns for view in views]
        self.views.currentChanged.connect(self._mark_current_view)
        self._mark_current_view(self.views.currentIndex())

    def _mark_current_view(self, index: int) -> None:
        """Mark `index` as current on every view's copy of the view buttons."""
        for buttons in self._view_button_sets:
            mark_current_view(buttons, index)
