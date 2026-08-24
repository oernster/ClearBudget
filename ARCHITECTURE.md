# ClearBudget Architecture

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
| No source file exceeds 400 lines and none sits in the 381 to 399 danger band: a file refactored down from over the cap lands at 350 or below rather than stopping the moment it clears 400 | `tests/structural/test_loc_limits.py` (both halves) |
| Only `shared/config.py` derives the real data directory. The suite never resolves it; the installer never so much as names it, so no test and no install can disturb live user data | `tests/structural/test_data_dir_isolation.py` (plus the autouse `CLEARBUDGET_HOME` fixture in `tests/conftest.py`) |
| The data-directory migration cannot lose data: resolution prefers the legacy `~/.clearbudget` while it exists (its disappearance is the completion signal), the copied tree verifies byte for byte before the old directory is removed and `main()` migrates before the single-instance lock, never under the override | `tests/shared/test_data_migration.py`, `tests/shared/test_config.py` and `tests/structural/test_data_dir_isolation.py::TestTheMigrationRunsFirstAtStartup` |
| A database the application has OPEN is never treated as an ordinary file: it is snapshotted out through SQLite's backup API and only ever replaced after its connection has been closed by the composition root. Both write to a scratch file and rename it into place, so a failure leaves the previous database whole | `tests/shared/test_db_copy.py` |
| A full restore that cannot complete changes nothing: every file in the backup is staged and schema-validated before a single live file is replaced, strays and path-traversal names are refused and files not named in the backup survive untouched | `tests/auth/test_full_backup.py` |
| 100% line AND branch coverage over `clear_budget`, `main` and the Qt-free half of the setup program | `--cov-fail-under=100` with `branch = True` (`.coveragerc`, `pyproject.toml`) |
| An exported report adds up: `opening + net == close` for every month whose Paid/Received flags agree with the calendar. In the anchored month an item actioned early (or missed) moves the close off the totals by exactly that amount, because the series never charges twice what the recorded balance already contains | `tests/application/test_projection_series.py::test_opening_plus_net_equals_the_close` and `::test_a_bill_paid_early_moves_the_anchored_close` |
| The exported report and the on-screen month graph can never disagree about a month they both cover, because both run the same day-by-day projection | `tests/application/test_projection_series.py::test_the_projection_agrees_with_the_month_graph` |
| The card graph and the Credit Cards tab open a future month from the SAME chained figure (`card_openings_at`), never from the stored balance and each month closes where the next one opens, its interest landing on its last day | `tests/application/test_month_graph_series.py::TestCardGraphChaining` |
| With ONE deliberate exception: the month in progress opens from the recorded bank balance, not the previous month's projected close. The recorded balance is the only figure in the report that is a fact; the gap is the drift the report exists to expose | `tests/application/test_projection_series.py::test_the_current_month_is_anchored_on_the_recorded_balance` and `::test_months_outside_the_current_one_still_chain_when_today_is_inside` |
| An exported HTML file references nothing outside itself, so it survives being emailed and opens offline | `tests/application/reporting/test_reports.py::test_a_report_references_nothing_outside_itself` |
| User-entered text cannot inject markup into an exported report | `tests/application/reporting/test_reports.py::test_user_text_cannot_inject_markup_into_a_report` |
| Highlight text takes the ACCENT, never the ring colour: the ring says where focus is, the accent says what is selected. Stated in roles, so it survived both colours being retired | `tests/ui_logic/test_highlight_text_colour.py` |
| Every colour value in the tree lives in `clear_budget/shared/palette.py` and nowhere else. `ui.theme_tokens`, `installer.ui.themes` and `application.reporting` hold what a colour is FOR and reference it by name; a hex literal anywhere else fails the build. Prose is exempt, so a docstring may still quote a hex it is recording a decision about | `tests/structural/test_colour_source.py` |
| Money is integer pence everywhere. No financial value is ever a float, so nothing rounds away between what the user typed and what a projection uses | `Amount(pence: int)` is a frozen value object; signed balances are plain `int` pence |
| Payload extraction and repair cannot write outside their destination directory | `tests/installer/test_payload.py::test_an_entry_that_escapes_the_target_is_refused` and `::test_an_entry_that_escapes_the_target_stops_the_extraction` |
| A budget belonging to another account cannot be opened without that account's password. Every account's budget sits in one directory the Load dialog opens on, where loading validated the schema alone, so any signed-in user could pick an administrator's budget out of the file list. Ownership comes from a stamp written inside the database, falling back to the file name for anything written before the stamp existed | `tests/shared/test_db_ownership.py`, plus `tests/infrastructure/test_session_database.py` for the stamping |
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
  - `name`, `amount`, `is_reliable` (excluded from counted totals when false)
  - `start_ym`, `end_ym` - active month range, mirroring `Bill`. BOTH are
    nullable and a null means unbounded on that side, unlike a bill's
    mandatory start: every income row written before these columns existed has
    no start to record and inventing one would rewrite the months it already
    appeared in. An income that stops names its final month rather than being
    deleted, so the months it really did arrive in keep it
  - `is_active_in_month(year_month)` - checks the range, the same rule `Bill`
    applies, so a month decides what it contains identically on both sides of
    the ledger
  - `is_month_only: bool` - one-off "this month only" entry not tied to a
    template; stored in `income_month_extras`, an unrelated table with its own
    id space, which is why a one-off and a recurring source are matched by NAME
    wherever the two have to be compared
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
- `MonthGap(income_pence, bank_bills_pence, card_interest_pence)` - what one
  month costs against what it brings in. `needed_pence` derives the shortfall
  (positive) or the headroom (negative) and `holds_flat` reads it. Whole-month
  arithmetic on both sides deliberately, so it describes the SHAPE of the month
  rather than how far through it we are: "what does a month like this need" is
  a structural question, so the answer must not move simply because time
  passed. Card interest is carried alongside and never folded into
  `needed_pence`, because it accrues on the cards and never leaves the bank
  account, so adding it would overstate the gap by money that was never going
  to move (`tests/domain/value_objects/test_month_gap.py` asserts exactly that)
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
  inputs and with `today` always a parameter, never read from the clock.
  `sustainable_spend(projection, today, floor_pence, window_months)` returns a
  `SustainableResult` (signed `amount_pence`, the `binding_day` that set the
  minimum, the `covered_end` the figure makes a promise up to, the floor
  echoed back, plus `shortfall_pence` and `shortfall_day` for the gap beyond
  it). The window bounds how far the calculation LOOKS; what it OFFERS is
  bounded by `_covered_and_beyond`, the longest run of whole months from
  today whose own lowest day clears the floor with nothing spent.
  Two wrong answers were tried before this one and the rule reconciles both.
  Truncating at the first breaching DAY reported the healthy stretch as
  though the days after it did not exist, so the figure it offered deepened
  the very month it had skipped while saying nothing about it. Letting every
  day veto instead reported nothing spendable whenever any month in the
  window collapsed, which answers "does my budget hold" in the slot reserved
  for "what can I spend": a user with real headroom in front of them read
  NOTHING SAFE TO SPEND. Bounding at a MONTH boundary and carrying the
  shortfall separately keeps both truths: the promise is one a reader can
  state ("everything through October holds") and the gap it does not fix is
  named rather than netted off. A month after a collapse is excluded even
  when it looks healthy, because it is projected from that collapse.
  Only when today's own month is under the floor is `amount_pence` negative;
  it is then THIS month's shortfall rather than the window's deepest
  point, because the nearest gap is the one that can still be acted on.
  `sustainable_capacity(...)` answers the rest of the month rather than one
  day: `tuple[CapacityStep, ...]`, one step per CHANGE in the figure, each
  carrying `from_day`, the signed `amount_pence` from that day onward and
  the `binding_day` that set it. Each step is a suffix minimum over its own
  window, so waiting past a tight day raises what a day can carry while
  every step stays measured across whole months. Only days in today's own
  calendar month are reported, because the question is what THIS month can
  carry. Both functions take their window from one shared `_window_days()`
  helper, so the headline and the schedule cannot disagree about what they
  are measured over and the first step always equals the headline.
  `SustainableError` is the module's typed failure
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
  skip/override/received, "this month only" extras and `end_income` (the
  mirror of `end_bill`: sets the income's end month so earlier and archived
  months keep it)
