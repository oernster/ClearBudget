# <img width="64" height="64" alt="clearbudget_64" src="https://github.com/user-attachments/assets/4e8c5620-7890-4527-9eb6-14adad1ebea8" /> ClearBudget

A personal budget planning application for managing income, bills, and credit cards with
detailed solvency analysis. Supports multiple user accounts with secure authentication.

**Author:** Oliver Ernster  
**Licence:** GNU Lesser General Public Licence v3.0 (LGPL-3.0)

---

## Features

- Multi-user login with bcrypt password hashing and recovery codes
- Per-user isolated budget databases
- Month-by-month budget tracking with income and bill templates
- Per-bill monthly skip (exclude a bill from one month without deleting it)
- Per-bill monthly overrides (amount and due day overrides for a specific month)
- Solvency analysis with forward cashflow projections (next 2 months)
- Mid-month overdraft detection (accounts for bills clustering before late income)
- Credit card management: limits, interest rates, payment due dates, utilisation tracking
- Per-card monthly cashflow breakdown (charges, payment, interest, minimum due, projected closing balance)
- 6-month rolling balance projection per card (colour-coded by available headroom)
- Dynamic payment methods: assign bills to bank account or specific credit cards
- Database export and validated import (File menu)
- Display currency selection - 25 currencies covering English-speaking countries (File > Preferences)
- Dark theme UI with scrollable tabs and scroll position indicators
- SQLite storage: per-user budget database + shared users database

---

## Application Tabs

- **Monthly Budget** - View and manage bills for the selected month; toggle active/skip per bill; view balance or projected end-of-month figure
- **Solvency** - Financial health analysis, overdraft alerts, mid-month cashflow risk, per-card utilisation bars, forward projections for the next two months
- **Credit Cards** - Add, edit, delete cards; month-navigation shows projected closing balances for future months; 6-month projection strip
- **Archive** - Historical month summaries by year with navigation; drill down into individual months

---

## File Menu

| Action | Description |
|--------|-------------|
| New Budget... | Wipe all budget data and start fresh (double confirmation required) |
| Export Database... | Copy active database to a chosen location |
| Import Database... | Replace active database from a backup file (validated before write) |
| Preferences... | Choose display currency |
| Switch User | Return to login screen |
| Exit | Close application |

---

## User Accounts

On first launch, a setup wizard creates an admin account. A one-time recovery code is
displayed and must be acknowledged before the wizard completes.

Subsequent launches show a login screen. The "Forgot password?" link allows password
reset using the recovery code.

Admin users have access to a **Users** menu for adding and removing accounts. Admins
cannot delete their own account. Non-admin users do not see the Users menu.

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
- Credit limit and current balance used
- Interest rate (APR) or minimum payment percentage (per-card calibrated)
- Payment due day
- Card expiry date
- Active/inactive status

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

---

## Database Import / Export

- **Export** (File > Export Database...): Save As dialog, `.db` extension enforced, copies active database
- **Import** (File > Import Database...): file validated as SQLite and verified to contain all required ClearBudget tables and columns before any write; confirmation required if active database has data; window reloads automatically after import - no restart needed

---

## Solvency Panel

- **Overdraft alert**: SAFE / AT RISK / CAUTION / CRITICAL based on projected balance
- **Mid-month alert**: detects temporary overdraft when bills cluster before the last income payment of the month
- **Freedom to spend**: discretionary headroom calculated as the next month's lowest projected bank balance minus a configurable buffer (default £50). Represents money genuinely safe to spend without the account dipping below the buffer at any point in the coming month. Editable buffer field shown directly on the panel.
- **Credit Card Status**: one progress bar per card showing current balance vs limit; projected month-end closing balance, charges, payment, interest, minimum due, and net direction all shown inline
- **Forward Projection**: day-by-day cashflow narrative for the next two months including card state

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
