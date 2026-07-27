# Clear Budget Architecture

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
  - `start_ym`, `end_ym` - active month range; `end_ym` is the final month a bill
    appears (set in the dialog for a subscription's last payment or by the
    history-safe delete to end a bill from the viewed month onward)
  - `skipped_for_month: bool` - per-month skip flag (joined from `bill_month_skips`)
  - `has_month_override: bool` - per-month override flag (joined from `bill_month_overrides`)
  - `paid_for_month: bool` - per-month paid flag; excludes the bill from "still due"
    totals and the projected balance for the rest of that month
  - `is_active_in_month(year_month)` - checks date range

- `IncomeSource` - Recurring income (salary, benefits)
  - `name`, `amount`, `is_reliable` (for forward projections)
  - `is_month_only: bool` - one-off "this month only" entry not tied to a template
  - `skipped_for_month` / `has_month_override` / `received_for_month` - same
    per-month machinery as `Bill`

- `CreditCard` - Credit card tracking
  - `id`, `name`, `credit_limit`, `current_balance_used`
  - `interest_rate_apr` (nullable), `payment_due_day` (1-31)
  - `card_expiry_month` (1-12, nullable), `card_expiry_year` (nullable)
  - `minimum_payment_pence` (nullable), `minimum_payment_percent` (nullable)
  - `active` (soft-delete flag, 1 or 0)
  - `balance_applied_year` / `balance_applied_month` / `balance_applied_day` - the
    date `current_balance_used` is accurate as-of. A `day` marks a mid-month manual
    entry (balance as-of that day); `day = None` marks a whole-month fold. The
    same-month stamp also makes the elapsed-date fold skip a freshly entered figure
    rather than overwrite it
  - `current_balance_used` is stored verbatim: exactly the figure the user enters,
    which is their balance as-of `balance_applied_day`. "Current Balance" and "Used"
    are the same number. The start-of-month opening the projection needs is derived
    on the fly (see `_card_live_projection.anchored_month_opening_pence`); nothing is
    transformed at rest
  - `scheduled_limit_changes` - upcoming dated changes to the credit limit (any
    number over time, sorted by effective date). The effective limit for any date
    is derived on the fly (see `services.credit_limit_schedule`); once a change's
    date passes it folds into `credit_limit` and is dropped
  - Properties: `available`, `utilization_percent`

- `MonthBill` - Bill instantiated for a specific month
- `MonthIncome` - Income for a specific month

**Value Objects** (frozen, immutable):
- `Amount(pence: int)` - Non-negative currency; `__str__` uses `get_symbol()` from `shared.currency`
- `YearMonth(year, month)` - Date validation with arithmetic
- `SolvencyResult` - Outcome of solvency calculation
- `CardExhaustionWarning` - Credit card exhaustion analysis
- `CreditLimitChange(effective_year, effective_month, effective_day, new_limit)` -
  one scheduled credit-limit change; validates its date is a real calendar date

**Domain Services**:
- `SolvencyCalculatorService.calculate()` - Computes balance, deficit, forward shortfall
- `CardExhaustionService.analyse()` - Months until card maxes out
- `BankCashflowService`:
  - `find_first_negative_day()` - Detects overdraft date
  - `project_month(starting_balance_pence, events, overdraft_limit_pence)` -
    day-by-day simulation returning `MonthCashflowProjection`
    (opening/closing/min balance, day of min balance, first negative day,
    overdraft-exceeded day)
  - `MonthCashflowProjection.overdraft_severity(overdraft_limit_pence)` ->
    `"none" | "amber" | "red"`
  - `estimate_daily_overdraft_interest_pence(overdrawn_pence, apr_basis_points)` -
    daily interest estimate from APR stored in basis points
- `_prorating.py` - shared pro-rating helpers (`days_in_month`,
  `prorate_remaining_pence`) used by live card projection and balance projection
- `CardMonthlyCalculator.calculate_card_monthly_state()` - Per-card monthly cashflow
  - Inputs: card, opening balance pence, bills list
  - Computes charges, payment received, interest, closing balance, minimum payment
  - Returns `CardMonthlyState` frozen dataclass
- `_card_live_projection.py` - live pro-rated balance: undated bills accrue evenly
  across the elapsed days of the month (rounded up), dated bills count fully once
  their due day has passed
  - `month_to_date_net_pence()` - signed charges-minus-payments accrued so far this
    month; the shared core of the live balance (live = `max(0, opening + net)`)
  - `anchored_month_opening_pence()` - the start-of-month opening derived on the fly
    from a verbatim `current_balance_used` and its `balance_applied_day` anchor. For
    the anchor month it backs out the pre-anchor net (the part of the entered figure
    already posted this month); for any other month, or a card with no day anchor, it
    returns the stored value unchanged. This is what lets "Used" equal exactly what
    you typed while the projection and solvency stay correctly anchored