- `OverdraftOperationsMixin` (`_overdraft_operations.py`) - overdraft facility
  settings, `get_month_gap()` (the month's bank shortfall and its card
  interest, as a `MonthGap`), `get_month_cashflow_projection()` and
  `first_overdrawn_month()`
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
  reusing the same projection day conventions as the rest of the app. A card
  month AFTER the current one opens from `card_openings_at`
  (`_card_projection.py`), the same chained openings the Credit Cards tab's
  panels and projection strip read, never from the stored balance: the stored
  figure is as-of the day it was entered, so a distant month opened from it
  drew a balance untouched by every intervening payment and every month's
  interest. The viewed month's interest (one shared
  `monthly_interest_pence` rule with the monthly state) lands on the series'
  last day, so a month closes exactly where the next one opens
- `SafeToSpendOperationsMixin` (`_safe_to_spend_operations.py`) - the Safe to
  Spend Today adapter and its settings. `get_safe_to_spend(today=None)`
  builds the per-day projection across the forecast window, then calls
  the pure domain calculation with the stored floor and window.
  The current month runs from today's stored balance over the same still-due
  items the Solvency panel's timeline shows, an undated bill counted at its
  prorated REMAINING portion because its elapsed portion is already inside
  the stored balance (the raw month-graph convention charges the full undated
  amount again near month end, which double-counted elapsed spending and made
  the headline disagree with the panel it sits on); its close therefore
  equals the panel's projected end-of-month figure. Later months chain day by
  day from that close, over the same 24-month window the overdraft runway
  walks. `get_spending_capacity(today=None)` runs the capacity
  schedule over that same projection, floor and window, so it and the
  headline are two readings of one forecast rather than two forecasts.
  `get_assumed_expectations(today=None)` returns the (month, income) pairs the
  assumed reading counts that a reading of only what was entered would not,
  scoped to the sustainable window because that is what a figure promises to
  keep standing.
  `get_assumed_month_summary(year_month, today=None)` states the same
  assumption as a MonthSummary, filling a later month's gaps from this month's
  income exactly as the per-day projection does, so the projection page's
  spendable figure and its month narrative are two readings of one assumption
  rather than two implementations of it. A month at or before the current one
  comes back unfilled: income repeats forward, so there is nothing for an
  earlier month to receive

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
- `get_safe_to_spend(today=None)` → `SustainableResult` - Safe to
  Spend Today from the stored floor and window; `today` is injectable so the
  result is decided by its inputs rather than by the day the code runs
- `get_spending_capacity(today=None)` → `tuple[CapacityStep, ...]` -
  what could be spent from each remaining day of this month onward, one entry
  per change; the first entry always equals `get_safe_to_spend`
- `get_assumed_expectations(today=None)` → `tuple[tuple[YearMonth, IncomeSource], ...]` -
  the money the assumed reading counts that a reading of only what was entered
  would not, as (month, income) pairs so the panel can say WHEN each amount has
  to arrive
- `get_assumed_month_summary(year_month, today=None)` → `MonthSummary` - one
  month as the repeat assumption sees it, for the projection page's forward
  narrative. Fills gaps only, never reducing a month below what was entered
  for it; the current month and every earlier one are left alone
- `get_safe_to_spend_floor()` / `set_safe_to_spend_floor(amount)` - the
  floor, which the UI calls the Safe to Spend "buffer" (the naming split:
  floor is the domain term the calculation uses, buffer is what a user
  reads). Defaults to 20.00 in the active currency when never set; an
  explicitly saved zero is honoured as zero
- `get_sustainable_window_months()` / `set_sustainable_window_months(months)` -
  how many months the figure must keep standing, defaulting to 4 when never
  set; the dialog offers 1 to 12
- `get_overdraft_limit()` / `set_overdraft_limit(amount)` - overdraft facility limit
- `get_overdraft_apr_basis_points()` / `set_overdraft_apr_basis_points(basis_points)` -
  overdraft APR, stored as basis points (1bp = 0.01%)
- `get_month_gap(year_month)` → `MonthGap` - the month's full bank bills against
  its full income, plus the interest accruing across its active cards; drives
  the Solvency "needs X more to hold flat" line
- `get_month_cashflow_projection(year_month, summary)` → `MonthCashflowProjection` -
  drives the Monthly Budget mid-month overdraft warning
- `first_overdrawn_month(from_year_month, from_balance_pence)` → `YearMonth | None` -
  first future month whose day-by-day projection dips below zero (a mid-month dip
  counts even when the month closes positive); drives the Solvency runway warning
  and the "overdrawn in <month>" escalation
- `end_bill(bill_id, last_active_month)` - history-safe delete: set the bill's end
  month, leaving every earlier month (and archived snapshots) untouched
- `end_income(income_id, last_active_month)` - the same for income. Deleting the
  source instead would remove it from months it really did arrive in, which is
  why this exists and why the income dialog offers no way to turn a recurring
  income into a one-off
- `get_recorded_months()` → `list[YearMonth]` - months already snapshotted into the
  archive (drives the Archive tab)
- `archive_month(year_month)` - snapshot one month's generated bills and income into
  `months` / `month_bills` / `month_income` (idempotent; the internal archiving
  primitive)
- `auto_archive_elapsed_months(current_month)` - archiving is automatic, never manual:
  run at launch (alongside `apply_elapsed_limit_changes`), it archives every elapsed
  month up to the live month, filling any gap from the earliest recorded month so a
  month is captured the moment it ends even across several missed launches

**The repeat-forward assumption** (`_safe_to_spend_operations._missing_from`):
- Every income entered for the current month is assumed to arrive, then to
  arrive again in each later month with no entry of THAT NAME. It only fills
  gaps, so it can never reduce a month below what was entered for it.
  Matching is by name because a recurring source and a one-off live in
  different tables with unrelated ids
- It is NOT optional and there is no second, unassumed reading to select.
  There was: a `ProjectionBasis` enum with `KNOWN` and `REPEAT_CURRENT`,
  from when the bank page showed one figure and the projection page the
  other. Once the spendable figure moved to the projection page for good,
  every call passed `REPEAT_CURRENT` and the parameter selected between one
  behaviour and a dead one, so it went. One projection, one assumption,
  stated on the page that shows it
- It replaced a per-item "reliable" tick as the basis of the second reading.
  The tick still excludes income from the counted totals. An assumption
  nobody remembers to switch on is not a second reading, so the assumption is
  DERIVED from the shape of the current month
- **An ENDED income is never filled forward.** The rule exists to cover an
  absence of DATA (ad hoc money typed in only where it has already
  happened), so `_missing_from` also tests `is_active_in_month` on the
  target month and skips a source whose final month has passed. Without
  that test the rule resurrects income the user deliberately stopped and
  the spendable figure does not fall when an income ends, which is exactly
  when it must. Held by
  `tests/application/test_ended_income_not_repeated.py`; it is also why
  `test_income_month_bounds.py::test_the_spendable_figure_reads_the_ended_income`
  exists

**DTOs**:
- `MonthSummary` - `year_month`, `total_income`, `total_bills`, `bank_bills`,
  `balance`, `bills`, `all_bills`, `income_sources` (the counted set),
  `all_income_sources` and `assumed_income_sources` (active but not reliable,
  carried separately whether or not they were counted, so the gap
  specification can name them)
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

**Per-user database** (`budget_<username>.db` in the app data directory):
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
  3. `income_sources` - templates; `start_year` / `start_month` / `end_year` / `end_month` (migration) bound the months it appears in, all four nullable and all NULL on every row that predates them, so an upgraded database behaves exactly as it did
  4. `months` - one row per archived month (written by auto-archive at launch)
  5. `month_bills` - archived per-month bill snapshot
  6. `month_income` - archived per-month income snapshot
  7. `credit_cards` - includes `minimum_payment_percent` (migration)
  8. `settings` - key/value store (`bank_balance`, `bank_balance_day`,
     `bank_balance_date` (the fold baseline; legacy databases without it fall
     back to `bank_balance_day`), `currency`,
     `overdraft_limit`, `overdraft_apr_bp`, `safe_to_spend_floor`,
     `sustainable_window_months`)
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
  - `list_active_for_month()` - LEFT JOINs the per-month override, skip and
    received tables and filters on the month bounds, where a NULL on either
    side reads as unbounded
  - `IncomeMonthExtrasMixin` (`_income_month_extras.py`) - the one-off rows in
    `income_month_extras`, split out as a distinct concern from template CRUD
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

**Central users database** (`users.db` in the app data directory):
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

