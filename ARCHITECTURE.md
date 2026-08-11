# Clear Budget Architecture

A clean architecture implementation with 4 isolated layers: Domain, Application, Infrastructure and UI.
An additional Auth layer sits alongside the main layers for user identity and credential management.

## Invariants

The rules the design turns on. Each one is enforced by a test rather than by
convention, so it is named here with the test that fails when it is broken.
Everything below this section explains how the code satisfies them.

| Invariant | Enforced by |
|-----------|-------------|
| Dependencies point inward: UI → Application → Domain ← Infrastructure. The Domain imports nothing outward, has no I/O and no framework | `tests/structural/test_layering_rules.py` (AST scan for forbidden imports) |
| The auth layer's surface stays where it is declared: identity and credentials never leak into budget infrastructure | `tests/structural/test_auth_structure.py` |
| No source file exceeds 400 lines | `tests/structural/test_loc_limits.py` |
| Only `shared/config.py` derives the real data directory. The suite never resolves it; the installer never so much as names it, so no test and no install can disturb live user data | `tests/structural/test_data_dir_isolation.py` (plus the autouse `CLEARBUDGET_HOME` fixture in `tests/conftest.py`) |
| 100% line AND branch coverage over `clear_budget`, `main` and the Qt-free half of the setup program | `--cov-fail-under=100` with `branch = True` (`.coveragerc`, `pyproject.toml`) |
| An exported report adds up: `opening + net == close` for every month whose Paid/Received flags agree with the calendar. In the anchored month an item actioned early (or missed) moves the close off the totals by exactly that amount, because the series never charges twice what the recorded balance already contains | `tests/application/test_projection_series.py::test_opening_plus_net_equals_the_close` and `::test_a_bill_paid_early_moves_the_anchored_close` |
| The exported report and the on-screen month graph can never disagree about a month they both cover, because both run the same day-by-day projection | `tests/application/test_projection_series.py::test_the_projection_agrees_with_the_month_graph` |
| With ONE deliberate exception: the month in progress opens from the recorded bank balance, not the previous month's projected close. The recorded balance is the only figure in the report that is a fact; the gap is the drift the report exists to expose | `tests/application/test_projection_series.py::test_the_current_month_is_anchored_on_the_recorded_balance` and `::test_months_outside_the_current_one_still_chain_when_today_is_inside` |
| An exported HTML file references nothing outside itself, so it survives being emailed and opens offline | `tests/application/reporting/test_reports.py::test_a_report_references_nothing_outside_itself` |
| User-entered text cannot inject markup into an exported report | `tests/application/reporting/test_reports.py::test_user_text_cannot_inject_markup_into_a_report` |
| Highlight text is teal, never green: green is the ring saying where focus is, not what is selected | `tests/ui_logic/test_highlight_text_colour.py` |
| Money is integer pence everywhere. No financial value is ever a float, so nothing rounds away between what the user typed and what a projection uses | `Amount(pence: int)` is a frozen value object; signed balances are plain `int` pence |
| Payload extraction and repair cannot write outside their destination directory | `tests/installer/test_payload.py::test_an_entry_that_escapes_the_target_is_refused` and `::test_an_entry_that_escapes_the_target_stops_the_extraction` |
| No mock libraries: real implementations and hand-written fakes only | House rule; `tests/*/fakes.py` are the doubles |

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
│    RememberedLogin → OS credential store + sidecar file     │
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
- `safe_to_spend.py` - the Safe to Spend Today calculation, pure over its
  inputs: `safe_to_spend(projection, today, income_days, floor_pence, horizon)`
  returns a `SafeToSpendResult` (signed `amount_pence`, the `binding_day` that
  set the minimum, the `first_breach_day` the projection first sits below the
  floor or None, `horizon_end`, the floor echoed back). `today` is a
  parameter, never read from the clock; a negative result is the shortfall and
  is deliberately not clamped here (presentation is the UI's job).
  `HorizonStrategy` defaults to `FULL_FORECAST` (the whole projection: a
  spend today lowers every later day, so a shorter horizon overstates safety
  whenever a later month does not pay for itself); `UNTIL_NEXT_INCOME` ends
  the day before the next income event strictly after today, degrading to the
  full window when none exists
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
    already posted this month); for any other month or a card with no day anchor, it
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
  from a month onward) reverses its logged applications and a manual balance
  entry clears the log because the typed figure supersedes them