- `credit_limit_schedule.py` - effective credit limit over a card's scheduled
  changes:
  - `effective_credit_limit_pence(card, as_of)` - the latest change on or before
    `as_of`, else the current `credit_limit`; same-day ties resolve to the last
    entered
  - `month_end_effective_limit_pence(card, year, month)` - the limit at a month's
    end, used by the projection strip and the per-month available-headroom colours

### Application Layer

**Orchestration** - Coordinates domain layer, defines cross-boundary DTOs.

**BudgetService** (main orchestrator) - frozen dataclass (`slots=True`) composed of
focused mixins to stay under the 400-LOC-per-file limit:
- `BillOperationsMixin` (`_bill_operations.py`) - bill CRUD, per-month
  skip/override/paid and `end_bill` (history-safe delete: sets the bill's end
  month so earlier and archived months keep it)
- `IncomeOperationsMixin` (`_income_operations.py`) - income CRUD, per-month
  skip/override/received, "this month only" extras
- `OverdraftOperationsMixin` (`_overdraft_operations.py`) - overdraft facility
  settings, `get_month_cashflow_projection()` and `first_overdrawn_month()`
  (the runway: first future month to dip into the red, delegating to
  `_overdraft_projection.py`)
- `CardOperationsMixin` (`_card_operations.py`) - credit-card pass-throughs and
  folds (card monthly states/projections, live balance, as-of-today balance
  save, elapsed-date and limit-change folds)
- `BalanceApplicationMixin` (`_balance_application.py`) - same-day
  `apply_bill_to_balance_now` / `apply_income_to_balance_now` plus the
  `balance_applied` log helpers; deleting a bill or income (or ending a bill
  from a month onward) reverses its logged applications, and a manual balance
  entry clears the log because the typed figure supersedes them
