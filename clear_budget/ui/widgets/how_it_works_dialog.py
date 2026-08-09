"""How It Works dialog - plain-English explanation of ClearBudget's calculations and UI."""

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
<p>Some bills have no fixed day of the month - for example "Food",
where you spend a bit every day rather than paying it all at once.
For these bills, Clear Budget assumes the cost is spread evenly across
the month and only counts the part that is still ahead of you.</p>
<p><b>Equation:</b></p>
<ul>
  <li><b>days_in_month</b> = number of days in the current month</li>
  <li><b>elapsed</b> = bill amount &times; today's day &divide; days_in_month
      (rounded up)</li>
  <li><b>still due</b> = bill amount &minus; elapsed</li>
</ul>
<p><b>Example:</b> Food is &pound;200, today is the 11th of a 30-day month.<br>
elapsed = &pound;200 &times; 11 &divide; 30 = &pound;73.33 (rounded up to &pound;74)<br>
still due = &pound;200 &minus; &pound;74 = &pound;126.00</p>
<p>Bills with a fixed day of the month work differently: the full
amount counts as "still due" until that day arrives, then drops to
&pound;0 once it has passed.</p>
<p>This pro-rating also affects your projected bank balance: each day
that passes, the "elapsed" portion of an undated bill (like Food) is
treated as already spent, so the projected balance drops a little
each day even before the bill is paid in full - not just the
"still due" figure shown in the Solvency tab.</p>

<hr>
<h3>Your bank balance</h3>
<p>You set your balance once with the &#128221; button beside the balance
figure (the dialog opens with the figure selected, so you can type straight
over it); Clear Budget then keeps
it up to date. When a bank bill with a due day reaches that day, its amount
is deducted from your balance at midnight and its <b>Paid</b> box is ticked;
income with an arrival day is added the same way and marked <b>Received</b>.
Days that pass while the app is closed are caught up the next time it opens.
Adding a bill or income dated today, like editing an existing item's day to
today, asks whether to apply it to the balance straight away - say No if
your balance already reflects it. Deleting a bill
or income whose amount was applied automatically hands the amount back and
setting the balance yourself supersedes everything applied before it. Bills
paid by credit card never touch the bank balance.</p>

<hr>
<h3>Tabs</h3>
<ul>
  <li><b>Monthly Budget</b> - your bills and income for one month, in tables.</li>
  <li><b>Solvency</b> - your overall financial health and warnings for this month.</li>
  <li><b>Credit Cards</b> - balances, limits and minimum payments for each card.</li>
  <li><b>Archive</b> - past months, so you can look back at history.</li>
</ul>

<h3>Monthly Budget tab</h3>
<ul>
  <li><b>&larr; Previous / Next &rarr;</b> - move between months.</li>
  <li><b>&#128221; button (beside the balance figure)</b> - set your current
      bank account balance; from then on it is kept up to date automatically
      (see "Your bank balance" above). Past months are archived automatically
      as they end - there is no manual archive step.</li>
  <li><b>App icon (in the navigation tray)</b> - opens the viewed month as a
      graph: the bank balance day by day here or every card's balance on
      the Credit Cards tab. A button in the graph switches between bar and
      line styles. Hover a bar or one of the marked turning points on the
      line, to read out that day's balance. On the bar style a curve in a
      separate colour follows the shape of the month, passing through every
      day's figure (on the Credit Cards graph it follows the total across all
      your cards). The line style needs no curve; it already joins those
      figures. <b>Export HTML</b> saves the month you are viewing as a single
      web page carrying both styles at once. On Monthly Budget there is also
      <b>Export projection HTML</b>, which asks for a range of months and
      saves your bank balance across them, showing both where each month ends
      and the lowest it gets on the way; it is not offered on Credit Cards,
      where a bank projection would have nothing to do with the cards on
      screen. Both save to your Downloads folder and open in any browser with
      no internet connection.</li>
  <li><b>Sun / moon button (right side of the tray, every tab, before the
      information button)</b> - switches between light and dark mode. The
      whole app restyles immediately and your choice is remembered for next
      time.</li>
  <li><b>Overdraft warning</b> - if your projected balance dips below zero at
      any point this month, a warning appears under the nav row: amber if the
      dip stays within your overdraft facility (with an estimated daily
      interest cost), red if it would exceed your facility or you have none
      set. Configure your facility via Settings &gt; Bank Account or the bank
      button in the navigation tray.</li>
  <li><b>Add Bill</b> - opens a form to create a new bill.</li>
  <li><b>Delete Bill</b> - offers two scopes for the selected bill:
      <b>Stop from the viewed month</b> drops it from that month onward while
      earlier and archived months keep it (the history-safe way to end
      something), while <b>Delete entirely</b> removes it from every month,
      including history, for entries added by mistake.</li>
  <li><b>Active</b> checkbox (bills/income) - tick to include this item in
      calculations; untick to keep it without it affecting your budget.</li>
  <li><b>Skip</b> checkbox (bills/income) - tick to leave this item out of
      this month only, without changing it for future months.</li>
  <li><b>Paid</b> checkbox (bills) - tick once you have actually paid this
      bill this month. Removes it from "still due" and your projected
      balance for the rest of the month, since the money has already left
      your account. Ticked automatically when a dated bank bill is applied
      to your balance at midnight on its due day.</li>
  <li><b>Add Income</b> - opens a form to create a new income source.</li>
  <li><b>Delete Income</b> - removes the selected income source (asks for confirmation).</li>
  <li><b>Reliable</b> checkbox (income) - tick if this income is dependable
      and should count towards your safety calculations.</li>
  <li><b>Received</b> checkbox (income) - tick once this income has actually
      arrived this month. Ticked automatically when a dated income is
      applied to your balance at midnight on its arrival day.</li>