- `GraphSeriesMixin` (`_month_graph_series.py`) - month graph data:
  `get_bank_graph_series` (day-end projected bank balance across the viewed
  month, anchored through today's stored balance for the current month) and
  `get_card_graph_series` (one day-end balance series per active card),
  reusing the same projection day conventions as the rest of the app
- `SafeToSpendOperationsMixin` (`_safe_to_spend_operations.py`) - the Safe to
  Spend Today adapter and its settings. `get_safe_to_spend(today=None)` builds
  the per-day projection across the forecast window plus the income event
  dates (an income already marked Received cannot end the horizon), then
  calls the pure domain calculation with the stored floor and horizon
  strategy. The current month runs from today's stored balance over the same
  still-due items the Solvency panel's timeline shows, an undated bill
  counted at its prorated REMAINING portion because its elapsed portion is
  already inside the stored balance (the raw month-graph convention charges
  the full undated amount again near month end, which double-counted elapsed
  spending and made the headline disagree with the panel it sits on); its
  close therefore equals the panel's projected end-of-month figure. Later
  months chain day by day from that close, over the same 24-month window the
  overdraft runway walks

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
  needs it (`anchored_month_opening_pence`) and the same-month stamp makes the
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
- `get_safe_to_spend(today=None)` → `SafeToSpendResult` - Safe to Spend Today
  from the stored floor and horizon; `today` is injectable so the result is
  decided by its inputs rather than by the day the code runs
- `get_safe_to_spend_floor()` / `set_safe_to_spend_floor(amount)` - the safety
  floor (default zero)
- `get_safe_to_spend_horizon()` / `set_safe_to_spend_horizon(horizon)` - the
  `HorizonStrategy`, defaulting to `FULL_FORECAST` for an unset or
  unrecognised stored value
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
- `ReleaseInfo` / `ReleaseAsset` / `UpdateStatus` (`dto/update_info.py`) - the
  latest published release, its downloadable files and the outcome of an
  update check

**Update check**:
- `ports/release_source.py` - `ReleaseSource` Protocol: the one seam through
  which the application ever learns about releases; implemented in
  infrastructure, faked in tests
- `UpdateService` (`services/update_service.py`) - compares the running
  version against the latest published release, honours a skipped version and
  picks the download asset for the running platform by filename suffix
  (`.exe` / `.dmg` / `.flatpak`); an unreachable source reports no update
- `version_compare.is_newer` (`services/version_compare.py`) - pure dotted
  semver comparison with an optional leading "v"; a malformed tag is never
  newer, so it can never raise a spurious prompt

### Infrastructure Layer

**Per-user database** (`~/.clearbudget/budget_<username>.db`):
- `Database(db_path)` - SQLite connection and schema management. `_schema.py`
  holds the baseline DDL; `_migrations.py` holds the numbered migrations that
  bring an existing database forward. A column is added only after reading
  `PRAGMA table_info`, so "already present" is established by looking rather
  than inferred from a swallowed exception; every other failure propagates
- Schema - 19 application tables (plus SQLite's internal `sqlite_sequence`):
  1. `payment_methods` - id=1 is "Bank Account"
  2. `bills` - templates; includes `target_card_id` (migration). A bill starts
     in the month it was created and its start month is never moved afterwards,
     since moving it would make the bill appear in months before it existed. The
     retired `one_time` category is folded into `discretionary` by a numbered
     migration that runs once rather than on every launch. `amount_pence` here
     is only the ORIGINAL amount: what a bill costs in a given month comes from
     table 18 via `domain.services.bill_amount_schedule`
  3. `income_sources`
  4. `months` - one row per archived month (written by auto-archive at launch)
  5. `month_bills` - archived per-month bill snapshot
  6. `month_income` - archived per-month income snapshot
  7. `credit_cards` - includes `minimum_payment_percent` (migration)
  8. `settings` - key/value store (`bank_balance`, `bank_balance_day`,
     `bank_balance_date` (the fold baseline; legacy databases without it fall
     back to `bank_balance_day`), `currency`,
     `overdraft_limit`, `overdraft_apr_bp`, `safe_to_spend_floor`,
     `safe_to_spend_horizon`)
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
  18. `bill_amount_changes` - what a bill costs from a month onward, one row per
      change, unique per (bill, month). A change applies to its month and every
      month after it and to no month before it, so raising the rent leaves
      earlier months reporting what they actually cost
  19. `schema_version` - a single row recording how far this database has been
      migrated, so each migration runs once and in order

**Repositories**:
- `SQLiteBillRepository`
  - `list_active_for_month()` - LEFT JOINs `bill_month_skips` and `bill_month_overrides`
  - `skip_for_month` / `unskip_for_month`
  - `hard_delete(bill_id)` - cleans related skips and overrides
- `SQLiteIncomeSourceRepository`
- `SQLitePaymentMethodRepository`
  - `set_card_active(card_id, active)` - soft-delete toggle

**Update source** (`infrastructure/update/github_release_source.py`):
- `GitHubReleaseSource` - implements the `ReleaseSource` port with a single
  best-effort stdlib `urllib` GET against GitHub's latest-release endpoint
  (published releases only, so drafts, prereleases and bare tags can never
  prompt). Any failure yields None; the opener is injected so tests never
  touch the network. This is the only outbound network call in the
  application

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

**`RememberedLogin`** (`clear_budget/auth/remembered_login.py`):
- Backs the sign-in screen's Remember me checkbox. The password lives in the
  operating system's credential store (Windows Credential Manager, macOS
  Keychain, Linux Secret Service) via the `keyring` package under the service
  name `ClearBudget`; only the remembered USERNAME is written to disk, as
  `remembered_login.json` in the app directory, so the next launch knows which
  credential-store entry to look up
- `remember(username, password)` - keychain first, sidecar second, so a failed
  keychain write never leaves a dangling half-state
- `recall()` → `(username, password) | None`
- `forget()` - deletes the keychain entry and the sidecar; still removes the
  sidecar when the keychain is unavailable
- Every keychain failure (no backend, locked, denied) degrades to "nothing
  remembered": sign-in never crashes or blocks on the credential store
- The keyring boundary is an injected `SecretBackend` Protocol; tests use a
  hand-written in-memory fake and the module sits inside the coverage gate
- Constructed in `main.py` with `Config.app_dir()` and passed to `LoginDialog`;
  the UI ticks the box and prefills both fields when `recall()` returns
  credentials, forgets on untick and remembers (or forgets) on a successful
  sign-in according to the box

### Reporting (`clear_budget/application/reporting/`)

Pure string building for the HTML exports: no Qt, no file access, no clock, so
it is all under the coverage gate and testable without a QApplication.

- `curve.py` - the monotone cubic (Fritsch-Carlson) curve maths. It lives here
  rather than beside the widget because BOTH the on-screen chart and the exported
  SVG need it and the UI layer is not something the application layer may import
- `chart_svg.py` - the bar and line charts as inline SVG, following the same rules
  as `_line_bar_chart.py` (curve in bar mode only, axis always includes zero, zero
  line only when the range crosses it). The export redraws the series rather than
  screenshotting the widget: vector output stays sharp, needs no image file beside
  the HTML and can be tested as a string. Fixed DARK palette mirroring the app's
  `DARK` / `SERIES_DARK` / `CURVE_DARK` tokens (mirrored, not imported, because the
  application layer may not depend on the UI). Fixed rather than following the
  active theme, so an export does not change appearance depending on where the
  toggle happened to be. Each chart carries its own background rect so it reads
  correctly wherever it is embedded and the print rules keep the dark identity
  rather than dropping pale text onto a white page
- `document.py` - the page shell. The stylesheet is inline and the charts are inline
  SVG, so an exported file references nothing outside itself and survives being
  emailed or moved (there is a test asserting no `src`, `href` or `@import`)
- `month_report.py` - one month: both renderings plus the text saying what each is
  for and the four figures worth pulling out (opening, closing, change, the low
  and its day)
- `projection_report.py` - a month range: a chart of two lines per month, the
  month-end balance and the LOWEST point inside that month, plus a table and a
  traffic light per month. The two lines are the point of it: a month that opens
  and closes in credit can still bounce a payment mid-month and a report drawn
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
- Every one of those derives from ONE function, `_resolve_app_dir()`, which
  honours the `CLEARBUDGET_HOME` environment variable when it is set and
  non-blank. The app never sets it: it exists so that anything running OUTSIDE
  the app (the test suite, a probe, a script) writes to a scratch directory
  instead of live user data. The directory holds both databases, the saved UI
  settings (theme, remembered save-file location and any skipped update
  version) and the generated
  spin-arrow images and the Remember me sidecar
  (`remembered_login.json`); a write into it is silent, so it surfaces later as a bug
  report against the app: an offscreen probe applied the light theme in order
  to measure it, `theme.apply_theme` persisted that choice as it is supposed
  to and the app opened light from then on. Constrain the bad state rather than
  remember to avoid it. The variable is read at call time and never cached; otherwise a
  test could not redirect it. `tests/structural/test_data_dir_isolation.py`
  holds the rules in place: the suite never resolves the real directory, no
  other module in the package derives it and the installer never names it at
  all, so installing or reinstalling cannot disturb a saved setting

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
  `ScrollableTab`). The tray machinery itself (this builder, the app-icon
  graph button, the theme toggle and the glyph sizing) lives in
  `ui/utils/nav_header.py`, with the month/year label machinery in
  `ui/utils/nav_label.py`; both are re-exported through `format_helpers`,
  keeping every module clear of the LOC band with no call site moved. The
  label carries its breathing room as a real `QLabel.setMargin` (never
  stylesheet padding, which is painted but not reliably in the size hints)
  and pins its minimum width to its text on every `setText` and recolour, so
  a tray squeezed at the window's width floor sheds pixels from the stretch
  space and the flanking buttons, never from the date (a 13in flatpak
  install used to clip the year's last digit).
  `apply_nav_label_color` / `_nav_label_style` recolour the
  label; the colour is each month's OWN within-month solvency health (current
  month from its live balance, a future month from its Forward Projection),
  computed once by the Solvency panel and broadcast to every tab via
  `SolvencyPanel.month_label_color_changed` so no tab can disagree. A month is
  red only when its own balance breaches the overdraft floor (below zero with no
  facility or beyond an agreed facility); dipping into an agreed facility but
  staying within it is amber. A looming overdraft in a later month stays a
  banner warning and never colours the earlier month's title