- `GraphSeriesMixin` (`_month_graph_series.py`) - month graph data:
  `get_bank_graph_series` (day-end projected bank balance across the viewed
  month, anchored through today's stored balance for the current month) and
  `get_card_graph_series` (one day-end balance series per active card),
  reusing the same projection day conventions as the rest of the app

Key methods:
- `get_month_summary(year_month)` → `MonthSummary`
- `calculate_solvency(year_month)` → `SolvencyReport`
- `calculate_solvency_from_summary(year_month, month_summary)` → `SolvencyReport`
- `get_card_monthly_states(year_month)` → `list[CardMonthlyState]`
- `get_card_projection_months(start_month, n_months)` → `list[list[CardMonthlyState]]`
- `save_credit_card_today_balance(card, today_balance, is_new)` → `int` - persists a
  card from the as-of-today balance the user entered, stored verbatim and stamped with
  today's date as its `balance_applied` anchor. "Used" therefore equals exactly what
  was entered; the start-of-month opening is derived on the fly where the projection
  needs it (`anchored_month_opening_pence`), and the same-month stamp makes the
  elapsed-date fold skip the freshly entered figure rather than overwrite it
- `set_credit_limit_changes(card_id, changes)` - replace a card's scheduled limit
  changes (the dialog manages the list and persists it whole on save)
- `apply_elapsed_limit_changes(today=None)` - fold each card's elapsed scheduled
  limit changes into its current limit, keeping only the still-upcoming ones; run at
  launch alongside `update_card_balances_for_elapsed_dates`
- `skip_bill_for_month(bill_id, year_month)` / `unskip_bill_for_month(bill_id, year_month)`
- `delete_bill_month_override(bill_id, year_month)`
- `get_projected_month_end_balance_pence(year_month)` → `int` (signed)
- `get_bank_balance()` / `set_bank_balance(amount)` - the stored balance is
  stamped with the date it was set (`bank_balance_day` plus the full
  `bank_balance_date`), the baseline the elapsed fold advances from
- `apply_elapsed_bank_transactions(today=None)` → `int` (`_bank_transaction_fold.py`) -
  applies every dated bank bill/income that fell due after the balance baseline
  to the stored balance (local-midnight semantics), marks each item paid or
  received so no projection counts it twice, then advances the baseline to
  today; run at launch and re-run by the MainWindow midnight timer; a due day
  beyond a short month's end is applied on its last day; card bills are left to
  the card fold
- `adjust_bank_balance(delta_pence)` - signed delta to the stored balance,
  stamped as-of today (backs the same-day "update balance now?" prompt when an
  item dated today is added)
- `get_overdraft_limit()` / `set_overdraft_limit(amount)` - overdraft facility limit
- `get_overdraft_apr_basis_points()` / `set_overdraft_apr_basis_points(basis_points)` -
  overdraft APR, stored as basis points (1bp = 0.01%)
- `get_month_cashflow_projection(year_month, summary)` → `MonthCashflowProjection` -
  drives the Monthly Budget mid-month overdraft warning
- `first_overdrawn_month(from_year_month, from_balance_pence)` → `YearMonth | None` -
  first future month whose day-by-day projection dips below zero (a mid-month dip
  counts even when the month closes positive); drives the Solvency runway warning
  and the "overdrawn in <month>" escalation
- `end_bill(bill_id, last_active_month)` - history-safe delete: set the bill's end
  month, leaving every earlier month (and archived snapshots) untouched
- `reset_all_data()` - wipes all user budget data (New Budget feature)
- `get_recorded_months()` → `list[YearMonth]` - months already snapshotted into the
  archive (drives the Archive tab)
- `archive_month(year_month)` - snapshot one month's generated bills and income into
  `months` / `month_bills` / `month_income` (idempotent; the internal archiving
  primitive)
- `auto_archive_elapsed_months(current_month)` - archiving is automatic, never manual:
  run at launch (alongside `apply_elapsed_limit_changes`), it archives every elapsed
  month up to the live month, filling any gap from the earliest recorded month so a
  month is captured the moment it ends even across several missed launches

**DTOs**:
- `MonthSummary` - `year_month`, `total_income`, `total_bills`, `bank_bills`, `balance`, `bills`, `all_bills`, `income_sources`, `all_income_sources`
- `SolvencyReport` - `year_month`, `balance_pence: int` (signed), `deficit`, `buffer`, `forward_shortfall`, `is_solvent`, `first_negative_day`
- `GraphSeries` - `label`, `values` (one signed pence value per day of month)

### Infrastructure Layer

**Per-user database** (`~/.clearbudget/budget_<username>.db`):
- `Database(db_path)` - SQLite connection and schema management (the DDL and
  migrations live in `_schema.py`, split out for the LOC limit)
- Schema - 17 application tables (plus SQLite's internal `sqlite_sequence`):
  1. `payment_methods` - id=1 is "Bank Account"
  2. `bills` - templates; includes `target_card_id` (migration). Start months
     are normalised to 2000-01 except one-off bills (start == end), which stay
     scoped to their month; the retired `one_time` category is recategorised
     to `discretionary` (both are idempotent launch migrations)
  3. `income_sources`
  4. `months` - one row per archived month (written by auto-archive at launch)
  5. `month_bills` - archived per-month bill snapshot
  6. `month_income` - archived per-month income snapshot
  7. `credit_cards` - includes `minimum_payment_percent` (migration)
  8. `settings` - key/value store (`bank_balance`, `bank_balance_day`,
     `bank_balance_date` (the fold baseline; legacy databases without it fall
     back to `bank_balance_day`), `currency`,
     `overdraft_limit`, `overdraft_apr_bp`)
  9. `bill_month_overrides` - per-month bill amount/day override (`day_of_month` is a migration)
  10. `bill_month_skips` - per-month bill exclusion
  11. `bill_month_paid` - per-month bill "paid" flag (excludes it from "still due")
  12. `income_month_overrides` - per-month income amount override
  13. `income_month_skips` - per-month income exclusion
  14. `income_month_received` - per-month income "received" flag
  15. `income_month_extras` - "this month only" one-off income, not tied to a template
  16. `credit_limit_changes` - scheduled dated credit-limit changes (one row per
      change; no uniqueness, so a card may have any number over time)
  17. `balance_applied` - log of amounts the app applied to the bank balance
      automatically (midnight fold or same-day prompt), one signed row per item
      per month; deleting an item reverses its rows, a manual balance entry
      clears the log

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
- `create_user(username, password, is_admin)` → `(User, recovery_code)` - hashes
  password and recovery code with bcrypt. Only the first-ever user is created with
  `is_admin=True`; all subsequent accounts (login screen "Create Account..." or
  admin "Add User") are non-admin
- `import_viewer_account(...)` - creates or refreshes a read-only (`is_read_only=True`)
  account from an imported viewer package
- `change_password(username, new_password)`
- `delete_user(user_id)`
- `get_all_users()` → `list[User]`
- `close()`

**`User`** model (`clear_budget/auth/models.py`):
- `id`, `username`, `is_admin`, `is_read_only` (default `False`)

### Reporting (`clear_budget/application/reporting/`)

Pure string building for the HTML exports: no Qt, no file access, no clock, so
it is all under the coverage gate and testable without a QApplication.

- `curve.py` - the monotone cubic (Fritsch-Carlson) curve maths. It lives here
  rather than beside the widget because BOTH the on-screen chart and the exported
  SVG need it, and the UI layer is not something the application layer may import
- `chart_svg.py` - the bar and line charts as inline SVG, following the same rules
  as `_line_bar_chart.py` (curve in bar mode only, axis always includes zero, zero
  line only when the range crosses it). The export redraws the series rather than
  screenshotting the widget: vector output stays sharp, needs no image file beside
  the HTML and can be tested as a string. Fixed DARK palette mirroring the app's
  `DARK` / `SERIES_DARK` / `CURVE_DARK` tokens (mirrored, not imported, because the
  application layer may not depend on the UI). Fixed rather than following the
  active theme, so an export does not change appearance depending on where the
  toggle happened to be. Each chart carries its own background rect so it reads
  correctly wherever it is embedded, and the print rules keep the dark identity
  rather than dropping pale text onto a white page
- `document.py` - the page shell. The stylesheet is inline and the charts are inline
  SVG, so an exported file references nothing outside itself and survives being
  emailed or moved (there is a test asserting no `src`, `href` or `@import`)
- `month_report.py` - one month: both renderings plus the text saying what each is
  for, and the four figures worth pulling out (opening, closing, change, the low
  and its day)
- `projection_report.py` - a month range: a chart of two lines per month, the
  month-end balance and the LOWEST point inside that month, plus a table and a
  traffic light per month. The two lines are the point of it: a month that opens
  and closes in credit can still bounce a payment mid-month, and a report drawn
  from closing balances alone would show that month as healthy

`ProjectionMonth` (`application/dto/projection_month.py`) carries one month's
figures and derives its own state: red below the agreed overdraft floor, caution
for a dip below zero or a month that ends lower than it started, safe otherwise.
`ProjectionSeriesMixin.get_projection_months` builds them by running the SAME
day-by-day bank projection the month graph draws over each month in the range, so
the report and the graph can never disagree about a month they both cover (there
is a test asserting exactly that).

The opening balance comes from `GraphSeriesMixin.get_bank_month_opening_pence`,
which is the value the graph itself starts each month from. That method exists
because the two were computed separately at first and DRIFTED: for the current
month the graph anchors on the recorded bank balance wound back over what has
already been applied, while `get_projected_starting_balance_pence` returns
something else, so the exported table showed an opening that did not add up to
its own closing balance and read as unrelated to the user's money. With one
source, `opening + net == close` holds for every row and each month opens where
the previous one closed, which is what makes the report checkable against a real
bank statement. Both identities are tested.

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
- `build_centered_nav_header(...)` - the shared month/year navigation tray used
  by all four tabs (bordered, centred, hoisted above the scroll area by
  `ScrollableTab`). `apply_nav_label_color` / `_nav_label_style` recolour the
  label; the colour is each month's OWN within-month solvency health (current
  month from its live balance, a future month from its Forward Projection),
  computed once by the Solvency panel and broadcast to every tab via
  `SolvencyPanel.month_label_color_changed` so no tab can disagree. A month is
  red only when its own balance breaches the overdraft floor (below zero with no
  facility, or beyond an agreed facility); dipping into an agreed facility but
  staying within it is amber. A looming overdraft in a later month stays a
  banner warning and never colours the earlier month's title

**`ui_paths.default_downloads_dir()`** (`clear_budget/ui/ui_paths.py`):
- Cross-platform Downloads folder via `QStandardPaths.DownloadLocation`, falling
  back to `Path.home()`. Used as the default directory for all file dialogs
  (Export/Import Database, Export/Import Viewer Package).

**`db_validation`** (`clear_budget/shared/db_validation.py`):
- `REQUIRED_SCHEMA` + `validate_db(path)` - confirms an imported file is a genuine
  ClearBudget database (all required tables and columns present) before any
  Import Database write touches the active database.

**`resources`** (`clear_budget/shared/resources.py`):
- Runtime asset discovery for packaged builds: locates the app icon, the Qt
  window/taskbar icon, and the splash image across PyInstaller onefile
  (`sys._MEIPASS`), onedir (`_internal/`), beside-the-executable, dev repo layout,
  and the working directory, with `.ico` preferred and `.png` fallbacks. Keeps
  icon and splash loading robust however the app was packaged.

### UI Layer

**ViewModels**:
- `MonthViewModel` - month state, signals: `month_changed`, `month_summary_updated`
- `SolvencyViewModel` - signals: `solvency_updated`, `danger_warning_triggered`
  - `set_month()` fetches new month summary before refreshing
  - `update_month_summary()` called after balance edits via `month_summary_updated`

**Views**:
- `MonthView` - bill/income tables with inline editing; balance display adapts
  to current vs future month; composed of mixins (builders, table, edit, delete,
  apply-prompt) to stay under the LOC limit
- `SolvencyPanel` - overdraft alert, mid-month alert, card bars, forward projection
- `CreditCardView` - card CRUD, month navigation, 6-month projection strip
- `ArchiveView` - historical month summaries by year; year navigation

**Widgets**:
- `LoginDialog` - username/password form; grid layout with "Forgot password?"
  (opens `ResetPasswordDialog`) and Sign In on one row, "Import Viewer Package..."
  (opens the viewer-package import flow) and "Create Account..." (opens
  `CreateUserDialog`, non-admin) on the row below
- `ResetPasswordDialog` - username + recovery code + new password; distinct error for unknown username vs wrong code
- `CreateUserDialog` - new user form (first-run wizard, login screen, or admin
  "Add User"); `is_first_user=True` is the only path that creates an admin account;
  includes `RecoveryCodeDialog` on success
- `RecoveryCodeDialog` - displays one-time recovery code; X button disabled; clipboard copy button; checkbox gate before OK activates
- `UserManagementDialog` - admin-only; lists users, Add User, Delete Selected
  (disabled when own row selected); deleting a user always deletes their budget
  data file too (double confirmation)
- `CurrencyDialog` - combobox of 25 currencies; opened via File > Preferences
- `BankAccountSettingsDialog` - configure overdraft facility limit and APR; opened
  via File > Bank Account Settings
- `ExportViewerPackageDialog` - admin: bundle a snapshot of the budget DB into a zip
  for a read-only viewer account
- `_viewer_package_import_flow.py` - shared import flow used by both the login
  screen and File > Import Read-Only Viewer Package; raises `UsernameClashError`
  (with `existing_is_viewer`) if the package's username collides with a real account
- `BillDialog` - add/edit bill; "This month only" on Add creates a one-off
  scoped to exactly the viewed month (start == end), on Edit it stores a
  per-month override; optional end-month control (greyed while one-off is
  ticked, since the ending is implied)
- `CreditCardDialog` - add/edit credit card
- `IncomeDialog` - add/edit income source; "this month only" checkbox with
  contextual status text
- `BalanceDialog` - edit current bank balance; opens with the figure focused
  and selected for immediate overtype
- `ArchiveDetailDialog` - drill-down for a single archived month
- `HowItWorksDialog` - Help menu explanation of pro-rating, balances, archiving
- `AboutDialog` / `LicenceDialog` - app info and LGPL-3.0 text
- `ScrollableTab` - wraps any view in `QScrollArea` with scroll indicator
  buttons; also hoists the view's `nav_header` (the shared, centred month/year
  navigation tray) above the scroll area and zeroes the content's top margin so
  the tray stays full-width and centred on every tab
