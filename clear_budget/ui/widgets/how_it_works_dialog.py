"""How It Works dialog - what the screens cannot say for themselves.

Two jobs, in this order. It NAMES the furniture, each entry carrying the real
icon or glyph the tray and the tab row actually draw, so the pictures that
replaced the old text labels can be identified by someone who has just met
them. Then it explains the three rules the numbers depend on and that no
screen can state on its own: how an undated bill accrues, how the balance
maintains itself and what Safe to Spend Today is a promise about.

It is deliberately short. A button-by-button inventory was tried first and
read as a wall of text; so did the essay that replaced it, which explained
every rejected design alongside the shipped one. A help screen nobody
finishes explains nothing, so anything a control says for itself is left to
the control.

The tab icons are the BUNDLED IMAGES, pulled through the same resource lookup
the tab row itself uses, rather than described in words or approximated with
a similar-looking emoji. An icon guide showing something other than the icon
is worse than no guide.
"""

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

from clear_budget.ui import ui_scale
from clear_budget.ui.utils.tab_icons import (
    ARCHIVE_ICON,
    CREDIT_CARDS_ICON,
    MONTHLY_BUDGET_ICON,
    SOLVENCY_ICON,
)
from clear_budget.ui.widgets.auto_scroller import AutoScroller

# Height of an inline icon in the body text, unscaled. Sized to the text
# rather than to the tray, since here they are read in a sentence.
_INLINE_ICON_PX = 20


def _img(path, px: int) -> str:
    """One bundled image as an inline <img>; an empty string if unbundled.

    Empty rather than a placeholder: the line still reads without its
    picture; a missing asset must never stop the help screen opening.
    """
    if path is None:
        return ""
    return (
        f'<img src="file:///{str(path).replace(chr(92), "/")}" '
        f'width="{px}" height="{px}"> '
    )


def _tab_row(spec: str, name: str, text: str, px: int) -> str:
    """One tab's line, led by its real icon (an image or the archive glyph)."""
    from clear_budget.shared.resources import find_tab_icon_path

    lead = _img(find_tab_icon_path(spec), px) if spec.endswith(".png") else f"{spec} "
    return f"<p>{lead}<b>{name}</b> &ndash; {text}</p>"


def _body_html() -> str:
    """Build the help text, resolving the real icons at open time."""
    from clear_budget.shared.resources import find_logo_png_path

    px = ui_scale.px(_INLINE_ICON_PX)
    app_icon = _img(find_logo_png_path(), px)
    return f"""\
<h2>How Clear Budget Works</h2>

<h3>The four tabs</h3>
{_tab_row(MONTHLY_BUDGET_ICON, "Monthly Budget",
          "this month's bills and income, plus what the balance does.", px)}
{_tab_row(SOLVENCY_ICON, "Solvency",
          "whether the month holds, plus the two months after it. Three pages "
          "behind the buttons at the top: the bank, the cards and Safe to "
          "Spend.", px)}
{_tab_row(CREDIT_CARDS_ICON, "Credit Cards",
          "one panel per card, with a six-month projection.", px)}
{_tab_row(ARCHIVE_ICON, "Archive",
          "months that have finished. They are filed automatically; there is "
          "no archive button.", px)}
<p>Hover any tab to see its name.</p>

<hr>
<h3>The tray</h3>
<p>&#128194; load &nbsp;&middot;&nbsp; &#128190; save
&nbsp;&middot;&nbsp; &#128260; switch budget &nbsp;&middot;&nbsp;
&#9881;&#65039; currency &nbsp;&middot;&nbsp; &#127974; overdraft plus the
Safe to Spend buffer and window &nbsp;&middot;&nbsp; {app_icon}the month as a
graph &nbsp;&middot;&nbsp; &#9728;&#65039;/&#127769; light or dark
&nbsp;&middot;&nbsp; &#8505;&#65039; this screen</p>

<hr>
<h3>Three rules behind the numbers</h3>

<p><b>A bill with no due day spreads across the month.</b> Only the part
ahead of you counts as still due, so &pound;200 of food on the 11th of a
30-day month leaves &pound;126. A bill WITH a due day counts in full until
that day, then drops to zero.</p>

<p><b>&#128221; The balance keeps itself up to date.</b> Set it once. After
that, dated bills are deducted and dated income added at midnight on the day,
each ticking itself Paid or Received; days missed while the app was shut are
caught up at the next launch. Typing a balance yourself overrides everything
applied before it. Card bills never touch it.</p>

<p><b>Safe to Spend Today is a promise, not a balance.</b> It is the most you
could spend today with every month in your window still clearing its buffer.
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
here (earlier months keep it) or remove it everywhere.</p>
<p>An admin can export a read-only viewer package for someone else to import
from their sign-in screen. A viewer sees everything and changes nothing.</p>

<hr>
<h3>Keyboard</h3>
<p>Tab or Right goes forward, Shift+Tab or Left goes back, wrapping at both
ends. Up and Down walk table rows. Enter does what Space does. A green
outline means focused or hovered; a red one means disabled. Nothing is
highlighted until your first keypress.</p>
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
