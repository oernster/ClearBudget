# ClearBudget Architecture

A clean architecture implementation with 4 isolated layers: Domain, Application, Infrastructure, and UI.
An additional Auth layer sits alongside the main layers for user identity and credential management.

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

┌─────────────────────────────────────────────────────────────┐
│       Auth Layer (User Identity - cross-cutting)            │
│    UserStore → users.db   User, UserManagementDialog        │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│       Shared Layer (Config, Currency, Errors)               │
│    Config, Currency, Errors - used by all layers            │
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
- `Amount(pence: int)` - Non-negative currency; `__str__` uses `get_symbol()` from `shared.currency`
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
- `get_card_projection_months(start_month, n_months)` → `list[list[CardMonthlyState]]`
- `skip_bill_for_month(bill_id, year_month)` / `unskip_bill_for_month(bill_id, year_month)`
- `delete_bill_month_override(bill_id, year_month)`
- `get_projected_month_end_balance_pence(year_month)` → `int` (signed)
- `get_bank_balance()` / `set_bank_balance(amount)`
- `reset_all_data()` - wipes all user budget data (New Budget feature)

**DTOs**:
- `MonthSummary` - `year_month`, `total_income`, `total_bills`, `bank_bills`, `balance`, `bills`, `all_bills`, `income_sources`, `all_income_sources`
- `SolvencyReport` - `year_month`, `balance_pence: int` (signed), `deficit`, `buffer`, `forward_shortfall`, `is_solvent`, `first_negative_day`

### Infrastructure Layer

**Per-user database** (`~/.clearbudget/budget_<username>.db`):
- `Database(db_path)` - SQLite connection and schema management
- Schema — 11 tables:
  1. `payment_methods` - id=1 is "Bank Account"
  2. `bills` - templates; includes `target_card_id` (migration)
  3. `income_sources`
  4. `months`
  5. `month_bills`
  6. `month_income`
  7. `credit_cards` - includes `minimum_payment_percent` (migration)
  8. `settings` - key/value store (`bank_balance`, `bank_balance_day`, `currency`)
  9. `bill_month_overrides` - includes `day_of_month` (migration)
  10. `bill_month_skips` - per-month bill exclusion (bill_id, year, month)
  11. `sqlite_sequence`

**Repositories**:
- `SQLiteBillRepository`
  - `list_active_for_month()` - LEFT JOINs `bill_month_skips` and `bill_month_overrides`
  - `skip_for_month` / `unskip_for_month`
  - `hard_delete(bill_id)` - cleans related skips and overrides
- `SQLiteIncomeSourceRepository`
- `SQLitePaymentMethodRepository`
  - `set_card_active(card_id, active)` - soft-delete toggle

### Auth Layer

Separate from budget infrastructure. Manages user identity and credentials.

**Central users database** (`~/.clearbudget/users.db`):
- Single SQLite database shared across all users on the machine
- `users` table: `id`, `username`, `password_hash` (bcrypt), `recovery_code_hash` (bcrypt), `is_admin`

**`UserStore`** (`clear_budget/auth/user_store.py`):
- `has_users()` - drives first-run wizard
- `find_user(username)` → `User | None`
- `verify_password(username, password)` → `User | None`
- `verify_recovery_code(username, code)` → `bool`
- `create_user(username, password, is_admin)` → `User` - hashes password and recovery code with bcrypt
- `change_password(username, new_password)`
- `delete_user(user_id)`
- `get_all_users()` → `list[User]`
- `close()`

**`User`** model (`clear_budget/auth/models.py`):
- `id`, `username`, `is_admin`

### Shared Layer

**`Config`** (`clear_budget/shared/config.py`):
- `Config.default()` → legacy single-user path (`budget.db`) - kept for reference only
- `Config.for_user(username)` → `budget_<safe_username>.db`
- `Config.users_db_path()` → `users.db`
- `Config.app_dir()` → `~/.clearbudget/`