**`glyph_metrics`** (`clear_budget/ui/utils/glyph_metrics.py`):
- Painted-pixel measurement for both images and text. `opaque_bounding_rect`
  crops the nav icon to its real content (the source PNG carries uneven
  transparent margins that otherwise throw the tray spacing out) and
  `glyph_font_px_for_height` sizes an emoji by rendering it and measuring what
  it actually paints. See the Theme section for why a measurement replaced the
  fixed fraction that preceded it.

**`ui_paths.default_downloads_dir()`** (`clear_budget/ui/ui_paths.py`):
- Cross-platform Downloads folder via `QStandardPaths.DownloadLocation`, falling
  back to `Path.home()`. Used as the default directory for all file dialogs
  (Save As/Load Database, Export/Import Viewer Package).

**`db_validation`** (`clear_budget/shared/db_validation.py`):
- `REQUIRED_SCHEMA` + `validate_db(path)` - confirms a loaded file is a genuine
  ClearBudget database (all required tables and columns present) before any
  Load Database write touches the active database.

**`resources`** (`clear_budget/shared/resources.py`):
- Runtime asset discovery for packaged builds: locates the app icon, the Qt
  window/taskbar icon and the splash image across PyInstaller onefile
  (`sys._MEIPASS`), onedir (`_internal/`), beside-the-executable, dev repo layout
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
- `SolvencyPanel` - Safe to Spend Today headline (rendered by
  `_solvency_panel_display._update_safe_to_spend` from
  `BudgetService.get_safe_to_spend`, reusing the banner's traffic-light state
  property; a shortfall shows the amount short dated from the first day under
  the floor with the worst point named beneath, never a negative allowance),
  overdraft alert, mid-month alert, card bars, forward projection
- `CreditCardView` - card CRUD, month navigation, 6-month projection strip
- `ArchiveView` - historical month summaries by year; year navigation

**Update check ui** (`ui/update_check.py`):
- `UpdateCheckController` - owns the triggers (a delayed launch check, a daily
  re-check and Help > Check for Updates) and runs each check on a worker
  thread; the result crosses back through a queued signal to this ui-thread
  QObject, so the network call can never stall the ui. A newer release
  prompts with Download (the platform asset, falling back to the release
  page), Skip This Version (persisted in `ui_settings.json`) and Later.
  Automatic checks are silent on failure and when up to date; the manual
  check reports both

