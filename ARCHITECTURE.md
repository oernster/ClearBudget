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
  - `is_active_in_month(year_month)` - checks date range
  
- `IncomeSource` - Recurring income (salary, benefits)
  - `name`, `amount`, `is_reliable` (for forward projections)
  
- `CreditCard` - Credit card tracking
  - `id`, `name`, `credit_limit`, `current_balance_used`
  - `interest_rate_apr` (nullable), `payment_due_day` (1-31, auto-adjusted to working day)
  - `card_expiry_month` (1-12, nullable), `card_expiry_year` (nullable)
  - `minimum_payment_pence` (nullable), `active` (soft-delete flag, 1 or 0)
  - Properties: `available`, `utilization_percent`
  
- `MonthBill` - Bill instantiated for a specific month
  - References bill template, can override amount
  - `is_ad_hoc` flag for one-off bills
  
- `MonthIncome` - Income for a specific month
  - References source, can override amount
  - `is_reliable` flag for projections

**Value Objects** (frozen, immutable):
- `Amount(pence: int)` - Non-negative currency
  - Arithmetic: `+`, comparison operators
  - `from_pounds(float)`, `.pounds` property
  - `zero()`, `min()`, `max()`
  
- `YearMonth(year, month)` - Date validation (YYYY-MM)
  - Arithmetic: `next_month()`, `previous_month()`, `add_months(n)`
  - Comparison: `<`, `>`, `==`
  
- `SolvencyResult` - Outcome of solvency calculation
  - `balance: int` (pence, can be negative)
  - `deficit: Amount` (absolute shortfall)
  - `buffer: Amount` (safety cushion)
  - `forward_shortfall: Amount` (next 2 months)
  - `desired_acquire: Amount` (total target)
  - Properties: `has_deficit`, `is_solvent`
  
- `CardExhaustionWarning` - Credit card exhaustion analysis
  - `months_until_max: float` (infinity if paying down)
  - `status: str` (danger/warning/ok)
  - Properties: `is_danger`, `is_warning`

**Interfaces** (Protocol abstractions):
```python
class BillRepository(Protocol):
    def list_active_for_month(*, year_month: YearMonth) -> list[Bill]
    def get_by_id(*, bill_id: int) -> Bill | None
    def add(*, bill: Bill) -> Bill
    def update(*, bill: Bill) -> Bill
    def deactivate(*, bill_id: int) -> None

class IncomeSourceRepository(Protocol):
    def list_active() -> list[IncomeSource]
    def list_reliable() -> list[IncomeSource]
    def get_by_id(*, income_id: int) -> IncomeSource | None
    def add(*, source: IncomeSource) -> IncomeSource
    def update(*, source: IncomeSource) -> IncomeSource

class PaymentMethodRepository(Protocol):
    def get_all_credit_cards(*, include_inactive: bool = False) -> list[CreditCard]
    def get_credit_card_by_id(*, card_id: int) -> CreditCard | None
    def add_credit_card(*, card: CreditCard) -> CreditCard
    def update_credit_card(*, card: CreditCard) -> CreditCard
    def deactivate_credit_card(*, card_id: int) -> None
    def update_credit_card_balance(*, card_id: int, balance_used: int) -> None
```

**Services** (static methods, no state, no I/O):
- `SolvencyCalculatorService.calculate()` - Computes balance, deficit, forward shortfall
  - Inputs: month bills/income, next 2 months bills/income (from repositories)
  - Output: `SolvencyResult`
  
- `CardExhaustionService.analyze()` - Calculates months until card maxes out
  - Inputs: card limit, balance, monthly charge/payment
  - Output: `CardExhaustionWarning`
  
- `BankCashflowService.find_first_negative_day()` - Detects overdraft date
  - Inputs: starting balance, daily events (deposits/charges)
  - Output: day number or None

- `WorkingDayCalculatorService.adjust_to_working_day()` - Adjusts payment dates to working days
  - Inputs: day of month, year, month
  - Output: adjusted day (preceding working day if weekend/UK holiday)
  - Used for credit card payment due date calculations

### Application Layer

**Orchestration** - Coordinates domain layer, defines cross-boundary DTOs.

**Services**:
- `BudgetService` - Main orchestrator
  - `get_month_summary(year_month)` → Fetches bills/income, returns `MonthSummary`
  - `calculate_solvency(year_month)` → Calls `SolvencyCalculatorService`, returns `SolvencyReport`
  - Dependencies: `bill_repo`, `income_repo`, `month_generator`, domain services
  
- `MonthGenerator` - Creates `MonthBill` and `MonthIncome` from templates
  - `generate_month_bills(year_month)` → Expands bill templates for the month
  - `generate_month_income(year_month)` → Applies income for the month
  - Respects bill date ranges, expiring bills, one-time bills

**DTOs** (Data Transfer Objects):
- `MonthSummary` - Crosses application boundary
  - `year_month`, `total_income`, `total_bills`, `balance` (non-negative `Amount`)
  - Displays what user sees each month
  
