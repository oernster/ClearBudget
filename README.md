# <img width="64" height="64" alt="clearbudget_64" src="https://github.com/user-attachments/assets/4e8c5620-7890-4527-9eb6-14adad1ebea8" /> ClearBudget

A personal budget planning application for managing income, bills, and credit cards with detailed solvency analysis.

**Author:** Oliver Ernster  
**Licence:** GNU Lesser General Public Licence v3.0 (LGPL-3.0)

## Features

- Month-by-month budget tracking with income and bill templates
- Per-bill monthly skip (exclude a bill from one month without deleting it)
- Per-bill monthly overrides (amount and due day overrides for a specific month)
- Solvency analysis with forward cashflow projections (next 2 months)
- Mid-month overdraft detection (accounts for bills clustering before late income)
- Credit card management: limits, interest rates, payment due dates, utilisation tracking
- Per-card monthly cashflow breakdown (charges, payment, interest, minimum due, projected closing balance)
- 6-month rolling balance projection per card (colour-coded by available headroom)
- Dynamic payment methods: assign bills to bank account or specific credit cards
- Database export (Save As with .db extension enforcement) and validated import
- Help > About dialog with author credit and open source library attributions
- Dark theme UI with scrollable tabs and scroll position indicators
- SQLite database for persistent storage (`~/.clearbudget/budget.db`)

## Application Tabs

- **Monthly Budget** - View and manage bills for the selected month; toggle active/skip per bill; view balance or projected end-of-month figure
- **Solvency** - Financial health analysis, overdraft alerts, mid-month cashflow risk, per-card utilisation bars, forward projections for the next two months
- **Credit Cards** - Add, edit, delete cards; month-navigation shows projected closing balances for future months; 6-month projection strip
- **Archive** - Auto-loads last 12 months on open; export or import the active database

## Bill Categories

- `housing` — Rent, mortgage
- `utilities` — Electric, water, internet
- `subscriptions` — Recurring services
- `credit_payment` — Credit card payments
- `groceries` — Food and household
- `discretionary` — Entertainment and leisure
- `one_time` — One-off purchases

## Payment Methods

Each bill is assigned to either:
- Bank Account (default) — deducted from bank balance
- Credit Card — tracked separately, affects card utilisation

## Credit Card Tracking

For each card:
- Credit limit and current balance used
- Interest rate (APR) or minimum payment percentage (per-card calibrated)
- Payment due day
- Card expiry date
- Active/inactive status

Utilisation thresholds in projection views:
- Green: available headroom > £250
- Amber: available headroom ≤ £250
- Red: available headroom ≤ £100

## Monthly Skip / Override

Bills can be skipped or overridden for a single month without affecting other months or the bill template:
- **Skip**: bill excluded from that month's totals; shown greyed with "(skipped this month)"
- **Override**: amount and/or due day changed for one month; shown with blue `(*)` indicator

## Database Import / Export

- **Export**: Save As dialog, `.db` extension enforced, copies active database to chosen location
- **Import**: Open dialog; file validated as SQLite and verified to contain all required ClearBudget tables and columns before any write; confirmation required if active database has data; restart required after import

## Solvency Panel

- **Overdraft alert**: SAFE / AT RISK / CAUTION / CRITICAL based on projected balance
- **Mid-month alert**: detects temporary overdraft when bills cluster before the last income payment of the month
- **Freedom to spend**: income minus all bills (discretionary budget available)
- **Credit Card Status**: one progress bar per card showing current balance vs limit; projected month-end closing balance, charges, payment, interest, minimum due, and net direction all shown inline
- **Forward Projection**: day-by-day cashflow narrative for the next two months including card state

## Running

```
python main.py
```

## Requirements

- Python 3.11+
- PySide6 >= 6.8.0

## Licence

Distributed under the GNU Lesser General Public Licence v3.0.  
See Help > View Licence in the application, or visit https://www.gnu.org/licenses/lgpl-3.0.html

### Open Source Credits

- **Python** — Python Software Foundation (PSF Licence)
- **PySide6 (Qt for Python)** — The Qt Company (LGPL-3.0)
- **SQLite** — Public Domain
- **pytest** — Holger Krekel et al. (MIT)
- **black** — Łukasz Langa et al. (MIT)
- **pywin32** — Mark Hammond (PSF Licence)
- **PyInstaller** — PyInstaller contributors (GPL-2.0 + bootloader exception)