**`full_backup`** (`clear_budget/auth/full_backup.py`):
- Back Up Everything / Restore Everything behind File > Import / Export.
  File > Save covers only the active budget; `users.db` sat outside every
  backup path the app offered, so this module bundles the whole set into one
  zip: `users.db`, every `budget_*.db` and the `budgets_*.json` registry
  sidecars. Caches are excluded (regenerated) and so is the Remember-me
  sidecar, whose password lives in the OS keychain and cannot travel in a file
- `create_full_backup(app_dir, dest_path)` → the member names bundled
- `validate_full_backup(package_path)` → the member names, refusing a zip
  with no `users.db`, a stray member or a path-traversal name
- `restore_full_backup(package_path, app_dir)` stages first: members are
  extracted to `_restore_staging` inside the data directory, each budget
  database is schema-checked via `shared.db_validation` and `users.db` is
  confirmed to hold a `users` table; only then are live files replaced one by
  one. Strays and path-traversal names refuse the whole restore before any
  replacement. The caller must have closed every open connection (Windows
  refuses to replace an open database); `main.py` tears the session down,
  rebinds a fresh `UserStore` and returns to the sign-in screen
- Pure stdlib (`zipfile`, `sqlite3`, `shutil`) and inside the coverage gate;
  the UI flow (`ui/widgets/_full_backup_flow.py`: dialogs, unencrypted
  warning, double confirmation) sits outside it like the rest of the UI layer

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
  application layer may not depend on the UI), including the single-series role
  colours `SOLO_LINE` / `SOLO_BAR` / `SOLO_CURVE`, so an export and the screen
  agree on when the palette gives way to them. Fixed rather than following the
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

### Named budgets

One account owns SEVERAL budgets, each a whole database of its own: separate
bills, income, cards, overrides and settings. `budget_registry` is the record
of that set (`clear_budget/shared/budget_registry.py`), a per-user JSON sidecar
holding each budget's slug and display name plus which one is active.

- The design constraint was that an install predating the feature must open the
  same file it always did, with nothing moved and no migration step to get
  wrong. So the FIRST budget keeps the reserved empty slug, whose filename is
  the very `budget_<user>.db` that already exists; an absent or unreadable
  sidecar SYNTHESISES exactly that one record rather than failing. The sidecar
  is written the first time a second budget is created and not before, so the
  migration is that there is no migration
- Every failure mode of the sidecar collapses to that same single record: no
  file, bad JSON, the wrong shape, a budget list holding nothing usable, an
  active slug naming a budget that is gone. The databases are the data and the
  sidecar is only the map to them, so a lost map means "the one budget I can
  prove exists", never an error the user cannot act on
- A slug is a run-collapsed alphanumeric reduction of the name, so it can never
  itself contain the `__` that separates it from the username in the filename;
  colliding slugs are numbered apart. Renaming changes the name only, never the
  slug, so a rename never moves a file
- `main._open_user_database` is the ONE place that decides which file a session
  opens; it asks the registry. Switching budget is therefore a registry
  write plus the existing `database_replaced` signal, which already tore down
  and rebuilt a session for viewer-package import; no new session plumbing
- `File > New Budget` creates. It used to be a double-confirmed WIPE, because a
  user could own exactly one budget and the only way to hand them an empty one
  was to empty the one they had. That is the whole reason the destructive
  dialog existed and the whole reason it is gone
- Delete is disabled on the ACTIVE budget, which is a hard constraint rather
  than caution: this session holds that database open and Windows refuses to
  unlink an open file. It also means the last remaining budget can never be
  deleted, since it is always the active one
- Deleting an ACCOUNT deletes every budget it owns plus the sidecar
  (`delete_all_budgets`). Deleting only the legacy path, which was all there
  was to delete before, would strand the named ones in the data directory with
  no account able to reach them
- Read-only viewer accounts stay single-budget. A viewer's database arrives
  from an imported package and the account cannot write, so the button and both
  menu items are disabled exactly as Load and Save already are

### Shared Layer

**`Config`** (`clear_budget/shared/config.py`):
- `Config.default()` → legacy single-user path (`budget.db`) - kept for reference only
- `Config.for_user(username)` → `budget_<safe_username>.db`, the user's FIRST
  budget; identical to `for_user_budget(username, "")`
- `Config.for_user_budget(username, slug)` → `budget_<safe_username>__<slug>.db`,
  one named budget. The empty slug is RESERVED for the first budget and yields
  the unsuffixed legacy filename, which is why naming budgets moved no data
- `Config.budgets_index_path(username)` → `budgets_<safe_username>.json`
- `Config.users_db_path()` → `users.db`
- `Config.app_dir()` → the app data directory: `%LOCALAPPDATA%\ClearBudget`
  on Windows, `~/Library/Application Support/ClearBudget` on macOS,
  `$XDG_DATA_HOME/clearbudget` (default `~/.local/share/clearbudget`) on
  Linux. The pre-5.1 `~/.clearbudget` is PREFERRED for as long as it exists:
  its disappearance is the startup migration's completion signal
  (`shared/data_migration.py`), so a failed or interrupted move leaves the
  app running on the data it always had and retries next launch. The
  migration renames the whole directory when it can (atomic on one volume);
  otherwise it copies to a staging directory, verifies byte for byte,
  adopts the copy and only then retires the old directory, deleting the
  backup once the move has verified. A target already holding a `users.db`
  is a conflict (a downgraded launch recreated legacy data) and nothing is
  merged; the app keeps running on the legacy directory
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
- `build_centered_nav_header(...)` - the shared navigation tray used by all
  four tabs, built as TWO bordered rows and hoisted above the scroll area by
  `ScrollableTab`: the month or year cluster centred in the upper row, every
  icon button plus the four tabs in the lower one. The tray machinery itself (this builder, the app-icon
  graph button, the theme toggle and the glyph sizing) lives in
  `ui/utils/nav_header.py`, with the month/year label machinery in
  `ui/utils/nav_label.py`, the sun/moon toggle's glyph sizing and button in
  `ui/utils/nav_toggle.py` and the one glyph height they all read in
  `ui/utils/nav_glyph_size.py`; every one of them is re-exported through
  `format_helpers`, keeping each module clear of the LOC band with no call
  site moved. `nav_glyph_size` exists because the size is ONE number read
  from two modules that must never disagree, so it could not go on living
  inside either of them once they were split. The
  label carries its breathing room as a real `QLabel.setMargin` (never
  stylesheet padding, which is painted but not reliably in the size hints)
  and pins its minimum width to its text on every `setText` and recolour, so
  a tray squeezed at the window's width floor sheds pixels from the stretch
  space and the flanking buttons, never from the date (a 13in flatpak
  install used to clip the year's last digit).
  `apply_nav_label_color` / `_nav_label_style` recolour the
  label; the colour is each month's OWN within-month solvency health (current
  month from its live balance, a future month from its next-two-months block),
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
  window/taskbar icon, the splash image and the tab artwork across
  PyInstaller onefile (`sys._MEIPASS`), onedir (`_internal/`),
  beside-the-executable, dev repo layout and the working directory, with `.ico`
  preferred and `.png` fallbacks. Keeps every asset lookup robust however the
  app was packaged.
- Every sized-PNG lookup searches BOTH capitalisations. The repository ships
  `ClearBudget_256.png` (what `generate_icons.py` writes and what git tracks)
  while several build steps stage and several call sites ask for the
  lower-cased form; Windows and a default macOS volume hide the difference, a
  Linux or case-sensitive APFS volume does not. One tuple against a class of
  bug that can only appear on someone else's machine.
- `find_logo_png_path()` returns the largest bundled PNG, never the `.ico`,
  for callers that PAINT the icon into a widget: the nav tray's graph button,
  the About dialog and the sign-in dialog's logo, which had each grown their
  own copy of the same loop. It exists so that no caller resolves an
  asset by counting directory levels from its own module. One did so and was
  right on exactly one platform: the sign-in dialog reached three parents up
  for a 64px file that the Flatpak never stages and a PyInstaller bundle puts
  elsewhere, so the logo was silently absent on Linux and macOS. The
  `exists()` guard around it is what made the failure silent instead of
  loud.

### UI Layer

**ViewModels**:
- `MonthViewModel` - month state, signals: `month_changed`, `month_summary_updated`
- `SolvencyViewModel` - signals: `solvency_updated`, `danger_warning_triggered`
  - `set_month()` fetches new month summary before refreshing
  - `update_month_summary()` called after balance edits via `month_summary_updated`

