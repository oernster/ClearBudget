# Clear Budget - Development and Build Guide

How to set up a development environment and produce a distributable package of
Clear Budget on each supported platform.

- For the feature list and day-to-day usage, see [README.md](README.md).
- For the layer boundaries and design rules, see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Prerequisites (all platforms)

### 1. Install a suitable Python

Clear Budget targets **Python 3.11 or newer**.

- **Windows** - install from [python.org](https://www.python.org/downloads/) and
  tick "Add python.exe to PATH", or run `winget install Python.Python.3.12`.
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

`requirements.txt` holds the runtime dependencies (PySide6, bcrypt).
`requirements-dev.txt` adds the build and quality tooling (PyInstaller, pytest,
pytest-cov, coverage, black, flake8, ruff).

The icon scripts (`create_icons.py`, `create_icon.py` and the macOS
`dmg_icon.py`) need Pillow, which is not in `requirements-dev.txt` because the
icons under `assets/` are committed and a normal build never regenerates them.
Install it only if you are changing the artwork: `pip install pillow`.

### Run, test and lint from source

```
python main.py     # launch the app
pytest -v --cov    # run the full suite (100% coverage gate enforced)
black .            # format (line length 88)
flake8             # lint
ruff check .       # lint (wider default rule set)
```

The suite is Qt-free and runs clean in one process: the fragile widget-level
PySide6 tests were removed, and the UI layer is excluded from the coverage gate
(see `.coveragerc`). Pure UI-layer logic is still tested without a `QApplication`
under `tests/ui_logic`. Tests use real implementations and hand-written fakes, no
mock libraries.

A coverage-gated run prints the coverage table last and emits no "N passed"
line, so read the exit code rather than the tail of the output: `0` means the
tests passed AND the gate was met.

The gate covers everything except the `.coveragerc` omissions (UI, interfaces,
`main.py`, build scripts) and any line marked `# pragma: no cover`, of which
there are a fair number on thin pass-throughs and on the SQLite payment-method
repository. Read 100% as "100% of what is gated", not as "every line is
tested"; ARCHITECTURE.md says which parts sit outside it.

Appearance is verified with throwaway offscreen probes rather than tests, since
what matters is what gets painted. Run those with
`QT_QPA_PLATFORM=offscreen`, EXCEPT when measuring text or emoji: offscreen
substitutes Qt's own font database, so a font size tuned there does not match
what ships. Measure those on the real platform.

**Always point a probe at a scratch data directory.** `~/.clearbudget` holds
live user data: both databases, the logs and the saved theme. Set
`CLEARBUDGET_HOME` and every path the app resolves moves with it:

```powershell
$env:CLEARBUDGET_HOME = "$env:TEMP\cb-probe"
```

This is not a style preference. A probe that calls `theme.apply_theme` to
measure something persists that theme, because persisting is what the function
is for, and the app then opens in the theme the probe used. The test suite sets
the variable for itself through an autouse fixture in `tests/conftest.py`, and
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
  without a full build.

Never hardcode a version string anywhere except `VERSION`.

---

## Build per platform

Each build path is independent and writes its own artefact. Run from the
repository root with the venv active.

### Linux - Flatpak (`clearbudget.flatpak`)

Two helper scripts live in the repository root:

```bash
./cleanup_flatpak.sh   # optional: uninstall and purge any previous Flatpak build
./build_flatpak.sh     # build, install locally, and produce clearbudget.flatpak
```

`build_flatpak.sh` installs `flatpak` and `flatpak-builder` if they are missing
(via apt, dnf or pacman), adds the Flathub remote, pulls the Freedesktop runtime,
builds fully offline from pre-downloaded wheels, and writes **`clearbudget.flatpak`**
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

This produces **`clearbudget.dmg`** for installation on macOS. Code signing and
notarization are applied automatically when the matching environment variables
are set (`DEVELOPER_ID_APPLICATION`, `APPLE_ID`, `APPLE_APP_PASSWORD`,
`APPLE_TEAM_ID`); without them the build still completes, unsigned.

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
