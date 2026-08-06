"""File size held by assertion: the 400-line cap and the 5% danger band.

Ported from NarrateX's equivalent so the two do not drift apart in shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class LocOffender:
    path: str
    lines: int


def _repo_root() -> Path:
    # tests/structural/test_loc_limits.py -> tests/structural -> tests -> repo
    return Path(__file__).resolve().parents[2]


# Delivery scripts and their helpers, wherever they sit. Length is not a defect
# in these: they are linear recipes read top to bottom, where splitting a
# sequence of flags and steps across modules costs more than it buys. Listed
# rather than left to chance, so one cannot escape the cap merely by never
# having been thought of.
_BUILD_SCRIPTS = frozenset(
    {
        "buildexe.py",
        "buildinstaller.py",
        "builddmg.py",
        "dmg_icon.py",
        "build_utils.py",
        "build_payload.py",
        "generate_icons.py",
        "generate_scripts.py",
        "stamp_version.py",
    }
)

_IN_SCOPE_PREFIXES = ("clear_budget/", "installer/", "tests/")
_IN_SCOPE_ROOT_FILES = frozenset({"main.py"})

_EXCLUDED_PARTS = frozenset(
    {
        ".git",
        "__pycache__",
        "venv",
        ".venv",
        "build",
        "dist",
        "dist-installer",
        "dist-pyinstaller",
        ".flatpak-build",
        ".flatpak-builder",
        ".flatpak-repo",
        ".flatpak-wheels",
        ".egg",
    }
)


def _is_in_scope_python_file(path: Path, *, repo_root: Path) -> bool:
    if path.suffix != ".py":
        return False

    if {p.lower() for p in path.parts} & _EXCLUDED_PARTS:
        return False

    if path.name in _BUILD_SCRIPTS:
        return False

    try:
        rel = path.relative_to(repo_root).as_posix()
    except ValueError:
        return False

    return rel.startswith(_IN_SCOPE_PREFIXES) or path.name in _IN_SCOPE_ROOT_FILES


def _count_physical_lines(path: Path) -> int:
    # Physical lines, not logical LOC. Tolerant decoding so an odd encoding in
    # an artefact cannot fail the run for the wrong reason.
    return sum(1 for _ in path.open("r", encoding="utf-8", errors="ignore"))


# REFACTORING RULE (the 5% rule): 400 is the limit and the normal target, so a
# file below it and clear of the band below needs nothing doing to it.
#
# 5% of 400 is 20, so >380 and <400 (381 to 399) is the danger band. A file
# sitting in that band is reduced to <=350, never left at 399. That covers both
# a file that grew into the band and a file refactored down from over the cap,
# which must land at <=350 rather than stopping the moment it clears 400.
#
# Shaving one or two lines to sit just under 400 buys nothing: the next edit
# breaks it again and the same file gets refactored over and over. Extract a
# cohesive concern instead and take a real reduction once.
#
# Both halves are asserted below, one test each, so a red run names which was
# broken. The band assertion is the constrain-the-bad-state form: it stops a
# file entering the band rather than reporting it afterwards.
_CAP_LINES = 400

# 5% of the cap. Derived rather than written as 380, so the two numbers cannot
# drift apart if the cap ever moves.
_DANGER_BAND_PERCENT = 5
_DANGER_BAND_START = _CAP_LINES - (_CAP_LINES * _DANGER_BAND_PERCENT) // 100

# Where a file in the band has to land. Not just under the cap: see above.
_LANDING_LINES = 350


def _in_scope_line_counts(root: Path) -> list[LocOffender]:
    return [
        LocOffender(path=p.relative_to(root).as_posix(), lines=_count_physical_lines(p))
        for p in root.rglob("*.py")
        if _is_in_scope_python_file(p, repo_root=root)
    ]


def _report(offenders: list[LocOffender]) -> str:
    ordered = sorted(offenders, key=lambda o: (o.lines, o.path), reverse=True)
    return "\n".join(f"- {o.lines:4d}  {o.path}" for o in ordered)


def test_all_in_scope_python_files_are_at_most_400_lines() -> None:
    root = _repo_root()

    offenders = [f for f in _in_scope_line_counts(root) if f.lines > _CAP_LINES]

    if offenders:
        raise AssertionError(
            "File size constraint violated: every in-scope *.py must be "
            f"<= {_CAP_LINES} lines. Extract a cohesive module and land the "
            f"result at <= {_LANDING_LINES}, not just under the cap.\n"
            + _report(offenders)
        )


def test_no_in_scope_python_file_sits_in_the_danger_band() -> None:
    """The 5% rule, enforced rather than only documented.

    A file at 399 passes the cap and fails the next edit made to it, for a
    reason unrelated to that edit. Catching it here means it is dealt with
    while it is cheap, which is the whole point of the band.
    """

    root = _repo_root()

    offenders = [
        f
        for f in _in_scope_line_counts(root)
        if _DANGER_BAND_START < f.lines < _CAP_LINES
    ]

    if offenders:
        raise AssertionError(
            f"The 5% danger band ({_DANGER_BAND_START + 1} to {_CAP_LINES - 1} "
            "lines) is occupied. Take each file to "
            f"<= {_LANDING_LINES} by extracting a cohesive concern; do not shave "
            "lines to sit just under the cap, because the next edit undoes it.\n"
            + _report(offenders)
        )
