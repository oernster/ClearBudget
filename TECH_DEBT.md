# ClearBudget: Technical Debt

A standing reference to the project's outstanding technical debt. It records what is still open, weighs whether each item is worth doing and gives the rationale. Every item is a behaviour-preserving internal concern: nothing here proposes reverting a feature or changing any UI or UX behaviour. Scope is the whole repository (the `clear_budget` package, the bespoke installer, the delivery scripts for Windows, Linux and macOS, plus the GitHub Pages site under `docs/`) read against `ARCHITECTURE.md` and the tests under `tests/structural/`.

**There is no open technical debt in this repository.** Every numbered item has been resolved and deleted. The two sections below are standing decisions, not work: they record what is deliberately left alone and why, so that neither gets raised again as though it were debt.

---

## Looks like debt, not worth touching

- The delivery scripts (`buildexe.py`, `buildinstaller.py`, `builddmg.py`, `dmg_icon.py`, `build_utils.py`, `build_flatpak.sh`, `cleanup_flatpak.sh`, `stamp_version.py`). Linear recipes, exempt from the module cap by design. Do not raise length against them.
- Source and test files sitting between 351 and 380 lines. Under the cap, clear of the 381 to 399 danger band, nothing to do. Both halves of that rule are asserted in `tests/structural/test_loc_limits.py`, so this is held by the suite rather than by eye. Deliberately stated without a count: which files sit in that range changes with almost every commit, so a number here is a claim that goes stale on its own and says nothing the rule does not.
- The two root `.spec` files (`ClearBudget.spec`, `ClearBudgetSetup.spec`) are PyInstaller artefacts and are untracked.
- The `_leading_underscore.py` module naming inside `ui/views` and `application/services`. Unconventional, clear in intent (private to the package) and consistent.
- The seventeen tracked PNG files plus the two `.ico` files. The seven sized root PNGs and the root `.ico` are derived from `ClearBudget.png`, the 1024x1024 master, by `generate_icons.py`, which reproduces all eight byte for byte; the six PNGs and `favicon.ico` under `docs/` are the site's favicons, consumed by named paths in its HTML; `monthlybudget.png`, `solvency.png` and `creditcards.png` are the tab masters, cropped and downscaled at runtime by `ui/utils/tab_icons.py` exactly as the nav tray already does with `ClearBudget.png`. Do not raise the masters' size as debt: shipping a pre-sized derivative would need a second generator and a second thing to keep in step, for a few megabytes inside a fifty-megabyte payload.

## Not debt (do not "fix" these)

These look like candidates but are correct as they stand; changing them would regress or add cost for nothing.

- **`VERSION` at root with `stamp_version.py` writing the delimited tokens.** The single-source-of-truth pattern, correctly implemented, with the build scripts calling the stamper so it cannot be forgotten. This is the reference the rest of the portfolio should copy.
- **`tests/structural/test_data_dir_isolation.py`.** A structural test asserting the application never writes outside its own data directory. Exactly the right kind of invariant for a local-first app that holds someone's finances and unusual enough to be worth naming.
- **`tests/structural/test_auth_structure.py` and `test_layering_rules.py`.** Layer boundaries and the auth surface held by AST scan rather than by convention.
- **The per-platform requirements split** (`requirements.txt`, `requirements-dev.txt` and the Flatpak and macOS variants driven by the build scripts). Native dependencies genuinely differ per platform.
- **The three delivery paths being independent** (`buildexe.py` then `buildinstaller.py` on Windows, `build_flatpak.sh` on Linux, `builddmg.py` on macOS), with `cleanup_flatpak.sh` scoped only to Flatpak artefacts. That scoping is deliberate so one clean does not destroy another platform's build.
- **The setup program's three injectable seams** (`CommandRunner`, `ProcessController` and `InstallerIdentity`). They read like ceremony around `subprocess` and `winreg` until you notice they are what lets the privileged half of the installer sit inside the coverage gate without a test ever spawning a process or writing to the user's own registry key.
- **`.coveragerc` omitting `clear_budget/ui/*` wholesale.** Correct for painting, layout and Qt wiring; it matches the rest of the portfolio. This was once recorded as debt on the grounds that some of what sat in there was not presentation, which was true of the money, percentage and category formatting: turning pence into a figure a person reads is where a budgeting application gets a number wrong in a way the user believes. That formatting now lives in `clear_budget/application/formatting.py`, inside the gate and covered; the UI re-exports it so no call site moved. What remains under `ui/` is presentation, so the omission stands as a decision rather than an omission.
