# ClearBudget - Development and Build Guide

How to set up a development environment and produce a distributable package of
ClearBudget on each supported platform.

- For the feature list and day-to-day usage, see [README.md](README.md).
- For the layer boundaries and design rules, see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Prerequisites (all platforms)

### 1. Install a suitable Python

ClearBudget targets **Python 3.11 or newer**.

- **Windows** - install from [python.org](https://www.python.org/downloads/) and
  tick "Add python.exe to PATH" or run `winget install Python.Python.3.12`.
- **macOS** - the system Python is not suitable for building; install with
  Homebrew (`brew install python`) or from python.org.
- **Linux** - usually preinstalled. On Ubuntu and Debian, make sure the venv and
  pip modules are present: `sudo apt install python3 python3-venv python3-pip`.

### 2. Create and activate a virtual environment

Create it in the repository root and name it `venv`; the Linux Flatpak script
expects that exact name.

Windows (PowerShell):

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

macOS and Linux:

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install the dependencies

```
python -m pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt
```

`requirements.txt` holds the runtime dependencies (PySide6, bcrypt, keyring).
`requirements-dev.txt` adds the build and quality tooling (PyInstaller, pytest,
pytest-cov, coverage, black, flake8, ruff).

The icon scripts (`generate_icons.py` and the macOS `dmg_icon.py`) need Pillow,
which is not in `requirements-dev.txt` because the PNG sizes and the `.ico` at
the repository root are committed and a normal build never regenerates them.
Install it only if you are changing the artwork: `pip install pillow`.

`ClearBudget.png`, 1024x1024 RGBA, is the master and every other icon asset is
derived from it. `generate_icons.py` emits the seven PNG sizes and the
multi-resolution `.ico`; it reproduces all eight tracked files byte for
byte, so running it on a clean tree leaves `git status` empty. Change the
artwork by replacing the master and re-running it.

**The sized PNGs are `ClearBudget_<size>.png`, capitalised.** That is what
`generate_icons.py` writes, what git tracks and what `build_flatpak.sh` and
`builddmg.py` reference. It matters because Windows sets `core.ignorecase`
and macOS volumes are case-insensitive by default, so a file renamed to
`clearbudget_256.png` on either looks identical to git and to `ls`, while a
Linux checkout still gets the capitalised name. The working tree drifted into
exactly that state once and cost an afternoon of chasing a Flatpak bug that
did not exist. If `ls` here disagrees with `git ls-files`, believe
`git ls-files`. The Windows build steps (`buildexe.py`, `buildinstaller.py`)
and several runtime lookups still name the lower-cased form; that is safe
because they only ever run where the filesystem does not care. `shared/resources.py`
searches both capitalisations, so a case-sensitive filesystem cannot lose the
icon either way.

### Run, test and lint from source

```
python main.py     # launch the app
pytest -v --cov    # run the full suite (100% line and branch gate enforced)
black .            # format (line length 88)
flake8             # lint
ruff check .       # lint (default rules plus the blind-handler rules)
```

The suite is Qt-free and runs clean in one process: the fragile widget-level
PySide6 tests were removed and the UI layer is excluded from the coverage gate
(see `.coveragerc`). Pure UI-layer logic is still tested without a `QApplication`
under `tests/ui_logic`. Tests use real implementations and hand-written fakes, no
mock libraries.

A coverage-gated run prints the coverage table last and emits no "N passed"
line, so read the exit code rather than the tail of the output: `0` means the
tests passed AND the gate was met.

The gate is measured by BRANCH as well as by line (`branch = True` in
`.coveragerc`, `--cov-fail-under=100`) and it spans three sources:
`clear_budget`, `main` and the Qt-free half of the setup program under
`installer/`. The setup program is in there because it does the most privileged
work in the repository: registry writes, shortcut creation, per-user
deployment, process termination and directory removal. `installer/app.py` and
`installer/ui` are excluded on the same grounds as `clear_budget/ui` and
`installer/build_payload.py` is a build script.

Outside the gate: the `.coveragerc` omissions (UI, interfaces, `main.py`, build
scripts) and any line marked `# pragma: no cover`, of which there are a fair
number on thin pass-throughs and on the SQLite payment-method repository. Read
100% as "100% of what is gated", not as "every line is tested"; ARCHITECTURE.md
says which parts sit outside it.

### Testing the setup program

`tests/installer/` exercises everything under `installer/` except `app.py` and
`installer/ui`. Nothing in it touches a real installation and that is held in
place by four fixtures in `tests/installer/conftest.py`, each closing one
route to the real machine. Three are autouse and unconditional:

- the per-user profile directories are redirected through the environment
  variables the code reads;
- the `platformdirs` lookups are redirected **in their own right**, because
  `platformdirs` asks Windows for the known folder rather than reading
  `%LOCALAPPDATA%`. Without this fixture the legacy-directory migration would
  find and move your actual data;
- the payload anchor is redirected so a small stand-in bundle stands in for the
  real fifty-megabyte payload.

The fourth is requested by name rather than autouse: `scratch_identity` yields
an `InstallerIdentity` whose HKCU key lives under a test-only root and is
deleted in teardown. A test can only reach the registry by taking that
identity, so asking for it is the same act as needing it.

`tests/installer/fakes.py` holds the hand-written doubles for the three
injectable seams (`CommandRunner`, `ProcessController` and the identity value).
What can be exercised for real is: shortcuts are written through the same Shell
Link COM interface the install uses, the registry round-trips through `winreg`
against the scratch key; a full install deploys and registers a real bundle,
all inside the redirected tree.

Appearance is verified with throwaway offscreen probes rather than tests, since
what matters is what gets painted. Run those with
`QT_QPA_PLATFORM=offscreen`, EXCEPT when measuring text or emoji: offscreen
substitutes Qt's own font database, so a font size tuned there does not match
what ships. Measure those on the real platform.

**Always point a probe at a scratch data directory.** The real data
directory (`%LOCALAPPDATA%\ClearBudget` on Windows; see README's Data
Storage section for the other platforms, plus a surviving pre-5.1
`~/.clearbudget`) holds live user data: both databases, the saved UI
settings (theme, remembered save-file location and any skipped update
version) and the Remember me sidecar (`remembered_login.json`). Set
`CLEARBUDGET_HOME` and every path the app resolves moves with it:

```powershell
$env:CLEARBUDGET_HOME = "$env:TEMP\cb-probe"
```

This is not a style preference. A probe that calls `theme.apply_theme` to
measure something persists that theme, because persisting is what the function
is for and the app then opens in the theme the probe used. The test suite sets
the variable for itself through an autouse fixture in `tests/conftest.py` and
`tests/structural/test_data_dir_isolation.py` fails if that ever stops
happening.

---

## Versioning

The `VERSION` file at the repository root is the single source of truth. Bump the
patch/minor/major there and nothing else needs editing:

- the runtime reads it via `clear_budget/version.py`;
- `pyproject.toml` reads it dynamically (`[tool.setuptools.dynamic]`), so packaging
  metadata always matches;
- static docs that cannot read it at runtime (the GitHub Pages site under `docs/`)
  are stamped from it by `stamp_version.py`, which `buildexe.py` and
  `buildinstaller.py` run automatically at the start of every build. Run
  `python stamp_version.py` by hand after a bump if you want the docs updated
  without a full build. It is idempotent and prints what it touched.

`stamp_version.py` targets the `docs/` tree ONLY. The root markdown files
(README, ARCHITECTURE, TECH_DEBT, this file) carry no version data at all,
stamped or otherwise: they are read alongside the source, where `VERSION` is
the answer, so a copy of it in prose is one more thing that can disagree.

Never hardcode a version string anywhere except `VERSION`.

---

## Build per platform

Each build path is independent and writes its own artefact. Run from the
repository root with the venv active.

### Linux - Flatpak (`clearbudget.flatpak`)

Two helper scripts live in the repository root:

```bash
./cleanup_flatpak.sh   # optional: uninstall and purge any previous Flatpak build
./build_flatpak.sh     # build, install locally and produce clearbudget.flatpak
```

`build_flatpak.sh` installs `flatpak` and `flatpak-builder` if they are missing
(via apt, dnf or pacman), adds the Flathub remote, pulls the Freedesktop runtime,
builds fully offline from pre-downloaded wheels and writes **`clearbudget.flatpak`**
for external deployment. Pass `--no-bundle` to build and install locally without
producing the distributable bundle.

Install the bundle on another machine:

```bash
flatpak install --user clearbudget.flatpak
flatpak run com.oliverernster.clearbudget
```

### macOS - Disk image (`clearbudget.dmg`)

Requires macOS with the Xcode command-line tools and Homebrew.

```bash
python builddmg.py
```

This produces **`clearbudget.dmg`** for installation on macOS. Signing and
notarization are the default, not an option: credentials come from a
`notarytool` keychain profile (`ClearBudget`, override with
`APPLE_KEYCHAIN_PROFILE`) or from `APPLE_ID` with an app-specific
`APPLE_APP_PASSWORD` for CI; the signing identity and `APPLE_TEAM_ID` have
defaults that env vars can override. Credentials are checked before the build
starts where possible (a malformed app-specific password fails in seconds
rather than after a full PyInstaller run) and a failed notarization stops the
build outright, because an unnotarized DMG is rejected by Gatekeeper on every
machine but the one that signed it and that failure is invisible at build
time. Set `ALLOW_UNNOTARIZED=1` to build a local-testing image that must not
be released.

### Windows - Installer (`dist-installer\ClearBudgetSetup.exe`)

Run the two build steps in order, then launch the resulting installer:

```
python buildexe.py          # bundle the app with PyInstaller
python buildinstaller.py    # build the payload and the setup executable
dist-installer\ClearBudgetSetup.exe   # run the installer to perform a real install
```

`buildexe.py` creates the standalone application bundle at
`dist-pyinstaller\ClearBudget\ClearBudget.exe`. `buildinstaller.py` (Windows
only) wraps it into the single-file, per-user installer
**`dist-installer\ClearBudgetSetup.exe`**, which performs the actual install when
run.

---

## Artefact summary

| Platform | Command(s) | Artefact for deployment |
|----------|------------|-------------------------|
| Linux | `./build_flatpak.sh` | `clearbudget.flatpak` |
| macOS | `python builddmg.py` | `clearbudget.dmg` |
| Windows | `python buildexe.py` then `python buildinstaller.py` | `dist-installer\ClearBudgetSetup.exe` |
