"""How It Works dialog - plain-English explanation of ClearBudget's calculations and UI."""

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

from clear_budget.ui import ui_scale

_HOW_IT_WORKS_TEXT = """\
<h2>How ClearBudget Works</h2>

<h3>Pro-rated bills (no fixed due date)</h3>
<p>Some bills have no fixed day of the month - for example "Food",
where you spend a bit every day rather than paying it all at once.
For these bills, ClearBudget assumes the cost is spread evenly across
the month, and only counts the part that is still ahead of you.</p>
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
  <li><b>Archive Month</b> - store this month's data permanently in the
      Archive tab. Only available for months that have fully ended -
      disabled for the current and future months.</li>
  <li><b>&#128221; (pencil icon)</b> - set your current bank account balance.</li>
  <li><b>Add Bill</b> - opens a form to create a new bill.</li>
  <li><b>Delete Bill</b> - removes the selected bill (asks for confirmation).</li>
  <li><b>Active</b> checkbox (bills/income) - tick to include this item in
      calculations; untick to keep it without it affecting your budget.</li>
  <li><b>Skip</b> checkbox (bills/income) - tick to leave this item out of
      this month only, without changing it for future months.</li>
  <li><b>Paid</b> checkbox (bills) - tick once you have actually paid this
      bill this month. Removes it from "still due" and your projected
      balance for the rest of the month, since the money has already left
      your account.</li>
  <li><b>Add Income</b> - opens a form to create a new income source.</li>
  <li><b>Delete Income</b> - removes the selected income source (asks for confirmation).</li>
  <li><b>Reliable</b> checkbox (income) - tick if this income is dependable
      and should count towards your safety calculations.</li>
  <li><b>Received</b> checkbox (income) - tick once this income has actually
      arrived this month.</li>
</ul>

<h3>Bill dialog (Add/Edit Bill)</h3>
<ul>
  <li><b>Bill Name</b> - what the bill is called.</li>
  <li><b>Amount</b> - how much the bill costs.</li>
  <li><b>Payment Method</b> - which bank account or credit card pays this bill.</li>
  <li><b>Category</b> - groups the bill (housing, utilities, subscriptions, etc).</li>
  <li><b>Type</b> - fixed (same every month), variable (can change), or expiring
      (stops on its own at some point).</li>
  <li><b>Day of Month</b> - the day this bill is due. Set to 0 if it has no
      fixed day (it will then be pro-rated, as explained above).</li>
  <li><b>Pays Card</b> - for credit card payment bills, which card the
      payment goes towards.</li>
  <li><b>This month only</b> - tick to add this as a one-off for the current
      month, without changing your normal recurring bill.</li>
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
  <li><b>Bank Balance</b> - your current account balance.</li>
  <li><b>Committed this month</b> - bills already due and paid (or passed)
      so far this month.</li>
  <li><b>Still due (bank)</b> - bank bills left to pay this month, with
      no-fixed-day bills pro-rated as described above. Bills marked
      <b>Paid</b> are excluded.</li>
  <li><b>Still due (cards)</b> - credit card bills left to pay this month,
      pro-rated the same way. Bills marked <b>Paid</b> are excluded.</li>
  <li><b>Discretionary buffer</b> - the amount you'd like to keep spare for
      day-to-day spending; defaults to 20% of your balance (minimum &pound;20)
      until you set your own value. Saves automatically when you press Enter
      or click away.</li>
  <li><b>Forward Projection</b> - a look-ahead at your balance over the next
      couple of months.</li>
</ul>

<h3>Credit Cards tab</h3>
<ul>
  <li><b>&larr; Previous / Next &rarr;</b> - move between months.</li>
  <li><b>Add Card</b> - opens a form to create a new credit card.</li>
  <li><b>Edit Card</b> - opens a form to change the selected card's details.</li>
  <li><b>Delete Card</b> - removes the selected card (asks for confirmation).</li>
  <li><b>Active</b> checkbox - tick to include this card in calculations.</li>
  <li>Table columns show each card's limit, balance used, available
      credit, utilisation %, payment due day, interest rate, minimum
      payment, expiry, and this month's charges/payments/interest.</li>
</ul>

<h3>Credit Card dialog (Add/Edit Card)</h3>
<ul>
  <li><b>Card Name</b> - what the card is called.</li>
  <li><b>Credit Limit</b> - the card's total credit limit.</li>
  <li><b>Current Balance</b> - how much is currently owed on the card.</li>
  <li><b>Interest Rate</b> - the card's APR percentage.</li>
  <li><b>Payment Due Day</b> - the day the card payment is due each month.</li>
  <li><b>Card has expiry date</b> - tick if this card expires; reveals the
      Expiry Month/Year fields.</li>
  <li><b>Minimum Payment (fixed)</b> - a fixed pound amount for the minimum
      payment, used if no percentage is set.</li>
  <li><b>Min Payment %</b> - a percentage of the balance used as the
      minimum payment instead of a fixed amount.</li>
  <li><b>Active</b> - tick to include this card in calculations.</li>
  <li><b>OK / Cancel</b> - save or discard your changes.</li>
</ul>

<h3>Archive tab</h3>
<ul>
  <li><b>&larr; Previous / Next &rarr;</b> - move between years.</li>
  <li>Click a month row to see its full details (bills and income for that month).</li>
</ul>

<h3>File menu</h3>
<ul>
  <li><b>New Budget</b> - permanently wipes all your data and starts fresh
      (asks twice to confirm).</li>
  <li><b>Export Database</b> - saves a backup copy of your data to a file.</li>
  <li><b>Import Database</b> - replaces your data with a backup file.</li>
  <li><b>Export Read-Only Viewer Package</b> (admin only) - choose a username
      and password for someone you want to give read-only access to your
      data, e.g. a family member. This bundles a snapshot of your database
      and those credentials into a single file you can hand over (USB,
      email, etc).</li>
  <li><b>Preferences</b> - change the display currency.</li>
  <li><b>Switch User</b> - log out and return to the login screen.</li>
  <li><b>Exit</b> - close ClearBudget.</li>
</ul>

<h3>Read-only viewer accounts</h3>
<p>If someone gives you a Viewer Package file, use
<b>Import Viewer Package</b> on the sign-in screen and pick the file - this
sets up a read-only account on your computer using the username and password
you were given.</p>
<p>Signing in with a read-only account shows "(Read-only)" in the window
title. You can view all tabs and figures, but cannot add, edit, delete,
archive, change settings, or import/export data. To get updated figures
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

        btn_row = QHBoxLayout()
        close_btn = QPushButton("Close")
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self.setLayout(layout)
        close_btn.clicked.connect(self.accept)