**A tab is refreshed by the data it shows, not by the tab it sits on.**
`month_summary_updated` fires on EVERY change to the month's bills and income; it
drives both `SolvencyViewModel.update_month_summary` and
`CreditCardView.on_month_summary_updated`. The card tab needs it because its
figures are owned by another tab's data: a card's Payment Received, its closing
balance and the six-month strip are all computed from the `credit_payment` bill
that pays it; that bill is created and edited on Monthly Budget. Nothing on
the Credit Cards tab moves when that happens; switching tabs does not
recompute anything (`tabs.currentChanged` only marks the current tab), so
without this connection the tab showed figures calculated when the window was
built: a card paid off monthly projected a balance climbing past its own limit,
with Payment Received reading zero beside the bill paying it. Neither number was
wrong when calculated; neither was calculated again.
`CreditCardView.set_month` deliberately does NOT reload, because
`MonthViewModel.set_month` emits `month_changed` and THEN refreshes the summary,
so reloading there would be the first of two for one month change. The wiring
is held by `tests/structural/test_cross_tab_refresh.py`, a source scan rather
than a widget test because the suite is Qt-free.

**Row heights are measured, never chosen.** A table row is
`comfortable_row_height` (`ui/utils/text_metrics.py`): the polished widget's own
`QFontMetrics.height()`, plus the vertical chrome the stylesheet actually draws,
plus a comfort margin. The projection strip used to pin a literal 28 pixels. The
base font is 14pt, a 26 pixel line box with a 5 pixel descent; a header
section spends 4px padding plus a 1px border top and bottom, so 18 pixels were
left for 26 pixels of text: every descender was cut at the baseline and the
month column read "Auq 2026". The literal was not slightly small, it was
unrelated to what it had to hold.
- The chrome constants (`HEADER_SECTION_PADDING_PX`, `HEADER_SECTION_BORDER_PX`,
  `TABLE_ITEM_VPADDING_PX`, `TEXT_BREATHING_PX`) live in `theme_qss` and are read
  BOTH by the stylesheet f-string and by the height calculation, so the two
  cannot drift apart
- The row clears whichever of the header section or the cell spends more, since
  one height serves both the cells and the vertical header label
- `ensurePolished()` is not optional: a stylesheet `font-size` does not reach
  `QWidget.font()` until the widget is polished, so measuring too early silently
  returns the 9pt application default and reinstates the bug
- Applied by `apply_comfortable_rows` at every table's construction, so the
  height follows the font when the theme or `ui_scale` changes rather than being
  correct only at one display size

**Views**:
- `MonthView` - bill/income tables with inline editing; balance display adapts
  to current vs future month; composed of mixins (builders, table, edit, delete,
  apply-prompt) to stay under the LOC limit
- `SolvencyPanel` - two pages in a `QStackedWidget`: bank and projection. Each has a pilot button naming the ANSWER that page holds rather
  than the method behind it, which is why the second button reads "Switch to
  safe to spend" and not "Switch to projection": the bank page carries months
  ahead of its OWN, built from what is entered, so a button offering
  "projection" read as though those were the assumed months and made the
  entered figures look provisional. It also hid the figure most often wanted
  behind a word nobody goes looking for, which is why that button now leads
  the row. The button for the page being read is HIDDEN rather than disabled, so from
  anywhere each other page is one press away and the keyboard ring skips
  the control that would do nothing. The bank page carries account position,
  overall health and the two forward months, all of it built from money
  actually entered. Its first section is headed "Account Position" and NOT
  "Overdraft Status": a facility is optional and defaults to none, so with
  none arranged that section is not reporting on one at all, it is saying
  whether the balance stays above zero against a floor of zero. The old
  heading named a facility the reader may never have set up and made a
  healthy account read as though it were being measured against borrowing.
  The wording is true either way, so the heading does not move under the
  reader when a facility is added later. The banner BODY still names the
  overdraft, as it should: in a critical state ", with no overdraft arranged"
  is the fact that a payment bounces rather than drawing on something
  arranged. The banner is sentence case throughout, state prefix included
  ("Critical:", never "CRITICAL:"). The prefix still LEADS every line, since
  the word is what carries the state for a reader who does not take it from
  the fill, so it may be softened but never dropped. Capitals added nothing
  the word and the colour were not already saying; a line opening in shouting
  capitals reads as an alarm even in the Safe case, which is the one state
  that should read calmly. The palette key underneath is untouched, so
  the stylesheet and the traffic-light colours are unaffected.
- The MID-MONTH line beneath the banner (`_solvency_panel_midmonth.py`) reads
  its state the same way, against the agreed overdraft floor rather than
  against zero: a dip that stays inside an arranged facility is a Caution,
  since the facility exists to absorb it, while a dip beyond it (or any dip
  when none is arranged) is Critical, since that is a payment bouncing. It
  used to call every dip Critical, so a dip well inside an arranged overdraft
  was reported in the words of a bounced payment. It carries its state as a
  Qt property and lets the stylesheet supply the fill, exactly as the banner
  does; without that the strip kept its fixed danger red and a line reading
  "Caution" would have sat on a red field, moving the mismatch rather than
  fixing it. The base rule keeps the strong danger fill as the fallback,
  because the line only appears when there IS a dip, so the worse reading is
  the safer default if a state ever fails to resolve. The income day is named
  ONCE ("until the day-25 income lands"); it appeared twice in nine words
  before ("before day-25 income - rescued day 25")
  Guarded by `tests/structural/test_solvency_headings.py`, which scans for
  the WORD in any `_heading()` literal rather than pinning the replacement
  copy, so the principle survives a future rewording. The PROJECTION page carries the Safe to Spend
  Today headline (rendered by
  `_solvency_panel_safe_to_spend.SolvencyPanelSafeToSpendMixin` from
  `BudgetService.get_safe_to_spend`, which always repeats this month's
  income forward, reusing the banner's traffic-light state
  property; the secondary line names how far the promise reaches and the day
  that constrains it, "Holds every day through October 2026 above your £20.00
  buffer; constrained by 14 Oct", with a second line naming any month beyond
  that cannot be saved and stating that spending the headline deepens it; the
  banner takes the at-risk tone rather than the safe one whenever that second
  line is present, so a figure with a gap behind it never reads as an
  all-clear. `_sts_detail_lines` returns the two sentences SEPARATELY and they
  render into separate labels, because a QLabel carries one colour and the two
  are not the same kind of statement: the reach sentence keeps the muted body
  role while the shortfall takes `SolvencyShortfall`, the traffic light's own
  red. A gap no restraint closes is the one line on the tab reporting a fact
  rather than a caution; in one shared muted line it read as more small
  print under the sentence above it), the capacity schedule beneath
  it ("If you wait:" and one line per change, from `get_spending_capacity`,
  hidden entirely when the figure never moves so a flat month does not
  restate the headline) and beneath both the assumption in words with the
  months that follow from it. The BANK page's own contents are the overdraft
alert, the mid-month alert and its two forward-projection blocks. A third
page once carried per-card utilisation bars and the same two months per card.
It was removed: the Credit Cards TAB answers a card's position in full, so the
page restated another tab's job in a smaller space; keeping both meant two
renderings of the same figures to hold in step. Every month any page shows
  states its low
  point on a line of its own, plus what that month needs to hold flat, in one
  shape, whether or not the month is in trouble: a figure printed only for a
  month in difficulty makes the healthy months look as though they have none
  and leaves nothing to compare a worsening month against. A month can close
  in credit while running at a loss, which is precisely what a closing balance
  alone hides. The Overall Health line and every next-two-months block
  render that figure through ONE shared `_gap_clause()` helper
  (`_solvency_panel_narratives.py`), so the wording and the sign convention
  cannot drift apart between the two surfaces; each caller supplies its own
  subject, since one sits under a month heading already and the other does
  not. The forward blocks already had the number in hand as
  `monthly_drain_pence`, which until then only ever chose a traffic-light
  colour
- The projection page (`_solvency_panel_assumed.SolvencyPanelAssumedMixin`)
  runs the same month calculations on the repeat-forward assumption, painted
  in muted variants of the same traffic-light hues so it reads as provisional,
  with a gap specification from `get_assumed_expectations` naming what has to
  arrive and when. This mixin owns only the LOWER half of the page: the
  assumption in words, the gap specification and the two month blocks. The
  headline above it belongs to
  `_solvency_panel_safe_to_spend.SolvencyPanelSafeToSpendMixin` and is
  rendered outside `assumed_block()`. With nothing to assume it is the
  ASSUMPTION BLOCK alone that hides (its headings included), replaced by a
  line saying so; the headline stays, because a page reachable by a button
  must never be blank and the figure is defined whether or not there is
  anything to fill forward
