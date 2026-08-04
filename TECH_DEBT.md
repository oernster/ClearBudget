# ClearBudget: Technical Debt

A standing reference to the project's outstanding technical debt. It records what is still open, weighs whether each item is worth doing and gives the rationale. Every item is a behaviour-preserving internal concern: nothing here proposes reverting a feature or changing any UI or UX behaviour. Scope is the whole repository (the `clear_budget` package, the bespoke installer, the delivery scripts for Windows, Linux and macOS, and the GitHub Pages site under `docs/`) read against `ARCHITECTURE.md` and the tests under `tests/structural/`.

---

## 1. Two dead packages sit at repository root, one of them shadowing the core calculation

`models/` and `services/` are tracked at root, outside `clear_budget/`:

- `models/__init__.py`, `models/database.py`, `models/month.py`
- `services/__init__.py`, `services/solvency_calculator.py`

Nothing imports them. The only import between them is `services/solvency_calculator.py` doing `from models.month import Month`, so the two packages reference each other and nothing else in the repository references either. They are the pre-refactor structure, left in place when the code moved into `clear_budget/`.

They are also invisible to every gate the project runs: `.coveragerc` sets `source = clear_budget`, and `tests/structural/test_layering_rules.py` reasons about the package, not about root.

The reason this is item one rather than a footnote is the name. `services/solvency_calculator.py` is a stale copy of the application's headline capability, and the live implementation is `clear_budget/domain/services/solvency_calculator.py`. Anyone reading this repository for the first time, or grepping for the solvency logic, finds two files with the same name and only one that runs. A stale copy of the most important calculation in a budgeting application is the worst possible thing to leave lying around.

Delete both directories.

## 2. A file from another project is tracked in the installer

`installer/ops/shortcuts.py.narratex` is tracked. It is a copy of NarrateX's shortcuts module, saved with a suffix during a port of that installer into this repository and then committed.

It is inert (nothing imports a `.narratex` file) and it is a loose copy of another application's code sitting in this one's source tree. Delete it.

## 3. `_credit_card_view_loaders.py` is at 399 lines

`clear_budget/ui/views/_credit_card_view_loaders.py` is one line under the 400-line cap that `tests/structural/test_loc_limits.py` enforces. That is the worst place in the range for a file to be: the next edit fails the build for a reason unrelated to the change, and shaving a line to get back under puts it straight back in the same position.

Take it to 350 or below by extracting one cohesive concern, not by trimming. Three other files sit between 355 and 382 and are fine where they are.

The size test itself has no danger-band tier: it fails over 400 and says nothing about 381 to 399. Adding a second assertion at 380 would make this self-policing rather than something to notice by hand.

## 4. The installer is untested and carries unexplained broad handlers

`.coveragerc` omits `installer/*`, and there is no installer test package. `installer/ops/install_ops.py` alone has eight `except Exception` blocks with no `# noqa` and no comment, plus more in `installer/app.py`.

The decomposition is already right (`installer/ops` separated from `installer/ui`, no module over 400 lines), which is what makes the absence of tests worth closing rather than accepting. `ops/` is Qt-free, so the registry writes, the shortcut creation and the uninstall path can be tested against a temporary directory and a fake registry writer without any Qt at all. Bringing `installer/ops` into the coverage source is a contained piece of work.

Every broad handler should say in one line what it degrades and why. The `_schema.py` handlers show the house style being applied correctly; the installer ones simply have not had it applied yet.

## 5. Schema migration is a sequence of try-and-ignore `ALTER` statements

`clear_budget/infrastructure/sqlite/_schema.py` carries eight `except Exception: # noqa: S110, BLE001 (idempotent ALTER migration)` blocks. Each one attempts an `ALTER TABLE ... ADD COLUMN` and swallows the failure on the assumption that the column already exists.

This is honest, commented and it works, and for a single-user local SQLite file it is a defensible choice. The debt is what it cannot do:

