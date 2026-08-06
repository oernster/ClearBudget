"""Which operations may launch the application when setup finishes.

The sibling of `test_close_after_operation.py`, and the same shape of defect:
repair was left out of a set that decides post-operation behaviour. The launch
checkbox is on screen during a repair, so a ticked box did nothing at all.

Uninstall is the only operation that must never launch: there is no longer an
application to start.

`installer/ui` is outside the coverage gate, so this is not counted; it runs
regardless, and the decision under test is pure policy over an operation.
"""

from installer.state.model import Operation
from installer.ui._main_window_ops import LAUNCHABLE_OPS


class TestOperationsThatLeaveSomethingToLaunch:
    def test_install_may_launch(self) -> None:
        assert Operation.INSTALL in LAUNCHABLE_OPS

    def test_upgrade_may_launch(self) -> None:
        assert Operation.UPGRADE in LAUNCHABLE_OPS

    def test_reinstall_may_launch(self) -> None:
        assert Operation.REINSTALL in LAUNCHABLE_OPS

    def test_repair_may_launch(self) -> None:
        """Repair restores the executable, so the ticked box has to mean it."""
        assert Operation.REPAIR in LAUNCHABLE_OPS


class TestUninstallNeverLaunches:
    def test_uninstall_is_excluded(self) -> None:
        assert Operation.UNINSTALL not in LAUNCHABLE_OPS


class TestEveryOperationIsAccountedFor:
    def test_the_set_is_exactly_everything_bar_uninstall(self) -> None:
        """A new operation cannot be added without a decision being made here."""
        assert LAUNCHABLE_OPS == frozenset(Operation) - {Operation.UNINSTALL}
