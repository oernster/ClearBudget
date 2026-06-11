# <img width="64" height="64" alt="clearbudget_64" src="https://github.com/user-attachments/assets/4e8c5620-7890-4527-9eb6-14adad1ebea8" /> Clear Budget

A personal budget planning application for managing income, bills, and credit cards with
detailed solvency analysis. Supports multiple user accounts with secure authentication.

**Author:** Oliver Ernster  
**Licence:** GNU Lesser General Public Licence v3.0 (LGPL-3.0)

---

## Features

- Multi-user login with bcrypt password hashing and recovery codes
- Create an account from the sign-in screen at any time, not just on first
  launch (only the very first account ever created is an admin)
- Read-only viewer accounts: export a snapshot of a budget as a "viewer
  package" for someone else to import and browse without editing
- Per-user isolated budget databases
- Month-by-month budget tracking with income and bill templates
- Per-bill monthly skip (exclude a bill from one month without deleting it)
- Per-bill monthly overrides (amount and due day overrides for a specific month)
- Per-bill "paid" flag - excludes a paid bill from "still due" totals and the
  projected balance for the rest of the month
- Per-month income flexibility: per-month overrides, per-month skips, a
  "received" flag, and "this month only" one-off income entries
- Solvency analysis with forward cashflow projections (next 2 months)
- Mid-month overdraft detection (accounts for bills clustering before late income)
- Configurable bank overdraft facility (limit + APR) with a Monthly Budget
  warning when the projected balance dips below zero mid-month, even if the
  month ends positive
- Credit card management: limits, interest rates, payment due dates, utilisation tracking
- Per-card monthly cashflow breakdown (charges, payment, interest, minimum due, projected closing balance)
- Live pro-rated credit card balance projection between months
- 6-month rolling balance projection per card (colour-coded by available headroom)
- Dynamic payment methods: assign bills to bank account or specific credit cards
- Database export and validated import (File menu)
- Display currency selection - 25 currencies covering English-speaking countries (File > Preferences)
- Dark theme UI with scrollable tabs and scroll position indicators
- Built-in "How It Works" help screen explaining pro-rating, balances and archiving
- SQLite storage: per-user budget database + shared users database

---

## Application Tabs

- **Monthly Budget** - View and manage bills and income for the selected month; toggle active/skip/paid per bill and received per income; view balance or projected end-of-month figure; mid-month overdraft dip warning; hint linking to the Solvency tab
- **Solvency** - Financial health analysis, overdraft alerts, mid-month cashflow risk, per-card utilisation bars, forward projections for the next two months
- **Credit Cards** - Scrollable list of per-card panels (active toggle, status badge, overview and this-month figures, Edit/Delete); month-navigation shows projected closing balances for future months; 6-month projection strip
- **Archive** - Historical month summaries by year with navigation; drill down into individual months (only fully-completed months are shown)

---

## File Menu

| Action | Description |
|--------|-------------|
| New Budget... | Wipe all budget data and start fresh (double confirmation required) |
| Import / Export > Export Database... | Copy active database to a chosen location |
| Import / Export > Import Database... | Replace active database from a backup file (validated before write) |
| Import / Export > Export Read-Only Viewer Package... (admin only) | Bundle a snapshot of the budget into a zip for a viewer account |
| Import / Export > Import Read-Only Viewer Package... (admin only) | Import a viewer package, creating or refreshing a read-only account |
| Preferences... | Choose display currency |
| Bank Account Settings... | Configure an overdraft facility (limit and APR) |
| Switch User | Return to login screen |
| Exit | Close application |

Read-only viewer accounts have most of these actions disabled, and the window title
shows "(Read-only)".

---

## User Accounts

On first launch, a setup wizard creates an admin account - the only account that is
ever an admin. A one-time recovery code is displayed and must be acknowledged before
the wizard completes.

Subsequent launches show a login screen with username/password fields plus:
- **Forgot password?** - reset using the recovery code
- **Import Viewer Package...** - import a read-only viewer account from a package file
- **Create Account...** - create a new (non-admin) account at any time, without
  needing an admin

Admin users have access to a **Users** menu for adding and removing accounts (added
accounts are also non-admin). Admins cannot delete their own account. Deleting a user
account always permanently deletes that user's budget data too (two confirmations
required) - there is no way to keep an orphaned data file after the account's
credentials are destroyed. Non-admin users do not see the Users menu.

A **read-only viewer account** can sign in to browse a snapshot of someone else's
budget but cannot edit anything.