- `SolvencyReport` - Detailed solvency analysis
  - `year_month`, `balance_pence: int` (can be negative), `deficit`, `buffer`, `forward_shortfall`, `desired_acquire`
  - `is_solvent: bool`, `first_negative_day: int | None`

### Infrastructure Layer

**Concrete Implementations** - SQLite persistence, repository implementations.

**Database**:
- `Database(db_path)` - SQLite connection and schema management
  - `connect()` - Opens SQLite connection
  - `create_schema()` - Creates 7 tables on first run:
    1. `payment_methods` - Payment method types (id=1 is "Bank Account", others are credit cards)
    2. `bills` - Bill templates with `payment_method_id` foreign key
    3. `income_sources` - Income templates
    4. `months` - Month tracking
    5. `month_bills` - Instantiated bills per month
    6. `month_income` - Instantiated income per month
    7. `credit_cards` - Card details with separate id namespace (2+, linked to payment_methods)
  
  - `get_or_create_month(year_month)` → Returns month_id

**Repositories**:
- `SQLiteBillRepository(database)` - Implements `BillRepository`
  - `list_active_for_month()` - Complex SQL date range logic with parentheses
  - `add()`, `update()`, `deactivate()`, `get_by_id()`
  
- `SQLiteIncomeSourceRepository(database)` - Implements `IncomeSourceRepository`
  - `list_active()`, `list_reliable()`
  - `add()`, `update()`, `get_by_id()`

- `SQLitePaymentMethodRepository(database)` - Implements `PaymentMethodRepository`
  - `get_all_credit_cards()` - Returns all active or all cards (with soft-delete support)
  - `get_credit_card_by_id()` - Returns single card by id or None
  - `add_credit_card()` - Inserts into both payment_methods and credit_cards tables
  - `update_credit_card()` - Updates credit_cards table
  - `deactivate_credit_card()` - Soft-delete by setting active=0
  - `update_credit_card_balance()` - Updates current_balance_used_pence

**Testing**:
- All infrastructure tests use **real SQLite** via `tmp_path` fixture
- No mocking of database layer
- Schema created fresh for each test

### UI Layer

**Presentation** - PySide6 dark theme, ViewModels, signal/slot communication.

**ViewModels** (QObject subclasses):
- `MonthViewModel` - Manages month state
  - `current_month: YearMonth`
  - `month_summary: MonthSummary | None`
  - Signals: `month_changed(YearMonth)`, `month_summary_updated(MonthSummary)`
  - Methods: `set_month()`, `next_month()`, `previous_month()`, `refresh_month_summary()`
  
- `SolvencyViewModel` - Manages solvency state
  - `current_month: YearMonth`
  - `solvency_report: SolvencyReport | None`
  - Signals: `solvency_updated(SolvencyReport)`, `danger_warning_triggered(str)`
  - Methods: `set_month()`, `refresh_solvency()`, `get_status_color()`

**Views** (QWidget subclasses):
- `MonthView` - Bill table with month navigation
  - `QTableWidget` for bills (Name, Category, Amount, Type, Due, Payment Method, Active)
  - Connected to `MonthViewModel`
  - Payment method column shows "Bank" or credit card name (lookup by id)
  
- `SolvencyPanel` - Financial health display
  - Balance label, status, deficit warning
  - Forward projection, progress bar
  - Color-coded: green (solvent), red (deficit)
  
- `CreditCardView` - Card management and exhaustion tracking
  - Card table (Name, Limit, Used, Available, % Util, Due Day, Interest %, Min Pmt, Expiry, Status, Active)
  - Add/Edit/Delete buttons for card management
  - Status colors: danger (red 80%+), warning (yellow 50-80%), ok (green <50%)
  - Soft-delete support (delete button deactivates, hidden cards not shown)
  
- `ArchiveView` - Historical month browsing
  - Month history table
  - Export CSV button

**Widgets** (Dialog subclasses):
- `BillDialog` - Create/edit bills with dynamic payment method dropdown
  - Payment method combo populated from: Bank Account (id=1), all active credit cards
  - Default selected: Bank Account
  - Combo uses `setItemData()` to store payment_method_id
  - `load_bill()` performs name-based lookup for reliability
  
- `CreditCardDialog` - Create/edit credit cards
  - Fields: name, credit limit, interest rate, payment due day, expiry month/year, minimum payment, active flag
  - Validation: name required, limit > 0, due day 1-31
  - Used by CreditCardView for Add/Edit operations

**Main Application**:
- `MainWindow(QMainWindow)` - Tab-based layout
  - Tabs: Month Budget, Solvency, Credit Cards, Archive
  - Wires ViewModels to Views
  - Applies dark theme stylesheet
  
- `main.py` - Composition root (only place importing all layers)
  - Creates database, repositories, services
  - Instantiates ViewModels and payment_method_repo
  - Creates MainWindow and shows
  - Starts Qt event loop

## Dependency Injection

**No container** - Dependencies passed via constructor.

