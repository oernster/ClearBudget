"""Installer CLI.

Supports running as a registered uninstaller via UninstallString.
"""

from __future__ import annotations

import argparse


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(add_help=True)
    p.add_argument("--uninstall", action="store_true", help="Run uninstall flow")
    p.add_argument("--repair", action="store_true", help="Run repair flow")
    p.add_argument("--quiet", action="store_true", help="Do not show UI (best effort)")
    p.add_argument(
        "--remove-user-data",
        action="store_true",
        help="When uninstalling, also remove user data (default: true in UI flows)",
    )
    p.add_argument(
        "--keep-user-data",
        action="store_true",
        help="When uninstalling, keep user data",
    )
    return p.parse_args(argv)


def wants_remove_user_data(args: argparse.Namespace) -> bool:
    if getattr(args, "keep_user_data", False):
        return False
    if getattr(args, "remove_user_data", False):
        return True
    # Default to True for this project (per requirement).
    return True