</ul>

<h3>Bill dialog (Add/Edit Bill)</h3>
<ul>
  <li><b>Bill Name</b> - what the bill is called.</li>
  <li><b>Amount</b> - how much the bill costs.</li>
  <li><b>Payment Method</b> - which bank account or credit card pays this bill.</li>
  <li><b>Category</b> - groups the bill (housing, utilities, subscriptions, etc).</li>
  <li><b>Type</b> - fixed (same every month), variable (can change) or expiring
      (stops on its own at some point).</li>
  <li><b>Day of Month</b> - the day this bill is due. Set to 0 if it has no
      fixed day (it will then be pro-rated, as explained above).</li>
  <li><b>Pays Card</b> - for credit card payment bills, which card the
      payment goes towards.</li>
  <li><b>This bill ends (set a final month)</b> - give a subscription or a
      credit payment its last month; earlier months are untouched.</li>
  <li><b>This month only</b> - tick to add this as a one-off for the current
      month, without changing your normal recurring bill.</li>
  <li><b>Amount changes</b> (when editing) - record what the bill costs from
      a month onward, which is what a rent increase is. The new amount
      applies to that month and every month after it; months before it keep
      what they actually cost. A single-month override still wins in its own
      month.</li>
  <li><b>OK / Cancel</b> - save or discard your changes.</li>
</ul>

<h3>Income dialog (Add/Edit Income)</h3>
<ul>
  <li><b>Income Source Name</b> - what the income is called.</li>
  <li><b>Amount</b> - how much you expect to receive.</li>
  <li><b>Due Day</b> - the day this income normally arrives. Set to 0 if it
      has no fixed day.</li>
  <li><b>This month only</b> - tick to add this as a one-off extra payment
      for the current month only.</li>
  <li><b>OK / Cancel</b> - save or discard your changes.</li>
</ul>

<h3>Solvency tab</h3>
<ul>
  <li><b>&larr; Previous / Next &rarr;</b> - move between months.</li>
  <li><b>Overdraft Status</b> - a quick traffic-light style summary of how
      safe your money is this month.</li>
  <li><b>Mid-month alert</b> - warns if a temporary dip below zero is expected
      during the month even though it ends positive, e.g. when bills cluster
      before your last income payment arrives.</li>
  <li><b>Bank Balance</b> - your current account balance.</li>
  <li><b>Committed this month</b> - bills already due and paid (or passed)
      so far this month.</li>
  <li><b>Still due (bank)</b> - bank bills left to pay this month, with
      no-fixed-day bills pro-rated as described above. Bills marked
      <b>Paid</b> are excluded.</li>
  <li><b>Still due (cards)</b> - credit card bills left to pay this month,
      pro-rated the same way. Bills marked <b>Paid</b> are excluded.</li>
  <li>The balance breakdown also names the lowest point the month reaches
      and the day it falls on, even when that low lands on a bill day.</li>
  <li><b>Credit Card Status</b> - one progress bar per card showing current
      balance against limit, with the month's charges, payment, interest and
      minimum due inline.</li>
  <li><b>Forward Projection</b> - a look-ahead at your balance over the next
      couple of months.</li>
</ul>

<h3>Credit Cards tab</h3>
<ul>
  <li><b>&larr; Previous / Next &rarr;</b> - move between months; future
      months show each card's projected closing balance.</li>
  <li>Each card is its own panel: an <b>Active</b> checkbox (include the card
      in calculations), a status badge, an overview row (limit, used,
      available, utilisation, due day, interest, minimum payment, expiry)
      and a this-month row (charges, payment received, interest, minimum
      payment due), with <b>Edit</b> and <b>Delete</b> buttons on the panel.
      Delete asks for confirmation.</li>
  <li><b>Add Card</b> - opens a form to create a new credit card.</li>
  <li>The <b>projection strip</b> beneath the cards shows six months of
      projected balances per card, colour-coded by how much headroom is
      left.</li>
</ul>

