# ClearBudget: Technical Debt

A standing reference to the project's outstanding technical debt. It records what is still open, weighs whether each item is worth doing and gives the rationale. Every item is a behaviour-preserving internal concern: nothing here proposes reverting a feature or changing any UI or UX behaviour. Scope is the whole repository (the `clear_budget` package, the bespoke installer, the delivery scripts for Windows, Linux and macOS, and the GitHub Pages site under `docs/`) read against `ARCHITECTURE.md` and the tests under `tests/structural/`.

---

## 1. `_credit_card_view_loaders.py` is at 399 lines

`clear_budget/ui/views/_credit_card_view_loaders.py` is one line under the 400-line cap that `tests/structural/test_loc_limits.py` enforces. That is the worst place in the range for a file to be: the next edit fails the build for a reason unrelated to the change, and shaving a line to get back under puts it straight back in the same position.

Take it to 350 or below by extracting one cohesive concern, not by trimming. Three other files sit between 355 and 382 and are fine where they are.

The size test itself has no danger-band tier: it fails over 400 and says nothing about 381 to 399. Adding a second assertion at 380 would make this self-policing rather than something to notice by hand.

## 2. The installer UI still carries unexplained broad handlers

`installer/ui/_main_window_actions.py`, `icons.py`, `worker.py`, `_header_fit.py`, `lgpl3_license_text.py`, `main_window.py` and `_main_window_buttons.py` hold `except Exception` blocks, several of them silent. The Qt-free half has had the house style applied (every remaining broad handler names what it degrades and why; the rest are narrowed to `OSError`); the UI half has not.

`pyproject.toml` carries a per-file ignore for `installer/**/*.py` covering `BLE001`, `S110` and `S112` with a stated rationale, so the whole package passes `ruff check` under the project config. Run `ruff check --isolated` over `installer/ui` and fifty-four surface (31 `BLE001`, 21 `S110`, 2 `S112`), which is the honest measure of what is left. The two modules added with the close-running-app work, `_main_window_ops.py` and `close_app_dialog.py`, are clean, so this is inherited surface rather than a growing one.

The UI is outside the coverage gate, so these are not hiding an untested failure path in the way the `ops` ones were. They are a readability item: a reader cannot tell which are deliberate and which are inherited. Narrow the ones that can be narrowed and give the rest a one-line reason, then consider whether the per-file ignore can be dropped.

## 3. Two icon generators

`create_icon.py` and `create_icons.py` are both tracked at root. The portfolio's rule is one master PNG and one `generate_icons.py` emitting the whole set. Two scripts with near-identical names mean nobody can tell which one produced the fourteen tracked PNGs, and the wrong one will eventually be run.

Determine which is authoritative, delete the other and rename the survivor to `generate_icons.py` to match every other project here.

## 4. The UI layer is omitted from the gate in full

`.coveragerc` omits `clear_budget/ui/*` wholesale. For painting, layout and Qt wiring that is correct and matches the rest of the portfolio.

The item is that some of what sits in there is not presentation. `_credit_card_view_loaders.py` (item 1), `format_helpers.py` at 369 lines and `month_view.py` at 361 carry data shaping and formatting decisions, and formatting is where a budgeting application gets a number wrong in a way a user believes. `clear_budget/application` already holds the reporting DTOs and the projection series, so there is somewhere obvious for that logic to move to. This is continuous work, not a task with an end state; it is recorded so the omission is never read as "the UI has no logic".

---

## Looks like debt, not worth touching

- The delivery scripts (`buildexe.py`, `buildinstaller.py`, `builddmg.py`, `dmg_icon.py`, `build_utils.py`, `build_flatpak.sh`, `cleanup_flatpak.sh`, `stamp_version.py`). Linear recipes, exempt from the module cap by design. Do not raise length against them.
- The four files between 355 and 382 lines. Under the cap, clear of the danger band, nothing to do.
- The two root `.spec` files (`ClearBudget.spec`, `ClearBudgetSetup.spec`) are PyInstaller artefacts and are untracked.
- The `_leading_underscore.py` module naming inside `ui/views` and `application/services`. Unconventional, clear in intent (private to the package) and consistent.
- The fourteen tracked PNG sizes plus the `.ico`. Emitted from a single master and consumed by named packaging paths. Item 3 is about which script emits them, not about the assets.

## Not debt (do not "fix" these)

These look like candidates but are correct as they stand; changing them would regress or add cost for nothing.

- **`VERSION` at root with `stamp_version.py` writing the delimited tokens.** The single-source-of-truth pattern, correctly implemented, with the build scripts calling the stamper so it cannot be forgotten. This is the reference the rest of the portfolio should copy.
- **`tests/structural/test_data_dir_isolation.py`.** A structural test asserting the application never writes outside its own data directory. Exactly the right kind of invariant for a local-first app that holds someone's finances, and unusual enough to be worth naming.
- **`tests/structural/test_auth_structure.py` and `test_layering_rules.py`.** Layer boundaries and the auth surface held by AST scan rather than by convention.
- **The per-platform requirements split** (`requirements.txt`, `requirements-dev.txt` and the Flatpak and macOS variants driven by the build scripts). Native dependencies genuinely differ per platform.
- **The three delivery paths being independent** (`buildexe.py` then `buildinstaller.py` on Windows, `build_flatpak.sh` on Linux, `builddmg.py` on macOS), with `cleanup_flatpak.sh` scoped only to Flatpak artefacts. That scoping is deliberate so one clean does not destroy another platform's build.
- **The setup program's three injectable seams** (`CommandRunner`, `ProcessController` and `InstallerIdentity`). They read like ceremony around `subprocess` and `winreg` until you notice they are what lets the privileged half of the installer sit inside the coverage gate without a test ever spawning a process or writing to the user's own registry key.
