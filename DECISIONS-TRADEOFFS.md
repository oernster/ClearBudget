# Decisions and trade-offs

The deliberate choices ClearBudget rests on: what was chosen, what was given
up for it and why. Each entry is the decision as the product makes it today.
The detail behind each one, with the tests that hold it, lives in
[ARCHITECTURE.md](ARCHITECTURE.md); [TECH_DEBT.md](TECH_DEBT.md) records what
is deliberately left alone so it is not raised again as debt.

## The product as a whole

### Forward-looking, not a ledger

ClearBudget projects a current account forward day by day and says whether
each month holds together, including a month that dips under in the middle
and recovers by payday. It keeps no ledger of where past money went beyond an
archive of month summaries.

- **Rather than:** a retrospective record of spending, which is what most
  budgeting tools are.
- **Gains:** the question answered is one that can still be acted on: the
  tightest day, the first month that goes under and what would prevent it.
- **Costs:** no categorised history, no reconciliation and no reporting on
  past spending.

### What ClearBudget deliberately is not

It models one current account with its income, its bills and its credit
cards. It does no bookkeeping or tax, connects to no bank, tracks no
investments or net worth and synchronises nothing between devices.

- **Rather than:** an all-purpose finance suite.
- **Gains:** a model small enough to be held under a complete coverage gate.
- **Costs:** those jobs need other tools; balances are entered by hand rather
  than fetched.

### Local first, one machine

Every account and every budget is kept in SQLite files in the platform's own
application-data folder. There is no service to sign up to and no cloud copy.

- **Rather than:** a server, an online account or synchronised budgets.
- **Gains:** it works with the network switched off; nothing about the
  budget leaves the computer.
- **Costs:** a budget belongs to one machine. Moving it is a save, a full
  backup or a copy by hand.

### Money in whole pence

Every amount is an integer number of pence. An amount that cannot be negative
has a type of its own; a balance that can go below zero is a plain signed
figure.

- **Rather than:** floating-point money.
- **Gains:** nothing rounds away between the figure typed and the figure a
  projection uses.
- **Costs:** two representations of money to keep apart.

## Privacy, accounts and the network

### One outbound call, through the standard library

The update check is the only connection the application opens itself, made
with Python's own library. The donate button and the download offered by an
update both hand an address to the browser.

- **Rather than:** a networking library; the application making those other
  requests itself.
- **Gains:** no third-party runtime dependency for one call; the offline
  promise is unchanged by a donate button existing.
- **Costs:** the Linux sandbox needs network access granted for that one
  call alone.

### Update checks: daily, published releases only, quiet on failure

A check runs a few seconds after launch and then every twenty-four hours. It
asks for the latest published release, so drafts, prereleases and bare tags
never prompt. A version that cannot be read is never treated as newer. A
failed check says nothing; one asked for from the Help menu always answers.
A release can be skipped for good.

- **Rather than:** no check at all; watching tags; a check that reports every
  outcome.
- **Gains:** updates are found without nagging; a tag pushed during
  development cannot reach anybody's screen.
- **Costs:** one unprompted request a day.

### The sign-in is access control, not encryption

Passwords and recovery codes are kept only as bcrypt hashes. The databases
themselves are ordinary unencrypted SQLite files and the README says so.

- **Rather than:** encrypting the budget files.
- **Gains:** plain files that any SQLite tool can inspect; the sign-in stops
  somebody sharing the computer from browsing a budget inside the app.
- **Costs:** anyone with the file and a SQLite tool can read it. Protection
  at rest is left to the operating system's disk encryption.

### A recovery code instead of a reset service

Creating an account shows a one-time recovery code that has to be
acknowledged before the dialog can continue. It is the only way back into an
account whose password is lost.

- **Rather than:** a reset by email, which would need a server and an
  address.
- **Gains:** no service, no address held and nothing sent.
- **Costs:** losing both the password and the code loses the account.

### One database per account, deleted with it

