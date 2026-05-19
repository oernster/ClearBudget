# ClearBudget Architecture

A clean architecture implementation with 4 isolated layers: Domain, Application, Infrastructure, and UI.

## Overview

```
┌─────────────────────────────────────────────────────────────┐
│                       UI Layer (PySide6)                    │
│    MainWindow → MonthView, SolvencyPanel, etc.              │
│    ViewModels → State management & signals                  │
└──────────────────────┬──────────────────────────────────────┘
                       │ DTOs (MonthSummary, SolvencyReport)
┌──────────────────────▼──────────────────────────────────────┐
│           Application Layer (Orchestration)                 │
│    BudgetService → MonthGenerator                           │
│    (coordinates domain services & repositories)             │
└──────────────────────┬──────────────────────────────────────┘
                       │ Domain Entities, Value Objects, Services
┌──────────────────────▼──────────────────────────────────────┐
│        Domain Layer (Pure Business Logic)                   │
│    Entities, Value Objects, Services (no I/O)              │
│    Interfaces (Protocols) → Repository abstraction          │
└──────────────────────┬──────────────────────────────────────┘
                       │ Concrete Repository implementations
┌──────────────────────▼──────────────────────────────────────┐
│       Infrastructure Layer (SQLite Persistence)             │
│    Database, Repositories, Schema Management                │
└─────────────────────────────────────────────────────────────┘
```

## Layer Responsibilities

### Domain Layer

**Pure Business Logic** - No I/O, no frameworks, fully testable.

**Entities** (frozen dataclasses with `slots=True`):
- `Bill` - Template for a recurring or one-time expense
  - `name`, `amount`, `category`, `bill_type`, `day_of_month`
  - `start_ym`, `end_ym` (expiring bills)
  - `skipped_for_month: bool` - per-month skip flag (joined from `bill_month_skips`)
  - `has_month_override: bool` - per-month override flag (joined from `bill_month_overrides`)
  - `is_active_in_month(year_month)` - checks date range

- `IncomeSource` - Recurring income (salary, benefits)
  - `name`, `amount`, `is_reliable` (for forward projections)

- `CreditCard` - Credit card tracking
  - `id`, `name`, `credit_limit`, `current_balance_used`
  - `interest_rate_apr` (nullable), `payment_due_day` (1-31)
  - `card_expiry_month` (1-12, nullable), `card_expiry_year` (nullable)
  - `minimum_payment_pence` (nullable), `minimum_payment_percent` (nullable)
  - `active` (soft-delete flag, 1 or 0)
  - Properties: `available`, `utilization_percent`

- `MonthBill` - Bill instantiated for a specific month
- `MonthIncome` - Income for a specific month

**Value Objects** (frozen, immutable):
- `Amount(pence: int)` - Non-negative currency
- `YearMonth(year, month)` - Date validation with arithmetic
- `SolvencyResult` - Outcome of solvency calculation
- `CardExhaustionWarning` - Credit card exhaustion analysis

**Domain Services**:
- `SolvencyCalculatorService.calculate()` - Computes balance, deficit, forward shortfall
- `CardExhaustionService.analyse()` - Months until card maxes out
- `BankCashflowService.find_first_negative_day()` - Detects overdraft date
- `WorkingDayCalculatorService.adjust_to_working_day()` - Adjusts payment dates
- `CardMonthlyCalculator.calculate_card_monthly_state()` - Per-card monthly cashflow
  - Inputs: card, opening balance pence, bills list
  - Computes charges, payment received, interest, closing balance, minimum payment
  - Returns `CardMonthlyState` frozen dataclass

### Application Layer

**Orchestration** - Coordinates domain layer, defines cross-boundary DTOs.

**BudgetService** (main orchestrator):
- `get_month_summary(year_month)` → `MonthSummary`
- `calculate_solvency(year_month)` → `SolvencyReport`
- `calculate_solvency_from_summary(year_month, month_summary)` → `SolvencyReport`
- `get_card_monthly_states(year_month)` → `list[CardMonthlyState]`
  - Projects each card's balance forward from today through the target month
- `get_card_projection_months(start_month, n_months)` → `list[list[CardMonthlyState]]`
  - Chains balances forward in one pass; used by 6-month projection strip