Example:
```python
database = Database(db_path)
database.connect()
database.create_schema()

bill_repo = SQLiteBillRepository(database)
income_repo = SQLiteIncomeSourceRepository(database)
payment_method_repo = SQLitePaymentMethodRepository(database)
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
    budget_service=budget_service,
)
```

All repositories passed to BudgetService via `payment_method_repo` attribute.

## Testing Strategy

### Domain Layer
- **Pure unit tests** - No I/O, deterministic
- **Parametrized edge cases** - Test boundary conditions
- **Hand-written fakes** - Mock repositories implement `Protocol` interfaces

Example:
```python
@dataclass
class FakeBillRepository:
    _bills: list[Bill] = field(default_factory=list)
    
    def list_active_for_month(self, *, year_month: YearMonth) -> list[Bill]:
        return [b for b in self._bills if b.is_active_in_month(year_month)]
```

### Application Layer
- **Service tests** use fakes from domain
- **DTO tests** verify JSON serialization
- **No database access**

### Infrastructure Layer
- **Real SQLite** via `tmp_path` fixture
- **Schema creation** tested per test
- **CRUD operations** verified against actual database

### UI Layer
- **ViewModel tests** with mocked `BudgetService`
- **No widget rendering** - test state and signals
- **Signal/slot verification** via state checks

### Structural Tests
- **AST-based enforcement** of layering rules
- `test_layering_rules.py` - Verifies no forbidden imports
- `test_loc_limits.py` - Ensures no file > 400 LOC

## Code Quality Standards

### Formatting & Linting
- **Black** - 88-char line length
- **Flake8** - No violations
- Extended ignore: `E203, W503` (black compatibility)

### Test Coverage
- **100% coverage** - `pytest --cov-fail-under=100`
- **175 tests** passing
- **541 statements** covered
- Excluded: `ui/`, `interfaces/`, `main.py`, `buildexe.py`, `buildinstaller.py`, `installer/`

### File Size
- **Max 400 LOC** - All files under limit
- Largest: `clear_budget/infrastructure/sqlite/bill_repository.py` (170 lines)
- Enforced by `test_loc_limits.py`

## Design Principles

### SOLID

**S (Single Responsibility)**
- Each class has one reason to change
- Services separated by domain boundary

**O (Open/Closed)**
- Open for extension (new repositories, services)
- Closed for modification (Protocols define contracts)

**L (Liskov Substitution)**
- Repository implementations are interchangeable
- Fakes and SQLite repos both satisfy `Protocol`

**I (Interface Segregation)**
- Protocols are minimal (`BillRepository` vs. monolithic repository)
- UI imports only DTOs, not entities

**D (Dependency Inversion)**
- Application depends on `BillRepository` (Protocol), not `SQLiteBillRepository`
- Enables testing with fakes

### Clean Architecture

**Dependency Direction**: Always inward
- UI → Application
- Application → Domain
- Infrastructure → Domain (implements protocol)
- **Never**: Domain → Application, Domain → UI

**Testability**
- Domain: 100% testable without external dependencies
- Application: 100% testable with fakes
- Infrastructure: Real SQLite testing
- UI: Testable with mocked services

### Value Objects

**Immutable** - Frozen dataclasses prevent accidental mutation
- `Amount(pence: int)` - Currency represented as integers (no floats)
- `YearMonth(year, month)` - Validated date (no invalid months)
- `SolvencyResult` - Outcome data, never changes mid-calculation

**Behavioral** - Encapsulate domain logic
- `Amount` has arithmetic operators (`+`, comparison)
- `YearMonth` has date arithmetic (`next_month()`)
- `SolvencyResult` has computed properties (`is_solvent`)

## Known Patterns

**Payment Method System**:
- Bills store `payment_method_id` (foreign key to payment_methods.id)
- `payment_methods` table has: id, name, type
- Credit cards have separate `credit_cards` table with full details
- ID mapping: payment_methods.id=1 is Bank Account; credit_cards have id=2+ (linked to payment_methods via INSERT to both tables)
- BillDialog populates dropdown dynamically from active credit cards + Bank Account
- MonthView displays payment method name (lookup by ID for display)

**Soft-Delete Pattern**:
- CreditCard entity has `active` flag (1 or 0)
- `deactivate_credit_card()` sets active=0 instead of hard-deleting
- Repositories filter by `active` status when loading
- CreditCardView hides inactive cards by default

**Working Day Adjustment**:
- Payment due dates nominally fixed (e.g., 22nd of month)
- `WorkingDayCalculatorService.adjust_to_working_day()` moves dates to preceding working day if weekend/UK holiday
- Used for solvency calculations and cashflow forecasting

## Future Enhancements

**Phase 7** - (planned)
- Invoice/receipt tracking (attach PDFs)
- Spending analytics (charts, trends)
- Multi-account support (multiple checking accounts)
- Scheduled transactions (recurring bills in calendar view)
- Mobile app (React Native or Flutter)

All future code will follow the same 4-layer architecture and 100% test coverage requirement.