Every account has its own budget files. Deleting an account deletes its
budgets too, behind two confirmations.

- **Rather than:** one shared database with rows per user; keeping a budget
  whose account is gone.
- **Gains:** one account's figures cannot reach another's through the app; no
  orphaned file survives the credentials that guarded it.
- **Costs:** an account cannot be removed while keeping its budget.

### A new account never inherits an old budget

The single-user budget file from before accounts existed is never adopted
automatically.

- **Rather than:** migrating it to whoever signed in first.
- **Gains:** a new user on the machine cannot silently receive somebody
  else's finances.
- **Costs:** an old single-user budget has to be loaded by hand.

### Two names that would share a file are refused

Budget files are named after a simplified form of the account name, so two
names differing only in punctuation or spacing would land on one file. The
account store refuses the second and names the account it clashes with.

- **Rather than:** relying on the uniqueness check alone, which sees the two
  names as different.
- **Gains:** two accounts can never share bills, income or a balance.
- **Costs:** some names a user would want are refused.

### Another account's budget: opened with its owner's password, never saved over

Loading a budget that belongs to another account asks for that account's
password, not the loader's. Saving over one is refused outright. Ownership
is read from a stamp inside the database first and from the file name for
anything written before the stamp existed.

- **Rather than:** checking the schema alone; asking the loader for their own
  password, which would prove nothing.
- **Gains:** the one shared folder the Load dialog opens on no longer exposes
  every budget in it. A copied file carries its stamp, so copying does not
  launder it.
- **Costs:** the two guards treat loading and saving differently on purpose:
  a load can be undone and a save cannot.

### Remembered sign-in: per account, two ticks, the password in the keychain

Each account can ask for its name to be remembered and separately for its
password. The password goes into the operating system's credential store;
the file beside it records only which accounts asked. Any keychain failure
means nothing is remembered and sign-in still works.

- **Rather than:** one remembered login for the whole machine; remembering
  the password whenever the name is.
- **Gains:** a household's accounts are each offered at the sign-in screen;
  remembering a password is a decision of its own; no password is ever in a
  file.
- **Costs:** it depends on a working keychain. The Linux package needs
  permission to reach one.

## The forecast

### A month is judged by its lowest day

A month reads as in danger when its balance breaches at any point inside it,
not when it closes under. The month title, the projection and the graph all
use that rule.

- **Rather than:** colouring a month from its closing balance, which once
  showed amber on the title while Solvency showed red.
- **Gains:** a month that bounces a payment and recovers by payday is shown
  as the danger it was.
- **Costs:** none recorded.

### Red means past the overdraft you have

Inside an arranged overdraft a dip reads amber; red is kept for going past
the facility. With no facility recorded the floor is zero. What a forecast
month needs to stay afloat is measured against the same floor.

- **Rather than:** red for any balance below zero.
- **Gains:** borrowing the bank has agreed to is not reported as an alarm.
- **Costs:** the verdict is only as good as the facility recorded.

### The balance keeps itself up to date

Dated bank bills and income are applied to the stored balance at local
midnight on their day, with any days the app was closed caught up at the next
launch. Each applied item has its Paid or Received tick set. Each
application is logged, so deleting the item hands the amount back; typing a
balance by hand supersedes the log.

- **Rather than:** retyping the balance; leaving the stored balance alone and
  projecting around it.
- **Gains:** the starting figure stays current without entry and nothing is
  counted twice.
- **Costs:** a payment that lands late at the bank is still applied on its
  day; the balance has to be corrected by hand.

### Paid and Received decide what has happened

Whether a bill or an income has happened is read from its tick, not assumed
from its calendar day.

- **Rather than:** treating everything before today as done.
- **Gains:** a bill paid early is not taken again; income received early is
  not added twice, in this month or in the months that open from it.
- **Costs:** a forgotten tick moves the current month's close off its totals
  by exactly that amount.

### The month in progress starts from the recorded balance

Every month opens where the previous one closed, with one exception: the
current month opens from the balance actually recorded.

