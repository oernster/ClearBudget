# Decisions and trade-offs

The deliberate choices ClearBudget rests on: what was chosen, what was given
up for it and why. The detail behind each one lives in
[ARCHITECTURE.md](ARCHITECTURE.md); [TECH_DEBT.md](TECH_DEBT.md) records what
is deliberately left alone.

## The product as a whole

### Forward-looking, deliberately narrow

ClearBudget projects one current account (its income, bills and credit
cards) forward day by day and says whether each month holds together. It keeps
no ledger beyond an archive of month summaries; it does no bookkeeping or tax,
connects to no bank and tracks no investments. The question it answers can
still be acted on; the cost is no categorised history and balances typed by
hand.

### Local first, one machine

Every account and budget lives in SQLite files in the platform's own data
folder, with no service and no cloud copy. It works offline and nothing
leaves the computer. A budget belongs to one machine; moving it is a save, a
full backup or a copy by hand.

### Money in whole pence

Every amount is an integer number of pence; an amount that cannot be negative
has its own type. Typed text is read as a decimal, never a float; a
figure finer than a penny is refused rather than rounded. Nothing rounds away
between the figure typed and the figure projected; a third decimal place has
to be retyped.

## Privacy, accounts and the network

### One outbound call: the update check

The update check is the only connection the application opens, made with
Python's own library; the donate button and an update's download hand an
address to the browser. A structural test forbids any other networking
import. The check runs shortly after launch and then daily, asks only for the
latest published release and stays silent on failure unless asked for from
the Help menu. A release can be skipped for good. The cost is one unprompted
request a day.

### Sign-in is access control, not encryption

Passwords and recovery codes are kept only as bcrypt hashes; the databases are
ordinary unencrypted SQLite. Any SQLite tool can inspect them. The sign-in
stops someone sharing the computer from browsing a budget in the app;
protection at rest is left to disk encryption.

### A recovery code instead of a reset service

A new account shows a one-time recovery code that must be acknowledged before
continuing. No email, no server and no address held. Losing both the password
and the code loses the account.

### Every account's budgets are its own

Each account has its own budget files, deleted with it behind two
confirmations. A new account never adopts a budget it did not create. A
name whose file form would clash with an existing account or hold the budget
separator is refused. One person's figures cannot reach another's; the cost
is that some names are refused and an account cannot be removed while
keeping its budget.

### Another account's budget: opened with its owner's password, never saved over

Loading a budget that belongs to another account asks for that account's
password; saving over one is refused. Ownership is read from a stamp inside
the database, so copying a file does not launder it. Loading and saving are
treated differently on purpose: a load can be undone and a save cannot.

### Remembered sign-in, per account, in the keychain

Each account chooses separately whether its name and its password are
remembered. The password goes into the operating system's credential store and
never into a file. A keychain failure means nothing is remembered; sign-in
still works.

## The forecast

### A month is judged by its lowest day, against the overdraft you have

A forecast month is in danger when its balance breaches at any point, not
when it closes under, so a month that bounces a payment and recovers by payday still
shows. Inside an arranged overdraft a dip reads amber; red is kept for going
past the facility, with zero as the floor when none is recorded. Borrowing the
bank has agreed to is not an alarm; the verdict is only as good as the
facility recorded.

### The balance keeps itself up to date

Dated bank bills and income are applied to the stored balance at local
midnight on their day and ticked Paid or Received; missed days are caught
up at launch. Each application is logged, so deleting the item hands the
amount back; a balance typed by hand supersedes the log. A payment that lands
late at the bank still has to be corrected by hand.

### Ticks decide what has happened

A Paid or Received tick marks an item as done even before its day, rather
than waiting for the calendar. A bill paid early is not taken twice; income
received early is not added twice. The cost is ticking what happens early.

A tick says that something happened, never when. So a typed card balance
records which of the card's payments and charges were already ticked as it
was saved: those are inside the figure, while anything ticked later still
moves the card, including the payments the midnight update ticks on their
own day. A payment that left before the balance was typed but was ticked only
afterwards is taken twice until the balance is typed again.

### Card interest: a whole month unless the month clears the card

A card carrying a balance is charged a whole month's interest on what it owed
when the month opened. A month that clears the card, its payments covering
the opening and every charge, is charged none, as a balance paid in full is
not. The rule is one line that every card figure shares. The cost is
precision: a balance paid down part way through the month is charged as
though it had stood all month, where a real card charges by the day.

### One anchored simulation

The current month opens from the balance actually recorded; every later month
opens where the previous one closed. Solvency and Reserves share one daily
walk of a month and one rule for what is still to come, so they cannot
disagree. The cost: in an export the current month's opening need not equal
the previous close.