**Widgets**:
- `LoginDialog` - username/password form; a Remember me checkbox under the
  password field (prefills both fields and ticks itself when `RememberedLogin`
  recalls credentials; unticking forgets them immediately; a successful sign-in
  stores or forgets according to the box); grid layout with "Forgot password?"
  (opens `ResetPasswordDialog`) and Sign In on one row, "Import Viewer Package..."
  (opens the viewer-package import flow) and "Create Account..." (opens
  `CreateUserDialog`, non-admin) on the row below
- `ResetPasswordDialog` - username + recovery code + new password; distinct error for unknown username vs wrong code
- `CreateUserDialog` - new user form (first-run wizard, login screen or admin
  "Add User"); `is_first_user=True` is the only path that creates an admin account;
  includes `RecoveryCodeDialog` on success
- `RecoveryCodeDialog` - displays one-time recovery code; X button disabled; clipboard copy button; checkbox gate before OK activates
- `UserManagementDialog` - admin-only; lists users, Add User, Delete Selected
  (disabled when own row selected); deleting a user always deletes their budget
  data file too (double confirmation)
- `CurrencyDialog` - combobox of 25 currencies; opened via Settings >
  Preferences or the tray's cog button
- `BankAccountSettingsDialog` - configure the overdraft facility (limit and
  APR) plus the Safe to Spend Today safety floor and horizon strategy; opened
  via Settings > Bank Account or the tray's bank button
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
- `AboutDialog` / `LicenceDialog` - app info and LGPL-3.0 text. The credits are
  two lists, not one: what is BUNDLED with the application (whose licences
  travel with the binary, which is what LGPL-3.0 compliance turns on) and what
  is only used to build and test it. The bundled list was checked against what
  the build actually ships, including the native libraries and the binding
  runtime, rather than against `requirements.txt`, which names neither.
  `pywin32` appears only on Windows, where it is genuinely shipped
- `ScrollableTab` - wraps any view in `QScrollArea` with scroll indicator
  buttons; also hoists the view's `nav_header` (the shared, centred month/year
  navigation tray) above the scroll area and zeroes the content's top margin so
  the tray stays full-width and centred on every tab. The indicators sit in a
  COLUMN of their own beside the page, laid out rather than positioned. They
  used to float on top of the content, placed by hand and a hand-placed
  overlay lands on whatever happens to be beneath it: measuring from the top of
  the whole tab put the up indicator inside the hoisted tray over the theme
  toggle and on a 900x580 window the down indicator sat on Monthly Budget's
  Delete Income button, where a click scrolled instead of reaching the button.
  A column cannot overlap anything. It is ALWAYS present, even while both
  buttons are hidden: showing and hiding it would change the page width, which
  can change whether the page overflows, which decides whether the buttons
  show, a loop that flickers on content sitting near the boundary. This was the
  only hand-placed child widget in the app; everything else is laid out and a
  layout cannot overlap its own children (verified by an overlap sweep over all
  four tabs at three window sizes and nine dialogs at two: zero)
- `_preferences_flow.py` / `_bank_account_settings_flow.py` - dialog-orchestration
  helpers extracted from `MainWindow` to stay under the LOC limit
- `_save_load_flow.py` - the Save / Save As / Load flows behind the File menu
  and the tray buttons, plus the builders for the tray's icon buttons (load,
  save, cog, bank, info) and their separator. Save copies the database to the
  remembered location (first save prompts, defaulting to Downloads, then asks
  before overwriting); Load validates via `db_validation` and confirms before
  replacing data. The remembered location persists in `ui_settings.json`
  through `clear_budget/ui/save_location.py`, which shares the file with the
  theme without disturbing it (`tests/ui_logic/test_save_location.py`)
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
- `_month_view_balance_mixin.py` (`MonthViewBalanceMixin`) - the balance
  label (stored balance for the month the user is in, projected month-end
  for any other) and the overdraft warning strip under the nav row
- `MonthGraphDialog` / `_line_bar_chart.py` (`LineBarChart`) - the month graph
  opened by the nav-tray icon button on Monthly Budget (bank balance by day)
  and Credit Cards (one series per card, with a legend); a pilot button
  toggles bar vs line rendering, drawn with QPainter (no chart dependency).
  ← Previous / Next → inside the dialog step it between months without
  closing it: the caller passes a `series_for(year_month)` callback the
  dialog re-queries on each step, with Previous bounded by the same base
  month the tray's own arrows stop at. The axes chrome lives in
  `_chart_axes.py` (`ChartAxesMixin`): the y-axis left margin is MEASURED
  per paint from the widest tick label via QFontMetrics (with a floor), so a
  large balance widens the margin rather than truncating; the SVG exporter
  mirrors the same rule with a character-count estimate, since SVG has no
  font metrics at build time
  - Curve maths is Qt-free and lives in `application/reporting/curve.py`, NOT
    beside the widget: the day-end totals (one curve however many series are
    plotted, so with a single series it IS that series), the inflection days
    where direction changes and the Bezier segments. The chart imports it and
    so does the SVG exporter, which is the reason it sits in the application
    layer rather than the UI one. Tested without a QApplication in
    `tests/application/reporting/test_curve.py`, under the coverage gate
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
  - "Export projection HTML" opens `MonthRangeDialog` for a first and last month,
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
- `FirstStopDialog` (`first_stop_dialog.py`) - dialog base that opens with focus
  already on its FIRST stop: the first control in its own tab order that is
  enabled, visible and takes tab focus, found by walking Qt's focus chain so the
  answer is whatever the first Tab press would have reached. Disabled and hidden
  controls are passed over, the same rule the ring applies everywhere else and a
  dialog with nothing focusable simply focuses nothing rather than failing.
  Replaced the old `NeutralDialog`: the neutral start belongs to the MAIN WINDOW,
  which you look at before you act in it, not to a dialog you opened deliberately
  to do one thing. Making a dialog wait for a Tab press costs a keystroke and
  tells the user nothing. Plain `QDialog` subclasses already behave this way
  through Qt's own default, so the rule holds across all 20 dialog classes