- `skip_bill_for_month(bill_id, year_month)` - Inserts into `bill_month_skips`
- `unskip_bill_for_month(bill_id, year_month)` - Removes from `bill_month_skips`
- `delete_bill_month_override(bill_id, year_month)` - Removes month override
- `get_projected_month_end_balance_pence(year_month)` → `int` (signed)
  - Returns signed int to avoid `InvalidAmountError` on negative projected balances
- `get_bank_balance()` / `set_bank_balance(amount)` - Persistent bank balance via settings table

**DTOs**:
- `MonthSummary` - `year_month`, `total_income`, `total_bills`, `bank_bills`, `balance`, `bills`, `all_bills`, `income_sources`, `all_income_sources`
- `SolvencyReport` - `year_month`, `balance_pence: int` (signed), `deficit`, `buffer`, `forward_shortfall`, `is_solvent`, `first_negative_day`

### Infrastructure Layer

**Database** (`~/.clearbudget/budget.db`):
- `Database(db_path)` - SQLite connection and schema management
- Schema — 11 tables:
  1. `payment_methods` - id=1 is "Bank Account"
  2. `bills` - templates; columns include `target_card_id` (migration)
  3. `income_sources`
  4. `months`
  5. `month_bills`
  6. `month_income`
  7. `credit_cards` - includes `minimum_payment_percent` (migration)
  8. `settings` - key/value store (bank balance, etc.)
  9. `bill_month_overrides` - per-month amount/day overrides; includes `day_of_month` (migration)
  10. `bill_month_skips` - per-month bill exclusion (bill_id, year, month)
  11. `sqlite_sequence`

**Repositories**:
- `SQLiteBillRepository`
  - `list_active_for_month()` - LEFT JOINs `bill_month_skips` and `bill_month_overrides`; sets `skipped_for_month` and `has_month_override` on returned entities; uses `o.bill_id IS NOT NULL` (not `o.id`) to avoid column ambiguity
  - `skip_for_month(bill_id, year_month)` / `unskip_for_month(bill_id, year_month)`
  - `hard_delete(bill_id)` - also cleans `bill_month_skips` and `bill_month_overrides`
- `SQLiteIncomeSourceRepository`
- `SQLitePaymentMethodRepository`
  - `set_card_active(card_id, active)` - soft-delete toggle

### UI Layer

**ViewModels**:
- `MonthViewModel` - month state, signals: `month_changed`, `month_summary_updated`
- `SolvencyViewModel`
  - `set_month()` now fetches the new month's summary before refreshing (fixes stale data on navigation)
  - `update_month_summary()` called by `MonthView` after balance edits (via `month_summary_updated` signal)

**Views**:
- `MonthView`
  - Bill table: 7 columns — Name, Category, Amount, Type, Due, Active, Skip
  - Skip column (col 6): per-bill checkbox toggles `skip_bill_for_month` / `unskip_bill_for_month`
  - Skipped bills: grey text + "(skipped this month)" suffix
  - Override bills: blue `(*)` suffix on name
  - Balance display: current month shows actual balance; future months show projected end balance via `get_projected_month_end_balance_pence`; negative renders as "−£X OVERDRAWN"
  - `on_edit_balance` emits `month_summary_updated` after saving so Solvency panel refreshes

- `SolvencyPanel`
  - Section 1: Overdraft alert (colour-coded SAFE/AT RISK/CAUTION/CRITICAL)
  - Mid-month CRITICAL alert: detects temporary overdraft when bills cluster before last income; undated bills use day 28 (not 1) to avoid false alarms
  - Section 2: Overall Health — freedom to spend, projected balance, committed/remaining breakdown
  - Credit Card Status: per-card `QProgressBar` (current balance / limit) with projected month-end closing balance in format text; detail line shows charges / payment / interest / min due / net direction; colour by available headroom (red ≤£100, amber ≤£250, green >£250)
  - Section 3: Forward Projection — m1 and m2 cashflow summaries with card state text
  - Health score and aggregate card utilisation percentage removed

- `CreditCardView`
  - Month navigation; snapshot columns (Used, Available, Util%, Status) show projected closing balance when viewing future months
  - 6-Month Balance Projection strip: rows = months, columns = active cards; colour by available headroom (same thresholds as Solvency)
  - Powered by `get_card_projection_months`

