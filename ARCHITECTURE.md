# ClearBudget Architecture

ClearBudget is a local-first PySide6 desktop budgeting application built as a
clean architecture: UI, Application, Domain and Infrastructure, with `auth` and
`shared` packages beside them and a bespoke setup program under `installer/`.
Why the design is shaped this way lives in
[DECISIONS-TRADEOFFS.md](DECISIONS-TRADEOFFS.md); this document says what the
structure is and which test holds each rule.

## Invariants

The rules the design turns on. Each is enforced by a test, named beside it.

| Invariant | Enforced by |
|-----------|-------------|
| Dependencies point inward: UI -> Application -> Domain <- Infrastructure. The Domain imports nothing but `shared` and no I/O, threading, network, logging or UI-framework module. Application never imports Infrastructure or the UI. Infrastructure never imports the UI (it may import the Application ports it implements). The UI never imports Infrastructure except `ui/window_builder.py`. The UI importing the Domain directly is recorded in [TECH_DEBT.md](TECH_DEBT.md) | [`tests/structural/test_layering_rules.py`](tests/structural/test_layering_rules.py) |
| `auth` imports only `auth`, `shared`, the standard library and `bcrypt`; never the Domain, Application, Infrastructure or UI | [`tests/structural/test_auth_structure.py`](tests/structural/test_auth_structure.py) |
| No source file exceeds 400 lines; none sits in the 381 to 399 danger band (a file refactored down lands at 350 or below) | [`tests/structural/test_loc_limits.py`](tests/structural/test_loc_limits.py) |
| Only `shared/config.py` derives the real data directory. The suite never resolves it and no installer module names it | [`tests/structural/test_data_dir_isolation.py`](tests/structural/test_data_dir_isolation.py) plus the autouse `CLEARBUDGET_HOME` fixture in `tests/conftest.py` |
| The legacy data-directory migration cannot lose data: it is one rename on the same volume, otherwise a copy verified before the old tree is retired; the old tree stays in use until then. It runs at startup before the single-instance lock, never under the override | [`tests/shared/test_data_migration.py`](tests/shared/test_data_migration.py) and `test_data_dir_isolation.py::TestTheMigrationRunsFirstAtStartup` |
| An open database is never copied as a file: it is snapshotted through SQLite's backup API and replaced only after its connection is closed, in `main.py` alone. A Load keeps the displaced budget until the loaded one opens | [`tests/shared/test_db_copy.py`](tests/shared/test_db_copy.py), [`test_db_copy_keep.py`](tests/shared/test_db_copy_keep.py), [`tests/structural/test_database_replacement_order.py`](tests/structural/test_database_replacement_order.py) |
| A full restore that cannot complete changes nothing: every member is staged and validated first; a failure part way puts each live file back with its SQLite sidecars | [`tests/auth/test_full_backup.py`](tests/auth/test_full_backup.py), [`test_full_backup_hostile.py`](tests/auth/test_full_backup_hostile.py) |
| A budget belonging to no restored account (or lying under a name a new account takes) is moved to `quarantine/`, never deleted | [`tests/auth/test_full_backup_estate.py`](tests/auth/test_full_backup_estate.py), [`test_user_store_new_account.py`](tests/auth/test_user_store_new_account.py) |
| A budget list cannot lose budgets: an unusable list is rebuilt from the files on disk, an unsafe slug is dropped on read and the list is written whole | [`tests/shared/test_budget_registry_recovery.py`](tests/shared/test_budget_registry_recovery.py) |
| Two accounts can never share one budget file: `UserStore.create_user` refuses a name whose safe file form collides with an existing account | [`tests/auth/test_user_store.py`](tests/auth/test_user_store.py) (`TestUsernamesThatWouldShareOneBudgetFile`) |
| Another account's budget opens only behind that account's password and can never be saved over. Ownership is a stamp inside the database, falling back to the file name | [`tests/shared/test_db_ownership.py`](tests/shared/test_db_ownership.py), [`tests/infrastructure/test_session_database.py`](tests/infrastructure/test_session_database.py) |
| A destructive confirmation is never raised over a file that will be refused: in Load and Save every refusal precedes the overwrite question | [`tests/structural/test_refusal_order.py`](tests/structural/test_refusal_order.py) |
| 100% line and branch coverage over `clear_budget` and the Qt-free half of `installer` | `--cov-fail-under=100`, `branch = True` in [`.coveragerc`](.coveragerc) and [`pyproject.toml`](pyproject.toml) |
| Money is integer pence. Typed text is read by `application/formatting.pence_from_text` through `Decimal`; a fraction of a penny, a negative (outside signed fields), a non-number or anything over `MAX_AMOUNT_PENCE` is refused, never rounded | [`tests/application/test_pence_from_text.py`](tests/application/test_pence_from_text.py) |
| An exported report adds up (`opening + net == close`), agrees with the on-screen month graph and anchors the current month on the recorded balance | [`tests/application/test_projection_series.py`](tests/application/test_projection_series.py) |
| The card graph and the Credit Cards view open a future month from the same chained figure (`card_openings_at`) | [`tests/application/test_month_graph_series.py`](tests/application/test_month_graph_series.py) (`TestCardGraphChaining`) |
| A single exported HTML file references nothing outside itself; an exported package links only to bare sibling filenames; user text cannot inject markup | [`tests/application/reporting/test_reports.py`](tests/application/reporting/test_reports.py), [`test_package_report.py`](tests/application/reporting/test_package_report.py) |
| The Solvency page and the bank graph agree about every month ahead, because what the current month still has to come has one home (`pending_income` and `pending_bills` in `_balance_projection.py`) | [`tests/application/test_solvency_agrees_with_graph.py`](tests/application/test_solvency_agrees_with_graph.py) |
| The Solvency bank page and the Reserves page read one simulation, `application/services/_month_walk.walk_month` | [`tests/application/test_month_walk.py`](tests/application/test_month_walk.py) |
| Every colour value lives in `shared/palette.py`; a hex literal anywhere else fails the build | [`tests/structural/test_colour_source.py`](tests/structural/test_colour_source.py) |
| Highlight text takes the accent colour, never the focus-ring colour | [`tests/ui_logic/test_highlight_text_colour.py`](tests/ui_logic/test_highlight_text_colour.py) |
| One Return press runs a dialog's submit once: no slot answers both `returnPressed` and `clicked` | [`tests/structural/test_return_key_invariants.py`](tests/structural/test_return_key_invariants.py) |
| Every table takes focus from the keyboard only (`TabFocus`) and draws no focus ring in any state | [`tests/structural/test_table_focus_invariants.py`](tests/structural/test_table_focus_invariants.py) |
| A sign-in handover that begins always ends: the composition root ends it in a `finally` and `end_handover` is idempotent | [`tests/structural/test_handover_invariants.py`](tests/structural/test_handover_invariants.py) |
| Every picture button and view button is named on the How It Works screen; its worked pro-rating example is what `prorate_remaining_pence` returns | [`test_help_names_the_tray.py`](tests/structural/test_help_names_the_tray.py), [`test_help_names_the_views.py`](tests/structural/test_help_names_the_views.py), [`test_help_example_is_arithmetic.py`](tests/structural/test_help_example_is_arithmetic.py) |
| The update check is the only connection the application opens: only its GitHub adapter may import `urllib.request` | [`tests/structural/test_no_network.py`](tests/structural/test_no_network.py) |
| Installer payload extraction and repair cannot write outside their destination | [`tests/installer/test_payload.py`](tests/installer/test_payload.py) |
| No mock libraries: real implementations and hand-written fakes only | House rule; the doubles are `tests/application/fakes.py` and `tests/installer/fakes.py` |