- The spendable figure lives on the PROJECTION page and nowhere else. This is
  the settled position, reached by trying the alternatives. It sat on
  the bank page first, where a number printed beside entered balances reads as
  a fact about the account rather than as a promise about months that have not
  happened. Restating the bank page's figure on the projection page beside the
  assumed one was tried too, so the "lower than the known figure" line had
  both its terms; it was worse. The assumed figure is the SMALLER of the
  two, so the larger number under the words "already entered" read as an
  amount the user was free to spend instead. One figure, on the page whose
  assumption qualifies it, in the bank page's order: the number and its
  schedule, the assumption in words, what has to arrive for it to hold, then
  the months after this one
- The projection page's headline block is deliberately OUTSIDE
  `assumed_block()`, so it shows whether or not this month has anything to
  repeat forward. With nothing to assume the figure simply equals what was
  entered; hiding it there would leave the application with no spendable
  figure at all in the commonest case, which is every month filled in
- The assumed forward projection reads
  `BudgetService.get_assumed_month_summary`, which fills a later month's gaps
  from this month's income on the same rule `_build_safe_to_spend_inputs`
  applies per day. One statement of the assumption, two readings of it: a
  spendable figure and a
  month narrative on one page could otherwise disagree about the same month.
  Each month then goes through the SAME `_build_month_cashflow_summary` the
  bank page uses, so the two pages differ in their evidence and never in their
  arithmetic. `_month_cashflow_state()` returns the state key behind that
  builder's colour, so the muted rendering resolves the state rather than
  reverse-engineering a hex; `_overdraft_facility_outcome` returns a state key
  for the same reason (it previously returned dark-theme literals, which the
  light theme would have painted wrong)
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
- `LoginDialog` - username/password form, its logo resolved through
  `resources.find_logo_png_path` rather than a path built from this module's
  own location; a Remember me checkbox under the
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
  APR) plus the Safe to Spend Today buffer and the sustainable window (a spin
  box, 1 to 12 months, defaulting to 4); opened via Settings > Bank Account or
  the tray's bank button
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
- `IncomeDialog` - add/edit income source. Which controls appear depends on
  what is being edited, each labelled for the job it does there: adding shows
  `one_off_check` alone; editing a one-off shows it too, untickable to promote
  the entry to a recurring income; editing a recurring income shows
  `ends_check` with `end_month_edit` (worded exactly as `BillDialog` words its
  own) plus `scope_check` for how far this edit reaches. A note beneath states
  what OK will do before it is pressed. One checkbox used to carry two
  unrelated jobs, identity and edit scope, so it had to change meaning by
  context and was greyed with no explanation in the one context it could not
  express. There is deliberately NO control that turns a recurring income into
  a one-off: that would delete the source and so erase months it really did
  arrive in
- `BalanceDialog` - edit current bank balance; opens with the figure focused
  and selected for immediate overtype
- `ArchiveDetailDialog` - drill-down for a single archived month
- `HowItWorksDialog` - two jobs in one page. It NAMES the furniture, each
  entry led by the real icon the tray or the tab row draws, which the tabs
  now need because their text labels became pictures. Then it states the three
  rules the numbers rest on and that no screen can say for itself: how an
  undated bill accrues, how the balance maintains itself, what Safe to Spend
  Today promises. The tab icons are the BUNDLED IMAGES, inlined through the
  same `find_tab_icon_path` the tab row uses rather than described in words or
  approximated with a similar-looking emoji; an icon guide showing something
  other than the icon is worse than none. Length is the recurring failure
  here. A button-by-button inventory was tried and read as a wall of text;
  the essay that replaced it explained every rejected design alongside the
  shipped one. Anything a control says for itself is left to the control
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
  remembered location (first save prompts, defaulting to the app's own data
  directory via `ui_paths.default_data_dir`, then asks before overwriting); Load validates via `db_validation` and confirms before
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
- `_month_view_delete_mixin.py` (`MonthViewDeleteMixin`) - the delete
  confirmation flows. Bills and income share one stop-from-month vs
  delete-entirely choice, so the two sides of the ledger behave alike. A
  one-off income is exempt and simply confirms: it exists in one month, so
  stopping it from that month and deleting it are the same act
- `_month_view_income_convert.py` (`MonthViewIncomeConvertMixin`) - promoting a
  one-off income entry to a recurring source. The two live in different
  tables, so it is a delete plus an add rather than an update; it
  confirms first. Only this direction exists; the reverse would rewrite
  history
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
- Each view's `nav_targets()` is the DECLARED ring order for its tab and it is
  READING order, which with two stacked trays means the UPPER tray first and
  the lower one after it, each left to right as drawn, then the page's own
  controls. Two views override that with TASK-FLOW order by decision
  (2026-08-24): Solvency places its visible pilot button just before the
  Credit Cards tab (page turn, then next tab) and Credit Cards runs its card
  panels (Active toggle, Edit, Delete per card) then Add Card between the
  tab run and the graph icon, because the cards are what the tab is opened
  for. Both overrides are deliberate and documented at the declaration.
- A view may declare `nav_entry_stop()`: the control the FIRST Tab lands on
  when the ring is entered from neutral (launch or a tab switch). Solvency
  names its visible pilot; Credit Cards names the first card's Active toggle
  (Add Card when there are no cards); Monthly Budget and Archive keep the
  default menu-first entry. `MainWindow._current_nav_entry` hands the
  navigator a callable and `KeyboardNavigator._entry` prefers the declared
  stop on forward entry only; backward entry and every fallback keep the
  ring's ends. The tab switch still restores the NEUTRAL sink (nothing is
  highlighted); the entry stop decides only where the first press lands. The
  switch handler also clears the menu-bar highlight, because a title left
  active outlives the focus move (the bar even reclaims focus for it) and the
  ring would resume from the menu instead of entering at the declared stop.
  Wiring held by `tests/structural/test_nav_entry_invariants.py`; behaviour
  by an offscreen probe
- Turning a Solvency page (`_show_page`) hands focus to the surviving pilot,
  the one that reverts, so flicking between the two readings costs one key
  per flick; at build time the panel is not yet visible and the neutral
  start stands
- The card Active toggle is a QCheckBox drawn as a pill-and-knob slider
  (`switch_images.py`, the spin-arrow image pattern: generated per theme
  colour into the app data directory, because a checkbox indicator has no
  knob subcontrol for QSS to draw). Its ring stays the widget's own border
  (hover/focus the ring colour, disabled red), because a widget-state-then-subcontrol
  selector is parsed and silently ignored A ring that disagrees with the
  drawing does not present as a wrong order, it presents as a SKIPPED control,
  because the user tabs past where a button visibly is and lands somewhere
  else. Two of the four declarations were already one pair out (the graph
  button was offered before Previous while it is drawn after it) and the tray
  rearrangement would have made all four wrong. Verified by mapping every
  tray stop's centre to (row, x) and requiring ascending on all four tabs, plus
  a check that no enabled, visible tray button is missing from its declaration
  bar the current tab, which is correctly not a stop. That measurement is a PROBE rather than a test, because the
  suite is Qt-free by design and ring order is geometry
- One application-level `KeyboardNavigator` event filter drives an explicit
  focus ring: menu-bar titles, then the active tab's stops (each
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
  to be added. That policy is `TabFocus`, never `StrongFocus`: `StrongFocus`
  also grants CLICK focus, so clicking anywhere on a page background put the
  ring round the whole panel even on a page that does not overflow and is
  therefore not a stop at all (measured: `nav_scroll_stop()` returned None
  while the panel wore the ring). Focus may only arrive here from the ring,
  which already skips a page that fits. Left and Right deliberately still STEP THE RING here rather than
  scrolling horizontally, unlike the general scrollable-region rule: nothing in
  this app scrolls sideways and Left/Right stepping everywhere is what stops
  focus being trapped. The stop paints the same ring on focus and none at
  rest (measured: 0 pixels at rest, ~2980 focused, both themes), with no hover
  rule, since the pointer sits over the page most of the time the app is open
- EVERY TAB IS A STOP on the ring, which now costs nothing to say: the
  tabs are ordinary buttons in the navigation tray, so each is a stop like any
  other. Walking the ring moves focus and switches nothing; Enter or Space
  commits. The tab already showing is dropped from the declaration
  (`ring_tab_stops`) rather than disabled, since a disabled control paints the
  permanent red ring and would read as broken rather than as current