- `_preferences_flow.py` / `_bank_account_settings_flow.py` - dialog-orchestration
  helpers extracted from `MainWindow` to stay under the LOC limit
- `_main_window_menus.py` (`MainWindowMenuMixin`) - status-bar and File/Users/Help
  menu construction, extracted from `MainWindow` to stay under the LOC limit
- `_month_view_builders.py` (`MonthViewBuilderMixin`) - builds the `MonthView`
  sections (header, tables, buttons); the month nav tray carries only Previous/Next
  now that archiving is automatic (no manual "Archive Month" button)
- `_month_view_edit_mixin.py` (`MonthViewEditMixin`) - inline cell edits and
  the active/skip/paid/received checkbox handlers
- `_month_view_delete_mixin.py` (`MonthViewDeleteMixin`) - the bill
  (stop-from-month vs delete-entirely) and income delete confirmation flows
- `_month_view_apply_prompt.py` (`MonthViewApplyPromptMixin`) - the "update
  balance now?" offer for an item added dated today or edited to today's date
  (dialog or inline); fires only on a genuine transition to today and skips
  items already paid, received or skipped
- `MonthGraphDialog` / `_line_bar_chart.py` (`LineBarChart`) - the month graph
  opened by the nav-tray icon button on Monthly Budget (bank balance by day)
  and Credit Cards (one series per card, with a legend); a pilot button
  toggles bar vs line rendering, drawn with QPainter (no chart dependency)
  - `_chart_curve.py` - Qt-free curve maths: the day-end totals (one curve
    however many series are plotted, so with a single series it IS that series)
    plus the inflection days where direction changes. Tested without a
    QApplication in `tests/ui_logic/test_chart_curve.py`, like the solvency
    colour rules
  - Bar mode overlays that as a smooth curve FOLLOWING the data, in a `curve`
    colour held outside the series palette so it never reads as one more
    series. Monotone cubic interpolation (Fritsch-Carlson): it passes through
    every day's real value and never overshoots a peak or a trough, because a
    curve cutting across a tall day would draw a balance the account never had.
    An averaged trend line was tried first and rejected for exactly that reason
  - Line mode carries no curve. The line already joins every day's real value,
    so a curve through the same points restates the line it sits on. One
    `_curve_shown()` predicate gates the drawing, the legend entry and the
    axis range together, so the axis is never padded for a curve that is not
    there
  - "Export HTML" writes THIS month as a standalone page carrying BOTH renderings
    at once, since a page has room for both where the dialog has room for one. It
    exports whatever is plotted, so it is offered from both pages
  - "Export balance projection" opens `MonthRangeDialog` for a first and last month,
    then writes the BANK balance across that range. It is built only when the caller
    supplies a `budget_service` and an `anchor_month`: Monthly Budget does, Credit
    Cards deliberately does NOT. A bank-balance projection offered from a graph of
    card balances claims to project what is on screen and does not, which is why the
    button is scoped rather than the report being retitled. A card-balance projection
    would be a separate report with its own state rule (headroom against each card's
    limit, not an overdraft floor)
  - Both default to the user's Downloads folder (`ui_paths.default_downloads_dir`,
    Qt's `DownloadLocation` so it is right on Windows, macOS and Linux, falling back
    to home)
  - `_chart_hover.py` (`ChartHoverMixin`) - hovering reads out the balance at
    the point under the pointer (`Day 14: £1,204.55`, prefixed with the series
    label when more than one is plotted). Line mode marks each inflection day
    with a dot to aim at; bar mode treats the whole bar as the target. Hit
    testing uses the chart's own `_geometry()`, so a readout can only land on a
    point that was drawn