- **Rather than:** chaining every month from a projected close.
- **Gains:** the one figure that is a fact anchors the forecast; any gap
  against the previous close is drift the report exists to show.
- **Costs:** in an export, the current month's opening need not equal the
  previous month's close.

### One simulation and one rule for what is still to come

The Solvency page, the Reserves page and the graph read the same day-by-day
walk of a month. What the current month still has to come after the stored
balance has one home that every chain uses.

- **Rather than:** each page with its own copy. A Solvency copy once kept
  counting income already received.
- **Gains:** two pages cannot disagree about the same month.
- **Costs:** none recorded.

### Safe to Spend is bounded by the last month that stands alone

The headline is the most that could be spent today while every month up to
the last one that clears its floor unaided keeps clearing it. A later month
that is short whatever happens gets a red line of its own: its month, its
amount and the fact that spending the headline deepens it.

- **Rather than:** stopping at the first breaching day, which offered money
  that funded its own deficit; letting every day veto the figure, which
  reported nothing safe while the nearer months still had room.
- **Gains:** the figure is genuinely spendable and the gap beyond it is
  stated rather than hidden.
- **Costs:** the answer is two lines to read rather than one.

### A buffer and a window the user sets

The figure always leaves a buffer in hand: twenty pounds unless changed, with
zero allowed. A window of one to twelve months, four by default, sets how
far ahead the calculation looks.

- **Rather than:** a fixed horizon.
- **Gains:** the margin and the reach are the user's own choice; planning to
  the wire is possible on purpose.
- **Costs:** two settings to understand.

### Safe to Spend sits beside the assumption it rests on

The figure lives on its own page, measured on the assumption that income
entered for this month arrives again in any later month with no entry of
that name. The page says so and names what has to arrive. An income whose
final month has passed is never filled forward. The bank page carries only
money actually entered.

- **Rather than:** a figure beside the entered balances; a hand-ticked
  reliable flag that nobody remembered to set; counting only income already
  typed in.
- **Gains:** a promise about future months is not read as a fact about the
  account; months whose ad hoc income is not yet typed in do not read as a
  shortfall the user does not have.
- **Costs:** income is matched by name, so an income renamed from one month
  to the next counts as missing.

### Two figures for a month, never the same number

What a month needs to hold flat is its whole bills and reserves against its
whole income, regardless of where it opens. What a forecast month needs to
stay afloat is the money that would keep its lowest point at or above the
floor, dated to the first day it goes under.

- **Rather than:** one figure for both questions; forecast months closing on
  the hold-flat gap, which could report hundreds for a month in no danger.
- **Gains:** the shape of a month and its rescue are each answered; the
  rescue carries a deadline, since money arriving after a refusal did not
  prevent it.
- **Costs:** two figures that differ by design need explaining.

### Card interest beside the gap, never inside it

Credit card interest is reported on its own line under what a month needs to
hold flat.

- **Rather than:** adding it to the bank shortfall.
- **Gains:** the gap claims only money that leaves the bank account; interest
  accrues on the cards.
- **Costs:** a reader has to add the two lines for the whole cost.

### The colour carries the alarm; the words carry the number

Each forecast month is two lines. The first is the answer, the sum needed and
the day it must arrive by; the second is where the month opens, its lowest
day and where it closes.

- **Rather than:** a block of seven lines, five of them saying the month went
  overdrawn, with the actionable sum last.
- **Gains:** the figure that can be acted on is read first.
- **Costs:** none recorded.

## Bills, income and history

### A change applies from its month forward

A bill can change amount from a month onward; earlier months keep the amount
they had. A single-month override still wins over that schedule. A new bill
starts in the month it was created and editing it never moves its start.

- **Rather than:** editing the amount in place, which restated every earlier
  month; rebasing every bill's start month on each launch.
- **Gains:** a month already reported keeps reporting what it really cost.
- **Costs:** an amount schedule and per-month overrides are two mechanisms to
  learn.

