# ClearBudget

A professional Python/PySide6 personal budget planning application built with clean architecture, SOLID principles, and good test coverage (within the limits of PyQt).

## Features

- **Month-by-Month Budget Planning** - Track income and bills for each month
- **Solvency Analysis** - Know your financial health and plan for deficits
- **Credit Card Management** - Add, edit, delete credit cards with interest rates, expiry dates, payment due days
- **Credit Card Monitoring** - Track utilization % and exhaustion risk (danger/warning/ok status)
- **Dynamic Payment Methods** - Assign bills to bank account or specific credit cards
- **Bill Templates** - Organize recurring and one-time expenses by category
- **Income Tracking** - Monitor reliable vs. variable income sources
- **Working Day Adjustment** - Payment due dates auto-adjust to preceding working day (weekends/UK holidays)
- **Dark Theme UI** - Professional dark interface with PySide6

## Requirements

- Python 3.13+
- PySide6 (Qt framework)
- SQLite (included with Python)

## Installation

### From Source

1. Clone the repository:
   ```bash
   git clone https://github.com/oliverernster/clearbudget.git
   cd ClearBudget
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   python main.py
   ```

### Development Setup

1. Install dev dependencies:
   ```bash
   pip install -r requirements-dev.txt
   ```

2. Run tests:
   ```bash
   pytest
   ```

3. Format code:
   ```bash
   black .
   ```

4. Check linting:
   ```bash
   flake8 .
   ```

## Usage

### Starting the Application

```bash
python main.py
```

The app creates a SQLite database at `~/.clearbudget/budget.db` on first run.

### Tabs

- **Month Budget** - Add, edit, and view bills for the selected month; assign each bill to Bank or a credit card
- **Solvency** - Financial health analysis, forward projections, and deficit warnings
- **Credit Cards** - Manage cards (add/edit/delete); view utilization, interest rates, payment due dates, and exhaustion status
- **Archive** - Browse historical month data and trends

### Bill Management

Bills are organized by category:
- **housing** - Rent, mortgage
- **utilities** - Electric, water, internet
- **subscriptions** - Recurring services
- **credit_payment** - Credit card payments
- **groceries** - Food and household
- **discretionary** - Entertainment and leisure
- **one_time** - One-off purchases

Bill types:
- **fixed** - Same amount every month
- **variable** - Amount varies (estimated or actual)
- **expiring** - One-time or limited duration

**Payment Methods:**
Each bill can be assigned to:
- **Bank Account** (default) - Deducted from bank balance
- **Credit Card** - Charged to a specific credit card (affects card utilization tracking)

### Solvency Panel

Shows:
- **Balance** - Income minus bills for the month (green if positive, red if negative)
- **Deficit** - Amount short if balance is negative
- **Forward Shortfall** - Projected shortfalls in next 2 months
- **Desired Acquire** - Target amount to accumulate (deficit + buffer + forward shortfall)

### Credit Card Management

Add and manage credit cards with:
- Card name, credit limit, current balance
- Annual interest rate (APR)
- Payment due day (1-31, auto-adjusted to working day if weekend/holiday)
- Card expiry date (month/year)
- Minimum payment amount
- Active/inactive status (soft-delete)

Utilization tracking:
- **OK** (green) - Less than 50% used
- **WARNING** (yellow) - 50-80% used
- **DANGER** (red) - 80%+ used

## Architecture

ClearBudget follows **clean architecture** with 4 isolated layers:

1. **Domain** - Pure business logic (no I/O)
   - Entities: Bill, IncomeSource, CreditCard, MonthBill, MonthIncome
   - Value Objects: Amount, YearMonth, SolvencyResult, CardExhaustionWarning
   - Services: SolvencyCalculator, CardExhaustion, BankCashflow
   - Interfaces: Repository protocols

2. **Application** - Orchestration and DTOs
   - BudgetService: Coordinates domain logic
   - MonthGenerator: Creates month data from templates
   - DTOs: MonthSummary, SolvencyReport

