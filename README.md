# ClearBudget

A PySide6-based monthly spending planner for forward-looking budget management with credit card tracking and solvency warnings.

## Features

- **Template-based monthly planning** — define bills once, apply to all future months
- **Expiring items** — automatically hide bills after their end date (e.g., Camera Amazon layaway ends Nov 2026)
- **Solvency panel** — real-time calculation of:
  - Current month balance
  - Deficit warning (if spending > income)
  - **Desired acquire amount** = deficit + £600 buffer + next 2 months' shortfall (using reliable income only)
- **Credit card tracking**:
  - Per-card balance, limit, and available credit
  - Monthly charge vs. payment calculations
  - Exhaustion warnings (when card will max out)
  - Bills directly charged to each card (e.g., CapitalOne has Render, Prime, etc.)
- **No overdraft protection** — accounts for the fact that your bank account cannot go negative
- **Income timing** — tracks when income arrives (M+D loan on 1st, Universal Credit on 21st)
- **Archive system** — move past months to read-only archive

## Quick Start

```bash
pip install -r requirements.txt
python main.py
```

## Data Storage

Database stored in `~/.clearbudget/budget.db` (auto-created on first run).