- This used to need a `QTabBar` subclass, `NavTabBar`, carrying a keyboard
  cursor separate from the bar's selection, plus a pair of walking helpers in
  `_tab_cursor` (one wrapping for Up and Down, one bounded for Tab so the ring
  could not be trapped in the strip) and a cursor ring painted by hand on the
  pill geometry the stylesheet drew. All of it existed to work around one Qt
  behaviour: a `QTabBar` ties its focus to its CURRENT tab, so a focused bar
  can only ring the tab the user is already on, which is a dead stop. A button
  carries no such tie. When the tabs moved into the tray the whole mechanism
  became unreachable and was deleted rather than left as a hidden bar nobody
  drives
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
- A TAB SWITCH returns to that same sink. Switching hides the control that was
  clicked, so Qt hands its focus to whatever the newly shown page offers next
  in its chain; that control then wore the ring beside the current tab's
  accent border and the tray read as two tabs being current at once. Qt has
  already moved the focus by the time `currentChanged` arrives (measured, not
  assumed), so the handler sets the sink last and nothing overwrites it. A new
  page starts neutral for the same reason the window does. Guarded by
  `tests/structural/test_tray_switch_invariants.py`, which asserts the signal
  is connected AND that the handler it names touches the sink, because a
  connection to a handler that had stopped focusing anything would otherwise
  read as wired
- Ring colours are three-state, enforced in the QSS: no ring at rest, the ring
  colour while an enabled control is hovered or focused, a permanent red ring
  while disabled (hover/focus rules are gated on `:enabled`)
- `ring` is a BORDER colour and nothing else. Every solid fill it used to
  double as has its own `checked_fill` token: the checked state of a checkbox,
  the same on a table indicator, the on position of a switch track. One value could
  not make both statements, because a border saying "focus is here" is a cue
  while the same colour as a filled block saying "this is on" is glare. That
  collision is what made a ticked box the loudest thing on the login screen
- `_credit_card_view_loaders.py` - builds the per-card panel list (`_build_card_frame`)
  for the Credit Cards tab

**Tab icons** (`ui/utils/tab_icons.py`):
- The four primary tabs carry a picture and no text; the text moved to the
  tooltip, so the row still names itself on hover and nothing was lost but
  four labels wide enough to push the tabs across the window
- Three are bundled PNG masters (`monthlybudget.png`, `solvency.png`,
  `creditcards.png`, resolved by `shared.resources.find_tab_icon_path` through
  the same candidate roots as every other asset) and the fourth is an emoji.
  Those are different KINDS of image sized by different rules, so both are
  reduced to one question, how tall the thing actually PAINTS, answered by
  measuring opaque pixels in each case (`glyph_metrics`)
- An image is cropped to its opaque content, then fitted by its HEIGHT. The
  scale that lifts it lives in `nav_glyph_size.NAV_GLYPH_SCALE` now, applied to
  the measured box before anything reads it, so the tray's own icons take it
  too; `TAB_IMAGE_SCALE` is 1.0 because scaling again here would put the tabs
  back above their neighbours. Fitting to a square box by the LONGER side
  was tried first and is what a picture-and-glyph row must not do: the
  calendar came out 42 tall and the cards 35 against the emoji's 46, so the
  pictures read small; worse still, their BASES sat high. A row of icons that
  do not share a bottom edge reads as badly set rather than as differently
  sized. Fitting by height puts every icon on one baseline by construction;
  the landscape card artwork running wider than its neighbours is the accepted
  cost, since a shared bottom edge is what the eye checks along a row
- `TAB_EMOJI_SCALE` is held EQUAL to `TAB_IMAGE_SCALE`. It mattered when the
  scale lifted the tabs alone: an archive glyph left at the smaller size read
  as the runt of the four. The two are equal at 1.0 now, since the box arrives
  pre-scaled, so the rule holds without either doing any work. The archive
  glyph is a tab first and an emoji second, which is why it still does not
  follow `nav_header.TOGGLE_GLYPH_SCALE`
- EVERY icon in the tray paints at the same height; every button holding one
  is the same size. The scale used to be the tabs' alone, which left the
  load, save, switch, users, preferences, bank and help icons painting 47
  against the tabs' 63 in the same band, a third smaller. Moving the scale to
  the base fixed all of them at once. `NAV_ICON_BTN_PADDING_PX` went to zero in
  the same pass, since a tray button carrying that padding was 8px taller than
  a tab holding an icon of exactly the same height
- A tab whose icon cannot be built keeps its label as visible text. A missing
  asset costs the tray its looks, never a route into the tab
- The tabs are BUTTONS in the navigation tray (`build_tab_buttons`), not a
  `QTabBar`. The `QTabWidget` is kept for what it is good at, owning the pages
  and switching between them; its bar is hidden. Every view builds its own
  four buttons because every view builds its own tray; `MainWindow` wires them
  all to the one tab widget and marks the current tab on every set at once, so
  the mark is right whichever tray is on screen
- That SIMPLIFIES the keyboard model rather than complicating it. `NavTabBar`
  existed because Qt ties a tab bar's focus to its CURRENT tab, so a focused
  bar could only ever ring the tab the user was already on, a dead stop; it
  carried a separate cursor to work around that. A button has no such tie, so
  walking the ring moves focus and changes nothing while Enter or Space
  activates and switches, which is exactly what the cursor was built to fake.
  The current tab is dropped from the ring declaration (`ring_tab_stops`)
  rather than disabled, because a disabled control paints the permanent red
  ring and would read as broken rather than as current
- The current tab is marked with a panel FILL and nothing else, through a
  dynamic property plus a repolish (`mark_current_tab`), never an inline
  stylesheet: an inline colour survives a theme switch and leaves the mark
  painted in the outgoing theme. It was a full accent rectangle once; at 2px
  the accent was indistinguishable from the ring, so on launch the current tab
  read as though it were hover-focused. It then carried a fill plus an accent
  underline, which was one mark too many. Rectangles stay the ring's own
  vocabulary (the ring colour on hover or focus, red when disabled) and the
  current tab's border is fully transparent, so the two can never be confused

**Sign-in and remembered accounts**:
- `auth/remembered_login.RememberedLogin` - remembers sign-in details PER ACCOUNT,
  never one slot for the machine. The JSON sidecar holds only which accounts are
  remembered and which asked for a password kept; the password itself lives in the
  OS credential store through `keyring`, reached behind the `SecretBackend`
  Protocol so the suite drives a hand-written fake. It also reads the earlier
  single-account file, which is on every machine the app has already run on
- `ui/widgets/login_dialog.LoginDialog` - offers a dropdown once more than one
  account is remembered and a plain field otherwise, with two independent ticks
  (username, password) applied on a completed sign-in
- `ui/widgets/reset_password_dialog.ResetPasswordDialog` - split out of
  login_dialog.py for the 400-line limit; imported where it is used so the two
  modules need not import each other
- `ui/widgets/_login_styles` - the field, dropdown and link styling the four
  sign-in-shaped dialogs share, resolved when a dialog is BUILT so it follows
  the theme in force. The username dropdown styles the COMBO rather than its
  inner line edit: styling only the child left an unthemed control whose edit
  fell back to a point-sized font too tall for the box, which clipped the name
  it was showing

**Who is signed in**:
- The account name sits at the left of every tab's month tray, built by
  `ui/utils/nav_header._build_nav_user_pair` and filled by `MainWindow` through
  `set_nav_user`. It is set on the HEADER, never the view: `ScrollableTab`
  lifts the header out of its view so it spans the full tab width, which
  leaves the label no longer a descendant of that view
- An empty MIRROR of the label sits at the far right of the same row, kept the
  same width, so the month cluster stays centred on the WINDOW rather than on
  what the name leaves behind (which would drift per account)
- `ui/utils/nav_label.NavUserLabel` caps its own width and elides a name that
  does not fit, putting the whole of it on the tooltip. Its size hint is
  measured from the FULL text: taken from the drawn text it collapses to an
  ellipsis and never recovers. Its minimum hint matches, because a hint alone
  gets shaved under width pressure
- `tests/structural/test_nav_user_label.py` pins all of it, including that the
  title bar no longer names the account

