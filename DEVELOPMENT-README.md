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
black, flake8).

### Run, test and lint from source

```
python main.py     # launch the app
pytest             # run the full suite (100% coverage gate enforced)
black .            # format (line length 88)
flake8             # lint
```

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