<h3>Credit Card dialog (Add/Edit Card)</h3>
<ul>
  <li><b>Card Name</b> - what the card is called.</li>
  <li><b>Credit Limit</b> - the card's total credit limit.</li>
  <li><b>Current Balance</b> - how much is owed on the card as of today.
      It is stored exactly as you type it; the projections work out the
      month's opening figure from it behind the scenes.</li>
  <li><b>Interest Rate</b> - the card's APR percentage.</li>
  <li><b>Payment Due Day</b> - the day the card payment is due each month.</li>
  <li><b>Card has expiry date</b> - tick if this card expires; reveals the
      Expiry Month/Year fields.</li>
  <li><b>Minimum Payment (fixed)</b> - a fixed amount for the minimum
      payment, used if no percentage is set (the percentage below overrides
      it).</li>
  <li><b>Min Payment %</b> - a percentage of the balance used as the
      minimum payment instead of a fixed amount.</li>
  <li><b>Active</b> - tick to include this card in calculations.</li>
  <li><b>Scheduled limit changes</b> - record dated future changes to the
      card's limit (any number, with Add change and Remove). Projections
      look ahead with the right limit and each change folds in by itself
      once its date passes.</li>
  <li><b>OK / Cancel</b> - save or discard your changes.</li>
</ul>

<h3>Archive tab</h3>
<ul>
  <li><b>&larr; Previous / Next &rarr;</b> - move between years.</li>
  <li>Click the &#128221; icon at the start of a month's row to see its full
      details (bills and income for that month). Only fully-completed months
      appear here.</li>
</ul>

<h3>File menu</h3>
<ul>
  <li><b>New Budget</b> - permanently wipes all your data and starts fresh
      (asks twice to confirm).</li>
  <li><b>Load</b> - replaces your data from a saved file. The file is checked
      first and you are asked before existing data is overwritten.</li>
  <li><b>Save</b> - copies your data to your save file, asking before
      overwriting it. The very first save asks where the file should go,
      offering your Downloads folder; the choice is remembered between
      runs.</li>
  <li><b>Save As</b> - picks a new save file and remembers it from then
      on.</li>
  <li><b>Import / Export</b> (admin only) - submenu containing:
    <ul>
      <li><b>Export Read-Only Viewer Package</b> - choose a
          username and password for someone you want to give read-only
          access to your data, e.g. a family member. This bundles a snapshot
          of your database and those credentials into a single file you can
          hand over (USB, email, etc).</li>
      <li><b>Import Read-Only Viewer Package</b> - import a
          viewer package on this computer, creating or refreshing a
          read-only account.</li>
    </ul>
  </li>
  <li><b>Exit</b> - close Clear Budget.</li>
</ul>

<h3>Settings menu</h3>
<ul>
  <li><b>Preferences</b> - change the display currency.</li>
  <li><b>Bank Account</b> - record an overdraft facility (limit and
      APR) so the Monthly Budget tab can warn you accurately about mid-month
      dips below zero.</li>
</ul>

<h3>Users menu</h3>
<ul>
  <li><b>Switch User</b> - log out and return to the login screen.</li>
  <li><b>Manage Users</b> (admin only) - add and remove accounts.</li>
</ul>

<h3>Navigation tray shortcuts</h3>
<p>Every tab's navigation tray carries the common actions as buttons. At the
far left: the folder (Load) and the diskette (Save), then a separator, then
the cog (Preferences) and the bank (Bank Account). At the far right: the
sun/moon theme toggle, then the blue information button that opens this
help.</p>

<h3>Keyboard navigation</h3>
<ul>
  <li><b>Tab or Right arrow</b> - move forward through the menus, the tabs
      and the controls on the current tab, wrapping around at the end.</li>
  <li><b>Shift+Tab or Left arrow</b> - move backward, wrapping the other
      way.</li>
  <li><b>Up / Down</b> - walk the rows inside a table or switch tabs while
      the tab bar is highlighted. A table is a single stop: Tab or the
      horizontal arrows leave it in one press rather than visiting every
      cell.</li>
  <li><b>Submenus</b> - inside an open menu, Right arrow on an item with a
      submenu (File &gt; Import / Export) opens it and Left arrow steps back
      out to the parent menu.</li>
  <li><b>Enter or Space</b> - press the highlighted button or checkbox.</li>
  <li>A green outline shows what is focused or hovered; a red outline marks
      a control that is disabled right now. Nothing is highlighted when the
      app opens - press Tab or Right to start.</li>
</ul>

<h3>Read-only viewer accounts</h3>
<p>If someone gives you a Viewer Package file, use
<b>Import Viewer Package</b> on the sign-in screen and pick the file - this
sets up a read-only account on your computer using the username and password
you were given.</p>
<p>Signing in with a read-only account shows "(Read-only)" in the window
title. You can view all tabs and figures and save a copy of the data but
cannot add, edit, delete, change settings or load data. To get updated figures
later, ask the admin to re-export the package and import it again - this
refreshes the same account with the latest data.</p>
"""


class HowItWorksDialog(QDialog):
    """Explains the pro-rating equation and every UI control in plain English."""

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