### Ending is not deleting

Bills and income both carry an end month. Deleting either offers two scopes.
Stopping from the viewed month keeps earlier and archived months; deleting
entirely is for an entry added by mistake. A one-off income can be promoted to a
recurring one; the reverse is not offered.

- **Rather than:** a delete that removes an item from every month it ever
  appeared in; demoting a recurring income, which erased months that had
  happened.
- **Gains:** a subscription or a job that stopped stays in the months it was
  real.
- **Costs:** two delete choices where one would be simpler.

### A one-off is a scope, not a category

"This month only" makes a bill or an income that exists in exactly one month.
The old One Time category was retired and its bills recategorised.

- **Rather than:** a category that duplicated the mechanism and carried no
  behaviour of its own.
- **Gains:** one way to say "this happens once".
- **Costs:** the recategorisation runs once on opening and cannot be undone;
  archived months keep their old label.

### The schema is versioned and loud

A database records how far its schema has been taken, so each migration runs
once and in order. A column is added only after looking for it; any other
failure stops the open.

- **Rather than:** schema changes wrapped in handlers that read every error
  as "already there".
- **Gains:** a corrupt, locked or full database is never mistaken for an
  up-to-date one.
- **Costs:** a database that cannot be migrated does not open.

## Reserves and recommendations

### Reserves accrue over the months remaining

A commitment such as an annual premium is put by evenly across the months
left before it falls due. The gentler natural rate is shown beside it.
Nothing is moved and no second account is assumed.

- **Rather than:** accruing over the bill's natural period; moving money into
  a separate pot.
- **Gains:** the rate is what the calendar actually asks for; the page
  changes only what the application is willing to call spendable.
- **Costs:** a commitment entered late has a steep first cycle.

### The floor rises as a bill gets closer

What Safe to Spend has to clear on a day is the buffer plus whatever the
reserves hold back on that day. The graph draws that floor and dims the part
of each bar beneath it. A budget with no commitments has a flat floor as
before.

- **Rather than:** one buffer for every day; painting a day under the floor
  amber, a colour that already means inside the overdraft.
- **Gains:** money already spoken for stops reading as free.
- **Costs:** the floor on the graph stands on the Safe to Spend buffer, not
  the Reserves page's own, so the two pages can show different safety nets.

### Set aside is a cost, not money gone

What a month sets aside counts in what it needs to hold flat and in its
colour. It does not reach the stay-afloat figure or the balance chain,
because money set aside has not left the account.

- **Rather than:** treating a reserve as spent; ignoring it altogether.
- **Gains:** a month that funds its bills while saving nothing toward a
  coming one is not reported as holding flat.
- **Costs:** a reserve moves a month's colour without moving its balance.

### A commitment due this month appears among the bills

It is shown read-only, marked as coming from Reserves, with no total.

- **Rather than:** leaving the bills table silent about it.
- **Gains:** the same obligation is not entered a second time by hand.
- **Costs:** a row in the bills table that cannot be edited there.

### The archive keeps what a month really held

A completed month reports its reserve as at its own last day. A commitment
since stopped still counts for the months it covered. The column appears only
for a budget that sets something aside.

- **Rather than:** evaluating the past from today.
- **Gains:** the archive is never rewritten by the present.
- **Costs:** none recorded.

### Recommendations suggest; they never apply

The page retimes what can move, then states any surviving shortfall as
income asks. There is no Apply button. A try-it-on tick shows a suggestion's
measured effect with nothing written anywhere.

- **Rather than:** applying a batch of changes on one press.
- **Gains:** every change to a budget is made knowingly in its own dialog.
- **Costs:** each suggestion has to be carried out by hand.

### Pausing a reserve is always priced

Where a month is still short the page may offer putting less by. It never
does so without stating what the due month then arrives short by.

- **Rather than:** listing a pause by what it improves.
- **Gains:** the one lever that always looks like a win is shown as
  borrowing from a later month.
- **Costs:** none recorded.

