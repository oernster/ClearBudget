# Testing

How ClearBudget is tested: running the checks, reading what they say, what the
gate holds and what it leaves out, the rules a run by hand has to follow and
how a new test or guard is written. The layer rules themselves are in
[ARCHITECTURE.md](ARCHITECTURE.md); setting up the environment the tests run in
is in [DEVELOPMENT.md](DEVELOPMENT.md).

## Running the checks

From the repository root, with the venv active:

```
pytest
black --check .
flake8
ruff check .
```

`pytest` alone is the gated run: the options in `pyproject.toml` add the
coverage measurement and the floor, so nothing else needs passing to it. Add
`-v` to see each test named as it runs.

**black, flake8 and ruff are not part of the suite.** No test runs them, so a
formatting or lint regression passes `pytest` untouched. Run all four and read
the exit code of each.

**A full run takes about a minute on Windows.** Measured on 2026-10-02: 1,966
tests passed in 63 seconds, with no window opened.

**Read the exit code, never the text.** The run prints the coverage table
then one summary line. A search of the output for a result word is still not
safe: coverage rows are named after modules, so `installer\ops\errors.py`
matches a search for "error" on a clean run. `0` means the tests passed AND the
floor was met; anything else means read the failures above the table. For a
count of tests without running them, `pytest --co -q --no-cov` ends with one.

**The full run is Windows only, which makes the gate Windows only too.**
`tests/installer/` drives the real registry and the Shell Link COM interface,
which the code under test refuses on any other platform, so on Linux or macOS
that directory fails wholesale and coverage falls short of the floor.
Everything else runs anywhere:

```
pytest --ignore=tests/installer --no-cov
```

## What the gate holds

The floor is 100%, measured by BRANCH as well as by line (`branch = True` in
`.coveragerc`, `--cov-fail-under=100` in `pyproject.toml`). In effect it spans
two sources: `clear_budget` and the Qt-free half of the setup program under
`installer/`. The pytest options also name `main` as a source; `.coveragerc`
then omits `main.py`, so nothing of it is measured. The setup program is inside
the floor because it does the most privileged work in the repository: registry
writes, shortcut creation, per-user deployment, process termination and
directory removal.

Outside the floor, stated in full so the number is not read as more than it is:

| Omitted | Why |
|---|---|
| `main.py` | the composition root |
| `clear_budget/ui/*`, `installer/app.py`, `installer/ui/*` | the Qt clients; their correctness lives in a real event loop rather than in branch coverage of pure logic |
| `clear_budget/domain/interfaces/*`, `clear_budget/application/ports/*` | Protocol-only modules with nothing to execute |
| `clear_budget/shared/resources.py` | the packaged-resource lookup |
| the root build scripts, `installer/build_payload.py` | linear build recipes |
| `installer/payload/*`, `installer/resources/*` | staged build output |

Then any line marked `# pragma: no cover`. Counted on 2026-10-02: 100 of
them across 28 files, most on thin pass-throughs in the application service
modules (18 in `_settings_operations.py`, 12 in `_income_operations.py`) and
12 in the SQLite payment-method repository. Read 100% as "100% of what is
gated", not as "every line is tested".

## Running it by hand

- **No window, ever.** The suite starts no `QApplication` and has no widget
  tests; the widget-level PySide6 tests were removed as fragile. Logic that
  lives in the UI layer but is pure Python is tested without one under
  `tests/ui_logic`. PySide6 is still imported: a few tests take Qt classes or
  enums directly; others import UI modules that load it.
- **Your data is never touched.** `isolate_app_dir` in `tests/conftest.py` is
  autouse and points `CLEARBUDGET_HOME` at a throwaway directory for every test,
  named `.clearbudget` like the real one so tests asserting on the name still
  hold. A test that needs the real path shape asks for `real_app_dir`, which
  clears the variable for that test alone and writes nothing.
  `tests/structural/test_data_dir_isolation.py` fails if the redirect ever stops
  happening.