## Overview

```
+-------------------------------------------------------------+
|  UI (PySide6): MainWindow, views, view models, dialogs      |
+------------------------------+------------------------------+
                               | DTOs (MonthSummary, SolvencyReport, ...)
+------------------------------v------------------------------+
|  Application: BudgetService, reporting, DTOs, ports         |
+------------------------------+------------------------------+
                               | entities, value objects, services
+------------------------------v------------------------------+
|  Domain: pure business logic, repository Protocols (no I/O) |
+------------------------------^------------------------------+
                               | implements the Protocols
+------------------------------+------------------------------+
|  Infrastructure: SQLite repositories, GitHub release source |
+-------------------------------------------------------------+

  auth:   UserStore (users.db), RememberedLogin, full_backup
  shared: config, currency, palette, budget registry, db helpers
```

Dependencies point inward. `main.py` is the composition root; the UI's
`window_builder.py` holds the per-budget wiring split out of it.

## Layer Responsibilities

### Domain (`clear_budget/domain/`)

Pure business logic: no I/O, no Qt, no clock (`today` is always a parameter).

| Package | Owns |
|---------|------|
| `entities/` | Frozen dataclasses: `Bill`, `IncomeSource`, `CreditCard`, `Commitment`, `MonthBill`, `MonthIncome`. Bills, income and commitments end by naming a final month rather than being deleted, so history keeps them |
| `value_objects/` | `Amount` (non-negative pence, capped at `MAX_AMOUNT_PENCE`), `YearMonth`, the due-day rule (`due_day`), `MonthGap` (hold-flat gap), `MonthAfloat` (what keeps a month above the overdraft floor), `Recurrence`, `CreditLimitChange`, `BillAmountChange`, `SolvencyResult`, card warnings |
| `services/` | `bank_cashflow` (day-by-day month simulation), `solvency_calculator`, `card_monthly_calculator` and `_card_live_projection`, `credit_limit_schedule`, `bill_amount_schedule`, `_prorating`, `safe_to_spend` (Safe to Spend Today and the capacity schedule), `reserve_accrual` and `reserve_floor`, `recommendations` (with `_recommendation_plan`, `_recommendation_trials`, `_recommendation_pauses`) |
| `interfaces/` | Repository Protocols the Infrastructure implements |