**Main Application**:
- `MainWindow` - all tabs in `ScrollableTab`; signals: `switch_user_requested`,
  `sign_out_requested`, `database_replaced`
  - File menu: New Budget and Switch Budget, then Load / Save / Save As (Save
    goes to the remembered save file, kept in `ui_settings.json`), then the
    "Import / Export" submenu (Read-Only Viewer Package export/import, then
    Back Up Everything / Restore Everything, all admin only), Exit; a full
    restore travels the `full_restore_requested` signal to `main.py`, which
    tears the session down before touching a file
  - Settings menu (adjacent to File): Preferences, Bank Account
  - Every combo box is a `ui/widgets/themed_combo_box.ThemedComboBox`, which
    paints its own arrow; `ui/_theme_inputs` makes `QComboBox::drop-down`
    transparent. The two halves only work together: Qt draws that subcontrol
    as a square native button over the right end of the field, so it paints
    across the corner the border-radius rounds; the one rule that stops it
    also stops the platform drawing the chevron. A plain `QComboBox` would
    still work and simply have no arrow, so
    `tests/structural/test_combo_box_invariants.py` pins that none is built
  - Users menu: Switch User and Log Out for every account; admins also get
    Manage Users (list, Add User, Delete Selected). The two ways out are
    separate signals on purpose and differ only in what a cancelled sign-in
    does. `switch_user_requested` SUSPENDS: `main.py` hides the window, keeps
    its database open and keeps tracking it, so a cancel shows it again.
    `sign_out_requested` ENDS: `main.py` destroys the window and closes the
    database, so a cancel finds no live session and quits. Pinned by
    `tests/structural/test_session_exit_invariants.py`, because crossing the
    two signals raises nothing and shows only as a cancelled switch quietly
    closing the application
  - Account and session handlers live in the `MainWindowAccountMixin`
    (`ui/_main_window_account.py`), alongside the menu and navigation mixins
  - The nav tray is TWO stacked trays, built together by
    `nav_header.build_centered_nav_header`, because they answer different
    questions. The UPPER tray carries only what is about the month being
    viewed: Previous, the month and year, then Next. The app icon used to sit
    here too. It OPENS the month graph, which acts on the application, while
    this row only says which month is being read; it moved down to sit
    with the tabs it is sized against. It holds nothing else, so a stretch either side centres it
    exactly. The LOWER tray carries everything that acts on the application,
    built by `_save_load_flow.build_save_load_buttons` /
    `build_budgets_button` / `build_settings_bank_buttons` /
    `build_info_button` and sized against the
    tab buttons: folder (Load), diskette (Save), arrows (Switch Budget),
    cog (Preferences), bank (Bank Account), a themed separator, then Monthly
    Budget, Solvency and Credit Cards, then the app icon that opens the month
    graph. Archive is pinned to the RIGHT of the stretch, beside the sun/moon
    toggle and the blue information button (How It Works). The separator
    divides the five controls that DO something from the tabs that only decide
    which page is being looked at
  - Every view builds its OWN tray, so the graph icon is built per view and a
    view that never calls the builder loses the capability silently: the tray
    still draws and the app still runs, with the month graph simply gone from
    that tab. Solvency lost it exactly that way. Every view that plots
    something builds the button and lists it in `nav_targets()`, guarded by
    `tests/structural/test_tray_switch_invariants.py`. Archive is excluded on
    purpose, since it plots nothing. Solvency draws the BANK series the Budget
    tab draws, because both tabs answer the same question about the same
    account and two tabs disagreeing would read as two accounts
  - The graph icon takes the same height as the three tab pictures, because it
    is drawn INSIDE that run. That used to need `TAB_IMAGE_SCALE` and now comes
    from the pre-scaled box every icon in the tray shares. Left at the tray's
    old bare glyph height it
    painted 46 tall against their 62 and its base sat 8px above theirs; a row
    of icons that do not share a bottom edge reads as badly set rather than as
    deliberately varied, which is the effect that constant exists to cure.
    Verified by measuring every icon's bottom edge in window coordinates on
    all three tabs that carry one
  - `build_centered_nav_header` SKIPS a None entry rather than passing it to
    `addWidget`. `build_graph_icon_button` returns None when the app icon
    cannot be resolved, so that a missing asset costs the tray one control
    rather than the window; without the skip that None took the application
    down at startup, which is the failure the None was there to avoid
  - Two trays rather than one row is what makes the centring free. In one row
    the cluster could be centred only by reserving the icon run's width again
    on the empty side. Two runs plus the cluster do not fit at the window's own
    width floor, so what gave way was the cluster: "Previous" came out as
    "Previo" and the year lost its last digits, which is the one thing the tray
    must never shed (`nav_label` pins its own width for the same reason). Give
    the cluster a row of its own and the arithmetic disappears rather than
    being balanced
  - Tray glyphs are drawn at the Previous button's height, UNSCALED. A 0.75
    factor lived in `nav_glyph_height` briefly, while the tabs were still a
    strip of their own and the tray was the heaviest band on the window. With
    the tabs now IN the tray, the tray is the band, so the icons are back at
    the height they started at
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
    exclusive `fcntl` advisory lock on a file in the app data directory on macOS and Linux
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
  `theme_tokens.py`; the sun/moon toggle in every nav tray's icon run
  switches them at runtime (`theme.toggle_theme`) and the choice persists in
  `ui_settings.json` in the app data directory, applying from the login
  screen onward
