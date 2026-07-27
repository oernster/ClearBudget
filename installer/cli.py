"""Installer CLI.

Supports running as a registered uninstaller via UninstallString.

There are deliberately no user-data flags. Uninstall removes the program and
leaves `~/.clearbudget` alone, so there is nothing to opt into or out of. The
`--remove-user-data` and `--keep-user-data` switches that used to sit here
controlled the deletion of two directories this app has never written to,
inherited from the installer this one was rebranded from.
"""

from __future__ import annotations

import argparse


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(add_help=True)
    p.add_argument("--uninstall", action="store_true", help="Run uninstall flow")
    p.add_argument("--repair", action="store_true", help="Run repair flow")
    p.add_argument("--quiet", action="store_true", help="Do not show UI (best effort)")
    return p.parse_args(argv)
