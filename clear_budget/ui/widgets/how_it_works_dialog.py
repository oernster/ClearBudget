"""How It Works dialog - what the screens cannot say for themselves.

Two jobs, in this order. It NAMES the furniture, each entry carrying the real
icon or glyph the tray and the view-button row actually draw, so the pictures that
replaced the old text labels can be identified by someone who has just met
them. Then it explains the three rules the numbers depend on and that no
screen can state on its own: how an undated bill accrues, how the balance
maintains itself and what Safe to Spend Today is a promise about.

It is deliberately short. A button-by-button inventory was tried first and
read as a wall of text; so did the essay that replaced it, which explained
every rejected design alongside the shipped one. A help screen nobody
finishes explains nothing, so anything a control says for itself is left to
the control.

Every entry carries the REAL icon the app draws, pulled through the same
resource lookup the tray and the view-button row use. Never a description in words;
never a similar-looking emoji standing in for a picture; never a decorative
glyph that corresponds to no control. An icon guide showing something other
than the icon is worse than no guide. The whole screen is pictures now, so
there is nothing left for a stand-in to stand in for.

The icons are drawn at half again the size they first shipped at. At 20px
they sat inside the line politely and could not be told apart from each
other, which is the one job this screen has.
"""

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

from clear_budget.ui import ui_scale
from clear_budget.ui.utils.view_buttons import (
    ARCHIVE_ICON,
    CREDIT_CARDS_ICON,
    GRAPH_ICON,
    MONTHLY_BUDGET_ICON,
    RECOMMENDATIONS_ICON,
    RESERVES_ICON,
    SOLVENCY_ICON,
)
from clear_budget.ui.widgets.auto_scroller import AutoScroller

# Height of an inline icon in the body text, unscaled. Half again the 20px it
# started at: the artwork is detailed (a folder with an arrow, a cabinet with
# a tick) and at 20px those details closed up, so two icons a user was trying
# to tell apart read as the same smudge. Bigger than the text it sits in on
# purpose; this screen is read to IDENTIFY a picture, not to skim a sentence.
_INLINE_ICON_PX = 30


def _img(path, px: int) -> str:
    """One bundled image as an inline <img>; an empty string if unbundled.

    Empty rather than a placeholder: the line still reads without its
    picture; a missing asset must never stop the help screen opening.

    Centred on the line rather than sitting on its baseline. At this size a
    baseline-aligned picture hangs below the words it leads, which reads as
    the row having slipped rather than as an icon in a sentence.
    """
    if path is None:
        return ""
    return (
        f'<img src="file:///{str(path).replace(chr(92), "/")}" '
        f'width="{px}" height="{px}" style="vertical-align: middle"> '
    )


def _view_row(spec: str, name: str, text: str, px: int) -> str:
    """One view's line, led by the picture its button actually draws."""
    from clear_budget.shared.resources import find_nav_icon_path

    return f"<p>{_img(find_nav_icon_path(spec), px)}<b>{name}</b>: {text}</p>"