- `NeutralDialog` (`neutral_dialog.py`) - dialog base with a neutral start: a
  0x0 focus sink absorbs the initial focus so nothing is highlighted until
  the first Tab or Right (used by the graph, About and Licence dialogs;
  BalanceDialog deliberately keeps its field focused and selected instead)
- `AboutDialog` credits auto-scroll (`_CreditsAutoScroller`) - the About text
  scrolls to the bottom at reading pace, pauses, rewinds faster and repeats;
  any manual interaction stops it

**Keyboard navigation** (`keyboard_nav.py` + `_main_window_nav.py`):
- One application-level `KeyboardNavigator` event filter drives an explicit
  focus ring: menu-bar titles, the tab bar, then the active tab's stops (each
  view's `nav_targets()`), recomputed live so disabled or hidden stops are
  skipped (a disabled Previous at the base month simply drops out)
- Tab and Right step forward, Shift+Tab and Left step back, wrapping at both
  ends; tables keep Up/Down for their rows, the tab strip walks its keyboard
  cursor on Up/Down, text inputs keep their arrows for the caret
- The tab strip's cursor is SEPARATE from its selection (`NavTabBar`). Qt ties
  a `QTabBar`'s focus to its current tab, so a plainly focused bar can only
  ring the tab the user is already on, which is a dead stop. `NavTabBar` holds
  its own cursor instead: the ring enters the strip on the next tab that is
  not current (forward) or the previous one (backward), Up/Down walk it
  wrapping and skipping the current tab, and only Enter or Space commits the
  switch. Stepping the ring therefore never changes which tab is shown. The
  cursor paints the green ring itself, on the pill geometry imported from
  `theme_qss` (`TAB_MARGIN_*`, `TAB_BORDER_PX`, `TAB_RADIUS_PX`) so the ring
  cannot drift from the pill; verified by matching its rendered pixel box
  against the selected pill's border box
