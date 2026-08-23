"""Button and control state for the installer main window.

Extracted from [`_main_window_actions`](installer/ui/_main_window_actions.py) to
keep that module inside the 400-line limit.  Everything here answers one
question: given the current state, which controls are visible, which are
enabled and what do they say.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from installer.state.model import Operation

if TYPE_CHECKING:  # pragma: no cover
    from installer.ui.main_window import InstallerMainWindow

# Primary operations, in the order they are offered in the centre row.
_PRIMARY_OPS = (
    Operation.INSTALL,
    Operation.UPGRADE,
    Operation.REINSTALL,
    Operation.REPAIR,
)

_OP_LABELS = {
    Operation.INSTALL: "Install",
    Operation.UPGRADE: "Upgrade",
    Operation.REINSTALL: "Reinstall",
    Operation.REPAIR: "Repair",
}


def set_buttons_for_allowed_ops(
    window: InstallerMainWindow,
    allowed: set[Operation] | frozenset[Operation],
) -> None:
    # Primary buttons are shown in the center row. We use up to two.
    # Uninstall is shown separately in red.
    window._btn_uninstall.setVisible(Operation.UNINSTALL in allowed)

    primary_ops: list[Operation] = [op for op in _PRIMARY_OPS if op in allowed]
    left = primary_ops[0] if primary_ops else None
    right = primary_ops[1] if len(primary_ops) > 1 else None

    _bind_primary(window, window._btn_primary_left, left)
    _bind_primary(window, window._btn_primary_right, right)


def _bind_primary(
    window: InstallerMainWindow,
    button,
    op: Operation | None,
) -> None:
    """Show, label and re-wire one primary button; hide it when unused."""
    if op is None:
        button.setVisible(False)
        return

    button.setVisible(True)
    button.setText(_OP_LABELS[op])
    try:
        button.clicked.disconnect()
    except RuntimeError:
        # PySide raises when there is nothing connected. No previous
        # connection to drop; re-wiring from scratch is fine.
        pass
    button.clicked.connect(lambda: window._request_operation(op))


def set_ui_busy(window: InstallerMainWindow, busy: bool) -> None:
    window._progress_bar.setVisible(busy)
    for w in [
        window._btn_primary_left,
        window._btn_primary_right,
        window._btn_uninstall,
        window._licence_btn,
        window._theme_toggle_btn,
        window._install_dir_edit,
        window._desktop_cb,
        window._startmenu_cb,
        window._launch_cb,
    ]:
        w.setEnabled(not busy)