def _body_html() -> str:
    """Build the help text, resolving the real icons at open time."""
    from clear_budget.shared.resources import find_nav_icon_path

    px = ui_scale.px(_INLINE_ICON_PX)
    # The Bank Account button is a PICTURE in the tray, so it is a picture
    # here. An icon guide showing something other than the icon is worse
    # than no guide.
    bank_icon = _img(find_nav_icon_path("bank-icon.png"), px)
    budgets_icon = _img(find_nav_icon_path("switchbudget.png"), px)
    load_icon = _img(find_nav_icon_path("opendb.png"), px)
    save_icon = _img(find_nav_icon_path("savedb.png"), px)
    info_icon = _img(find_nav_icon_path("information.png"), px)
    light_icon = _img(find_nav_icon_path("lightmode.png"), px)
    dark_icon = _img(find_nav_icon_path("darkmode.png"), px)
    # The Graph page's own controls, which are pictures too and which no
    # other line here names.
    plot_bank_icon = _img(find_nav_icon_path("bank-icon2.png"), px)
    plot_cards_icon = _img(find_nav_icon_path("creditcards2.png"), px)
    export_icon = _img(find_nav_icon_path("exporttohtml.png"), px)
    package_icon = _img(find_nav_icon_path("exportpackage.png"), px)
    # The footer's own button, which sits in no tray and which no other line
    # here names. A picture of a beer and a coffee says nothing on its own
    # about leaving the application, so this line says it.
    donate_icon = _img(find_nav_icon_path("donate.png"), px)
    return f"""\
<h2>How ClearBudget Works</h2>

<h3>The seven views</h3>
{_view_row(MONTHLY_BUDGET_ICON, "Monthly Budget",
          "this month's bills and income, plus what the balance does.", px)}
{_view_row(SOLVENCY_ICON, "Solvency",
          "whether the month holds, plus the two months after it, each led "
          "by what it would take to keep it afloat and the day that money has "
          "to arrive by. Two pages behind the button at the top: the bank and "
          "Safe to Spend.", px)}
{_view_row(CREDIT_CARDS_ICON, "Credit Cards",
          "one panel per card, with a six-month projection. A limit that "
          "changes on a known date is entered ahead of time, so each month is "
          "projected against the limit it will actually have.", px)}
{_view_row(RESERVES_ICON, "Reserves",
          "money held back for a bill that has not arrived yet. Name what is "
          "coming and it accrues a little each month, so Safe to Spend and "
          "the graph stop counting that money as spendable. Nothing is moved "
          "anywhere and no second account is assumed; what changes is only "
          "what the app is willing to call spendable. The emergency buffer "
          "the Recommendations page aims at is set here too.", px)}
{_view_row(GRAPH_ICON, "Graph",
          "the month drawn day by day, as bars or as a line. The heading "
          "above the chart always names what is plotted. The tray's arrows "
          "step its month like any other page.", px)}
{_view_row(RECOMMENDATIONS_ICON, "Recommendations",
          "what would make the months ahead survivable: which bills or "
          "incomes could move and how much extra the months still need, "
          "with an optional emergency buffer set at the top of the page. "
          "Suggestions only; nothing is changed for you. Tick any "
          "suggestion to see it tried across the page, still changing "
          "nothing.", px)}
{_view_row(ARCHIVE_ICON, "Archive",
          "months that have finished. They are filed automatically; there is "
          "no archive button. Its icon sits apart, at the right of the tray "
          "beside the light or dark toggle.", px)}
<p>Hover any view button to see its name.</p>

<hr>
<h3>On the Graph page</h3>
<p>{plot_bank_icon}/{plot_cards_icon}plot the bank balance or the cards
&nbsp;&middot;&nbsp; {export_icon}this month as one web page
&nbsp;&middot;&nbsp; {package_icon}a range of months as a folder of pages,
opened from its index</p>
<p>The two switches show what a press will PLOT, never what is on screen
now. Both exports are self-contained: no images to lose and nothing to
fetch, so they open on a machine that has never seen this app.</p>

<hr>
<h3>The tray</h3>
<p>{load_icon}load &nbsp;&middot;&nbsp; {save_icon}save
&nbsp;&middot;&nbsp; {budgets_icon}switch budget &nbsp;&middot;&nbsp;
{bank_icon}currency, overdraft and the Safe to
Spend buffer and window &nbsp;&middot;&nbsp; {light_icon}/{dark_icon}light or dark
&nbsp;&middot;&nbsp; {info_icon}this screen</p>
<p>Load and save open in the app's own data folder, where the live budgets
already are. Your signed-in name sits at the left of the row above, beside
the month; the arrows there step every view together.</p>

<hr>
<h3>The strip along the foot</h3>
<p>{donate_icon}buy the author a drink</p>
<p>A lighter strip under the page, holding one button at its left. It opens a
donation page in your browser; ClearBudget itself sends nothing, so it stays
as offline as the rest of the app. Nothing here is held back behind it.</p>

<hr>
<h3>Three rules behind the numbers</h3>

<p><b>A bill with no due day spreads across the month.</b> Only the part
ahead of you counts as still due, so &pound;200 of food on the 11th of a
30-day month leaves &pound;126.66. A bill WITH a due day counts in full until
that day, then drops to zero.</p>

<p><b>The balance keeps itself up to date.</b> Set it once. After
that, dated bills are deducted and dated income added at midnight on the day,
each ticking itself Paid or Received; days missed while the app was shut are
caught up at the next launch. Typing a balance yourself overrides everything
applied before it. Card bills never touch it.</p>

<p><b>Safe to Spend Today is a promise, not a balance.</b> It is the most you
could spend today with every month in your window still clearing its floor:
your buffer on every day, plus whatever the Reserves page is holding back on
that day, so the bar rises as a distant bill gets closer.
It assumes the income you entered for this month arrives again in each later
month that has none of that name, which is why it lives on its own Solvency
page with that assumption written under it. Months ahead look thin only
because their one-off income has not been typed in yet. If the window cannot
be saved, it says so and names the shortfall: that is money to find, not money
to spend.</p>

<hr>
<h3>Also worth knowing</h3>
<p>A bill or income can be skipped, overridden, ended, made a one-off or
given a new amount from a month onward. Deleting offers two scopes: stop it
here (earlier months keep it) or remove it everywhere. A red tick in its
dialog marks a day that cannot be moved in the real world; Recommendations
then never proposes retiming it.</p>
<p>One sign-in can hold several budgets, each a database of its own with its
own bills, income and cards. File &gt; New Budget makes one and the
switch-budget button in the tray moves between them; nothing you do in one
reaches another.</p>
<p>File &gt; Import / Export writes every account and every budget to a single
zip and puts the whole set back from one. Both belong to the first account ever
created, which is the only administrator. A restore is checked through before
any live file is replaced, so a backup that turns out to be broken changes
nothing.</p>
<p>The sign-in screen remembers accounts: choose one from the dropdown, with
a tick each for keeping the username and keeping the password. Keep the
recovery code you were shown when the account was made; it is the only way
back in if the password goes.</p>
<p>The Users menu holds Manage Users (admins only), Switch User and Log Out.
Switch User leaves this session running until somebody signs in, so
cancelling costs nothing; Log Out ends it there and then.</p>
<p>Help &gt; Check for Updates asks GitHub whether a newer ClearBudget has been
published; it also runs on its own once a day. That is the only time this
application touches the network and it sends nothing about you or your budget.
A version you would rather not hear about again can be skipped from the
prompt.</p>

<hr>
<h3>Keyboard</h3>
<p>Tab or Right goes forward, Shift+Tab or Left goes back, wrapping at both
ends. Up and Down walk table rows. Enter does what Space does. A green
outline means focused or hovered; a red one means disabled. Nothing is
highlighted on the main window until your first keypress; a dialog you open
starts on its own first control, because you opened it to do one thing.</p>
"""


class HowItWorksDialog(QDialog):
    """Names the icons, then explains the three rules behind the numbers."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("How It Works")
        self.setMinimumSize(ui_scale.px(640), ui_scale.px(560))
        layout = QVBoxLayout()

        body = QTextBrowser()
        body.setOpenExternalLinks(True)
        body.setHtml(_body_html())
        layout.addWidget(body)
        self._scroller = AutoScroller(body)

        btn_row = QHBoxLayout()
        close_btn = QPushButton("Close")
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self.setLayout(layout)
        close_btn.clicked.connect(self.accept)
