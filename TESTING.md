# Testing

How ClearBudget is tested. Layer rules are in [ARCHITECTURE.md](ARCHITECTURE.md);
environment setup is in [DEVELOPMENT.md](DEVELOPMENT.md).

## Before the first run

- **Use Windows for the full run.** `tests/installer/` drives the real registry
  and the Shell Link COM interface. The code under test refuses any other
  platform, so there that directory fails wholesale and coverage misses the
  floor.
- **Install both requirements files into `venv`** (see DEVELOPMENT.md);
  `requirements-dev.txt` brings pytest, the linters and pywin32.
- Nothing else: the suite opens no window and touches neither your data nor
  an installed copy.

## The gate

From the repository root:

```powershell
venv\Scripts\python.exe -m pytest
venv\Scripts\python.exe -m black --check .
venv\Scripts\python.exe -m flake8
venv\Scripts\python.exe -m ruff check .
```

`pytest` alone is the gated run: `addopts` in `pyproject.toml` adds coverage of
`clear_budget` and `installer` with `--cov-fail-under=100`; `.coveragerc`
turns on branch coverage. No test runs black, flake8 or ruff; run all four.

## Reading a result

**Read the exit code, never the text.** `0` means every test passed and the
floor was met; anything else means read the failures above the coverage table.
Do not search the output for a result word: coverage rows are named after
modules, so `installer\ops\errors.py` matches "error" on a clean run.

```powershell
venv\Scripts\python.exe -m pytest; $LASTEXITCODE
```

To count tests without running them: `pytest --co -q --no-cov`.

## Coverage floors

| Scope | Floor | Why not 100 |
|---|---|---|
| `clear_budget`, Qt-free `installer/` | 100% line and branch | |
| `clear_budget/ui/*`, `installer/app.py`, `installer/ui/*` | not measured | Qt clients; their correctness lives in a real event loop |
| `main.py` | not measured | the composition root |
| `domain/interfaces/*`, `application/ports/*` | not measured | Protocol-only; nothing to execute |
| `clear_budget/shared/resources.py` | not measured | packaged-resource lookup |
| `buildexe.py`, `buildinstaller.py`, `installer/build_payload.py` | not measured | linear build recipes |
| `installer/payload/*`, `installer/resources/*` | not measured | staged build output |

Lines marked `# pragma: no cover` are also excluded, mostly thin
pass-throughs. Read 100% as "100% of what is gated".

## What each suite proves

| Directory | Proves | Against |
|---|---|---|
| `domain/` | entities, value objects, domain services | values built in the test |
| `application/` | services and reports | hand-written fakes (`tests/application/fakes.py`) |
| `infrastructure/` | SQLite repositories, migrations, release source | a real SQLite file (the `db` fixture) |
| `auth/` | user store, remembered sign-in, full backup including hostile ones | real SQLite files |
| `shared/` | configuration, budget registry, database copy and validation, single instance | real files in a temp folder |
| `ui_logic/` | pure logic inside the UI layer | plain values; no `QApplication` |
| `installer/` | the Qt-free setup program | real registry under a scratch key; real Shell Link; redirected profile |
| `structural/` | rules no single test can see | the source tree |

The structural guards, one rule each:

| Guard | Holds |
|---|---|
| `test_layering_rules.py` | layer boundaries; a domain free of I/O and frameworks |
| `test_auth_structure.py` | the auth module's shape |
| `test_cross_package_imports.py` | every cross-package import exists |
| `test_loc_limits.py` | the 400-line cap and its danger band |
| `test_colour_source.py` | colours have one home |
| `test_donation_address.py` | the donation address has one home |
| `test_no_network.py` | the update check is the only connection anything shipped opens |
| `test_data_dir_isolation.py` | the suite never writes to the real data directory |
| `test_save_location_defaults.py` | Save and Load default to the data directory |
| `test_database_replacement_order.py` | a live database is closed before it is replaced |
| `test_restore_returns_to_sign_in.py` | Restore Everything always ends at sign-in |
| `test_refusal_order.py` | nothing threatens a budget until the target is known writable |
| `test_session_exit_invariants.py` | switching user and signing out stay distinct |
| `test_handover_invariants.py` | the sign-in screen is never stranded |
| `test_first_run_close.py` | the first-run wizard keeps its close button |
| `test_delivery_assets.py` | every runtime asset reaches every platform |
| `test_installer_layout_stability.py` | setup controls do not move during an operation |
| `test_view_page_lists_agree.py` | the three view lists agree, in order |
| `test_button_run_slices.py` | a view takes the button run whole, less Archive |
| `test_cross_view_refresh.py` | a view refreshes on the data it shows |
| `test_tray_switch_invariants.py` | switching views costs the tray nothing |
| `test_nav_entry_invariants.py` | the focus ring's entry point and wiring |
| `test_nav_user_label.py` | the signed-in account shows on every view |
| `test_table_focus_invariants.py` | no table takes the ring from a click |
| `test_return_key_invariants.py` | one Return runs a dialog's submit once |
| `test_combo_box_invariants.py` | every combo box is a `ThemedComboBox` |
| `test_solvency_headings.py` | no heading names a facility the reader may lack |
| `test_help_example_is_arithmetic.py` | How It Works' example matches the code |
| `test_help_names_the_tray.py` | every picture button is named on How It Works |
| `test_help_names_the_views.py` | every view button is named on How It Works |

## What the tests never do

- **Open a window.** No test creates a `QApplication`; widget tests were
  removed as fragile. PySide6 is still imported for Qt classes and enums.
  Appearance is checked by hand in a real build.
- **Touch your data.** The autouse `isolate_app_dir` fixture in
  `tests/conftest.py` points `CLEARBUDGET_HOME` at a temp directory for every
  test. `real_app_dir` clears it for one test and writes nothing.
- **Touch an installation.** `tests/installer/conftest.py` redirects the
  profile directories, the `platformdirs` lookups (which ask Windows directly,
  not `%LOCALAPPDATA%`) and the payload, all autouse. The registry is reachable
  only through the `scratch_identity` fixture, a test-only HKCU key deleted in
  teardown.
- **Mock.** Ports are stood in for by hand-written fakes; environment and
  attributes go through `monkeypatch`. Never call `monkeypatch.undo()`: it also
  undoes the data-directory redirect. Use `with monkeypatch.context():`.

A throwaway probe outside the suite must set the same redirect first, since
calls such as `theme.apply_theme` persist what they set:

```powershell
$env:CLEARBUDGET_HOME = "$env:TEMP\cb-probe"
```

## Running part of the suite

```powershell
venv\Scripts\python.exe -m pytest tests\domain --no-cov
venv\Scripts\python.exe -m pytest tests\structural\test_loc_limits.py --no-cov
venv\Scripts\python.exe -m pytest --ignore=tests/installer --no-cov
```

A partial run needs `--no-cov`; without it the floor fails the run. The third
command is the run for Linux and macOS.

A new guard is trusted only once it has been seen to fail: plant the
violation, read the failure, restore the tree in a `finally` block. A test for
a defect must fail before the fix for the reason named.

---

See also [README.md](README.md), [ARCHITECTURE.md](ARCHITECTURE.md) and
[DEVELOPMENT.md](DEVELOPMENT.md).
