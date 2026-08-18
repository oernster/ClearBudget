"""How It Works dialog - plain-English explanation of ClearBudget's calculations.

Deliberately about CONCEPTS, not controls: it explains only what the screens
cannot say for themselves (how pro-rating works, how the balance maintains
itself, what Safe to Spend Today means). A button-by-button inventory was
tried and read as a wall of text; buttons explain themselves in context.
"""

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

from clear_budget.ui import ui_scale
from clear_budget.ui.widgets.auto_scroller import AutoScroller

_HOW_IT_WORKS_TEXT = """\
<h2>How Clear Budget Works</h2>

<h3>Pro-rated bills (no fixed due date)</h3>
<p>A bill with no fixed day - "Food", say - is treated as spent evenly
across the month, so only the part still ahead of you counts as due:</p>
<p><b>still due</b> = amount &minus; (amount &times; today's day &divide;
days in month, rounded up)</p>
<p><b>Example:</b> Food is &pound;200 on the 11th of a 30-day month:
&pound;74 has notionally gone, &pound;126 is still due.</p>
<p>A bill with a fixed day counts in full until that day, then drops to
zero. The projected balance follows the same rule, so it eases down a
little each day rather than dropping all at once.</p>

<hr>
<h3>Your bank balance</h3>
<p>Set the balance once with the &#128221; button; Clear Budget then keeps
it up to date. A dated bank bill is deducted at midnight on its due day and
ticked <b>Paid</b>; dated income is added and ticked <b>Received</b>. Days
missed while the app was closed are caught up at the next launch. Adding an
item dated today offers to apply it immediately - say No if your balance
already reflects it. Deleting an auto-applied item hands the amount back;
typing a balance yourself supersedes everything applied before it. Card
bills never touch the bank balance.</p>

<hr>
<h3>Safe to Spend Today</h3>
<p>The headline of the Solvency tab: the most you could spend today with
every day of the next few months still clearing your buffer. No day is left
out of that promise. An earlier version stopped at the first day already
under, on the grounds that those days were lost anyway; the figure that gave
was real but it was not spendable, because money spent today lowers the lost
days too, so it quietly funded its own deficit.</p>
<p>When the window cannot survive, the answer is nothing rather than a
number, stating what the window is short by. That shortfall is money to
find, not money to spend. The buffer and the number of months the figure must
keep standing are in Settings &gt; Bank Account: a longer window is a harder
promise, so it allows less.</p>

<hr>
<h3>Shaping a month</h3>
<p>A bill or income can be <b>skipped</b> for one month, <b>overridden</b>
(amount or day) for one month, added as a <b>one-off</b> for just this
month, given a <b>final month</b> after which it stops or given an
<b>amount change from a month onward</b> - what a rent increase is; earlier
months keep what they actually cost. Deleting a bill offers two scopes:
stop it from the viewed month onward (history stays intact) or delete it
everywhere, for entries added by mistake.</p>

<hr>
<h3>Graphs and exports</h3>
<p>The app icon in the navigation tray opens the viewed month as a graph
(bank balance day by day or every card on the Credit Cards tab), steppable
between months. It can be exported as a single self-contained web page and
Monthly Budget can also export a projection across a range of months,
showing each month's close and its lowest point. Both open offline and
default to Downloads.</p>

<hr>
<h3>Archive</h3>
<p>Months are archived automatically the moment they end - there is no
manual step. The Archive tab holds only fully-completed months.</p>

<hr>
<h3>Saving, loading and viewer packages</h3>
<p>Save copies the database to a remembered file; Load validates a file
before replacing anything. An admin can export a <b>read-only viewer
package</b> (a snapshot plus credentials) for someone else to import from
their sign-in screen; re-exporting and re-importing refreshes the same
account. A viewer sees everything and can change nothing, with
"(Read-only)" in the title bar.</p>

<hr>
<h3>Keyboard</h3>
<p>Tab or Right moves forward; Shift+Tab or Left moves back, wrapping at
both ends. Up/Down walk table rows; Enter equals Space. Green outline:
focused or hovered. Red outline: disabled. Nothing is highlighted on launch
until the first keypress.</p>
"""


class HowItWorksDialog(QDialog):
    """Explains the calculations and concepts in plain English."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("How It Works")
        self.setMinimumSize(ui_scale.px(640), ui_scale.px(560))
        layout = QVBoxLayout()

        body = QTextBrowser()
        body.setOpenExternalLinks(True)
        body.setHtml(_HOW_IT_WORKS_TEXT)
        layout.addWidget(body)
        self._scroller = AutoScroller(body)

        btn_row = QHBoxLayout()
        close_btn = QPushButton("Close")
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self.setLayout(layout)
        close_btn.clicked.connect(self.accept)