- **No installation is touched either.** `tests/installer/conftest.py` closes
  the four routes from the setup program's tests to the real machine; see
  [Testing the setup program](#testing-the-setup-program).

## Where the tests live

`tests/` mirrors the package, one directory a concern:

| Directory | What it tests | Against |
|---|---|---|
| `domain/` | entities, value objects and the domain services, pure | values built in the test |
| `application/` | the services and the reports | hand-written fakes of the repositories (`tests/application/fakes.py`) |
| `infrastructure/` | the SQLite repositories, the migrations, the release source | a real SQLite file in a temporary folder (the `db` fixture) |
| `auth/` | the user store, remembered sign-in, full backup | real SQLite files in a temporary folder |
| `shared/` | configuration, the budget registry, database copy and validation, single instance | real files in a temporary folder |
| `ui_logic/` | the pure logic inside the UI layer | plain values; no `QApplication` |
| `installer/` | the Qt-free half of the setup program | the real registry under a scratch key and the real Shell Link interface, inside a redirected profile |
| `structural/` | the rules no single test can see | the source tree itself |

## Writing a test

- **No mocking library.** A port is stood in for by a hand-written fake:
  `tests/application/fakes.py` holds the repository fakes and
  `tests/installer/fakes.py` the setup program's. Environment and attributes are
  redirected with pytest's own `monkeypatch`.
- **A database.** Ask for the `db` fixture in `tests/infrastructure/conftest.py`
  for a connected database with the production schema, closed again in
  teardown.
- **Appearance is not a test.** What matters there is what gets painted, so it
  is checked with throwaway offscreen probes. Run those with
  `QT_QPA_PLATFORM=offscreen`, EXCEPT when measuring text or emoji: offscreen
  substitutes Qt's own font database, so a font size tuned there does not match
  what ships. Measure those on the real platform.
- **Always point a probe at a scratch data directory.** The real data directory
  (`%LOCALAPPDATA%\ClearBudget` on Windows; see the README's Data Storage
  section for the other platforms, plus a surviving legacy `~/.clearbudget`)
  holds live user data: both databases, the saved UI settings (theme,
  remembered save-file location and any skipped update version) and the
  Remember me sidecar (`remembered_login.json`). Set `CLEARBUDGET_HOME` and
  every path the app resolves moves with it:

  ```powershell
  $env:CLEARBUDGET_HOME = "$env:TEMP\cb-probe"
  ```

  This is not a style preference. A probe that calls `theme.apply_theme` to
  measure something persists that theme, because persisting is what the
  function is for; the app then opens in the theme the probe used.

## Testing the setup program

`tests/installer/` exercises everything under `installer/` except `app.py` and
`installer/ui`, on Windows only (see above). Nothing in it touches a real
installation and that is held in place by four fixtures in
`tests/installer/conftest.py`, each closing one route to the real machine.
Three are autouse and unconditional:

- the per-user profile directories are redirected through the environment
  variables the code reads;
- the `platformdirs` lookups are redirected **in their own right**, because
  `platformdirs` asks Windows for the known folder rather than reading
  `%LOCALAPPDATA%`. Without this fixture the legacy-directory migration would
  find and move your actual data;
- the payload anchor is redirected so a small stand-in bundle replaces the
  real fifty-megabyte payload.

The fourth is requested by name rather than autouse: `scratch_identity` yields
an `InstallerIdentity` whose HKCU key lives under a test-only root and is
deleted in teardown. A test can only reach the registry by taking that
identity, so asking for it is the same act as needing it.

`tests/installer/fakes.py` holds the hand-written doubles for the three
injectable seams (`CommandRunner`, `ProcessController` and the identity value).
What can be exercised for real is: shortcuts are written through the same Shell
Link COM interface the install uses; the registry round-trips through `winreg`
against the scratch key; a full install deploys and registers a real bundle,
all inside the redirected tree.

## Guards

A structural test checks the source tree rather than behaviour, so a rule holds
for code nobody has written yet. The suite in `tests/structural/`:

| Guard | Holds |
|---|---|
| `test_layering_rules.py` | the layer boundaries |
| `test_auth_structure.py` | the shape of the auth module |
| `test_cross_package_imports.py` | every name one package imports from another is actually there |
| `test_loc_limits.py` | the 400 line cap and the danger band below it |
| `test_colour_source.py` | colour values have one home |
| `test_donation_address.py` | the donation address has one home and is the one meant |
| `test_data_dir_isolation.py` | the suite never writes to the real data directory |
| `test_save_location_defaults.py` | Save and Load default to the data directory, not Downloads |
| `test_database_replacement_order.py` | a live database is closed before it is replaced, only in `main.py` |
| `test_refusal_order.py` | nothing threatens a budget until the chosen file is known to be writable |
| `test_session_exit_invariants.py` | switching user and signing out stay two different things |
| `test_handover_invariants.py` | the sign-in screen is never left stranded on screen |
| `test_first_run_close.py` | the first-run wizard keeps its close button |
| `test_delivery_assets.py` | every runtime asset reaches every platform the app ships on |
| `test_installer_layout_stability.py` | the setup program's controls do not move while an operation runs |
| `test_view_page_lists_agree.py` | the three lists of views agree, in order |
| `test_button_run_slices.py` | a view takes the button run whole, less Archive |
| `test_cross_view_refresh.py` | a view is refreshed by the data it shows, not by the view it lives on |
| `test_tray_switch_invariants.py` | switching views costs the tray no control and leaves no stray ring |
| `test_nav_entry_invariants.py` | the ring's entry point is a view decision and its wiring holds |
| `test_nav_user_label.py` | the signed-in account is shown on every view |
| `test_table_focus_invariants.py` | no table takes the ring from a click |
| `test_return_key_invariants.py` | one Return press runs a dialog's submit once |
| `test_combo_box_invariants.py` | every combo box is a `ThemedComboBox` |
| `test_solvency_headings.py` | a heading never names a facility the reader may not have |
| `test_help_example_is_arithmetic.py` | the worked example on How It Works is what the code returns |
| `test_help_names_the_tray.py` | every picture button is named on How It Works |
| `test_help_names_the_views.py` | every view button is named on How It Works |

**A guard is not trusted until it has been seen to fail.** A new guard is
proved by planting the violation it exists to catch and reading the failure,
then restoring the tree in a `finally` block so an interrupted proof cannot
leave the plant behind. A test written for a defect is run before the fix,
where it has to fail for the reason named, not merely fail.

---

See also [README.md](README.md), [ARCHITECTURE.md](ARCHITECTURE.md) and
[DEVELOPMENT.md](DEVELOPMENT.md).
