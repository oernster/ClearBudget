"""The setup program bows out when the operation it was asked for is done.

Install, upgrade, reinstall and repair all used to leave the window sitting
there: the launch branch returned without closing and repair fell past the
uninstall check entirely, so the only operation that ever closed was an
uninstall started from Windows Settings. A setup program still on screen after
it has finished reads as though something is pending.

`installer/ui` is outside the coverage gate, so this is not counted; it runs
regardless, and the decision under test is pure policy over an operation.
"""

from installer.state.model import Operation
from installer.ui._main_window_actions import _should_close_after


class _CliArgs:
    def __init__(self, *, uninstall: bool) -> None:
        self.uninstall = uninstall


class _Window:
    """Only what the decision reads."""

    def __init__(self, *, launched_as_uninstaller: bool = False) -> None:
        self._cli_args = _CliArgs(uninstall=launched_as_uninstaller)


class TestClosesWhenTheWorkIsDone:
    def test_install_closes(self) -> None:
        assert _should_close_after(_Window(), Operation.INSTALL)

    def test_upgrade_closes(self) -> None:
        assert _should_close_after(_Window(), Operation.UPGRADE)

    def test_reinstall_closes(self) -> None:
        assert _should_close_after(_Window(), Operation.REINSTALL)

    def test_repair_closes(self) -> None:
        """Repair was the one that fell through every branch."""
        assert _should_close_after(_Window(), Operation.REPAIR)


class TestUninstallKeepsItsOwnRule:
    def test_launched_from_windows_settings_it_closes(self) -> None:
        window = _Window(launched_as_uninstaller=True)
        assert _should_close_after(window, Operation.UNINSTALL)

    def test_chosen_by_hand_it_stays_open(self) -> None:
        """The window stays so the result is visible and another op can follow."""
        window = _Window(launched_as_uninstaller=False)
        assert not _should_close_after(window, Operation.UNINSTALL)

    def test_a_window_with_no_cli_args_at_all_stays_open(self) -> None:
        class _Bare:
            _cli_args = None

        assert not _should_close_after(_Bare(), Operation.UNINSTALL)