### Safe to Spend is bounded by the last month that stands alone

The headline is the most that could be spent today while every month up to
the last one that clears its floor unaided keeps clearing it. A later month
that is short whatever happens gets its own line saying so. The floor
always keeps a buffer, twenty pounds unless changed; the window looks one to
twelve months ahead, four by default. The figure is genuinely spendable; the
answer is two lines rather than one.

### Safe to Spend names the assumption it rests on

The figure lives on its own page and assumes income entered this month
arrives again in any later month with no entry of that name; the page says so
and names what has to arrive. An income past its final month is never filled
forward. A promise about the future is not read as a fact about the account;
income is matched by name, so a renamed income counts as missing.

### Two figures for a month, never the same number

What a month needs to hold flat is its whole bills and reserves against its
whole income. What it needs to stay afloat keeps its lowest point at or above
the floor, dated to the first day it goes under: money after a refusal does
not prevent it. Card interest stays out of the bank gap, reported per card,
since it accrues on the cards. Figures that differ by design need explaining.

### The colour carries the alarm; the words carry the number

Each forecast month leads with how far it goes overdrawn: the balance the
first day under ends on plus the deepest point when worse. A clean month
says "Never overdrawn". Then comes the sum needed and the day it must arrive by, then
where the month opens, dips and closes. Overdrawn means below zero, the bank's
word; the colour and the afloat line already carry the facility. The amount
leads because a day with no figure cannot be acted on. Every month gets the
line, clean ones included, because a missing line reads as one nobody worked
out. The figure comes from the shared month walk, so it agrees with the
afloat line beneath it.

## Bills, income and history

### A change applies from its month forward

A bill can change amount from a month onward while earlier months keep theirs;
a single-month override still wins. A new bill starts in the month it was
created. A month already reported keeps what it really cost; the cost is two
mechanisms to learn.

### Ending is not deleting

Bills and income carry an end month. Deleting offers two scopes: stop from the
viewed month (earlier and archived months keep it) or delete entirely for a
mistake. "This month only" is a scope rather than a category. A one-off
income can be promoted to recurring; the reverse is not offered, since it
would erase months that happened.

### The schema is versioned and loud

A database records how far its schema has been taken, so each migration runs
once and in order. A column is added only after looking for it; any other
failure stops the open. A corrupt or locked database is never mistaken for an
up-to-date one; it simply does not open.

## Reserves and recommendations

### Reserves accrue over the months remaining

A commitment such as an annual premium is put by evenly across the months
left before it falls due; where that runs steeper than the natural rate, the
row names the natural rate on hover.
Nothing is moved and no second account is assumed. A commitment entered late
has a steep first cycle.

### Set aside is a cost, not money gone

What a month sets aside counts in what it needs to hold flat and in its
colour; it stays out of the balance chain, since it has not left the account. The Safe to Spend floor rises by what
the reserves hold back each day; the graph draws it and dims any day in credit
that sits below it.
Money spoken for stops reading as free; a reserve moves a month's colour
without moving its balance.

### Reserves show where they are due and as they were

A commitment due this month appears read-only among the bills, so it is not
entered twice. The archive reports a reserve as at the month's own last day,
so the present never rewrites the past.

### Recommendations suggest; they never apply

The page retimes what can move, then states any shortfall as income asks.
There is no Apply button; a try-it-on tick shows the effect with nothing
written. Pausing a reserve is always priced by what the due month then
arrives short by. A date ticked as unable to move is never retimed. Every
change is made knowingly by hand.

## Files, saving and backups

### Several named budgets, each its own file

New Budget creates another named budget beside the existing ones; creating,
switching and renaming never touch another budget's contents. Starting afresh
destroys nothing; the cost is more files per account.

### An open database is never copied as a file

Save takes a snapshot through SQLite's backup interface; Load closes the live
database first. Both write a scratch file and rename it into place, so an
interrupted save or load leaves the previous database whole. Saving onto the
open budget itself is a commit.

### Save locations are remembered per account

Each account's save file is remembered under its own name; exports and full
backups default to Downloads because they are meant to leave. Save never
lands on somebody else's file by default.

### Back up everything in one file, restore all or nothing

An administrator can write every account and budget into one zip of SQLite
snapshots. A restore is staged and checked before any live file is replaced;
each live file is moved aside first, so a failure part way through is
undone. A lost machine comes back in one step; the zip is as unencrypted as
its files.

### Orphaned files are quarantined, never deleted

After a restore, a budget belonging to no restored account moves to a dated
quarantine folder, as the confirmation warns. Creating an account does the
same for files left under its name and logs it. No account inherits another's
budget and nothing is lost; the folder grows until emptied by hand.

### Data where each platform expects it