### Payment days fixed in the real world are not moved

A bill or an income can be ticked as unable to move; Recommendations never
proposes retiming it.

- **Rather than:** assuming every date is negotiable.
- **Gains:** suggestions the user could never act on are not offered.
- **Costs:** none recorded.

## Files, saving and backups

### Several named budgets, each its own file

New Budget creates another named budget alongside the existing ones.
Creating, switching and renaming never touch another budget's contents.

- **Rather than:** a New Budget that wiped the current one.
- **Gains:** starting afresh destroys nothing.
- **Costs:** more files per account; losing the small registry file costs
  the names but not the data.

### An open database is never copied as a file

Save takes a snapshot through SQLite's own backup interface. Load closes the
live database first, in the one place that owns its connection. Both write a
scratch file and rename it into place.

- **Rather than:** copying files over an open database, which once left a
  budget the right length and entirely zero bytes.
- **Gains:** an interrupted save or load leaves the previous database whole.
- **Costs:** loading rebuilds the window around the new database.

### Saving onto the open budget is a commit

Choosing the open database itself as a save destination commits any write
in flight and reports success. It is not remembered as the save location.

- **Rather than:** renaming a file over the open database, which Windows
  refuses and other systems allow silently.
- **Gains:** the obvious choice in the default folder works.
- **Costs:** none recorded.

### Save locations are remembered per account

Each account's save file is remembered under its own name. A first save
defaults to the application's data folder under a name carrying the account.
Exports and full backups default to Downloads, because those files are meant
to leave.

- **Rather than:** one remembered location for the machine, which offered
  the next account another person's live budget.
- **Gains:** Save never lands on somebody else's file by default.
- **Costs:** the location remembered before this change is ignored rather
  than adopted, at the price of one prompt per account.

### Back up everything in one file, restore all or nothing

An administrator can write every account and every budget into one zip and
restore it. A restore is staged and schema-checked before any live file is
replaced; each live file is moved aside first, so a failure part way through
is undone.

- **Rather than:** per-budget saves alone, which left the accounts database
  with no backup at all.
- **Gains:** a lost or rebuilt machine can be put back in one step; a broken
  backup changes nothing.
- **Costs:** the zip is as unencrypted as the files in it and holds every
  account in one portable file.

### Data in each platform's own folder, moved with proof

The data directory follows each platform's convention. An older install's
directory is copied across at startup, verified byte for byte and only then
removed; while it still exists it is the one used.

- **Rather than:** a dot folder in the home directory on every platform.
- **Gains:** files are where each system expects them; a migration that
  cannot finish loses nothing and tries again next launch.
- **Costs:** a move that keeps failing leaves the app on the old folder,
  retrying at every launch.

### A log file and a handler for every uncaught error

The application writes a plain log to its data directory and catches every
exception escaping a slot. A log directory that cannot be created is skipped
rather than stopping the app.

- **Rather than:** no logging, which made every fault in a windowed build look
  like nothing happening.
- **Gains:** a failure leaves something to diagnose.
- **Costs:** a local file naming the accounts that signed in.

## Exports and the graph

### Exports are self-contained HTML with drawn charts

A month exports as one page carrying both renderings with text saying what
each shows. Charts are generated as inline vector graphics; the page
references nothing outside itself.

- **Rather than:** screenshots; pages that load styles or images.
- **Gains:** a file that can be emailed, opened offline and tested as text
  without a window.
- **Costs:** the chart is drawn twice, once on screen and once for export;
  the export estimates label widths from character counts.

### A fixed dark palette for exports

Exports always use the application's dark colours.

- **Rather than:** following the theme toggle; a light print palette.
- **Gains:** an export looks the same whoever made it.
- **Costs:** a printed export is a dark page.

### A range of months exports as a folder

The range report becomes an index with a page per month, each named so a
folder listing sorts by calendar. Pages link only to siblings by bare file
name.