- Submenus keep Qt's native horizontal arrows: inside an open menu, Right on
  a submenu item (File > Import / Export) enters it with its first item
  active and Left inside a submenu exits back to the parent item; on plain
  items the arrows still step the ring between menu titles
- Every stop is actionable: a table is ONE stop, never one per read-only
  cell (`setTabKeyNavigation(False)` on all dialog tables, e.g. Manage
  Users, Archive Details); Up/Down walk its rows (arming Delete Selected in
  Manage Users) and Tab or Left/Right leave it in a single press
- Enter equals Space on buttons and checkboxes (main window and dialogs);
  inside modal dialogs the arrows walk the dialog's own tab order
- Neutral start: a 0x0 sink takes the initial focus so nothing is highlighted
  on launch
- Ring colours are three-state, enforced in the QSS: no ring at rest, a green
  ring while an enabled control is hovered or focused, a permanent red ring
  while disabled (hover/focus rules are gated on `:enabled`)
- `_credit_card_view_loaders.py` - builds the per-card panel list (`_build_card_frame`)
  for the Credit Cards tab

**Main Application**:
- `MainWindow` - all tabs in `ScrollableTab`; signals: `logout_requested`, `database_replaced`
  - File menu: New Budget, then "Import / Export" submenu (Export/Import Database,
    and Read-Only Viewer Package export/import, admin only), Preferences, Bank
    Account Settings, Switch User, Exit
  - Users menu (admin only): Manage Users (list, Add User, Delete Selected)
  - Help menu: About, How It Works, View Licence
  - Read-only accounts: window title shows "(Read-only)"; destructive/edit actions
    disabled across all views
