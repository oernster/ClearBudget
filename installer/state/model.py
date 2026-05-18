"""Installer state model and button visibility rules."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import FrozenSet, Optional

from installer.state.versioning import compare_versions


class Operation(str, Enum):
    INSTALL = "install"
    UPGRADE = "upgrade"
    REINSTALL = "reinstall"
    REPAIR = "repair"
    UNINSTALL = "uninstall"


@dataclass(frozen=True, slots=True)
class InstalledInfo:
    version: str
    location: Path


@dataclass(frozen=True, slots=True)
class InstallerState:
    installer_version: str
    installed: Optional[InstalledInfo]

    def allowed_operations(self) -> FrozenSet[Operation]:
        if self.installed is None:
            return frozenset({Operation.INSTALL})

        cmp_ = compare_versions(self.installer_version, self.installed.version)
        if cmp_ == 0:
            return frozenset(
                {Operation.REINSTALL, Operation.REPAIR, Operation.UNINSTALL}
            )
        if cmp_ > 0:
            return frozenset({Operation.UPGRADE, Operation.UNINSTALL})

        # Installer is older than what is installed: no downgrade.
        return frozenset({Operation.REPAIR, Operation.UNINSTALL})

    def status_line(self, app_name: str) -> str:
        if self.installed is None:
            return f"{app_name} is not installed on this user account."
        return (
            f"{app_name} v{self.installed.version} is already installed at "
            f"{self.installed.location}."
        )