- `ArchiveView`
  - Auto-loads last 12 months on init (no button required)
  - Export Database: Save dialog, forces `.db` extension, copies active database
  - Import Database: Open dialog; three-layer validation before any write:
    1. Must be valid SQLite (opened read-only via URI)
    2. Must contain all 7 required ClearBudget tables
    3. Each required table must have correct ClearBudget columns (verified via `PRAGMA table_info`)
  - Overwrite confirmation shown if active database has data

**Widgets**:
- `BillDialog` - `month_only_status` label shows scope when "This month only" checked; `load_bill` pre-checks checkbox for override bills; unchecking + OK on override bill calls `delete_bill_month_override`
- `AboutDialog` - app icon, author (Oliver Ernster), LGPL-3.0 notice, open source credits; accessed via Help menu
- `LicenceDialog` - LGPL-3.0 full notice + third-party attributions; "Open Full Licence Text" button opens gnu.org
- `ScrollableTab` - wraps any view in `QScrollArea`; overlays ▲/▼ system-icon buttons (sky blue, `rgba(56,189,248,200)`) at top-right/bottom-right; buttons appear only when scrollable content exists in that direction; clicking scrolls by a fixed step

**Main Application**:
- `MainWindow` - all tabs wrapped in `ScrollableTab`; Help menu (About / View Licence); restored geometry set to 88% of available screen before `showMaximized` so un-maximize always fits on screen
- `main.py` - scale factor capped at 1.5× to prevent oversized UI on 4K monitors; restored geometry calculated from `availableGeometry()`
- `ui_scale.py` - `init(factor)`, `px(value)`, `style(css)` — referenced throughout UI

**Theme** (`dark_theme.py`):
- `QMenuBar` / `QMenu` hover: orange `#f59e0b` 2px border
- `QPushButton` hover/press: orange `#f59e0b` 2px border; base has `border: 2px solid transparent` to prevent layout shift
- `QTabBar::tab` hover: orange `#f59e0b` 2px border; selected tab uses purple `#a78bfa` border

## Dependency Injection

No container — dependencies passed via constructor.

```python
database = Database(config.db_path)
database.connect()
database.create_schema()

bill_repo = SQLiteBillRepository(database.conn)
income_repo = SQLiteIncomeSourceRepository(database.conn)
payment_method_repo = SQLitePaymentMethodRepository(database.conn)
month_generator = MonthGenerator(bill_repo, income_repo)

budget_service = BudgetService(
    bill_repo=bill_repo,
    income_repo=income_repo,
    payment_method_repo=payment_method_repo,
    month_generator=month_generator,
)

month_view_model = MonthViewModel(budget_service=budget_service)
solvency_view_model = SolvencyViewModel(budget_service=budget_service)

window = MainWindow(
    month_view_model=month_view_model,
    solvency_view_model=solvency_view_model,
)
```

## Database Location

`~/.clearbudget/budget.db` (Windows: `C:\Users\<user>\.clearbudget\budget.db`)

## Testing Strategy

### Domain Layer
- Pure unit tests, no I/O
- Parametrized edge cases
- Hand-written fakes implementing Protocol interfaces

### Application Layer
- Service tests use domain fakes
- No database access

### Infrastructure Layer
- Real SQLite via `tmp_path` fixture — no mocking
- Schema created fresh per test

### UI Layer
- ViewModel tests with mocked `BudgetService`
- No widget rendering

### Structural Tests
- `test_layering_rules.py` - AST-based forbidden import enforcement
- `test_loc_limits.py` - No file > 400 LOC

## Code Quality Standards

- **Black** 88-char line length
- **Flake8** no violations
- **100% test coverage** (`pytest --cov-fail-under=100`) excluding UI, interfaces, main, build scripts
- **No magic numbers** — all domain values derive from data, config, or named constants

## Design Principles

**Dependency direction**: always inward. UI → Application → Domain ← Infrastructure.

**No magic numbers**: no hardcoded financial amounts, thresholds, day numbers, or limits in logic. All such values derive from data or named constants defined at the appropriate layer.

**Immutable value objects**: `Amount`, `YearMonth`, `SolvencyResult`, `CardMonthlyState` — all frozen dataclasses. Mutation creates new instances.

**Signed balance**: projected balances returned as `int` pence (not `Amount`) wherever negative values are valid, avoiding `InvalidAmountError` from `Amount.__post_init__`.