3. **Infrastructure** - SQLite database
   - Database: Schema and connection management
   - Repositories: Bill, IncomeSource, PaymentMethod operations
   - All tests use real SQLite via `tmp_path`

4. **UI** - PySide6 dark theme interface
   - ViewModels: MonthViewModel, SolvencyViewModel
   - Views: MonthView, SolvencyPanel, CreditCardView, ArchiveView
   - MainWindow: Tab-based layout

See [ARCHITECTURE.md](ARCHITECTURE.md) for details.

## Testing

- **175 tests** across all layers
- **100% code coverage** (541 statements)
- **No mocking** - hand-written fakes for domain testing, real SQLite for infrastructure
- **Structural tests** - AST-based architecture enforcement (layering rules, LOC limits)

Run tests:
```bash
pytest                    # Run all tests with coverage
pytest tests/domain/      # Run domain tests only
pytest -v                 # Verbose output
```

## Code Quality

- **Black** - Code formatting (line length: 88)
- **Flake8** - Linting (extended ignore E203, W503)
- **Max 400 LOC** - All files under 400 lines
- **100% coverage** - pytest --cov-fail-under=100

Format and lint:
```bash
black .
flake8 .
```

## Build & Distribution

### Create Standalone EXE

```bash
python buildexe.py
```

Creates `dist-pyinstaller/ClearBudget/ClearBudget.exe`.

### Create Installer

```bash
python buildinstaller.py
```

Creates `dist-installer/ClearBudgetSetup.exe` with:
- Install wizard
- Registry entries
- Start menu shortcuts
- Uninstall support

## File Structure

```
ClearBudget/
├── VERSION                      # App version (1.0.0)
├── README.md                    # This file
├── ARCHITECTURE.md              # Detailed architecture
├── LICENSE                      # License file
├── LGPL3-LICENSE                # Required for PySide6
├── main.py                      # Application entry point
├── buildexe.py                  # PyInstaller builder
├── buildinstaller.py            # Installer builder
├── pyproject.toml               # Black & pytest config
├── .flake8                      # Flake8 config
├── .coveragerc                  # Coverage config
├── requirements.txt             # Runtime dependencies
├── requirements-dev.txt         # Development dependencies
│
├── clear_budget/                # Main package
│   ├── domain/                  # Pure business logic
│   ├── application/             # Orchestration & DTOs
│   ├── infrastructure/          # SQLite
│   ├── ui/                      # PySide6 interface
│   └── shared/                  # Config, errors
│
├── tests/                       # Test suite
│   ├── domain/
│   ├── application/
│   ├── infrastructure/
│   ├── ui/
│   ├── structural/
│   └── shared/
│
└── installer/                   # Installer application
    ├── app.py
    ├── ops/
    ├── ui/
    └── shared/
```

## Development Notes

### Key Design Decisions

**Amount Value Object:**
- Stored as `pence: int` to avoid float rounding errors
- Non-negative only (use raw `int` for calculations that produce negatives)

**SolvencyResult.balance:**
- Type: `int` (pence), can be negative
- Represents income - bills (may have deficit)
- Not `Amount` because Amount rejects negatives

**CardExhaustionService:**
- `net_monthly = charge - payment` (can be negative if payment > charge)
- When `net ≤ 0`, months_until_max = infinity (card being paid down)
- Status: danger (≤1m), warning (1-3m), ok (>3m)

### No Mocking in Tests

Domain and application tests use hand-written fake repositories implementing `Protocol` interfaces instead of `unittest.mock`. Infrastructure tests use real SQLite via `tmp_path` fixture.

Benefits:
- Tests verify actual behavior, not implementation
- Fakes are minimal and readable
- No magic mock setup/assertion code

## License

LGPL3 - Required by PySide6 (Qt). See LICENSE and LGPL3-LICENSE.

## Author

Oliver Ernster

## Version

1.0.0