---

## Display Currency

File > Preferences opens a currency picker. 25 currencies are supported:

GBP, USD, EUR, AUD, CAD, NZD, ZAR, SGD, HKD, INR, NGN, GHS, KES, PHP, PKR, BDT,
JMD, TTD, NAD, BWP, ZMW, BZD, GYD, FJD, PGK

The selection is saved per user and takes effect immediately throughout the app.
Defaults to GBP.

---

## Bill Categories

- `housing` - Rent, mortgage
- `utilities` - Electric, water, internet
- `subscriptions` - Recurring services
- `credit_payment` - Credit card payments
- `groceries` - Food and household
- `discretionary` - Entertainment and leisure
- `one_time` - One-off purchases

---

## Payment Methods

Each bill is assigned to either:
- **Bank Account** (default) - deducted from bank balance
- **Credit Card** - tracked separately, affects card utilisation

---

## Credit Card Tracking

For each card:
- Credit limit and current balance used (live pro-rated between months)
- Interest rate (APR) or minimum payment percentage (per-card calibrated)
- Payment due day
- Card expiry date
- Active/inactive status

The Credit Cards tab shows each card as its own panel: active checkbox, name, status
badge, an overview row (limit/used/available/utilisation/due day/interest/minimum
payment/expiry), and a this-month row (charges/payment received/interest/minimum
payment due). Edits go through the Edit Card dialog; cards are deleted individually
with confirmation.

Utilisation thresholds in projection views:
- Green: available headroom > 250 (in active currency)
- Amber: available headroom <= 250
- Red: available headroom <= 100

---

## Monthly Skip / Override

Bills can be skipped or overridden for a single month without affecting other months
or the bill template:
- **Skip**: bill excluded from that month's totals; shown greyed with "(skipped this month)"
- **Override**: amount and/or due day changed for one month; shown with blue `(*)` indicator
- **Paid**: bill marked as paid for the month is excluded from "still due" totals and
  the projected balance for the rest of that month, since the money has already left
  the account

Income sources have the same per-month flexibility (overrides, skips, and a "received"
flag), plus "this month only" one-off entries for ad-hoc income not tied to a
recurring template.

---

## Database Import / Export

- **Export** (File > Import / Export > Export Database...): Save As dialog, `.db` extension enforced, copies active database
- **Import** (File > Import / Export > Import Database...): file validated as SQLite and verified to contain all required Clear Budget tables and columns before any write; confirmation required if active database has data; window reloads automatically after import - no restart needed

---

## Solvency Panel

- **Overdraft alert**: SAFE / AT RISK / CAUTION / CRITICAL based on projected balance
- **Mid-month alert**: detects temporary overdraft when bills cluster before the last income payment of the month
- **Credit Card Status**: one progress bar per card showing current balance vs limit; projected month-end closing balance, charges, payment, interest, minimum due, and net direction all shown inline
- **Forward Projection**: day-by-day cashflow narrative for the next two months including card state

The Monthly Budget tab also links here via "See the Solvency tab for full balance
projections."

---

## Bank Account Settings

File > Bank Account Settings opens a dialog to record an overdraft facility: a limit
(in the active currency) and an APR. With a facility recorded, the Monthly Budget tab
shows:
- An amber warning if the projected balance dips below zero but stays within the
  facility, including an estimated daily interest cost
- A red warning if the dip would exceed the facility, or if no facility is set at all

---

## Help Menu

- **How It Works** - plain-English explanation of pro-rating, balances, archiving and
  tab behaviour, kept in sync with the calculation logic
- **About Clear Budget**
- **View Licence (LGPL-3.0)**

---

## Running

```
python main.py
```

## Requirements

- Python 3.11+
- PySide6 >= 6.8.0
- bcrypt

---

## Licence

Distributed under the GNU Lesser General Public Licence v3.0.  
See Help > View Licence in the application, or visit https://www.gnu.org/licenses/lgpl-3.0.html

### Open Source Credits

- **Python** - Python Software Foundation (PSF Licence)
- **PySide6 (Qt for Python)** - The Qt Company (LGPL-3.0)
- **SQLite** - Public Domain
- **bcrypt** - Nate Lawson, Perry Metzger (Apache-2.0)
- **pytest** - Holger Krekel et al. (MIT)
- **black** - Lukasz Langa et al. (MIT)
- **pywin32** - Mark Hammond (PSF Licence)
- **PyInstaller** - PyInstaller contributors (GPL-2.0 + bootloader exception)
