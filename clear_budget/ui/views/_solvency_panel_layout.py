"""The Solvency tab's three pages, built here to keep the panel module small.

The tab carries three distinct readings of the same month and they had grown
into one column: the bank account's position (what is safe to spend, whether
the month holds together, how the next two months look), the credit cards'
position (utilisation, interest, per-card movement) and the projection, which
is the same arithmetic run on an assumption rather than on what is entered.

Read together they are a wall. Each mixes badly with the others in its own
way. The card block sat in the middle of the bank narrative, between the
month's own figures and the forward projection that continues them. The
projection sat directly under the spendable headline, where a muted second
figure next to the real one invites the two to be read as one reading with a
qualifier, which is exactly what it is not: it answers a different question
and is only true if its assumption is.

So they are three pages behind pilot buttons rather than one long scroll. Each
page is a coherent answer to a single question. A button names the page it
goes to rather than the page you are on, the same convention the month graph's
own pilot button uses. The button for the page you are already reading is
hidden rather than disabled, so the keyboard ring skips it instead of stopping
on a control that does nothing.

Every page is built once and kept alive in a stack: rebuilding on each switch
would drop the card bars' scroll position and make the change feel like a
reload rather than a turn of the page.
"""

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from clear_budget.ui import label_roles, ui_scale
from clear_budget.ui.utils.format_helpers import fmt

# Section headings on this tab share one QSS role (see _theme_controls).
_HEADING_ROLE = "SolvencySectionHeading"
# Unscaled type size of a forward-projection line, matching the card block's.
_PROJECTION_FONT_PX = 17
# The assumption, stated in the words the derivation is written in. It is
# not a setting anyone turned on, so the page has to say what it did.
_ASSUMPTION_TEXT = (
    "Income entered for this month is taken to arrive again in every later "
    "month with no entry of the same name. Later months keep their own bills "
    "and their own entries. None of this is counted anywhere else in the app."
)


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

    def _build_projection_page(self) -> QWidget:
        """The same arithmetic on an assumption instead of on what is entered.

        It has a page rather than a footnote because it answers a different
        question from the bank page: not "what does my budget say" but "what
        would it say if the months ahead resembled this one". Sitting under
        the real headline it read as a qualifier on that figure; here nothing
        it says can be mistaken for a fact about money already entered.

        It carries NO SPENDABLE FIGURE, deliberately. It had one, then a
        restatement of the bank page's beside it; both were withdrawn.
        "What can I spend today" is a question about money the user actually
        has, so a second answer to it on a page whose every number is
        conditional invites the conditional one to be spent. The two answers
        also disagree by construction, since surviving longer makes the later
        months count against today, so the assumed figure comes out lower and
        the pair reads as a contradiction rather than as two questions.

        What is left is what the page is for and it still reads in the bank
        page's order: the assumption in words, what has to arrive for it to
        hold, then the months after this one walked again under it.

        The page always has something to say. When there is nothing to assume
        the block hides and a line says so, because a page reachable by a
        button the user just pressed must never be blank.
        """
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(_heading("Safe to Spend If This Repeats"))
        self.sts_banner = _line("SolvencyBanner", wrap=False)
        layout.addWidget(self.sts_banner)
        self.sts_detail = _line("SolvencyCommitted")
        layout.addWidget(self.sts_detail)
        # A shortfall spending cannot fix gets its own label rather than a
        # second sentence in the line above: it is the one statement here that
        # no restraint answers, so it takes the traffic light's red while the
        # reach sentence keeps the muted body colour. One label could not hold
        # both, since a QLabel carries one colour.
        self.sts_shortfall = _line("SolvencyShortfall")
        self.sts_shortfall.hide()
        layout.addWidget(self.sts_shortfall)
        # Hidden when the figure never moves, so a flat month says nothing
        # rather than restating the headline.
        self.sts_capacity = _line("SolvencyBreakdown")
        self.sts_capacity.hide()
        layout.addWidget(self.sts_capacity)

        # Deliberately NOT part of assumed_block(): the figure is shown
        # whether or not this month has anything to repeat forward, because
        # with nothing to assume it simply equals what was entered. Hiding it
        # there would leave the app with no spendable figure at all in the
        # commonest case, which is every month fully filled in.
        self.assumed_terms_heading = _heading("What This Assumes")
        layout.addWidget(self.assumed_terms_heading)
        # The rule is DERIVED, so it has to be stated: nothing was ticked to
        # produce this page and the user cannot infer the rule from the
        # figures it produced.
        self.assumed_basis_label = _line("SolvencyCommitted", _ASSUMPTION_TEXT)
        layout.addWidget(self.assumed_basis_label)
        # Italic, because it is the one block on the page that is not yet
        # true: it names money that has to turn up. The colour stays neutral,
        # since a list of expectations has no traffic-light state of its own.
        self.assumed_gaps_label = _line("SolvencyAssumedNote")
        layout.addWidget(self.assumed_gaps_label)

        self.assumed_forward_heading = _heading("Forward Projection If This Repeats")
        layout.addWidget(self.assumed_forward_heading)
        # The months the bank page shows, walked again on the assumption. This
        # is the question the page is opened for: a bank page ending in an
        # overdrawn month is exactly when someone asks whether the money they
        # expect would rescue it; the page used to decline to answer.
        self.m1_assumed_projection_label = _projection_label()
        layout.addWidget(self.m1_assumed_projection_label)
        self.m2_assumed_projection_label = _projection_label()
        layout.addWidget(self.m2_assumed_projection_label)

        self.assumed_empty_label = _line(
            "SolvencyCommitted",
            "Nothing to assume: every month ahead already carries the income"
            " this one does.",
        )
        self.assumed_empty_label.hide()
        layout.addWidget(self.assumed_empty_label)

        for widget in self.assumed_block():
            widget.hide()

        layout.addStretch()
        return page

    def assumed_block(self) -> tuple:
        """Every widget of the projection page's populated state.

        Named once here so building the page and emptying it cannot disagree
        about what the block is: a heading left visible over a hidden body was
        the failure mode when the two lists were maintained separately.
        """
        return (
            self.assumed_terms_heading,
            self.assumed_basis_label,
            self.assumed_gaps_label,
            self.assumed_forward_heading,
            self.m1_assumed_projection_label,
            self.m2_assumed_projection_label,
        )

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
