"""The main window's tab pages and the wiring that keeps them in step.

Split out of `main_window` as one cohesive concern: building the five pages,
connecting the signals that keep their month and their data together, then
mapping every tray's copy of the tab buttons onto the pages. Together they
were what pushed that module into the LOC danger band
(`tests/structural/test_loc_limits.py`).

The pages are POSITIONAL. `_wire_tab_buttons` hands button index `i` to
`setCurrentIndex(i)`, so the order the pages are added here must match
`tab_icons.TAB_SPECS` exactly; `tests/structural/test_tray_switch_invariants`
asserts the two lists against each other, because a page in the wrong slot
sends every tray to the wrong page and looks entirely normal doing it.
"""

from __future__ import annotations

from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from clear_budget.ui.utils.nav_header import set_nav_user
from clear_budget.ui.utils.tab_icons import mark_current_tab
from clear_budget.ui.views.archive_view import ArchiveView
from clear_budget.ui.views.credit_card_view import CreditCardView
from clear_budget.ui.views.graph_view import GraphView
from clear_budget.ui.views.month_view import MonthView
from clear_budget.ui.views.solvency_panel import SolvencyPanel
from clear_budget.ui.widgets.scrollable_tab import ScrollableTab


class MainWindowTabsMixin:
    """Builds the tab pages and keeps every tray's tab buttons in step."""

    def init_ui(self) -> None:
        """Build main window with tabs."""
        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        # The bar is HIDDEN and stays that way. The tabs are icon buttons
        # in each view's navigation tray, so a strip above them would be a
        # second, empty copy of the same control. The QTabWidget is kept for
        # what it is actually good at, owning the pages and switching between
        # them; nothing styles or navigates the bar, because nobody sees it.
        self.tabs.tabBar().hide()

        month_view = MonthView(self.month_view_model)
        self.tabs.addTab(self._scrollable(month_view), "Monthly Budget")

        solvency_panel = SolvencyPanel(
            self.solvency_view_model,
            base_month=self.month_view_model.base_month,
        )
        self.tabs.addTab(self._scrollable(solvency_panel), "Solvency")

        credit_card_view = CreditCardView(
            self.month_view_model.budget_service,
            self.month_view_model.current_month,
            base_month=self.month_view_model.base_month,
        )
        self.tabs.addTab(self._scrollable(credit_card_view), "Credit Cards")

        # Between Credit Cards and Archive, which is where the graph icon has
        # always been drawn. It was an icon button opening a modal dialog; it
        # is a page now, so the tray looks the same and behaves like the rest
        # of it.
        graph_view = GraphView(
            self.month_view_model.budget_service,
            self.month_view_model.current_month,
        )
        self.tabs.addTab(self._scrollable(graph_view), "Graph")

        archive_view = ArchiveView(self.month_view_model.budget_service)
        self.tabs.addTab(self._scrollable(archive_view), "Archive")

        # Every tray carries the same icon shortcuts; all of them drive the
        # same window-level flows their menu items do.
        for _tray_view in (
            month_view,
            solvency_panel,
            credit_card_view,
            graph_view,
            archive_view,
        ):
            _tray_view.save_btn.clicked.connect(self._on_save_database)
            _tray_view.load_btn.clicked.connect(self._on_load_database)
            _tray_view.budgets_btn.clicked.connect(self._on_manage_budgets)
            _tray_view.users_btn.clicked.connect(self._on_users)
            _tray_view.settings_btn.clicked.connect(self._on_preferences)
            _tray_view.bank_btn.clicked.connect(self._on_bank_account_settings)
            _tray_view.info_btn.clicked.connect(self._on_how_it_works)
            set_nav_user(
                _tray_view.nav_header,
                self.current_user.username,
            )

        layout.addWidget(self.tabs)
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        self.month_view_model.month_changed.connect(self.solvency_view_model.set_month)
        self.month_view_model.month_changed.connect(credit_card_view.set_month)
        self.month_view_model.month_changed.connect(graph_view.set_month)
        self.month_view_model.month_summary_updated.connect(
            self.solvency_view_model.update_month_summary
        )
        # The card panels and the six-month strip are driven by the month's
        # bills, which are edited on a DIFFERENT tab, so they need the same
        # summary signal Solvency already takes. Without it the Credit Cards
        # tab showed whatever was true when the window was built.
        self.month_view_model.month_summary_updated.connect(
            credit_card_view.on_month_summary_updated
        )
        # The graph plots the same bills, edited on a different tab, so it
        # needs the same signal for the same reason.
        self.month_view_model.month_summary_updated.connect(
            graph_view.on_month_summary_updated
        )

        solvency_panel.prev_btn.clicked.connect(self.month_view_model.previous_month)
        solvency_panel.next_btn.clicked.connect(self.month_view_model.next_month)
        credit_card_view.prev_btn.clicked.connect(self.month_view_model.previous_month)
        credit_card_view.next_btn.clicked.connect(self.month_view_model.next_month)
        graph_view.prev_btn.clicked.connect(self.month_view_model.previous_month)
        graph_view.next_btn.clicked.connect(self.month_view_model.next_month)

        for _nav in (solvency_panel, credit_card_view, graph_view):
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

        # Solvency owns the nav-label health colour; mirror it onto every tab.
        for _view in (month_view, credit_card_view, graph_view, archive_view):
            solvency_panel.month_label_color_changed.connect(_view.set_nav_label_color)

        if self.month_view_model.month_summary:
            self.solvency_view_model.update_month_summary(
                self.month_view_model.month_summary
            )

        _views = [
            month_view,
            solvency_panel,
            credit_card_view,
            graph_view,
            archive_view,
        ]
        self._wire_tab_buttons(_views)
        self._setup_keyboard_nav(_views)

    @staticmethod
    def _scrollable(widget: QWidget) -> ScrollableTab:
        return ScrollableTab(widget)

    def _wire_tab_buttons(self, views: list) -> None:
        """Point every view's tab buttons at the pages and keep them in step.

        Every view carries its OWN four buttons, because every view builds its
        own tray. They all drive the one QTabWidget; every set is marked
        together on each switch, so the tab you are on is marked whichever
        tray you happen to be looking at.
        """
        for view in views:
            for index, button in enumerate(view.tab_btns):
                button.clicked.connect(
                    lambda _checked=False, target=index: self.tabs.setCurrentIndex(
                        target
                    )
                )
        self._tab_button_sets = [view.tab_btns for view in views]
        self.tabs.currentChanged.connect(self._mark_current_tab)
        self._mark_current_tab(self.tabs.currentIndex())

    def _mark_current_tab(self, index: int) -> None:
        """Mark `index` as current on every view's copy of the tab buttons."""
        for buttons in self._tab_button_sets:
            mark_current_tab(buttons, index)