Signed balances are plain `int` pence; `Amount` is used only where a value
cannot be negative.

### Application (`clear_budget/application/`)

Orchestration plus the DTOs that cross into the UI.

`BudgetService` (`services/budget_service.py`) is a frozen dataclass composed
of focused mixins, one per concern, with helper modules beside them, so each
file stays under the size cap:

| Modules | Concern |
|--------------|---------|
| `_bill_operations`, `_income_operations` | CRUD, per-month skip/override/paid/received, history-safe `end_bill` / `end_income` |
| `_overdraft_operations`, `_overdraft_projection` | Overdraft settings, `MonthGap`, the first future overdrawn month |
| `_card_operations`, `_card_projection`, `_card_balance_updates`, `_card_limit_updates` | Credit cards, chained card openings, elapsed-date folds |
| `_balance_application`, `_bank_transaction_fold` | Applying dated items to the stored bank balance (one transaction per fold) |
| `_month_graph_series`, `_projection_series` | Month graph series and the multi-month projection behind exports |
| `_month_summary_builder` | `MonthSummary` construction |
| `_safe_to_spend_operations` | Safe to Spend adapter, including the repeat-forward income assumption |
| `_recommendation_operations` | Recommendations adapter over the pure engine |
| `_reserve_operations` | Commitments CRUD and every Reserves figure |

Shared helpers: `_month_walk.walk_month` simulates one month and returns its
low and the day of the low, the first day below zero with the balance that day
ends on (`first_negative_balance`), the first day below a given floor and its
close; `_balance_projection` states what the current month still has to come.
`month_generator.py` builds months from templates.

Other packages:

| Package | Owns |
|---------|------|
| `dto/` | `MonthSummary`, `SolvencyReport`, `GraphSeries`, `ProjectionMonth`, update-check DTOs |
| `ports/` | `ReleaseSource`, the one seam to published releases |
| `reporting/` | Pure string builders for the HTML exports: `curve` (monotone cubic, shared with the on-screen chart), `chart_svg`, `document`, `month_report`, `projection_report`, `package_report` |
| `formatting.py` | `fmt()` money rendering and `pence_from_text` |
| `services/update_service.py`, `version_compare.py` | Compare the running build with the latest release and pick the platform asset |

### Infrastructure (`clear_budget/infrastructure/`)

| Module | Owns |
|--------|------|
| `sqlite/database.py` | Connection and schema management; `_schema.py` holds the baseline DDL and `_migrations.py` the numbered migrations, tracked in `schema_version` |
| `sqlite/*_repository.py` | `SQLiteBillRepository`, `SQLiteIncomeSourceRepository` (one-off rows in `_income_month_extras`), `SQLitePaymentMethodRepository`, `SQLiteCommitmentRepository` |
| `sqlite/session_database.py` | `open_user_database`, the one place that decides which file a session opens (via the budget registry), plus `load_currency` |
| `update/github_release_source.py` | `GitHubReleaseSource`: one best-effort stdlib `urllib` GET of the latest published release; any failure yields `None` |

Each budget database holds 20 application tables: payment methods, bill and
income templates, archived months, credit cards, settings, the per-month
override/skip/paid/received/extras tables, scheduled credit-limit and bill
amount changes, the balance-applied log, commitments and `schema_version`.