- The toggle's emoji is sized to MATCH the nav icon, both from
  `format_helpers.nav_glyph_height` (the Previous button's height). One source
  because the two are built in different functions, which is how they drifted
  apart in the first place. The font is applied as a WIDGET-level stylesheet,
  not `setFont`: the app stylesheet sets `font-size` on `QWidget` and any
  stylesheet rule beats `setFont`, so the size was silently ignored. A widget's
  own sheet beats the application's and setting only `font-size` leaves the
  object-name ring rules intact (verified: 0 ring pixels at rest, 385 ring-coloured
  on focus, 380 red when disabled). The rule MUST carry a selector
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
  colour made a hovered tab read as a second, slightly different selection, two
  near-identical shades on one strip. `tests/ui_logic/test_highlight_text_colour.py`
  holds every one of those surfaces to it. The keyboard cursor's tab is the one
  exception and keeps muted text under its ring, because the cursor marks
  where the keyboard is rather than what is live; Qt gives no way to say
  otherwise anyway (measured: with a stylesheet active, `setTabTextColor` is
  ignored entirely)
- The sheet is split by surface across `_theme_tabs.py` (down to the pane, the
  card the tab content sits on), `_theme_inputs.py` (the fields
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
- Ring colours per theme follow the three-state model (the ring colour on hover or focus when
  enabled, permanent red on disabled, none at rest); `outline: none` on the
  base rule keeps the ring as the only focus indicator
- Object-name rules for the nav tray, nav graph button, theme toggle and the
  status-bar date label live in `_theme_controls.widget_extras_qss`; the
  semantic label roles (`_theme_labels.label_roles_qss`, named in
  `label_roles.py`) carry every other text colour. A widget takes a role by
  object name instead of an inline stylesheet, which is what lets a live
  theme switch restyle it: `label_roles.set_role` repolishes when a severity
  role changes at runtime (a balance turning from good to danger)
- The tab strip carries no rules at all: the bar is hidden and the tabs are
  `QPushButton#NavTabButton` in the tray, styled in `_theme_controls` with the
  rest of the tray. `_theme_tabs` is down to the pane, the card the tab
  CONTENT sits on. One Qt fact is worth keeping from what was deleted, because
  it costs an afternoon to rediscover: in a subcontrol focus rule the
  subcontrol must come FIRST (`QTabBar::tab:selected:focus` works, while the
  widget-state-first `QTabBar:focus::tab:selected` is parsed and then silently
  ignored, no warning and no effect)
- Spin-box arrows are IMAGES, generated per colour (`spin_arrows.py`), not CSS
  triangles. Qt's stylesheet engine does not implement the `width: 0` plus
  transparent-side-borders idiom: it honours the zero size, draws nothing and
  leaves the button box, which is why the year pickers showed two empty
  rectangles (measured: the up button was 366 pixels of one flat colour).
  `image: url(...)` is Qt's only stylesheet route to a glyph there. The images
  are drawn into the app data directory's `arrows/` and cached under a filename made from
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
- A chart plotting exactly ONE series takes ROLE colours instead of the series
  palette: the line light blue (`chart_line_colour_for`), the bars the SAFE
  colour at or above zero (`chart_bar_colour_for`, `#b8a1d9` dark / `#6b4c9a`
  light) and the curve over those bars light blue (`solo_curve_colour_for`).
  Amber (`chart_bar_within_facility_colour_for`) is the WITHIN-FACILITY state
  below, never the resting bar fill. The LINE carries no verdict, because
  one stroke spans the whole month and a safe colour there read as a positive
  balance over days that were not. A BAR is one day, so the safe colour is
  honest on it: a bar fills with it only where that day's value is at or above
  zero and keeps the danger red below it, which is why the two marks take
  different colours from the same rule
- The safe colour is a muted lavender, not a green. The green it replaced was
  bright enough to glare at a lightness of 52%; it was also the same literal as
  the focus ring, so neither role could move without the other. Splitting them
  is what allowed the ring to go neutral and the bar to go lavender in one pass
- Green and teal are retired app-wide. The ring and the accent were the last
  two holdouts and they parted company at the same time: the ring is CHROME, so
  it went to a near neutral that says the system is responding without claiming
  a meaning, while the accent is IDENTITY (section titles, the current-tab
  underline, the progress bar) so it kept a hue. `primary_text` is the one white
  that did not collapse into `text`, because a button label on a saturated blue
  measures 4.00:1 in the softer white against 4.95:1 in pure white
- The multi-series palette's first slot is a near neutral, because the lavender
  sits ten degrees from the violet already in the palette and two cards must
  never wear one face; a near neutral is told apart by saturation, which none
  of the other seven compete for
- A bar carries THREE states, not two, read against the agreed overdraft floor
  rather than against zero: the safe colour at or above zero, amber below zero but no
  further than the arranged facility, red past it. That is the banner's own
  reading applied to one day, so the graph and the banner above it never
  describe the same position in two different colours. The floor reaches the
  chart through `LineBarChart.set_overdraft_limit_pence` and the exporter
  through `chart_svg(floor_pence=...)`; both default to ZERO, meaning no
  facility, which collapses to the old two-state red-below-zero behaviour. A
  CARD graph never passes one, since an overdraft is a bank arrangement
- The limit is NOT re-resolved in `paintEvent`, where the colours are. The
  colours follow the theme so they must be re-read per paint; the limit is
  data a caller set, so re-reading it there zeroed it on every repaint and
  painted every below-zero bar red however large the facility was. Caught by
  a probe that counts painted pixels rather than by reading the branch back Light blue and amber carry no
  such reading. The rule is keyed on series COUNT, not on which view opened the
  chart, so the credit-card graph (one series per card) keeps the palette,
  because telling the cards apart is the whole job of colour there; its curve
  keeps the magenta that holds it outside the palette. Negative values are
  unaffected either way: a below-zero bar stays `danger` red, since that is a
  state colour rather than a series one
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

All files live in the app data directory: `%LOCALAPPDATA%\ClearBudget` on
Windows, `~/Library/Application Support/ClearBudget` on macOS,
`$XDG_DATA_HOME/clearbudget` (default `~/.local/share/clearbudget`) on
Linux; a surviving pre-5.1 `~/.clearbudget` is still used until its
startup migration completes.

| File | Purpose |
|------|---------|
| `users.db` | Central user accounts (all users) |
| `budget_<username>.db` | The user's FIRST budget (the reserved empty slug), the filename that predates named budgets |
| `budget_<username>__<slug>.db` | One database per additional named budget |
| `budgets_<username>.json` | The registry sidecar: that user's budgets and which is active. A map to the databases, never the data itself |
| `ui_settings.json` | Theme, remembered save-file location and any skipped update version. No budget data |
| `remembered_login.json` | The Remember me username (the password is in the OS credential store, never on disk) |
| `arrows/`, `switches/` | Generated per-theme images (spin-box arrows, the card toggle slider); regenerated on demand |
| `logs/` | Application log directory |

The first three are what `full_backup` bundles; the generated images and the
Remember-me sidecar are deliberately excluded (regenerated; a keychain
password cannot travel in a file).

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

ClearBudget is a single PySide6 codebase that ships as a native package on
Windows, macOS and Linux. The application layers carry no OS-specific logic;
platform differences are isolated to a few well-defined seams:

- **Single-instance lock**: per-OS implementation in `main.py` (named kernel mutex
  on Windows, `fcntl` advisory file lock on macOS and Linux).
- **Data directory**: `Config.app_dir()` resolves to each platform's
  conventional application-data location (see Database Locations); all
  databases and the lock file live there. A pre-5.1 `~/.clearbudget` is
  migrated at startup by `shared/data_migration.py`.
- **File-dialog defaults**: `ui_paths` uses Qt `QStandardPaths`, so dialogs open
  in the correct per-OS location.
- **Runtime assets**: `shared/resources.py` discovers icons, the splash image
  and the tab artwork across frozen (PyInstaller) and source layouts. Every
  caller that paints the app icon goes through `find_logo_png_path`; three
  modules had each grown their own copy of the same "first PNG in the
  candidate list" loop while a fourth (the sign-in dialog) had not, which is
  how its logo went missing on two platforms.
- **What the app bundle carries**: ONE sized PNG (the 256), the `.ico`, the
  three tab images and VERSION. It used to carry all seven sizes plus the
  1024 master. Since every consumer takes the first PNG from one ordered list
  and the 256 heads it, the smaller five could never be selected by any code
  path; the master appears in no lookup table at all: they shipped and
  were never read. The SETUP program keeps its own full set, which its own UI
  genuinely reads at several sizes. It also DEPLOYS that set (the seven sized
  PNGs plus the `.ico`) beside the installed executable
  (`ops/registration.py` over `APP_ICON_PNG_NAMES`), as a Qt runtime fallback
  for the window and taskbar icon where the ICO plugin is unavailable. So an
  installed directory holds all seven while the PyInstaller bundle inside it
  carries one; the two counts differ on purpose and neither is a leftover.
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
  to produce "Please close ClearBudget and click Retry". The setup program now
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
entry: ClearBudget has no such feature, so an installer switch for it would be
a product decision rather than a packaging one.

**The installer never touches user data.** Install, repair, reinstall and
uninstall all deal in program files, shortcuts and the registry entry only, so
the data directory survives every one of them and a reinstall carries on from
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
- Pure UI-layer logic is still covered without Qt under `tests/ui_logic`,
  twelve modules covering the Solvency month-colour rule and its low-point
  line (by instantiating the mixins directly), the spendable headline's reach
  and shortfall sentences, the projection page's gap specification,
  the income one-off and edit-scope rules, the bill amount-change entry,
  inline edits, highlight colour, theme and save-location persistence, the
  skipped-update record and the window-geometry arithmetic. What lands here is logic a widget happens to host, extracted far
  enough from Qt to be asserted on: where a mixin's method reads a widget, the
  state arrives as an argument instead so the decision can be made without a
  `QApplication`
- The UI layer is excluded from the coverage gate (see `.coveragerc`)
- Anything that must be seen rather than asserted (a painted ring, a glyph
  against an icon, a window's placement on a monitor) is measured with an
  offscreen probe outside the suite. Measure emoji and font sizes on the REAL
  platform though: under `QT_QPA_PLATFORM=offscreen` Qt substitutes its own
  font database and the answer does not describe the shipped app

### Setup Program
- `tests/installer/` covers everything under `installer/` except `app.py` and
  `installer/ui`, at 100% line and branch
- `conftest.py` carries four isolations, each guarding one way a test could
  reach the real machine. THREE are autouse: the profile directories are
  redirected through the environment variables the code reads; the
  platformdirs lookups the legacy migration makes are redirected in their own
  right, because platformdirs asks Windows for the known folder rather than
  reading `%LOCALAPPDATA%`; and the payload anchor is redirected so a small
  stand-in bundle replaces the real fifty-megabyte payload. The fourth,
  `scratch_identity`, is requested by name: it yields an `InstallerIdentity`
  whose HKCU key lives under a test-only root and is deleted in teardown;
  a test reaches the registry only by taking it
- `fakes.py` holds the hand-written doubles for the three seams. No mocking
  library is used
- What is exercised for real is exercised for real: shortcuts are written
  through the same Shell Link COM interface the install uses (into the
  redirected profile), the registry round-trips through `winreg` against the
  scratch key; a full install deploys and registers a real bundle

### Structural Tests
- `test_layering_rules.py` - AST-based forbidden import enforcement
- `test_loc_limits.py` - no file over 400 LOC and none in the 381 to 399
  danger band, so a file is never shaved to just under the cap only to break
  it again on the next edit
- `test_auth_structure.py` - Auth layer structure validation
- `test_data_dir_isolation.py` - the suite cannot resolve the real data
  directory (legacy or platform), only `shared/config.py` derives it, the
  installer never names it and `main()` migrates before the lock, never
  under the override. A `conftest.py` autouse fixture points `CLEARBUDGET_HOME` at a
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
