"""Taking the foreground, exercised without a real window anywhere."""

from __future__ import annotations

from clear_budget.shared import foreground

_OWN_THREAD = 100
_HOLDER_THREAD = 200
_HANDLE = 4242


class _FakeUser32:
    """Records the sequence, which is the whole behaviour under test."""

    def __init__(self, *, holder_thread: int = _HOLDER_THREAD, attach_ok: bool = True):
        self._holder_thread = holder_thread
        self._attach_ok = attach_ok
        self.calls: list[tuple] = []

    def GetForegroundWindow(self):  # noqa: N802 (Win32 name)
        self.calls.append(("GetForegroundWindow",))
        return 999

    def GetWindowThreadProcessId(self, hwnd, pid_out):  # noqa: N802 (Win32 name)
        self.calls.append(("GetWindowThreadProcessId", hwnd, pid_out))
        return self._holder_thread

    def AttachThreadInput(self, own, other, attach):  # noqa: N802 (Win32 name)
        self.calls.append(("AttachThreadInput", own, other, attach))
        return 1 if self._attach_ok else 0

    def BringWindowToTop(self, hwnd):  # noqa: N802 (Win32 name)
        self.calls.append(("BringWindowToTop", hwnd))
        return 1

    def SetForegroundWindow(self, hwnd):  # noqa: N802 (Win32 name)
        self.calls.append(("SetForegroundWindow", hwnd))
        return 1


class _FakeKernel32:
    def GetCurrentThreadId(self):  # noqa: N802 (Win32 name)
        return _OWN_THREAD


def _names(user32: _FakeUser32) -> list[str]:
    return [call[0] for call in user32.calls]


class TestForceForeground:
    def test_no_other_platform_touches_the_windows_api(self):
        """Elsewhere the toolkit's own raise is the whole story."""
        user32 = _FakeUser32()
        assert (
            foreground.force_foreground(
                _HANDLE, platform="linux", user32=user32, kernel32=_FakeKernel32()
            )
            is False
        )
        assert user32.calls == []

    def test_it_joins_the_holder_input_queue_before_asking(self):
        """Without the attach, Windows refuses the call. This was measured."""
        user32 = _FakeUser32()
        assert (
            foreground.force_foreground(
                _HANDLE, platform="win32", user32=user32, kernel32=_FakeKernel32()
            )
            is True
        )
        assert _names(user32) == [
            "GetForegroundWindow",
            "GetWindowThreadProcessId",
            "AttachThreadInput",
            "BringWindowToTop",
            "SetForegroundWindow",
            "AttachThreadInput",
        ]

    def test_it_leaves_nothing_attached_afterwards(self):
        """Two threads sharing an input queue is a state, not a call."""
        user32 = _FakeUser32()
        foreground.force_foreground(
            _HANDLE, platform="win32", user32=user32, kernel32=_FakeKernel32()
        )
        attaches = [call for call in user32.calls if call[0] == "AttachThreadInput"]
        assert [call[3] for call in attaches] == [True, False]
        assert all(call[1:3] == (_OWN_THREAD, _HOLDER_THREAD) for call in attaches)

    def test_the_window_asked_for_is_the_one_raised(self):
        user32 = _FakeUser32()
        foreground.force_foreground(
            _HANDLE, platform="win32", user32=user32, kernel32=_FakeKernel32()
        )
        raised = [call for call in user32.calls if call[0] == "BringWindowToTop"]
        assert raised == [("BringWindowToTop", _HANDLE)]

    def test_the_app_already_holding_the_foreground_attaches_to_nothing(self):
        """A thread cannot attach to itself; the call would simply fail."""
        user32 = _FakeUser32(holder_thread=_OWN_THREAD)
        assert (
            foreground.force_foreground(
                _HANDLE, platform="win32", user32=user32, kernel32=_FakeKernel32()
            )
            is True
        )
        assert "AttachThreadInput" not in _names(user32)

    def test_a_refused_attach_still_asks_and_detaches_nothing(self):
        """Best effort: the ask may still land; there is nothing to undo."""
        user32 = _FakeUser32(attach_ok=False)
        assert (
            foreground.force_foreground(
                _HANDLE, platform="win32", user32=user32, kernel32=_FakeKernel32()
            )
            is True
        )
        assert _names(user32).count("AttachThreadInput") == 1
        assert "SetForegroundWindow" in _names(user32)
