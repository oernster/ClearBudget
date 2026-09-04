"""Credit card view widget - displays credit card status and exhaustion warnings."""

from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from clear_budget.application.services.budget_service import BudgetService
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.ui import theme, ui_scale
from clear_budget.ui.theme_tokens import STATE_CAUTION, STATE_RED, STATE_SAFE
from clear_budget.ui.utils.format_helpers import (
    apply_nav_label_color,
    build_centered_nav_header,
    nav_glyph_height,
)
from clear_budget.ui.views._credit_card_projection_strip import (
    _PROJECTION_MONTHS,
    CreditCardProjectionStripMixin,
)
from clear_budget.ui.views._credit_card_view_loaders import (
    CreditCardViewLoaderMixin,
)
from clear_budget.ui.utils.view_buttons import (
    build_view_buttons,
    ring_view_stops,
)
from clear_budget.ui.widgets._tray_buttons import (
    build_budgets_button,
    build_info_button,
    build_save_load_buttons,
    build_tray_separator,
    build_bank_button,
)
from clear_budget.ui.widgets.credit_card_dialog import CreditCardDialog
from clear_budget.ui.utils.table_focus import keyboard_only_focus
from clear_budget.ui.utils.text_metrics import apply_comfortable_rows


class CreditCardView(
    CreditCardProjectionStripMixin, CreditCardViewLoaderMixin, QWidget
):
    """Displays credit card status with exhaustion warnings."""

    def __init__(
        self,
        budget_service: BudgetService,
        current_month: YearMonth | None = None,
        base_month: YearMonth | None = None,
    ) -> None:
        """Initialize credit card view widget.

        `base_month` is the month the tray's Previous arrow stops at; the
        month graph dialog inherits the same bound so the two navigations
        agree. It defaults to the starting month, which is what the tray's
        own wiring bounds it to when the app opens on today.
        """
        super().__init__()
        self.budget_service = budget_service
        self.current_month = current_month or YearMonth.today()
        self.base_month = base_month or self.current_month
        self.init_ui()
        self.load_cards()

    def init_ui(self) -> None:
        """Build credit card view layout."""
        layout = QVBoxLayout()

        self.prev_btn = QPushButton("← Previous")
        self.next_btn = QPushButton("Next →")
        _glyph_h = nav_glyph_height(self.prev_btn)
        self.load_btn, self.save_btn = build_save_load_buttons(_glyph_h)
        self.budgets_btn = build_budgets_button(_glyph_h)
        _sep, self.bank_btn = build_bank_button(_glyph_h)
        self.info_btn = build_info_button(_glyph_h)
        # The primary view buttons live in this tray, so every view builds its
        # own set; MainWindow wires them and keeps the current-view mark in
        # step across all four.
        self.view_btns = build_view_buttons(_glyph_h)
        (
            self.nav_header,
            self.month_label,
            self.theme_btn,
        ) = build_centered_nav_header(
            "",
            prev_btn=self.prev_btn,
            next_btn=self.next_btn,
            leading=(
                self.load_btn,
                self.save_btn,
                self.budgets_btn,
                _sep,
                self.bank_btn,
            ),
            views=self.view_btns[:-1],
            pre_theme=(build_tray_separator(_glyph_h), self.view_btns[-1]),
            trailing=(self.info_btn,),
        )
        self._refresh_month_label()

        cards_group = QGroupBox("Credit Cards")
        cards_outer_layout = QVBoxLayout()

        # Cards stack directly in the group. The whole view already lives inside a
        # ScrollableView, so a second inner scroll only stole height and left an
        # empty gap above the Add Card button whenever few cards were present.
        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(ui_scale.px(8))
        cards_outer_layout.addWidget(self.cards_container)

        # Buttons below the card list
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("Add Card")
        btn_layout.addWidget(self.add_btn)
        btn_layout.addStretch()
        cards_outer_layout.addLayout(btn_layout)

        cards_group.setLayout(cards_outer_layout)
        layout.addWidget(cards_group, 0)

        proj_group = QGroupBox(f"{_PROJECTION_MONTHS}-Month Balance Projection")
        proj_layout = QVBoxLayout()
        self.projection_table = QTableWidget()
        apply_comfortable_rows(self.projection_table)
        keyboard_only_focus(self.projection_table)
        self.projection_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.projection_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        _ph = self.projection_table.horizontalHeader()
        _ph.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        # Columns always stretch to fit, so no horizontal scrollbar is ever
        # needed; turning it off keeps it from eating into the fixed height and
        # clipping the final month row.
        self.projection_table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        # The strip is locked to exactly its rows in _build_projection_strip,
        # once the columns (and so the real header height) are populated.
        proj_layout.addWidget(self.projection_table)
        proj_group.setLayout(proj_layout)
        proj_group.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
        )
        self.projection_group = proj_group
        layout.addWidget(proj_group, 0)
        # With few cards the content is shorter than the view: let the slack fall
        # to the bottom so the card list and projection stay compact at the top,
        # rather than the card list stretching and pushing the projection off.
        layout.addStretch(1)

        self.setLayout(layout)

        self.add_btn.clicked.connect(self.on_add_card)

    def set_month(self, year_month: YearMonth) -> None:
        """Update the displayed month. The reload follows on the summary.

        This does NOT call `load_cards` itself. `MonthViewModel.set_month`
        emits `month_changed` and then refreshes the summary, so a reload here
        would be the first of two for one month change. The month is set first,
        which matters: `load_cards` reads `current_month`.
        """
        object.__setattr__(self, "current_month", year_month)
        self._refresh_month_label()

    def on_month_summary_updated(self, _summary) -> None:
        """Recompute the panels and the projection when the month's data changes.

        A card's Payment Received and its whole projection are driven by a
        `credit_payment` bill, which is created and edited on the Monthly
        Budget view. Nothing on THIS view changes when that happens, so without
        this the panels kept whatever was true when the window was built: a
        card paid off every month still projected a balance climbing past its
        limit; Payment Received sat at zero beside the bill paying it.

        The summary is ignored. It arrives because the signal carries it and
        because being told the month's data moved is the whole message; the
        card figures are read from the service, not from the summary.
        """
        self.load_cards()

    def _refresh_month_label(self) -> None:
        from clear_budget.ui.utils.format_helpers import MONTH_NAMES

        self.month_label.setText(
            f"{MONTH_NAMES[self.current_month.month]} {self.current_month.year}"
        )

    def set_nav_label_color(self, color: str) -> None:
        """Recolour the nav month label to match the Solvency view."""
        apply_nav_label_color(self.month_label, color)

    def restyle(self) -> None:
        """Rebuild the card panels and projection cells after a theme switch."""
        self.load_cards()

    def nav_targets(self) -> list:
        """Ordered keyboard-ring stops for this view.

        READING order, which with two stacked trays means the TOP tray first
        and the lower one after it, each left to right as drawn. A ring that
        disagrees with the drawing does not present as a wrong order, it
        presents as a SKIPPED control: the user views past where a button
        visibly is and lands somewhere else entirely.

        The button for the view being shown is not in the list. It is a stop
        that could do nothing, dropped here rather than disabled, because a
        disabled control paints the permanent red ring and would read as
        broken rather than as current.
        """
        # Archive was moved out of the button run to the right-hand group,
        # so the ring has to walk it there. A ring that disagrees with the
        # drawing reads as a SKIPPED control, not as a wrong order.
        #
        # The card panels sit BEFORE the graph icon by decision (2026-08-24):
        # the work of this view is its cards, so the ring runs toggle, Edit,
        # Delete per panel, then Add Card, then continues into the graph icon
        # and the right-hand tray group. A task-flow override of the strict
        # reading order, chosen deliberately.
        others = ring_view_stops(self.view_btns[:-1])
        archive_stop = ring_view_stops(self.view_btns[-1:])
        card_stops = list(getattr(self, "card_nav_stops", []))
        return [
            self.prev_btn,
            self.next_btn,
            self.load_btn,
            self.save_btn,
            self.budgets_btn,
            self.bank_btn,
            *others,
            *card_stops,
            self.add_btn,
            *archive_stop,
            self.theme_btn,
            self.info_btn,
            self.projection_table,
        ]

    def nav_entry_stop(self):
        """Where the ring is entered from neutral on this view.

        The first card's Active toggle: arriving on Credit Cards, the first
        Tab lands on the first card rather than on the File menu, because the
        cards are what the view is opened for. With no cards yet, Add Card is
        the one action the view offers.
        """
        stops = getattr(self, "card_nav_stops", [])
        return stops[0] if stops else self.add_btn

    def _get_status_text(self, utilization: float) -> str:
        """Get status text based on card utilization."""
        if utilization >= 80:
            return "DANGER"
        if utilization >= 50:
            return "WARNING"
        return "OK"

    def _get_status_color(self, status: str) -> QColor:
        """Traffic-light colour for a card's utilisation status."""
        states = theme.state_colours()
        if status == "DANGER":
            return QColor(states[STATE_RED])
        if status == "WARNING":
            return QColor(states[STATE_CAUTION])
        return QColor(states[STATE_SAFE])

    def on_add_card(self) -> None:
        dialog = CreditCardDialog(self)
        if dialog.exec():
            card = dialog.get_card()
            if card:
                existing = self.budget_service.get_credit_cards(include_inactive=True)
                if any(c.name.lower() == card.name.lower() for c in existing):
                    QMessageBox.warning(
                        self,
                        "Duplicate Card",
                        f"A card named '{card.name}' already exists.",
                    )
                    return
                new_id = self.budget_service.save_credit_card_today_balance(
                    card=card, today_balance=card.current_balance_used, is_new=True
                )
                self.budget_service.set_credit_limit_changes(
                    card_id=new_id, changes=dialog.get_limit_changes()
                )
                self.load_cards()

    def on_edit_card(self, card_id: int) -> None:
        card = self.budget_service.payment_method_repo.get_credit_card_by_id(
            card_id=card_id
        )
        if not card:
            return
        # Pre-fill with the live balance shown as "Used" so the field reflects
        # what the user owes now; the save path re-anchors it to today.
        live_balance = self.budget_service.get_live_card_balance(card=card)
        dialog = CreditCardDialog(
            self, replace(card, current_balance_used=live_balance)
        )
        if dialog.exec():
            updated_card = dialog.get_card()
            if updated_card:
                self.budget_service.save_credit_card_today_balance(
                    card=updated_card,
                    today_balance=updated_card.current_balance_used,
                    is_new=False,
                )
                self.budget_service.set_credit_limit_changes(
                    card_id=updated_card.id, changes=dialog.get_limit_changes()
                )
                self.load_cards()

    def on_delete_card(self, card_id: int, name: str) -> None:
        reply = QMessageBox.question(
            self,
            "Delete Card",
            f"Delete '{name}'? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.budget_service.payment_method_repo.hard_delete_credit_card(card_id=card_id)
        self.load_cards()

    def _on_card_active_toggled(self, card_id: int, checked: bool) -> None:
        self.budget_service.payment_method_repo.set_card_active(
            card_id=card_id, active=checked
        )
        self.load_cards()