**`Currency`** (`clear_budget/shared/currency.py`):
- `CURRENCIES: list[Currency]` - 25 currencies for English-speaking countries
- `DEFAULT_CURRENCY` - GBP
- `get_symbol()` → active currency symbol (used by `Amount.__str__`)
- `get_currency()` → active `Currency` object
- `set_currency(code)` → activates named currency (falls back to GBP for unknown codes)
- Module-level state: set once per session after loading user's DB settings

**`format_helpers.fmt(amount)`** (`clear_budget/ui/utils/format_helpers.py`):
- `fmt(pence: int)` → `"{symbol}{pence/100:.2f}"`
- `fmt(pounds: float)` → `"{symbol}{pounds:.2f}"`
- Used throughout UI for all inline currency formatting not going through `Amount.__str__`

### UI Layer

**ViewModels**:
- `MonthViewModel` - month state, signals: `month_changed`, `month_summary_updated`
- `SolvencyViewModel` - signals: `solvency_updated`, `danger_warning_triggered`
  - `set_month()` fetches new month summary before refreshing
  - `update_month_summary()` called after balance edits via `month_summary_updated`

**Views**:
- `MonthView` - bill/income tables with inline editing; balance display adapts to current vs future month
- `SolvencyPanel` - overdraft alert, mid-month alert, freedom-to-spend, card bars, forward projection
- `CreditCardView` - card CRUD, month navigation, 6-month projection strip
- `ArchiveView` - historical month summaries by year; year navigation

**Widgets**:
- `LoginDialog` - username/password form; "Forgot password?" link opens `ResetPasswordDialog`
- `ResetPasswordDialog` - username + recovery code + new password; distinct error for unknown username vs wrong code
- `CreateUserDialog` - new user form (first-run wizard or admin add-user); includes `RecoveryCodeDialog` on success
- `RecoveryCodeDialog` - displays one-time recovery code; X button disabled; clipboard copy button; checkbox gate before OK activates
- `UserManagementDialog` - admin-only; lists users; Delete Selected disabled when own row selected
- `CurrencyDialog` - combobox of 25 currencies; opened via File > Preferences
- `BillDialog` - add/edit bill; month-only scope toggle
- `CreditCardDialog` - add/edit credit card
- `IncomeDialog` - add/edit income source
- `BalanceDialog` - edit current bank balance
- `ArchiveDetailDialog` - drill-down for a single archived month
- `AboutDialog` / `LicenceDialog` - app info and LGPL-3.0 text
- `ScrollableTab` - wraps any view in `QScrollArea` with scroll indicator buttons

**Main Application**:
- `MainWindow` - all tabs in `ScrollableTab`; signals: `logout_requested`, `database_replaced`
  - File menu: New Budget, Export Database, Import Database, Preferences, Switch User, Exit
  - Users menu (admin only): Manage Users
  - Help menu: About, View Licence
- `main.py` - composition root; manages full session lifecycle:
  - `_session_loop()` → login → open DB → load currency → build window → show
  - `_reload_database()` → triggered by `database_replaced`; closes old DB, reopens, loads currency, rebuilds window
  - Single-instance mutex prevents duplicate launches
  - UI scale capped at 1.5x for 4K monitors

**Theme** (`dark_theme.py`):
- Applied at `QApplication` level - covers all windows and dialogs
- `QPushButton` hover/press: orange `#f59e0b` 2px border
- `QTabBar::tab` hover: orange `#f59e0b`; selected: purple `#a78bfa`
- `QMenuBar` / `QMenu` hover: orange `#f59e0b`

## Application Startup Flow