- It cannot distinguish "column already present" from "the database is corrupt", "the file is locked" or "the disk is full". Every one of those becomes a silent no-op and the application continues against a schema it has not verified.
- It has no notion of a schema version, so migrations cannot be ordered, cannot be skipped and cannot be reasoned about backwards.
- The count only goes up. Eight blocks today is eight `ALTER` attempts on every single startup.

The proportionate fix is a `schema_version` table and a numbered migration list applied in order, with each step failing loudly. It is a bounded piece of work and it removes eight broad exception handlers from the shipped code path at the same time.

## 6. Two icon generators

`create_icon.py` and `create_icons.py` are both tracked at root. The portfolio's rule is one master PNG and one `generate_icons.py` emitting the whole set. Two scripts with near-identical names mean nobody can tell which one produced the fourteen tracked PNGs, and the wrong one will eventually be run.

Determine which is authoritative, delete the other and rename the survivor to `generate_icons.py` to match every other project here.

## 7. The UI layer is omitted from the gate in full

`.coveragerc` omits `clear_budget/ui/*` wholesale. For painting, layout and Qt wiring that is correct and matches the rest of the portfolio.

The item is that some of what sits in there is not presentation. `_credit_card_view_loaders.py` (item 3), `format_helpers.py` at 369 lines and `month_view.py` at 361 carry data shaping and formatting decisions, and formatting is where a budgeting application gets a number wrong in a way a user believes. `clear_budget/application` already holds the reporting DTOs and the projection series, so there is somewhere obvious for that logic to move to. This is continuous work, not a task with an end state; it is recorded so the omission is never read as "the UI has no logic".

---

## Looks like debt, not worth touching

- The delivery scripts (`buildexe.py`, `buildinstaller.py`, `builddmg.py`, `dmg_icon.py`, `build_utils.py`, `build_flatpak.sh`, `cleanup_flatpak.sh`, `stamp_version.py`). Linear recipes, exempt from the module cap by design. Do not raise length against them.
- The four files between 355 and 382 lines. Under the cap, clear of the danger band, nothing to do.
- The two root `.spec` files (`ClearBudget.spec`, `ClearBudgetSetup.spec`) are PyInstaller artefacts and are untracked.
- The `_leading_underscore.py` module naming inside `ui/views` and `application/services`. Unconventional, clear in intent (private to the package) and consistent.
- The fourteen tracked PNG sizes plus the `.ico`. Emitted from a single master and consumed by named packaging paths. Item 6 is about which script emits them, not about the assets.

## Not debt (do not "fix" these)

These look like candidates but are correct as they stand; changing them would regress or add cost for nothing.

- **`VERSION` at root with `stamp_version.py` writing the delimited tokens.** The single-source-of-truth pattern, correctly implemented, with the build scripts calling the stamper so it cannot be forgotten. This is the reference the rest of the portfolio should copy.
- **`tests/structural/test_data_dir_isolation.py`.** A structural test asserting the application never writes outside its own data directory. Exactly the right kind of invariant for a local-first app that holds someone's finances, and unusual enough to be worth naming.
- **`tests/structural/test_auth_structure.py` and `test_layering_rules.py`.** Layer boundaries and the auth surface held by AST scan rather than by convention.
- **The `_schema.py` handlers' `# noqa: S110, BLE001 (idempotent ALTER migration)` comments.** Item 5 proposes replacing the mechanism. Until that happens, these comments are the correct way to carry it: the reason is stated, so the decision is reviewable.
- **The per-platform requirements split** (`requirements.txt`, `requirements-dev.txt`, and the Flatpak and macOS variants driven by the build scripts). Native dependencies genuinely differ per platform.
- **The three delivery paths being independent** (Nuitka or PyInstaller on Windows, `build_flatpak.sh` on Linux, `builddmg.py` on macOS), with `cleanup_flatpak.sh` scoped only to Flatpak artefacts. That scoping is deliberate so one clean does not destroy another platform's build.