### Auth (`clear_budget/auth/`)

| Module | Owns |
|--------|------|
| `user_store.py` | `UserStore` over `users.db`: bcrypt password and recovery-code hashes, the first account as the only admin, refusal of colliding names, quarantine of files already under a new name |
| `models.py` | The immutable `User` |
| `remembered_login.py` | Per-account Remember me: passwords in the OS credential store through `keyring` behind a `SecretBackend` Protocol; only which accounts are remembered goes to `remembered_login.json`. Any keychain failure degrades to "nothing remembered" |
| `full_backup.py` | Back Up Everything / Restore Everything: one zip of `users.db`, every budget database and every budget list, each database snapshotted; restore stages and validates before replacing |

### Shared (`clear_budget/shared/`)

| Module | Owns |
|--------|------|
| `config.py` | Every data path, derived from one `_resolve_app_dir()` that honours `CLEARBUDGET_HOME` |
| `data_migration.py` | One-time move from the legacy `~/.clearbudget` |
| `budget_registry.py`, `budget_files.py` | Named budgets per account (a JSON sidecar of slugs and names); reading an account back out of a file name; quarantine |
| `db_copy.py`, `db_validation.py`, `db_ownership.py` | Snapshot and replace; schema plus `quick_check` validation; the owner stamp |
| `currency.py` | 25 currencies (default GBP) and the active symbol |
| `palette.py` | Every colour literal in the tree |
| `single_instance.py`, `raise_request.py`, `foreground.py` | One running copy per user; a second launch asks the first to come forward |
| `diagnostics.py` | `logs/clearbudget.log` and the uncaught-exception hooks for the main and worker threads |
| `resources.py` | Asset discovery across PyInstaller and source layouts |
| `errors.py` | Shared error types |

### UI (`clear_budget/ui/`)

The only Qt client. It is outside the coverage gate; logic a widget hosts is
extracted far enough from Qt to be tested under `tests/ui_logic`.

**Structure.**

| Area | Contents |
|------|----------|
| Window | `main_window.py` (`MainWindow`) composed of `_main_window_account`, `_main_window_menus`, `_main_window_nav` and `_main_window_views` mixins; it emits the session signals `switch_user_requested`, `sign_out_requested`, `database_replaced`, `full_restore_requested` and `database_load_requested` |
| Wiring | `window_builder.py` (`build_main_window`), `startup.py`, `login_flow.py`, `launch_screen.py`, `ui_scale.py`, `_window_geometry.py`, `raise_watcher.py`, `update_check.py` |
| View models | `MonthViewModel` and `SolvencyViewModel`. `month_summary_updated` fires on every bill or income change and refreshes Solvency and Credit Cards, since their figures depend on Monthly Budget data |
| Views | Seven views, in `VIEW_SPECS` order: Monthly Budget (`month_view`), Solvency (`solvency_panel`), Credit Cards, Reserves, Graph, Recommendations, Archive. Each sits in a `ScrollableView` |
| Widgets | Dialogs (sign-in, accounts, bill, income, card, commitment, balance, settings, budgets, How It Works, About, licence), `_line_bar_chart` with axes and hover mixins, `bottom_tray` (the donate footer), `auto_scroller`, `first_stop_dialog` |
| Utils | Navigation tray (`nav_header`, `nav_label`, `nav_toggle`, `nav_glyph_size`, `view_buttons`, `icon_buttons`), tables (`table_sort`, `sort_header`, `table_focus`, `text_metrics`), `amount_fields`, Qt-free wording modules (`reserves_text`, `recommendation_text`) |

**Mixin split pattern.** A large view or window is a thin class composed of
private mixin modules named after it (`_month_view_builders`,
`_month_view_edit_mixin`, `_month_view_delete_mixin`,
`_solvency_panel_month_lines`, `_solvency_panel_narratives` and so on). This
is how every file stays under the size cap; decisions that need no widget
take their state as arguments so they can be tested without a
`QApplication`.