- `auto_scroller.py` (`AutoScroller`) - gentle auto-scroll shared by the About
  credits and the How It Works text: the surface holds still on open, reads
  down slowly (one step every second tick), holds at the bottom, rewinds fast
  and repeats. Any manual input (wheel, click, keys, the scrollbar or keyboard
  focus entering the surface) only SUSPENDS it; after a moment of stillness it
  resumes from wherever the reader left it. A modal above the surface freezes
  the cycle in place. One set of pace constants for the whole app, on the
  class, never per dialog

**Keyboard navigation** (`keyboard_nav.py` + `_main_window_nav.py`):
- One application-level `KeyboardNavigator` event filter drives an explicit
  focus ring: menu-bar titles, the tab bar, then the active tab's stops (each
  view's `nav_targets()`), recomputed live so disabled or hidden stops are
  skipped (a disabled Previous at the base month simply drops out)
- Tab and Right step forward, Shift+Tab and Left step back, wrapping at both
  ends; tables keep Up/Down for their rows, text inputs keep their arrows for
  the caret
- THE PAGE BODY IS THE LAST STOP on every tab, when it has something to
  scroll. `ScrollableTab.nav_scroll_stop()` returns its `QScrollArea` only
  while the content overflows, so a page that fits is skipped (a stop must be
  actionable: landing on a page that scrolls nowhere spends a keypress and does
  nothing). Without it the ring ran out at the theme toggle and wrapped
  straight back to the File menu, so a long page such as Solvency could only be
  read with the mouse: there was nowhere to put the keyboard that the arrows
  would scroll. Qt scrolls a focused `QAbstractScrollArea` on Up, Down, Page
  and Home/End by itself, so only the focus policy and the ring membership had
  to be added. Left and Right deliberately still STEP THE RING here rather than
  scrolling horizontally, unlike the general scrollable-region rule: nothing in
  this app scrolls sideways and Left/Right stepping everywhere is what stops
  focus being trapped. The stop paints the same green ring on focus and none at
  rest (measured: 0 pixels at rest, ~2980 focused, both themes), with no hover
  rule, since the pointer sits over the page most of the time the app is open
- EVERY TAB IS A STOP on the ring, not the strip as a whole. Tab and Shift+Tab
  walk the tabs in visual order and only leave the strip once there are none
  left in that direction, so on Credit Cards with the cursor on Archive,
  Shift+Tab reaches Solvency. Treating the strip as one stop sent that keypress
  out to the menu bar and made the tab order wrong. The ring ENTERS at the side
  it arrives from, leftmost tab going forward and rightmost coming back, rather
  than beside the current tab: entering beside it meant a forward pass could
  only ever reach the tabs to its right and the rest of the strip needed a
  turn round. Two walks back this: `_tab_cursor.next_candidate` wraps and
  belongs to Up and Down, the strip's own keys; `next_candidate_bounded` stops
  at the ends and belongs to Tab, since wrapping there would trap the ring in
  the tab bar for ever
- The tab strip's cursor is SEPARATE from its selection (`NavTabBar`). Qt ties
  a `QTabBar`'s focus to its current tab, so a plainly focused bar can only
  ring the tab the user is already on, which is a dead stop. `NavTabBar` holds
  its own cursor instead: the tab already showing is never a candidate and
  only Enter or Space commits a switch. Stepping the ring therefore never
  changes which tab is shown. The
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
- Neutral start, MAIN WINDOW ONLY: a 0x0 sink takes the initial focus so nothing
  is highlighted on launch and no menu drops open. Dialogs do the opposite and
  open on their first stop (`FirstStopDialog`); a window is looked at before it is
  acted in, a dialog was opened to do one specific thing
- Ring colours are three-state, enforced in the QSS: no ring at rest, a green
  ring while an enabled control is hovered or focused, a permanent red ring
  while disabled (hover/focus rules are gated on `:enabled`)
- `_credit_card_view_loaders.py` - builds the per-card panel list (`_build_card_frame`)
  for the Credit Cards tab

