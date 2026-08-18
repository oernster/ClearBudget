"""The Solvency tab's two pages, built here to keep the panel module small.

The tab carries two distinct readings of the same month and they had grown
into one column: the bank account's position (what is safe to spend, whether
the month holds together, how the next two months look) and the credit cards'
position (utilisation, interest, per-card movement). Read together they are a
wall; the card block also sits in the middle of the bank narrative, between
the month's own figures and the forward projection that continues them.

So they are two pages behind one pilot button rather than one long scroll.
Each page is a coherent answer to a single question. The button names the
page it goes to rather than the page you are on, which is the same convention
the month graph's own pilot button uses.

Both pages are built once and kept alive in a stack: rebuilding on each
switch would drop the card bars' scroll position and make the toggle feel
like a reload rather than a turn of the page.
"""

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from clear_budget.ui import label_roles, ui_scale
from clear_budget.ui.utils.format_helpers import fmt

# Section headings on this tab share one QSS role (see _theme_controls).
_HEADING_ROLE = "SolvencySectionHeading"
# Unscaled type size of a forward-projection line, matching the card block's.
_PROJECTION_FONT_PX = 17


def _heading(text: str) -> QLabel:
    """A section heading in the tab's shared heading role."""
    label = QLabel(text)
    label.setObjectName(_HEADING_ROLE)
    return label


def _line(object_name: str, text: str = "", *, wrap: bool = True) -> QLabel:
    """A body line carrying a QSS role by object name."""
    label = QLabel(text)
    label.setWordWrap(wrap)
    label.setObjectName(object_name)
    return label


def _projection_label() -> QLabel:
    """One month's forward-projection block."""
    label = QLabel("")
    label.setWordWrap(True)
    label.setStyleSheet(
        ui_scale.style(f"font-size: {_PROJECTION_FONT_PX}px; padding: 5px;")
    )
    return label


class SolvencyPanelLayoutMixin:
    """Builds the bank page and the cards page."""

    def _build_bank_page(self) -> QWidget:
        """The bank account's position: spendable, solvent and what is coming.

        Everything here answers one question, "does the account hold", so the
        page reads top to bottom as a single argument: what you can spend
        today, whether you are heading for an overdraft, where the month
        stands and then the two months after it.
        """
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(_heading("Safe to Spend Today"))
        self.sts_banner = _line("SolvencyBanner", wrap=False)
        layout.addWidget(self.sts_banner)
        self.sts_detail = _line("SolvencyCommitted")
        layout.addWidget(self.sts_detail)
        # Hidden when the figure never moves, so a flat month says nothing
        # rather than restating the headline.
        self.sts_capacity = _line("SolvencyBreakdown")
        self.sts_capacity.hide()
        layout.addWidget(self.sts_capacity)

        # The second reading, hidden until something is marked as expected.
        self.assumed_heading = _heading("If the expected income arrives")
        self.assumed_heading.hide()
        layout.addWidget(self.assumed_heading)
        self.sts_assumed = _line("SolvencyCommitted")
        self.sts_assumed.hide()
        layout.addWidget(self.sts_assumed)
        self.assumed_gaps_label = _line("SolvencyCommitted")
        self.assumed_gaps_label.hide()
        layout.addWidget(self.assumed_gaps_label)

        layout.addWidget(_heading("Overdraft Status"))
        self.overdraft_alert = _line(
            "SolvencyBanner", f"SAFE: {fmt(0)} buffer", wrap=False
        )
        layout.addWidget(self.overdraft_alert)
        self.midmonth_alert = _line("SolvencyMidmonthAlert")
        self.midmonth_alert.hide()
        layout.addWidget(self.midmonth_alert)

        layout.addWidget(_heading("Overall Health"))
        self.balance_label = _line(label_roles.VALUE, f"Bank Balance: {fmt(0)}")
        layout.addWidget(self.balance_label)
        self.committed_label = _line("SolvencyCommitted", "Committed this month: -")
        layout.addWidget(self.committed_label)
        self.remaining_bank_label = _line(
            "SolvencyRemainingBank", "Still due this month (bank): -"
        )
        layout.addWidget(self.remaining_bank_label)
        self.remaining_card_label = _line(
            "SolvencyRemainingCard", "Still due this month (cards): -"
        )
        layout.addWidget(self.remaining_card_label)
        self.month_breakdown_label = _line("SolvencyBreakdown")
        layout.addWidget(self.month_breakdown_label)
        self.gap_label = _line("SolvencyCommitted")
        layout.addWidget(self.gap_label)

        layout.addWidget(_heading("Forward Projection"))
        self.m1_projection_label = _projection_label()
        layout.addWidget(self.m1_projection_label)
        self.m2_projection_label = _projection_label()
        layout.addWidget(self.m2_projection_label)

        layout.addStretch()
        return page

    def _build_cards_page(self) -> QWidget:
        """The cards' position: utilisation now, then the same two months.

        The card lines used to sit inside the bank page's forward projection
        blocks. They are the same two months, so they keep their headings
        here and the reader can hold the two pages against each other.
        """
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(_heading("Credit Card Status"))
        self.card_interest_label = _line("SolvencyCommitted")
        layout.addWidget(self.card_interest_label)

        self.card_bars_container = QWidget()
        self.card_bars_layout = QVBoxLayout(self.card_bars_container)
        self.card_bars_layout.setSpacing(ui_scale.px(3))
        self.card_bars_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.card_bars_container)

        layout.addWidget(_heading("Card Projection"))
        self.m1_cards_label = _projection_label()
        layout.addWidget(self.m1_cards_label)
        self.m2_cards_label = _projection_label()
        layout.addWidget(self.m2_cards_label)

        layout.addStretch()
        return page
