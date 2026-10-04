# ClearBudget: Technical Debt

Open internal debt across the whole repository, read against
`ARCHITECTURE.md` and `tests/structural/`. Every item is behaviour-preserving:
none changes a feature or the UI. The two closing sections are standing
decisions, not work.

## 1. The UI imports the domain directly

The architecture has the UI reach the application layer through DTOs. In
practice 24 UI modules import the domain in 43 statements: 34 take value
objects (`Amount`, `YearMonth` and their kind), 5 take entities and 4 take
domain services. Every written layer rule holds; the cost is that a domain
change can reach a widget without passing the application layer.

`tests/structural/test_layering_rules.py` allows it for now so the rest of the
layering could be enforced at once. Clearing it means moving the entity and
service uses behind the application layer and deciding whether value objects
such as `Amount` stay as shared vocabulary; then the UI rule in that test gains
`domain`. Blocked on an owner decision about the value objects.

---

## Looks like debt, not worth touching

- **The delivery scripts** (`buildexe.py`, `buildinstaller.py`, `builddmg.py`,
  `dmg_icon.py`, `build_utils.py`, `build_flatpak.sh`, `cleanup_flatpak.sh`,
  `stamp_version.py`): linear recipes, exempt from the module cap by design.
- **Files between 351 and 380 lines**: under the cap and clear of the 381 to
  399 danger band, both asserted by `test_loc_limits.py`. No count is kept; it
  changes with almost every commit.
- **The two `sqlite_master` reads in `shared/db_validation.py`**:
  `validate_db` keeps its connection for `PRAGMA table_info` and reports the
  SQLite error; `is_accounts_database` answers yes or no and closes. A shared
  helper would cost more than the lines it saves.
- **The root `.spec` files**: PyInstaller output, git-ignored.
- **`_leading_underscore.py` modules** in `ui/views` and
  `application/services`: package-private, clear and consistent.
- **The tracked PNG and `.ico` files**: the sized PNGs and the `.ico` are
  derived byte for byte from `ClearBudget.png` by `generate_icons.py`. That is
  settled; do not re-verify it (it needs Pillow, which is deliberately absent).
  `docs/` holds the site's favicons, screenshots and its derived
  `donate.png`; the other root PNGs are artwork masters cropped and scaled at
  runtime by `ui/utils/view_buttons.py` and `ui/utils/icon_buttons.py`. Do not
  raise the masters' size: a pre-sized copy needs a second generator to keep
  in step.

## Not debt (do not "fix" these)

- **Ownership by stamp first, file name second** (`shared/db_ownership.py`).
  An unstamped legacy budget is recognised by name; opening it stamps it, so
  the state ends itself. The Load challenge and the Save refusal share exactly
  this reach on purpose.
- **`VERSION` with `stamp_version.py`**: the single-source pattern, with the
  build scripts calling the stamper so it cannot be forgotten.
- **`test_data_dir_isolation.py`**, **`test_auth_structure.py`** and
  **`test_layering_rules.py`**: invariants held by the suite rather than
  by convention.
- **Two requirements files**: `requirements.txt` for runtime (what the
  Flatpak build installs and the DMG build checks against) and `requirements-dev.txt` for tooling,
  with platform-only packages behind environment markers.
- **Three independent delivery paths**, with `cleanup_flatpak.sh` scoped to
  Flatpak output so one clean cannot destroy another platform's build.
- **The setup program's seams** (`CommandRunner`, `ProcessController`,
  `InstallerIdentity`): they let the privileged installer sit inside the
  coverage gate without a test spawning a process or writing the user's own
  registry key.
- **`.coveragerc` omitting `clear_budget/ui/*`**: what remains there is
  presentation. Money, percentage and category formatting lives in
  `clear_budget/application/formatting.py`, inside the gate.
- **Table focus rules in a structural test**: `test_table_focus_invariants.py`
  holds both the focus-policy route and the stylesheet route to a ring round a
  table; planted violations prove it bites.