- **Rather than:** a single projection file beside a separate month export.
- **Gains:** a year can be read from its summary down to any day; the folder
  copies to a stick and opens offline.
- **Costs:** the no-outside-references rule had to widen by one step for a
  package.

### The curve passes through every day

The bar graph carries a monotone curve through each day's real balance. The
line graph carries none, since its line already joins the same points.

- **Rather than:** an averaged trend line, which drew balances the account
  never had.
- **Gains:** the curve never overshoots a peak or a trough.
- **Costs:** none recorded.

### The graph is a page that chooses what it plots

The graph is a view like the others, stepped by the same Previous and Next
arrows. A switch on the page chooses the bank balance or the cards; the range
export follows the switch and is offered only for the bank.

- **Rather than:** a modal dialog that carried its own copy of the month
  arrows and plotted whatever the view it was opened from implied.
- **Gains:** no hidden state about where it was opened from; the controls
  are the ones every view uses.
- **Costs:** one more button in the tray.

## The interface

### One home for every colour, in two themes

Every colour value lives in one palette module; the themes, the reports and
the setup program ask it for roles. A test fails the build on a colour
written anywhere else. Light and dark themes switch live and the choice is
remembered.

- **Rather than:** colours written where they are used, which had drifted
  into near-duplicates with unrelated roles sharing one.
- **Gains:** a recolour moves every surface that shares the role and nothing
  else.
- **Costs:** a new colour has to earn a place in the palette.

### The ring belongs to the keyboard

A focus ring means the keyboard is here. A button clicked with the mouse does
not keep focus; tables take focus only from the keyboard and never draw a
ring at all, since the highlighted row already says where the keyboard is.

- **Rather than:** the toolkit's default of focusing whatever is clicked.
- **Gains:** a ring never appears where the user did not put the keyboard.
- **Costs:** two separate guards, one on focus and one on the stylesheet,
  because a ring can arrive from either direction.

### Everything reachable from the keyboard

Tab and the arrow keys walk every control in the window; Enter equals Space.
The main window opens with nothing focused; a dialog opens on its first
usable control, passing over a page that is only for reading.

- **Rather than:** mouse-first controls.
- **Gains:** the whole application works without a mouse.
- **Costs:** every new control needs a place in the ring; several structural
  tests exist only to keep the ring complete.

### View buttons are pictures, held to the help screen

The views are picture buttons in each view's navigation tray, named on hover.
How It Works names every button with the very picture it draws. Tests fail
the build if a button is missing from it, if its heading miscounts them or if
its worked example stops matching the calculation.

- **Rather than:** labelled tabs; a help page kept true by hand.
- **Gains:** the guide cannot drift from the controls it explains.
- **Costs:** pictures have to be learned; the help's other prose is still held
  by nothing.

### Switch User and Log Out are two different things

Switch User suspends the session, so cancelling the sign-in screen returns to
it. Log Out ends it, so cancelling closes the application. Both are on the
Users menu only.

- **Rather than:** one way out that quit when sign-in was cancelled; a tray
  button that a stray click could press.
- **Gains:** a cancelled switch loses nothing.
- **Costs:** two menu items where one looked sufficient.

### The sign-in screen stays up until the window is ready

After a password is accepted the sign-in screen stays on screen as a progress
bar and closes only when the main window can be shown.

- **Rather than:** closing at once and leaving nothing on screen while the
  window builds.
- **Gains:** a slow start never looks like a failed one.
- **Costs:** the screen is inert while it waits, so every route out of a
  session has to end it; the start-up code does so in a backstop.

### A second launch brings the first forward

Launching again while ClearBudget runs leaves a request in the data directory
and exits; the running copy brings its window forward.

- **Rather than:** a warning box over a window the user could not find.
- **Gains:** clicking the icon again does what was meant; one file works the
  same on every platform.
- **Costs:** the running copy polls for that file.

### Opens on the monitor it was started from

The screen under the pointer at launch is taken as the one the user started
from. Dialogs open over the window that raised them.

