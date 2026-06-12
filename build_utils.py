#!/usr/bin/env python3
"""Shared shell helpers for the ClearBudget build scripts."""

from __future__ import annotations

import shutil
import subprocess
import sys


def run(cmd: list[str], check: bool = True, **kwargs) -> subprocess.CompletedProcess:
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    return subprocess.run(cmd, check=check, **kwargs)


def require(tool: str, brew_pkg: str | None = None) -> None:
    if shutil.which(tool):
        return
    pkg = brew_pkg or tool
    print(f"{tool} not found — installing via brew...")
    run(["brew", "install", pkg])
    if not shutil.which(tool):
        sys.exit(f"ERROR: {tool} still not found after brew install. Aborting.")


def section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")