**Main Application**:
- `MainWindow` - all tabs in `ScrollableTab`; signals: `logout_requested`, `database_replaced`
  - File menu: New Budget, then Load / Save / Save As (Save goes to the
    remembered save file, kept in `ui_settings.json`), then the
    "Import / Export" submenu (Read-Only Viewer Package export/import, admin
    only), Exit
  - Settings menu (adjacent to File): Preferences, Bank Account
  - Users menu: Switch User for every account; admins also get Manage Users
    (list, Add User, Delete Selected)
  - Every tab's nav tray mirrors the common actions as icon buttons, built by
    `_save_load_flow.build_save_load_buttons` / `build_settings_bank_buttons` /
    `build_info_button` and sized against the app-icon button: folder (Load)
    and diskette (Save) at the far left, a themed separator, then cog
    (Preferences) and bank (Bank Account); after the theme toggle at the far
    right, a blue information button opens How It Works
  - Help menu: About, Check for Updates (runs the real update check via
    `UpdateCheckController` and reports the outcome, Up to date and unreachable
    included), How It Works, View Licence
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
    it is resolved once rather than per window or a dialog would open on whichever
    monitor the mouse was resting on. `installer/app.py` does the same before
    showing the setup window
  - Screen-aware UI scale (`ui_scale.init`): factor = the LAUNCH screen's available
    height / 1260, capped at 1.5x on tall/4K displays and floored at 0.5x, so the UI
    scales *down* on short displays such as a 13in MacBook and scales for the
    monitor the app actually opens on
  - Default window geometry: 33% of available width x 92% of available height,
    centred, with absolute minimum floors (860 x 780 logical points, capped to the
    available screen) so the multi-column Bills/Income tables stay readable on small
    laptops. The arithmetic is `_window_geometry.default_window_rect`, kept Qt-free
    and tested in `tests/ui_logic/test_window_geometry.py` because multi-monitor
    placement cannot be exercised on a one-screen machine. It works in virtual-desktop
    coordinates, so a monitor left of or above the primary one (negative x or y) needs
    no special case
  - Centring positions the window's FRAME, not its client rect and happens AFTER the
    window is shown. `setGeometry()` places the client rect while `move()` places the
    frame, so centring geometry alone leaves the window half a title bar high and half
    a border left (measured: a 23px title bar with 4+4px borders puts it 19px out).
    Worse, a layout can insist on a larger size than the window was given and a window
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
- The toggle's emoji is sized to MATCH the nav icon, both from
  `format_helpers.nav_glyph_height` (the Previous button's height). One source
  because the two are built in different functions, which is how they drifted
  apart in the first place. The font is applied as a WIDGET-level stylesheet,
  not `setFont`: the app stylesheet sets `font-size` on `QWidget` and any
  stylesheet rule beats `setFont`, so the size was silently ignored. A widget's
  own sheet beats the application's and setting only `font-size` leaves the
  object-name ring rules intact (verified: 0 ring pixels at rest, 385 green on
  focus, 380 red when disabled). The rule MUST carry a selector
  (`QPushButton#ThemeToggleButton { ... }`): a bare `font-size` cascades to the
  widget's whole subtree and its TOOLTIP counts, which is what briefly rendered
  the hover text at the emoji's size
- An emoji does not fill its em box and no two fill it alike, so the font size
  is MEASURED per glyph by `glyph_metrics.glyph_font_px_for_height`: the glyph
  is painted to a scratch canvas at the target height and the font is scaled by
  however far its opaque pixels missed. On Windows at a 42px font the sun paints
  43px tall and the moon 38px, so the single 1.08 fraction that preceded this
  ran the sun about 10% proud of the icon while the moon sat right. The
  measurement is what puts the two glyphs on the same height as each other. The
  height they are put on is `format_helpers.TOGGLE_GLYPH_SCALE` of the nav
  icon's and deliberately not equal to it: matching bounding heights was tried
  and reads wrong, because the sun and the moon are solid saturated shapes that
  fill their outline while the icon is a pictogram with light space in it, so
  at equal heights the emoji looks the heavier. Optical weight is what the eye
  compares, not the bounding box. The
  target height rides on the button as a `navGlyphTargetPx` property so
  `theme._refresh_toggle_buttons` re-sizes the INCOMING glyph after each switch
  through `format_helpers.apply_toggle_glyph`; a plain `setText` left the new
  glyph wearing the size the outgoing one needed. Measure this on the real
  platform: under `QT_QPA_PLATFORM=offscreen` Qt substitutes its own font
  database, where both glyphs measure 38px and the discrepancy is invisible
- HIGHLIGHT TEXT IS TEAL, NEVER GREEN, everywhere: the hovered tab, the
  selected tab, a menu-bar title and a menu item. Green is the RING, the border
  saying where the pointer or the keyboard is; the words inside it take the
  accent, the same colour that marks the selected tab. Text in the ring's own
  green made a hovered tab read as a second, slightly different selection, two
  greens a few degrees apart on one strip. `tests/ui_logic/test_highlight_text_colour.py`
  holds every one of those surfaces to it. The keyboard cursor's tab is the one
  exception and keeps muted text under its green ring, because the cursor marks
  where the keyboard is rather than what is live; Qt gives no way to say
  otherwise anyway (measured: with a stylesheet active, `setTabTextColor` is
  ignored entirely)
- The sheet is split by surface across `_theme_tabs.py` (the tab strip plus the
  pill geometry NavTabBar paints its cursor on), `_theme_inputs.py` (the fields
  the user types in), `_theme_menus.py`, `_theme_controls.py` and
  `_theme_labels.py`, each a pure string builder taking the token dict. The
  split is what keeps every module under the LOC limit and it is also what
  makes the highlight rule testable: `build_qss` as a whole CANNOT run without
  a QApplication, since it resolves the system font and generates the spin-box
  arrow images, while the per-surface builders touch no Qt at all. The blocks
  are interpolated in their original order, because QSS is order sensitive
- `QToolTip` is styled app-wide (size, colour, background, border). Without a
  rule, tooltips take the platform default and are the one surface that escapes
  the theme entirely, as well as being open to inheriting whatever font-size a
  widget's own stylesheet sets
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
  whichever tab the cursor sits on and a focus rule on the selected pill
  would put a second green ring on the strip. (If one is ever reinstated, the
  subcontrol must come first: `QTabBar::tab:selected:focus` works while the
  widget-state-first form `QTabBar:focus::tab:selected` is silently ignored by
  Qt.) `MainWindow` sets `tabBar().setDrawBase(False)` because Qt ignores
  drawBase from a stylesheet and would draw a rule under the strip
- Spin-box arrows are IMAGES, generated per colour (`spin_arrows.py`), not CSS
  triangles. Qt's stylesheet engine does not implement the `width: 0` plus
  transparent-side-borders idiom: it honours the zero size, draws nothing and
  leaves the button box, which is why the year pickers showed two empty
  rectangles (measured: the up button was 366 pixels of one flat colour).
  `image: url(...)` is Qt's only stylesheet route to a glyph there. The images
  are drawn into `~/.clearbudget/arrows/` and cached under a filename made from
  the colour and size, so each theme gets its own without any being shipped,
  hand-maintained or added to the packaging scripts. A `QProxyStyle` drawing
  `PE_IndicatorSpinUp` is NOT an alternative: once a global stylesheet is set,
  `QStyleSheetStyle` renders the styled spin box itself and never delegates that
  primitive (verified: zero calls reached the proxy)
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
              └── else       → LoginDialog (prefilled from RememberedLogin
                               when Remember me was ticked last time)
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

update_service = UpdateService(
    source=GitHubReleaseSource(),
    current_version=__version__,
    platform_key=platform_key_for(sys.platform),
)

window = MainWindow(
    month_view_model=month_view_model,
    solvency_view_model=solvency_view_model,
    current_user=user,
    user_store=user_store,
    db_path=database.db_path,
    update_service=update_service,
)
```

## Database Locations

| File | Path | Purpose |
|------|------|---------|
| `users.db` | `~/.clearbudget/users.db` | Central user accounts (all users) |
| `budget_<username>.db` | `~/.clearbudget/budget_<username>.db` | Per-user budget data |
| `remembered_login.json` | `~/.clearbudget/remembered_login.json` | The Remember me username (the password is in the OS credential store, never on disk) |

Username is sanitised to lowercase alphanumeric + `_-` before use in filename.

## Currency

Currency is stored per-user in the `settings` table (`key='currency'`, `value='GBP'`).
It is loaded from the DB immediately after opening the user session and activates the
module-level symbol in `shared.currency`. `Amount.__str__` and `fmt()` both call
`get_symbol()` at render time, so all displayed values reflect the active currency
without any additional wiring. On currency change (Settings > Preferences), the new
code is saved to the DB, `set_currency()` is called and `database_replaced` is emitted
to rebuild the window with updated labels.

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
| macOS | `builddmg.py` | `clearbudget.dmg` (signed and notarized; the build fails rather than produce an unnotarized release, with `ALLOW_UNNOTARIZED=1` as a local-testing escape hatch) |
| Linux | `build_flatpak.sh` (+ `cleanup_flatpak.sh`) | `clearbudget.flatpak`, on the Freedesktop runtime |

The Windows installer is itself a small PySide6 application under `installer/`
(with its own `cli`, `ops`, `state`, `ui` and payload-builder modules). It wraps
the PyInstaller bundle into the per-user setup executable and is a build and
distribution tool, kept separate from the runtime application described above.

### The setup program

The `installer` package follows the same shape as the application, for the same
reason. `ops` holds the side effects (payload extraction, staging, shortcuts,
process control, registration and the install, repair and uninstall sequences),
`state` holds the HKCU registration, version comparison and the state model the
window reads, `shared` holds resource resolution and logging, while `ui` is the
only Qt client. `app.py` is the composition root.

Three seams keep the privileged work testable, which is what allows everything
outside `installer/ui` to sit inside the 100% gate:

- every external command goes through an injectable `CommandRunner`
  (`ops/commands.py`), so no test spawns a process it did not intend to;
- every process query and every termination goes through an injectable
  `ProcessController` (`ops/running_app.py`), so no test lists or ends a real
  process; matching is on the resolved executable path rather than the
  image name so an unrelated copy elsewhere is never touched;
- the HKCU key and the shortcut names are fields on the `InstallerIdentity`
  value rather than constants baked into each function, so a test writes to a
  scratch key instead of the user's own registration; the per-user
  directories come from environment variables the suite redirects into a
  temporary tree.

The payload anchor is resolved relative to the `installer` package
(`shared/resource_path.bundled_data_root()`), which is the repository root from
source and the unpacked bundle root when frozen. Every asset lookup uses that
one anchor rather than counting directory levels from its own module, which is
what previously resolved one level above the repository in `app.py` while the
frozen build's `_MEIPASS` branch masked it.

Four behaviours are worth naming because they are what a user notices:

- **A running application is offered a close, not a lecture.** Detecting it used
  to produce "Please close Clear Budget and click Retry". The setup program now
  offers to close it, states that the running session ends, force-terminates
  every matching process and then polls until the file lock releases, with a
  bounded deadline and a typed `AppStillRunningError` if the process will not
  go. Forced rather than a close request, because a request can be declined and
  a process that declines still holds the lock.
- **A fresh install is guarded too.** `is_app_running` guards install, upgrade,
  reinstall, repair and uninstall alike. Installing into a directory that
  already holds a running executable would try to replace files Windows has
  locked, which fails part way through.
- **Every operation reports a percentage.** Repair walks a manifest whose length
  is known, so it reports real per-entry progress; uninstall reports each phase.
  Both used to emit bare strings, so the bar sat at zero and then jumped to
  complete.
- **Extraction cannot write outside its destination.** `ops/payload.py` resolves
  every archive member and every repair-manifest path through one guard. The
  payload is first-party, so this enforces a guarantee rather than fixing an
  exploit; enforcing it is what keeps the guarantee true.

Two things the setup program deliberately does not do. There is no
"remove my user data" option (see below); there is no launch-on-sign-in
entry: Clear Budget has no such feature, so an installer switch for it would be
a product decision rather than a packaging one.

**The installer never touches user data.** Install, repair, reinstall and
uninstall all deal in program files, shortcuts and the registry entry only, so
`~/.clearbudget` survives every one of them and a reinstall carries on from
where the user left off, saved theme included. Uninstall offers no option to
delete it: that directory holds every account and every user's budget, deleting
it is irreversible and an installer is the wrong place to offer it. Anyone who
wants it gone deletes the folder by hand, which the uninstall dialog says.
`tests/structural/test_data_dir_isolation.py` fails if any installer module so
much as names the directory. What was there before was inherited from the
installer this one was rebranded from: it seeded a `playback_volume` file and
deleted two platformdirs directories, none of which this app has ever used, so
an option that read as "remove my data" removed nothing.

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
- `RememberedLogin` tested against a hand-written in-memory keychain fake,
  including keychain-failure degradation and sidecar corruption

### Shared Layer
- `test_config.py` - path construction and safe username
- `test_currency.py` - currency registry, `get_symbol`, `set_currency`, reset fixture

### UI Layer
- The suite is Qt-free: fragile widget-level PySide6 tests (which needed a
  `QApplication` and were flaky) have been removed
- Pure UI-layer logic is still covered without Qt under `tests/ui_logic`: the
  Solvency month-colour rule (by instantiating the colour mixins directly), the
  tab-strip keyboard cursor, theme persistence and the window-geometry
  arithmetic. What lands here is logic a widget happens to host, extracted far
  enough from Qt to be asserted on
- The UI layer is excluded from the coverage gate (see `.coveragerc`)
- Anything that must be seen rather than asserted (a painted ring, a glyph
  against an icon, a window's placement on a monitor) is measured with an
  offscreen probe outside the suite. Measure emoji and font sizes on the REAL
  platform though: under `QT_QPA_PLATFORM=offscreen` Qt substitutes its own
  font database and the answer does not describe the shipped app

### Setup Program
- `tests/installer/` covers everything under `installer/` except `app.py` and
  `installer/ui`, at 100% line and branch
- `conftest.py` carries four autouse isolations, each guarding one way a test
  could reach the real machine: the profile directories are redirected through
  the environment variables the code reads; the platformdirs lookups the legacy
  migration makes are redirected in their own right, because platformdirs asks
  Windows for the known folder rather than reading `%LOCALAPPDATA%`; the
  payload anchor is redirected so a small stand-in bundle replaces the real
  fifty-megabyte payload; and `scratch_identity` yields an `InstallerIdentity`
  whose HKCU key lives under a test-only root and is deleted in teardown
- `fakes.py` holds the hand-written doubles for the three seams. No mocking
  library is used
- What is exercised for real is exercised for real: shortcuts are written
  through the same Shell Link COM interface the install uses (into the
  redirected profile), the registry round-trips through `winreg` against the
  scratch key; a full install deploys and registers a real bundle

### Structural Tests
- `test_layering_rules.py` - AST-based forbidden import enforcement
- `test_loc_limits.py` - No file > 400 LOC
- `test_auth_structure.py` - Auth layer structure validation
- `test_data_dir_isolation.py` - the suite cannot resolve the real
  `~/.clearbudget`, only `shared/config.py` derives it and the installer never
  names it. A `conftest.py` autouse fixture points `CLEARBUDGET_HOME` at a
  scratch directory for EVERY test and these assert that it is in force

## Code Quality Standards

- **Black** 88-char line length
- **Flake8** no violations
- **Ruff** clean (`ruff check .`) under its default rules plus the three
  blind-handler rules (`BLE001`, `S110`, `S112`) enabled repo-wide in
  `pyproject.toml`, so a new blind exception handler fails the lint rather
  than waiting to be noticed. Run alongside black and flake8 rather than
  replacing either. A genuine false positive is suppressed with a targeted
  `# noqa: <RULE>` and a reason, never by changing behaviour; where ruff and
  black disagree on formatting, black wins
- **100% line and branch coverage** (`pytest -v --cov`, gated at
  `--cov-fail-under=100` with `branch = True`) over `clear_budget`, `main` and
  the Qt-free half of the setup program, excluding UI, interfaces, main.py and
  the build scripts. The suite is Qt-free and runs clean in one process
- The setup program is inside the gate because it does the most privileged work
  in the repository: registry writes, shortcut creation, per-user deployment,
  process termination and directory removal. `installer/app.py` and
  `installer/ui` are excluded on the same grounds as `clear_budget/ui` and
  `installer/build_payload.py` is a build script
- What the gate does NOT include, stated plainly so the number is not read as
  more than it is: besides the `.coveragerc` omissions above, every line marked
  `# pragma: no cover` is outside it. That is the whole of
  `SQLitePaymentMethodRepository` and most of the thin pass-throughs in
  `application/services`. Several are exercised by tests anyway (the credit-card
  ones are, through `tests/application/test_budget_service_crud.py`, which reads
  through the real repository rather than a fake precisely because the gate says
  nothing about it). Retiring the pragmas is worthwhile and has not been done
- **No mock libraries** - real implementations and hand-written fakes only
- **No magic numbers** - all domain values derive from data, config or named constants

## Design Principles

**Dependency direction**: always inward. UI → Application → Domain ← Infrastructure.

**No magic numbers**: no hardcoded financial amounts, thresholds, day numbers or limits in logic.

**Immutable value objects**: `Amount`, `YearMonth`, `SolvencyResult`, `CardMonthlyState` - all frozen dataclasses.

**Signed balance**: projected balances returned as `int` pence (not `Amount`) wherever negative values are valid.

**Per-user isolation**: each user has a completely separate budget database. No cross-user data access is possible.

**Session lifecycle signals**: `logout_requested` and `database_replaced` on `MainWindow` drive all session transitions without tight coupling between UI and `main.py`.