- **Rather than:** always opening on the primary display.
- **Gains:** a multi-monitor desk gets the window where it was launched.
- **Costs:** the pointer is a proxy: Windows passes no launch monitor and a
  launch with no pointer falls back to the primary screen.

### The window does not grow to fit a table

The bills table's name column takes up the slack and elides a long name; the
default window stays a third of the screen's width.

- **Rather than:** a wider default window, tried and reverted.
- **Gains:** a table is always exactly as wide as its view.
- **Costs:** a long name is shortened on screen.

### The signed-in account is named on every view

The account name sits at the left of every view's month row, as large as the
month itself.

- **Rather than:** a few pixels of title bar.
- **Gains:** on a shared machine, whose budget is on screen is never in
  doubt.
- **Costs:** a long name is elided, shown in full on hover.

### Reading pages scroll themselves

About, the licence notice and How It Works scroll gently on their own and
stop the moment the reader takes over, resuming from where they stopped.

- **Rather than:** static pages.
- **Gains:** long text can be read hands free.
- **Costs:** none recorded.

### The donate button lives at the foot of the window

One strip along the foot of the window holds the donate button; it opens a
page in the browser. Nothing is withheld behind a donation.

- **Rather than:** a copy in every view's tray, among controls that act on
  the budget.
- **Gains:** the one control that leaves the application belongs to none of
  its pages.
- **Costs:** a second strip on every view.

## Building and installing

### A setup program of its own, installed per user

On Windows the bundle is built with PyInstaller and installed by a setup
program written in PySide6. It installs into the user's own Programs folder
and registry, so no administrator rights are needed; an existing install is
maintained where it was registered.

- **Rather than:** a generic installer; a machine-wide install.
- **Gains:** no administrator prompt; upgrading never moves the program or
  breaks a shortcut.
- **Costs:** the setup program is ClearBudget's own to maintain; each account
  on a machine installs separately.

### Installing never touches the user's data

Install, repair, upgrade and uninstall deal in program files, shortcuts and
the registry entry alone. Uninstall offers no option to delete the data
directory; a test fails if any installer module names it.

- **Rather than:** a "remove my data" option at uninstall.
- **Gains:** a reinstall picks up exactly where the user left off; one
  checkbox can never erase every account on the machine.
- **Costs:** removing the data is a manual job.

### A running copy is closed, not lectured

If ClearBudget is running, setup offers to close it, says the session ends,
then waits for the file lock to release. If it will not close, setup stops
and says so.

- **Rather than:** asking the user to close it and retry; a polite close
  request that can be declined.
- **Gains:** no install fails part way through on a locked file.
- **Costs:** the running copy is ended by force rather than asked.

### The setup program wears the application's colours

Its stylesheet is filled from the application's own theme roles, in both
themes.

- **Rather than:** a palette of its own, chosen separately.
- **Gains:** the first thing a user sees looks like the thing it installs.
- **Costs:** none recorded.

### The macOS release must be notarised

The disk image build fails unless it can notarise and staple both the
application and the image. A local escape hatch builds an unnotarised copy
labelled unreleasable.

- **Rather than:** skipping notarisation when credentials were absent, which
  produced images that would not open on any other Mac.
- **Gains:** a published image always opens.
- **Costs:** an Apple developer account and stored credentials to build a
  release.

### The Linux sandbox is widened for three reasons

The Flatpak is granted the network for the update check, the home folder for
chosen files and the old data directory, plus the keychain service for a
remembered password.

- **Rather than:** the tightest sandbox, which broke each of those features
  silently.
- **Gains:** the Linux build behaves like the others.
- **Costs:** a broader sandbox than an offline budget strictly needs.

### Release files carry no version

The Windows setup program, the disk image and the Flatpak have the same names
in every release.

- **Rather than:** versioned file names.
- **Gains:** a link to the latest release never goes stale.
- **Costs:** none recorded.

### One version number, stamped into the site