```
main()
  └── QApplication created
  └── app.setStyleSheet(get_dark_qss())        # theme applied globally
  └── UserStore opened (users.db)
  └── _session_loop()
        └── _run_login_flow()
              └── first run? → CreateUserDialog → RecoveryCodeDialog
              └── else       → LoginDialog
        └── _open_user_database(username)       # budget_<username>.db
        └── _load_currency(database)            # set_currency() from settings
        └── _build_main_window(database, user, user_store)
        └── _show_window(user, window)
              └── window.database_replaced → _reload_database()
              └── window.logout_requested  → _session_loop()
```

## Dependency Injection

No container - dependencies passed via constructor.

```python
database = Database(config.db_path)        # Config.for_user(username)
database.connect()
database.create_schema()

bill_repo             = SQLiteBillRepository(database.conn)
income_repo           = SQLiteIncomeSourceRepository(database.conn)
payment_method_repo   = SQLitePaymentMethodRepository(database.conn)
month_generator       = MonthGenerator(bill_repo, income_repo)

budget_service = BudgetService(
    bill_repo=bill_repo,
    income_repo=income_repo,
    payment_method_repo=payment_method_repo,
    month_generator=month_generator,
)

month_view_model    = MonthViewModel(budget_service=budget_service)
solvency_view_model = SolvencyViewModel(budget_service=budget_service)

window = MainWindow(
    month_view_model=month_view_model,
    solvency_view_model=solvency_view_model,
    current_user=user,
    user_store=user_store,
    db_path=database.db_path,
)
```

## Database Locations

| File | Path | Purpose |
|------|------|---------|
| `users.db` | `~/.clearbudget/users.db` | Central user accounts (all users) |
| `budget_<username>.db` | `~/.clearbudget/budget_<username>.db` | Per-user budget data |

Username is sanitised to lowercase alphanumeric + `_-` before use in filename.

## Currency

Currency is stored per-user in the `settings` table (`key='currency'`, `value='GBP'`).
It is loaded from the DB immediately after opening the user session and activates the
module-level symbol in `shared.currency`. `Amount.__str__` and `fmt()` both call
`get_symbol()` at render time, so all displayed values reflect the active currency
without any additional wiring. On currency change (File > Preferences), the new code is
saved to the DB, `set_currency()` is called, and `database_replaced` is emitted to
rebuild the window with updated labels.

## Testing Strategy

### Domain Layer
- Pure unit tests, no I/O
- Parametrized edge cases
- Hand-written fakes implementing Protocol interfaces

### Application Layer
- Service tests use domain fakes
- No database access

### Infrastructure Layer
- Real SQLite via `tmp_path` fixture - no mocking
- Schema created fresh per test

### Auth Layer
- Real SQLite via `tmp_path` fixture
- bcrypt round-trip tested

### Shared Layer
- `test_config.py` - path construction and safe username
- `test_currency.py` - currency registry, `get_symbol`, `set_currency`, reset fixture

### UI Layer
- ViewModel tests with mocked `BudgetService`
- No widget rendering

### Structural Tests
- `test_layering_rules.py` - AST-based forbidden import enforcement
- `test_loc_limits.py` - No file > 400 LOC
- `test_auth_structure.py` - Auth layer structure validation

## Code Quality Standards

- **Black** 88-char line length
- **Flake8** no violations
- **100% test coverage** (`pytest --cov-fail-under=100`) excluding UI, interfaces, main, build scripts
- **No magic numbers** - all domain values derive from data, config, or named constants

## Design Principles

**Dependency direction**: always inward. UI → Application → Domain ← Infrastructure.

**No magic numbers**: no hardcoded financial amounts, thresholds, day numbers, or limits in logic.

**Immutable value objects**: `Amount`, `YearMonth`, `SolvencyResult`, `CardMonthlyState` - all frozen dataclasses.

**Signed balance**: projected balances returned as `int` pence (not `Amount`) wherever negative values are valid.

**Per-user isolation**: each user has a completely separate budget database. No cross-user data access is possible.

**Session lifecycle signals**: `logout_requested` and `database_replaced` on `MainWindow` drive all session transitions without tight coupling between UI and `main.py`.