**Solvency panel.** Two pages in a `QStackedWidget`: the bank page (account
position and the months ahead, from entered figures) and the projection page
(Safe to Spend Today and the repeat-forward reading). Each forward month (like
the displayed month's breakdown) leads with how far it goes overdrawn and when
(`_solvency_panel_month_lines._overdrawn_line`, reading `walk_month`); a
forward month then states what has to arrive to stay afloat and the day it
must beat, then its shape line.

**Navigation tray.** Every view builds its own two-row tray: the account name
and month cluster above; load, save, switch budget, bank, the seven view
buttons, the theme toggle and How It Works below. View buttons are plain
buttons over a `QTabWidget` whose bar is hidden; the current view is marked by
a dynamic property (`mark_current_view`). One `BottomTray` along the foot of
the window carries the donate button.

**Keyboard ring.** One application-level `KeyboardNavigator`
(`keyboard_nav.py`) walks an explicit ring: menu titles, then the active
view's `nav_targets()`, then the scrollable page body, then the footer.
Disabled or hidden stops are skipped; the current view's button is left out
(`ring_view_stops`). Tab and Right step forward, Shift+Tab and Left step back.
The main window starts on a neutral sink; dialogs derived from
`FirstStopDialog` open on their first stop. A mouse click never leaves a ring
on a button; tables take focus from the keyboard only.

**Theme and palette tokens.** Colour literals live only in
`shared/palette.py`. `theme_tokens.py` names what each colour is for (chrome
tokens plus chart-series and solvency-state palettes) for dark and light;
`theme_qss.build_qss(tokens)` assembles one stylesheet from per-surface
builders (`_theme_pane`, `_theme_inputs`, `_theme_menus`, `_theme_controls`,
`_theme_labels`, `_theme_labels_solvency`). `theme.apply_theme` applies it at
`QApplication` level and persists the choice. Text colour is carried by
named roles (`label_roles.set_role`) and state by Qt properties, so a live
theme switch restyles everything; content painted in code exposes
`restyle()`. Focus rings are three-state (none at rest; ring colour on hover
or focus; red while disabled). Spin-box arrows and the card toggle are
generated images (`spin_arrows`, `switch_images`). The setup program asks
`theme_tokens` for the same roles.

## Application Startup Flow

1. `main()` calls `ui/startup.begin()`: migrate the legacy data directory,
   create the `QApplication`, install the tooltip style, start the log, take
   the single-instance lock (or ask the running copy to come forward and
   exit), resolve the launch monitor and set the UI scale.
2. Apply the saved theme; open `UserStore` over `users.db`.
3. Schedule `_session_loop` with `QTimer.singleShot(0, ...)` and run
   `app.exec()`.
4. `_session_loop` runs `run_login_flow`: the first-run account wizard or the
   sign-in screen. A cancel resumes a hidden window or quits.
5. Inside `try`/`finally`, the sign-in screen becomes a progress bar
   (`begin_handover`); `open_user_database` opens the registry's active
   budget; `load_currency` activates its currency; `build_main_window` wires
   the session and runs the catch-up folds (card balances, limit changes,
   bank transactions, auto-archive); the window is shown and its session
   signals connected; `end_handover` closes the screen.
6. If the build raises, the exception is logged, the user is told where the
   log is and the event loop exits with a failure code.

`database_replaced` (a new or switched budget, a currency change) reopens the
database and rebuilds the window. `database_load_requested` does the same for
a Load, putting the displaced budget back if the loaded one will not open. A
full restore tears the session down and returns to sign-in.

## Dependency Injection

No container: constructors take their collaborators.
`ui/window_builder.build_main_window` is the wiring for one open budget:

```python
bill_repo           = SQLiteBillRepository(database.conn)
income_repo         = SQLiteIncomeSourceRepository(database.conn)
payment_method_repo = SQLitePaymentMethodRepository(database.conn)
commitment_repo     = SQLiteCommitmentRepository(database.conn)
month_generator     = MonthGenerator(bill_repo, income_repo)
budget_service      = BudgetService(bill_repo=..., income_repo=...,
                                    payment_method_repo=..., commitment_repo=...,
                                    month_generator=...)
month_view_model    = MonthViewModel(budget_service=budget_service)
solvency_view_model = SolvencyViewModel(budget_service=budget_service)
update_service      = UpdateService(source=GitHubReleaseSource(), ...)
window              = MainWindow(...)
```

`main.py` keeps what only it can hold: the session, the database connection,
the windows and the order in which one replaces another.

## Data Locations

Everything lives in one data directory: `%LOCALAPPDATA%\ClearBudget` on
Windows, `~/Library/Application Support/ClearBudget` on macOS and
`$XDG_DATA_HOME/clearbudget` (default `~/.local/share/clearbudget`) on Linux.
A surviving legacy `~/.clearbudget` is used until the startup migration
completes. `CLEARBUDGET_HOME` overrides it for tests and probes; the app never
sets it.

| File | Purpose |
|------|---------|
| `users.db` | Accounts |
| `budget_<user>.db` | The account's first budget |
| `budget_<user>__<slug>.db` | Each further named budget |
| `budgets_<user>.json` | The budget list and which budget is active |
| `ui_settings.json` | Theme, remembered save files and any skipped update |
| `remembered_login.json` | Which accounts are remembered (passwords are in the OS credential store) |
| `quarantine/` | Files moved aside by a restore or by account creation |
| `arrows/`, `switches/` | Generated theme images |
| `logs/` | `clearbudget.log` |

`<user>` is the username with every character outside `[A-Za-z0-9_-]` replaced
by an underscore, then lower-cased. A full backup carries `users.db`, the
budget databases and the budget lists.

## Currency

The currency code is stored per budget in the `settings` table.
`load_currency` activates it in `shared.currency` when a session opens;
`Amount.__str__` and `fmt()` read the active symbol at render time. Changing
it (Settings > Bank Account) saves the code, activates it and emits
`database_replaced` so every view rebuilds.

## Cross-Platform Packaging and the Setup Program

One codebase; platform differences sit behind a few seams: the
single-instance lock (a named mutex on Windows, `fcntl.flock` elsewhere), the
data directory in `Config`, `QStandardPaths` for file-dialog defaults and
`shared/resources.py` for assets.

| Platform | Built by | Produces |
|----------|----------|----------|
| Windows | `buildexe.py` (PyInstaller) then `buildinstaller.py` | `ClearBudgetSetup.exe`, a per-user installer |
| macOS | `builddmg.py` | `clearbudget.dmg`, signed and notarized (`ALLOW_UNNOTARIZED=1` for local testing only) |
| Linux | `build_flatpak.sh` | `clearbudget.flatpak` |

The setup program (`installer/`) mirrors the application's shape: `ops` holds
the side effects (payload, staging, shortcuts, registration, install, repair,
uninstall, process control), `state` the registry and state model, `shared`
resource resolution and logging, `ui` the Qt client and `app.py` the
composition root. Three seams keep the privileged work testable: an injectable
`CommandRunner`, an injectable `ProcessController` and an `InstallerIdentity`
value carrying the registry key and shortcut names. It never touches the
user data directory. Build steps are in [DEVELOPMENT.md](DEVELOPMENT.md).

## Quality Enforcement

Black and flake8 at 88 columns over the whole tree; ruff with the blind-handler
and naive-datetime rules enabled; 100% line and branch coverage (the omissions
are listed in `.coveragerc`). The structural tests in `tests/structural/`
read source rather than run widgets:

| Test | Holds |
|------|-------|
| `test_layering_rules.py`, `test_auth_structure.py`, `test_cross_package_imports.py` | Import direction; every cross-package name exists |
| `test_loc_limits.py` | The 400-line cap and danger band |
| `test_data_dir_isolation.py`, `test_restore_returns_to_sign_in.py`, `test_database_replacement_order.py` | Live data safety |
| `test_no_network.py`, `test_donation_address.py` | Network surface; the one donation address |
| `test_colour_source.py`, `test_combo_box_invariants.py`, `test_solvency_headings.py` | Theme and wording rules |
| `test_return_key_invariants.py`, `test_table_focus_invariants.py`, `test_button_run_slices.py`, `test_nav_entry_invariants.py`, `test_tray_switch_invariants.py`, `test_view_page_lists_agree.py` | Keyboard ring and view wiring |
| `test_refusal_order.py`, `test_save_location_defaults.py`, `test_handover_invariants.py`, `test_session_exit_invariants.py`, `test_first_run_close.py`, `test_cross_view_refresh.py`, `test_nav_user_label.py` | Flow ordering and session behaviour |
| `test_help_names_the_tray.py`, `test_help_names_the_views.py`, `test_help_example_is_arithmetic.py` | How It Works stays true |
| `test_delivery_assets.py`, `test_installer_layout_stability.py` | Packaging and the setup window |

## Testing

How the suite is run, what each part proves and its coverage floors are in
[TESTING.md](TESTING.md).

---

See also [README.md](README.md), [TESTING.md](TESTING.md),
[DEVELOPMENT.md](DEVELOPMENT.md) and
[DECISIONS-TRADEOFFS.md](DECISIONS-TRADEOFFS.md).