One version file is the only place the version is written. The application
and the packaging read it; a stamper writes it into the website, which cannot
read it at render time. No root document carries a version. The same stamper
links each of the site's stylesheets and scripts by a hash of its content, so
a browser fetches a changed file at once.

- **Rather than:** the version typed wherever it is shown; leaving the site's
  assets to expire from a browser's cache in their own time, which could pair
  a new page with an old stylesheet.
- **Gains:** a version change is made once and cannot disagree with itself; a
  published page never renders against stale styling.
- **Costs:** the site has to be stamped after every bump and after every
  change to a stylesheet.

### LGPL-3.0, with a commercial licence offered

ClearBudget is distributed under LGPL-3.0, the licence PySide6 carries. A
commercial licence for the author's own code is offered separately.

- **Rather than:** one licence for every user.
- **Gains:** open source by default; a route for anyone whose terms differ.
- **Costs:** two licences to keep straight.

## Engineering

### Layers that meet in one place

The code is split into domain, application, infrastructure and interface,
with authentication alongside. Dependencies point inward only and are wired
together by constructor in one composition root. Structural tests read the
imports and hold the boundaries.

- **Rather than:** convention alone; a dependency injection container.
- **Gains:** the money rules are tested with no disk, clock or window.
- **Costs:** more modules and more explicit wiring.

### Complete coverage where it means something

Line and branch coverage must be total over the ClearBudget package and the
setup program's non-graphical half. Interface code is outside the gate;
formatting money for display was moved inside it.

- **Rather than:** one figure over the whole program; leaving money formatting
  in the excluded interface layer.
- **Gains:** anything short of complete in the logic is a decision nobody
  made; where pence become a figure a person reads is held by tests.
- **Costs:** interface code relies on targeted tests and measurement. Lines
  explicitly marked to be skipped also sit outside the figure.

### Small modules, with a danger band

No source or test file may exceed four hundred lines; none may sit within the
last twenty. A file cut down from over the cap lands well below it. Build
scripts are exempt.

- **Rather than:** letting files grow; shaving a file to just under the cap.
- **Gains:** files split at real seams instead of breaking the build on the
  next unrelated edit.
- **Costs:** many small modules.

### Tests with real parts

No mocking library: real SQLite in temporary folders and hand-written fakes.
There are no widget tests; logic a widget hosts is pulled out far enough to
test without a running window. Guards are proved by planting the violation
they forbid.

- **Rather than:** mocks; widget tests that needed a running application and
  were flaky.
- **Gains:** a passing test means the real thing works; a guard is known to
  bite.
- **Costs:** fakes are written by hand; what can only be seen is measured
  outside the suite.

### Tests can never reach real data

Only one function derives the data directory and it honours an override; the
suite redirects it for every test and a structural test checks it cannot
resolve the real one.

- **Rather than:** several modules each working out the path.
- **Gains:** no test, probe or install can change a user's live data. A
  probe once flipped a user's saved theme this way.
- **Costs:** every new file location has to go through that one function.

### The whole tree is linted

flake8 reads every source file, with only build output and the virtual
environment excluded. ruff runs its default rules plus the rules against
blind exception handlers.

- **Rather than:** an exclude list that silently hid the interface, both
  services packages and the setup program.
- **Gains:** a clean lint means the whole repository was read.
- **Costs:** every exception to a rule has to be named and justified where it
  is declared, tests included.

### The user's calendar, not UTC

Dates are taken from the local clock.

- **Rather than:** timezone-aware UTC dates.
- **Gains:** a budget month is the user's own calendar month, whichever side
  of UTC they live on.
- **Costs:** every such call carries a marker to quiet the linter's timezone
  rule.

### No magic numbers, by review rather than by test

Amounts, thresholds, days and limits come from data, configuration or named
constants. That rule is a house rule the code is written and reviewed
against; nothing checks it automatically.

- **Rather than:** literals in the logic.
- **Gains:** a value that changes in the real world changes in one place.
- **Costs:** it holds only as long as review does.
