"""Resilient header sizing for the installer UI.

Windows DPI scaling / Accessibility text size / mixed-DPI multi-monitor setups
can produce 1-2px rounding differences in Qt's font metrics and layout.

That can lead to visible clipping of the last glyph (e.g. the "p" in "Setup")
even when `QFontMetrics.elidedText()` would not elide.

This module centralizes the header sizing logic to keep
[`InstallerMainWindow`](installer/ui/main_window.py:43) small.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QEvent, QTimer, Qt
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import QApplication


@dataclass(slots=True)
class HeaderFitController:
    """Ensure the installer header title is never visually truncated."""

    window: Any
    title_attr: str = "_header_title"
    _scheduled: bool = False
    _in_progress: bool = False

    def on_theme_applied(self) -> None:
        """Capture baseline font sizes after a QSS/style change."""

        title = getattr(self.window, self.title_attr, None)
        if title is None:
            return

        f: QFont = title.font()
        base_px = f.pixelSize() if f.pixelSize() > 0 else None
        base_pt = f.pointSizeF() if f.pointSizeF() > 0 else None
        title.setProperty("_base_header_font_px", base_px)
        title.setProperty("_base_header_font_pt", base_pt)

        # Lock in a minimum size based on the post-style size hint. This prevents
        # the header row from being sized to a slightly-too-small height/width
        # due to font metric rounding.
        try:
            title.setMinimumSize(title.sizeHint())
        except Exception:
            pass

    def schedule(self) -> None:
        if self._scheduled:
            return
        self._scheduled = True
        # Layout/style can settle over multiple event loop turns.
        QTimer.singleShot(0, self._ensure_fits)
        QTimer.singleShot(50, self._ensure_fits)

    def ensure_now(self) -> None:
        """Run a sizing pass immediately (best effort)."""

        self._ensure_fits()

    def should_watch_event_type(self, et) -> bool:  # noqa: ANN001
        watched = {
            QEvent.Type.ScreenChangeInternal,
            QEvent.Type.FontChange,
            QEvent.Type.StyleChange,
            QEvent.Type.ApplicationFontChange,
        }
        # Not all PySide6 builds expose every Qt event enum. Guard optional ones.
        dpi_change = getattr(QEvent.Type, "DpiChange", None)
        if dpi_change is not None:
            watched.add(dpi_change)
        return et in watched

    def _ensure_fits(self) -> None:
        self._scheduled = False
        if self._in_progress:
            return

        w = self.window
        title = getattr(w, self.title_attr, None)
        if title is None:
            return
        if not w.isVisible():
            return

        self._in_progress = True
        try:
            QApplication.processEvents()

            missing_w, missing_h = self._ensure_label_has_bbox_room(title)
            if self._fits(title):
                return

            self._try_grow_window(missing_w=missing_w, missing_h=missing_h)
            self._ensure_window_minimum_for_layout()
            if self._fits(title):
                return

            self._shrink_font_until_fit(title)
            self._ensure_window_minimum_for_layout()
        finally:
            self._in_progress = False

    def _ensure_window_minimum_for_layout(self) -> None:
        """Ensure the whole installer UI has enough room for all labels.

        This does not attempt to make *arbitrarily long* dynamic strings fit
        horizontally (e.g. very long paths in editable controls), but it does
        ensure the window can expand to fit the layout's size hint so that
        labels are not clipped by an artificially-small window.
        """

        w = self.window
        cw = w.centralWidget()
        if cw is None:
            return

        hint = cw.sizeHint()
        if not hint.isValid():
            return

        screen = w.screen() or QApplication.primaryScreen()
        if screen is not None:
            max_w = int(screen.availableGeometry().width() * 0.98)
            max_h = int(screen.availableGeometry().height() * 0.98)
        else:
            max_w = w.width()
            max_h = w.height()

        min_w = min(max_w, max(w.minimumWidth(), hint.width()))
        min_h = min(max_h, max(w.minimumHeight(), hint.height()))
        w.setMinimumSize(min_w, min_h)

        target_w = min(max_w, max(w.width(), min_w))
        target_h = min(max_h, max(w.height(), min_h))
        if target_w != w.width() or target_h != w.height():
            w.resize(target_w, target_h)
            QApplication.processEvents()

    @staticmethod
    def _fits(title) -> bool:  # noqa: ANN001
        fm = QFontMetrics(title.font())

        # Basic guard: if Qt would elide, it doesn't fit.
        available = max(0, title.contentsRect().width())
        elided = fm.elidedText(title.text(), Qt.ElideRight, available)
        if elided != title.text():
            return False

        # Strong guard: avoid 1-2px clipping even when not elided.
        try:
            tight = fm.tightBoundingRect(title.text())
            return (
                title.contentsRect().width() >= int(tight.width() + 4)
                and title.contentsRect().height() >= int(tight.height() + 4)
            )
        except Exception:
            return True

    @staticmethod
    def _tight_requirements_px(title) -> tuple[int, int]:  # noqa: ANN001
        fm = QFontMetrics(title.font())
        try:
            tight = fm.tightBoundingRect(title.text())
            req_w = int(tight.width() + 6)
            req_h = int(tight.height() + 6)
        except Exception:
            # Fallback: conservative.
            req_w = int(fm.horizontalAdvance(title.text()) + 10)
            req_h = int(fm.height() + 6)
        return req_w, req_h

    def _ensure_label_has_bbox_room(self, title) -> tuple[int, int]:  # noqa: ANN001
        """Ensure the label itself has enough contents rect in both axes."""

        req_w, req_h = self._tight_requirements_px(title)
        have_w = max(0, title.contentsRect().width())
        have_h = max(0, title.contentsRect().height())

        missing_w = max(0, req_w - have_w)
        missing_h = max(0, req_h - have_h)

        if missing_h > 0:
            title.setMinimumHeight(max(title.minimumHeight(), req_h))
        if missing_w > 0:
            title.setMinimumWidth(max(title.minimumWidth(), req_w))

        return missing_w, missing_h

    def _try_grow_window(self, *, missing_w: int, missing_h: int) -> None:
        w = self.window

        screen = w.screen() or QApplication.primaryScreen()
        if screen is not None:
            max_w = int(screen.availableGeometry().width() * 0.98)
            max_h = int(screen.availableGeometry().height() * 0.98)
        else:
            max_w = w.width()
            max_h = w.height()

        # Width: prefer growing by measured missing pixels.
        if missing_w > 0 and w.width() < max_w:
            new_w = min(max_w, w.width() + missing_w + 24)
            if new_w > w.width():
                w.setMinimumWidth(new_w)
                w.resize(new_w, w.height())
                QApplication.processEvents()

        # Height: only grow if needed.
        if missing_h > 0 and w.height() < max_h:
            new_h = min(max_h, w.height() + missing_h + 16)
            if new_h > w.height():
                w.setMinimumHeight(new_h)
                w.resize(w.width(), new_h)
                QApplication.processEvents()

    def _shrink_font_until_fit(self, title) -> None:  # noqa: ANN001
        """Last resort: reduce header font size until it fits."""

        base_px = title.property("_base_header_font_px")
        base_pt = title.property("_base_header_font_pt")

        if not base_px and not base_pt:
            cur = title.font()
            base_px = cur.pixelSize() if cur.pixelSize() > 0 else None
            base_pt = cur.pointSizeF() if cur.pointSizeF() > 0 else None

        f = QFont(title.font())
        if base_px:
            size = int(base_px)
            min_px = 22
            while size > min_px:
                size -= 1
                f.setPixelSize(size)
                title.setFont(f)
                QApplication.processEvents()
                self._ensure_label_has_bbox_room(title)
                if self._fits(title):
                    return
        elif base_pt:
            size = float(base_pt)
            min_pt = 10.0
            while size > min_pt:
                size -= 0.5
                f.setPointSizeF(size)
                title.setFont(f)
                QApplication.processEvents()
                self._ensure_label_has_bbox_room(title)
                if self._fits(title):
                    return