The data directory follows each platform's convention. An older location is
moved at startup: one rename on the same drive, otherwise a copy verified
byte for byte before the old one is removed. The old location stays in use
until the move completes, so one that cannot finish loses nothing and retries
next launch.

### A log for every escaped error

The application writes a plain log to its data directory and records every
exception escaping a slot or a worker thread. A failure in a windowed build
leaves something to diagnose; the cost is a local file naming the accounts
that signed in.

## Exports and the graph

### Exports are self-contained HTML

A month exports as one page with charts drawn as inline vector graphics and
nothing referenced outside it, always in the dark palette. A range of months
becomes a folder: an index and a page per month, linked by bare file name. It
emails, opens offline and tests as text; the chart is drawn twice, once on
screen and once for export.

### The curve passes through every day

The bar graph carries a monotone curve through each day's real balance, so it
never draws a balance the account did not have. The line graph needs none.

### The graph is a page like the others

The graph is a view stepped by the same month arrows, with a switch between
the bank balance and the cards. It holds no hidden state about where it was
opened from; the cost is one more tray button.

## The interface

### One home for every colour

Every colour lives in one palette module that the themes, the reports and the
setup program ask for roles; a test fails the build on a colour written
anywhere else. Light and dark switch live. A recolour moves every surface
sharing the role and nothing else.

### The keyboard reaches everything; the ring belongs to it

Tab and the arrow keys walk every control and Enter equals Space. A focus ring
means the keyboard is here: a clicked button does not keep focus and tables
never draw a ring. The application works without a mouse; every new control
needs a place in the ring.

### View buttons are pictures, held to the help

Views are picture buttons named on hover. How It Works shows each with the
picture it draws; tests fail the build if a button is missing or its
worked example stops matching the calculation. Pictures have to be learned.

### Switch User and Log Out differ

Switch User suspends the session, so cancelling sign-in returns to it; Log
Out ends it. Both live on the Users menu only, out of reach of a stray click.

### Start-up never looks like failure

After a password is accepted the sign-in screen stays as a progress bar until
the window is ready. A second launch asks the running copy to come forward
instead of warning. The window opens on the monitor under the pointer.

### The window never grows to fit

The bills table's name column takes the slack and elides a long name rather
than widening the window. The signed-in account is named on every view, so
whose budget is on screen is never in doubt.

### Reading pages scroll themselves

About, the licence and How It Works scroll gently and stop the moment the
reader takes over.

### The donate button sits at the foot of the window

One strip along the foot holds it, away from controls that act on the budget.
It opens the browser and nothing is withheld behind a donation.

## Building and installing

### A setup program of its own, installed per user

On Windows the bundle is installed by ClearBudget's own setup program into
the user's own Programs folder, so no administrator rights are needed. It
wears the application's colours. Install, repair, upgrade and uninstall touch
program files, shortcuts and the registry entry alone, never the data; a
running copy is closed rather than lectured. Removing the data is a manual
job.

### Releases that always open

The macOS disk image build fails unless it can notarise; an unnotarised local
build is labelled unreleasable. The Flatpak is granted the network, the home
folder and the keychain, broader than an offline budget strictly needs but
needed for each feature to work.

### One version, unversioned release files

One version file is the only place the version is written; the application
and the packaging read it. Release files have the same names every release,
so a link to the latest never goes stale.

### LGPL-3.0, with a commercial licence offered

ClearBudget is under LGPL-3.0, the licence PySide6 carries, with a commercial
licence for the author's own code offered separately.

## Engineering

### Layers that meet in one place

Domain, application, infrastructure and interface, with authentication
alongside, depend inward only and are wired in one composition root;
structural tests hold the boundaries. The money rules are tested with no
disk, clock or window, at the cost of more explicit wiring.

### Complete coverage where it means something

Line and branch coverage must be total over the logic and the setup program's
non-graphical half; interface code sits outside the gate, money formatting
inside it. Anything short of complete is a decision nobody made; interface
code relies on targeted tests.

### Small modules, with a danger band

No source or test file may exceed four hundred lines or sit in the last five
percent below that. Files split at real seams instead of breaking on the next
edit; the cost is many small modules.

### Tests with real parts, never real data

No mocking library: real SQLite in temporary folders and hand-written fakes;
guards are proved by planting the violation they forbid. One function derives
the data directory and the suite redirects it for every test, so no test can
touch a user's live data.

### Linted whole, on the user's calendar

flake8 and ruff read the whole tree, with blind exception handlers and naive
datetimes ruled out. Dates come from the local clock deliberately, so a
budget month is the user's own; each such call carries a marker saying so.

### No magic numbers, by review

Amounts, thresholds and limits come from data, configuration or named
constants. That is a house rule held by review; nothing checks it
automatically.
