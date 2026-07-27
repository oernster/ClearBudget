"""Forward-projection rendering for SolvencyPanel.

Extracted from _solvency_panel_display to keep both modules under the 400-LOC
limit (tests/structural/test_loc_limits.py). Owns one concern: the next two
months' projection lines, the card-state text under each, and the title-bar
colour broadcast that follows from the displayed month's own health.
"""

from clear_budget.domain.services._card_live_projection import (
    anchored_month_opening_pence,
)
from clear_budget.domain.services.card_monthly_calculator import (
    calculate_card_monthly_state,
)
from clear_budget.ui import ui_scale
from clear_budget.ui.utils.format_helpers import MONTH_NAMES, apply_nav_label_color

# Unscaled type size of a projection line; the colour comes from the month's
# own traffic-light state, so it is resolved per render rather than in QSS.
_PROJECTION_FONT_PX = 17


class SolvencyPanelForwardMixin:
    """Renders the Forward Projection section and the title-bar colour."""

    def _render_forward_projection(
        self, report, overdraft_limit_pence: int, is_current_month: bool
    ) -> None:
        """Fill the M1/M2 projection labels and broadcast the title colour."""
        service = self.view_model.budget_service
        m1 = report.year_month.next_month()
        m2 = m1.next_month()
        m1_summary = service.get_month_summary(year_month=m1)
        m2_summary = service.get_month_summary(year_month=m2)
        m1_bank = self._bank_total(m1_summary)
        m2_bank = self._bank_total(m2_summary)
        m1_end_pence = report.balance_pence + m1_summary.total_income.pence - m1_bank

        self._rebuild_card_bars(report)

        m1_text, m1_color, m1_clarion = self._build_month_cashflow_summary(
            report.balance_pence,
            m1_summary,
            m1_bank - m1_summary.total_income.pence,
            overdraft_limit_pence,
        )
        m2_text, m2_color, m2_clarion = self._build_month_cashflow_summary(
            m1_end_pence,
            m2_summary,
            m2_bank - m2_summary.total_income.pence,
            overdraft_limit_pence,
        )

        cards = service.get_credit_cards(include_inactive=False)
        m1_card_opening = {
            c.id: anchored_month_opening_pence(
                card=c, bills=list(m1_summary.bills), year=m1.year, month=m1.month
            )
            for c in cards
        }
        m1_card_states = {
            c.id: calculate_card_monthly_state(
                card=c,
                opening_balance_pence=m1_card_opening[c.id],
                bills=list(m1_summary.bills),
            )
            for c in cards
        }
        m2_card_opening = {
            c.id: m1_card_states[c.id].closing_balance.pence for c in cards
        }

        self._set_projection_label(
            self.m1_projection_label,
            heading=f"{MONTH_NAMES[m1.month]} {m1.year}",
            body=m1_text,
            card_text=self._build_card_state_text(
                cards, m1_summary.bills, m1_card_opening
            ),
            colour=m1_color,
            clarion=m1_clarion,
        )
        self._set_projection_label(
            self.m2_projection_label,
            heading=f"{MONTH_NAMES[m2.month]} {m2.year}",
            body=m2_text,
            card_text=self._build_card_state_text(
                cards, m2_summary.bills, m2_card_opening
            ),
            colour=m2_color,
            clarion=m2_clarion,
        )

        # The title-bar colour is the displayed month's OWN within-month health,
        # the same colour Solvency shows for that month: red only when that
        # month's balance actually drops below zero, amber when it dips low or
        # runs at a loss but stays in the black, green when it stays comfortable.
        # It must NOT inherit the banner's next-month overdraft warning: a month
        # that itself never goes negative (e.g. dips to a small positive low)
        # stays amber even while the banner shouts about the month after it.
        current_month_color = self._title_health_color(
            report, is_current_month, overdraft_limit_pence
        )
        apply_nav_label_color(self.month_label, current_month_color)
        # Solvency is the single source of truth for the nav label colour;
        # broadcast it so the other tabs' month/year labels match.
        self.month_label_color_changed.emit(current_month_color)

    @staticmethod
    def _bank_total(summary) -> int:
        """Total pence of a month's bills paid from the bank account."""
        return sum(b.amount.pence for b in summary.bills if b.payment_method_id == 1)

    @staticmethod
    def _set_projection_label(
        label, *, heading: str, body: str, card_text: str, colour: str, clarion: bool
    ) -> None:
        """Write one projection line, in its month's traffic-light colour."""
        text = f"{heading}\n{body}"
        if card_text:
            text += f"\n{card_text}"
        style = f"font-size: {_PROJECTION_FONT_PX}px; padding: 5px; color: {colour};"
        if clarion:
            style += " font-weight: bold; font-style: italic;"
        label.setText(text)
        label.setStyleSheet(ui_scale.style(style))