- `main.py` - composition root; manages full session lifecycle:
  - `_session_loop()` → login → open DB → load currency → build window → show
  - `_reload_database()` → triggered by `database_replaced`; closes old DB, reopens, loads currency, rebuilds window
  - `_build_main_window()` calls `update_card_balances_for_elapsed_dates()` so any
    fully-elapsed months are folded into card balances at session start, then
    `apply_elapsed_bank_transactions()` so dated bank bills/income that fell due
    while the app was closed are folded into the bank balance; while the app is
    open, a MainWindow timer re-runs the bank fold just after each local midnight
  - Cross-platform single-instance lock: a named kernel mutex on Windows, an
    exclusive `fcntl` advisory lock on a file in `~/.clearbudget/` on macOS and Linux
  - Launch monitor (`launch_screen.init`): resolved ONCE at startup as the screen
    under the mouse pointer, falling back to the primary screen when the pointer is
    on none. Everything the session opens (the login dialog, the main window) is
    placed on that screen, so on a multi-monitor desktop the app appears where it
    was started from instead of on whichever display Windows calls primary. The
    shell passes no launch monitor, so the pointer is a proxy, not an exact answer;
    it is resolved once rather than per window, or a dialog would open on whichever
    monitor the mouse was resting on. `installer/app.py` does the same before
    showing the setup window
  - Screen-aware UI scale (`ui_scale.init`): factor = the LAUNCH screen's available
    height / 1260, capped at 1.5x on tall/4K displays and floored at 0.5x, so the UI
    scales *down* on short displays such as a 13in MacBook, and scales for the
    monitor the app actually opens on
  - Default window geometry: 33% of available width x 92% of available height,
    centred, with absolute minimum floors (860 x 780 logical points, capped to the
    available screen) so the multi-column Bills/Income tables stay readable on small
    laptops. The arithmetic is `_window_geometry.default_window_rect`, kept Qt-free
    and tested in `tests/ui_logic/test_window_geometry.py` because multi-monitor
    placement cannot be exercised on a one-screen machine. It works in virtual-desktop
    coordinates, so a monitor left of or above the primary one (negative x or y) needs
    no special case
  - Centring positions the window's FRAME, not its client rect, and happens AFTER the
    window is shown. `setGeometry()` places the client rect while `move()` places the
    frame, so centring geometry alone leaves the window half a title bar high and half
    a border left (measured: a 23px title bar with 4+4px borders puts it 19px out).
    Worse, a layout can insist on a larger size than the window was given, and a window
    centred before that happens is off centre by however much it grew. `launch_screen.centre`
    therefore places twice: once immediately, so the window is created on the right
    monitor and never jumps across displays, then again on the next event-loop turn
    with the real frame size, before the first paint. A window larger than its screen
    is clamped to that screen's origin so its title bar stays reachable
  - A dialog is given a SIZE, never a position: `setGeometry(100, 100, w, h)` pins a
    dialog to whichever monitor covers virtual-desktop (100, 100) regardless of where
    its parent window is. Sized alone, Qt centres it on its parent

**Theme** (`theme.py` + `theme_tokens.py` + `theme_qss.py` + `_theme_controls.py`):
- Applied at `QApplication` level - covers all windows and dialogs
- Two themes, dark and light, built from ONE stylesheet template
  (`theme_qss.build_qss(tokens)`) fed by semantic token dicts in
  `theme_tokens.py`; the sun/moon toggle at the far right of every nav tray
  switches them at runtime (`theme.toggle_theme`) and the choice persists in
  `~/.clearbudget/ui_settings.json`, applying from the login screen onward
- Dark: background near-black `#0a0a0d`, panels/trays `#242938`, borders
  `#3a4156`, table selection deep blue `#1e3a5f`; light: grey `#f3f4f6`
  background, white panels, slate borders, blue selection
- Buttons royal blue `#3b5bdb` (hover `#4a68d6`, pressed `#2f4bb8`) in both
- Ring colours per theme follow the three-state model (green hover/focus on
  enabled, permanent red on disabled, none at rest); `outline: none` on the
  base rule keeps the ring as the only focus indicator
- Object-name rules for the nav tray, nav graph button, theme toggle and the
  status-bar date label live in `_theme_controls.widget_extras_qss`; the
  semantic label roles (`_theme_labels.label_roles_qss`, named in
  `label_roles.py`) carry every other text colour. A widget takes a role by
  object name instead of an inline stylesheet, which is what lets a live
  theme switch restyle it: `label_roles.set_role` repolishes when a severity
  role changes at runtime (a balance turning from good to danger)
- The primary tabs are pills: unselected are transparent and quiet, the
  selected one takes a panel fill with an accent border and hover gives the
  green ring. There is deliberately NO `QTabBar::tab:selected:focus` rule:
  the green ring belongs to `NavTabBar`'s keyboard cursor, which paints it on
  whichever tab the cursor sits on, and a focus rule on the selected pill
  would put a second green ring on the strip. (If one is ever reinstated, the
  subcontrol must come first: `QTabBar::tab:selected:focus` works while the
  widget-state-first form `QTabBar:focus::tab:selected` is silently ignored by
  Qt.) `MainWindow` sets `tabBar().setDrawBase(False)` because Qt ignores
  drawBase from a stylesheet and would draw a rule under the strip
- Content whose colours are computed in code (card panels, projection cells,
  solvency lines, table row colours) cannot follow the stylesheet, so those
  views expose `restyle()` and `theme.apply_theme` calls it after a switch
- The solvency banner carries its traffic-light state as a Qt property
  (`state="red"` etc.) and the stylesheet supplies the fill per theme, so no
  view holds a banner colour
