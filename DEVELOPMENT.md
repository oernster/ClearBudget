# ClearBudget - Development and Build Guide

How to set up a development environment and produce a distributable package of
ClearBudget on each supported platform.

- For the feature list and day-to-day usage, see [README.md](README.md).
- For the layer boundaries and design rules, see [ARCHITECTURE.md](ARCHITECTURE.md).
- For running and writing the tests, see [TESTING.md](TESTING.md).

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

`donate.png` is a SECOND master, for the footer's donate button. It is
handled separately because it is not an icon: it is a wide picture drawn at a
button's height, so squaring it would spend half the height on empty canvas.
The application derives nothing from it, since `image_icon_pixmap` crops and
scales the full-size master at runtime exactly as it does for every other tray
picture. The landing page cannot do that, so the one derived copy
`generate_icons.py` writes is `docs/donate.png`, cropped to its artwork and
scaled by height alone. It is idempotent there too.

That root `.ico` is also what `buildexe.py` and `buildinstaller.py` embed as
each executable's own icon, through PyInstaller's `--icon`. That is a
different mechanism from the `--add-data` staging beside it: `--icon` writes
into the executable's resources, where Explorer and the taskbar read it,
while `--add-data` ships a file the running code opens. Omit it and
PyInstaller embeds its own default, which is a picture of a diskette.

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
pytest             # run the full suite (100% line and branch gate enforced)
black .            # format (line length 88)
flake8             # lint
ruff check .       # lint (default rules, blind-handler rules, DTZ)
```

How to read a run, what the gate holds and leaves out, the setup program's
tests and how a new test or guard is written are in [TESTING.md](TESTING.md).

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
  without a full build. It is idempotent and prints what it touched. It also
  puts a content hash on every local stylesheet and script link in the site
  (`styles.css?v=<hash>`) so a browser cannot pair a fresh page with a stale
  cached stylesheet.

`stamp_version.py` targets the `docs/` tree ONLY. The root markdown files
(README, ARCHITECTURE, TECH_DEBT, this file) carry no version data at all,
stamped or otherwise: they are read alongside the source, where `VERSION` is
the answer, so a copy of it in prose is one more thing that can disagree.

Never hardcode a version string anywhere except `VERSION`.

---

## Build per platform

Each build path is independent and writes its own artefact. Run from the
repository root with the venv active.

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

---

## Artefact summary

| Platform | Command(s) | Artefact for deployment |
|----------|------------|-------------------------|
| Windows | `python buildexe.py` then `python buildinstaller.py` | `dist-installer\ClearBudgetSetup.exe` |
| macOS | `python builddmg.py` | `clearbudget.dmg` |
| Linux | `./build_flatpak.sh` | `clearbudget.flatpak` |

---

See also [README.md](README.md), [ARCHITECTURE.md](ARCHITECTURE.md) and
[TESTING.md](TESTING.md).