- Colour literals live ONLY in `theme_tokens.py`: chrome tokens plus two data
  palettes (chart series, solvency states) per theme. Every dark value equals
  the literal it replaced, so the dark theme is unchanged pixel for pixel
  (verified by an offscreen diff); the light values are chosen to pass WCAG AA
  on the light background
- The month-graph chart follows the theme too: `_line_bar_chart` resolves its
  chrome tokens, its series palette AND its curve colour per paint
  (`theme_tokens.series_colours_for` / `curve_colour_for`), so pastels plot on
  the dark canvas and saturated mid-tones on the light one, same hue order
  either way
- Amber/red semantic warning colours (card thresholds, overdraft warnings) are
  theme-independent

## Application Startup Flow

```
main()
  └── QApplication created
  └── apply_theme(app, load_saved_theme())     # persisted theme applied globally
  └── UserStore opened (users.db)
  └── QTimer.singleShot(0, _session_loop)   # deferred; app.exec() must be live first
  └── app.exec()
  └── _session_loop()                        # fires on first event loop tick
        └── _run_login_flow()
              └── first run? → CreateUserDialog(is_first_user=True) → RecoveryCodeDialog
              └── else       → LoginDialog
                    └── Create Account...     → CreateUserDialog(is_first_user=False)
                    └── Import Viewer Package → viewer-package import flow
              └── X button   → app.quit() → process exits
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

## Cross-Platform Support and Packaging

Clear Budget is a single PySide6 codebase that ships as a native package on
Windows, macOS and Linux. The application layers carry no OS-specific logic;
platform differences are isolated to a few well-defined seams:

- **Single-instance lock**: per-OS implementation in `main.py` (named kernel mutex
  on Windows, `fcntl` advisory file lock on macOS and Linux).
- **Data directory**: `Config.app_dir()` is `~/.clearbudget/` on every platform;
  all databases and the lock file live there.
- **File-dialog defaults**: `ui_paths` uses Qt `QStandardPaths`, so dialogs open
  in the correct per-OS location.
- **Runtime assets**: `shared/resources.py` discovers icons and the splash image
  across frozen (PyInstaller) and source layouts.
- **Display scaling**: `ui_scale` adapts the UI to the screen, scaling down on
  small laptops and capping growth on 4K.
- **Conditional dependencies**: Windows-only packages (`pywin32`) are guarded by
  environment markers in the requirements files.

Each platform produces one distributable artefact from this shared codebase:

| Platform | Built by | Produces |
|----------|----------|----------|
| Windows | `buildexe.py` (PyInstaller) then `buildinstaller.py` | `ClearBudgetSetup.exe`, a single-file per-user installer |
| macOS | `builddmg.py` | `clearbudget.dmg` (signed and notarized when Apple credentials are configured) |
| Linux | `build_flatpak.sh` (+ `cleanup_flatpak.sh`) | `clearbudget.flatpak`, on the Freedesktop runtime |

The Windows installer is itself a small PySide6 application under `installer/`
(with its own `cli`, `ops`, `state`, `ui`, and payload-builder modules). It wraps
the PyInstaller bundle into the per-user setup executable and is a build and
distribution tool, kept separate from the runtime application described above.

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
- The suite is Qt-free: fragile widget-level PySide6 tests (which needed a
  `QApplication` and were flaky) have been removed
- Pure UI-layer logic is still covered without Qt under `tests/ui_logic` - e.g.
  the Solvency month-colour rule is exercised by instantiating the colour mixins
  directly (no widgets)
- The UI layer is excluded from the coverage gate (see `.coveragerc`)

### Structural Tests
- `test_layering_rules.py` - AST-based forbidden import enforcement
- `test_loc_limits.py` - No file > 400 LOC
- `test_auth_structure.py` - Auth layer structure validation

## Code Quality Standards

- **Black** 88-char line length
- **Flake8** no violations
- **100% test coverage** (`pytest -v --cov`, gated at `--cov-fail-under=100`) excluding
  UI, interfaces, main, build scripts. The suite is Qt-free and runs clean in one
  process
- **No mock libraries** - real implementations and hand-written fakes only
- **No magic numbers** - all domain values derive from data, config, or named constants

## Design Principles

**Dependency direction**: always inward. UI → Application → Domain ← Infrastructure.

**No magic numbers**: no hardcoded financial amounts, thresholds, day numbers, or limits in logic.

**Immutable value objects**: `Amount`, `YearMonth`, `SolvencyResult`, `CardMonthlyState` - all frozen dataclasses.

**Signed balance**: projected balances returned as `int` pence (not `Amount`) wherever negative values are valid.

**Per-user isolation**: each user has a completely separate budget database. No cross-user data access is possible.

**Session lifecycle signals**: `logout_requested` and `database_replaced` on `MainWindow` drive all session transitions without tight coupling between UI and `main.py`.
