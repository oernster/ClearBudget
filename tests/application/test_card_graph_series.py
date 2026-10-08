"""Tests for the month graph's card series and its chained openings."""

from clear_budget.application.services._card_projection import card_openings_at
from clear_budget.domain.entities.credit_card import CreditCard
from clear_budget.domain.value_objects.amount import Amount
from tests.application._graph_support import (
    _AUGUST,
    _JULY,
    _OCTOBER,
    _SEPTEMBER,
    _TODAY,
    _bill,
)


class TestCardGraphSeries:
    def _add_card(self, svc, name: str, used: int) -> CreditCard:
        card = CreditCard(
            id=0,
            name=name,
            credit_limit=Amount(pence=500000),
            current_balance_used=Amount(pence=used),
        )
        return svc.payment_method_repo.add_credit_card(card=card)

    def test_card_series_tracks_charges_and_payments(self, budget_service):
        card = self._add_card(budget_service, "Visa", 10000)
        budget_service.add_bill(bill=_bill("Sub", 3000, 10, method=card.id))
        budget_service.add_bill(
            bill=_bill(
                "Visa payment",
                2000,
                20,
                category="credit_payment",
                target_card_id=card.id,
            )
        )
        series = budget_service.get_card_graph_series(year_month=_AUGUST)
        assert [s.label for s in series] == ["Visa"]
        values = series[0].values
        assert len(values) == 31
        assert values[0] == 10000
        assert values[9] == 13000  # charge lands day 10
        assert values[19] == 11000  # payment lands day 20
        assert values[30] == 11000

    def test_card_balance_never_goes_negative(self, budget_service):
        card = self._add_card(budget_service, "Visa", 1000)
        budget_service.add_bill(
            bill=_bill(
                "Big payment",
                50000,
                5,
                category="credit_payment",
                target_card_id=card.id,
            )
        )
        series = budget_service.get_card_graph_series(year_month=_AUGUST)
        assert series[0].values[10] == 0

    def test_no_cards_means_no_series(self, budget_service):
        assert budget_service.get_card_graph_series(year_month=_AUGUST) == []


def _chained_card(svc, name: str, used: int, apr: float | None = None) -> CreditCard:
    card = CreditCard(
        id=0,
        name=name,
        credit_limit=Amount(pence=500000),
        current_balance_used=Amount(pence=used),
        interest_rate_apr=apr,
    )
    return svc.payment_method_repo.add_credit_card(card=card)


class TestCardGraphChaining:
    """A future month's card series opens from the chained projection.

    The stored balance is as-of the day it was entered, so opening a distant
    month from it drew a balance untouched by every intervening payment and
    every month's interest: May 2028 showed the card where it stood today.
    """

    def test_a_future_month_opens_from_the_chained_projection(self, budget_service):
        card = _chained_card(budget_service, "Visa", 100000)
        budget_service.add_bill(
            bill=_bill(
                "Visa payment",
                10000,
                20,
                category="credit_payment",
                target_card_id=card.id,
            )
        )
        values = budget_service.get_card_graph_series(
            year_month=_OCTOBER, today=_TODAY
        )[0].values
        # July, August and September each pay 10000 off before October opens.
        assert values[0] == 70000
        assert values[18] == 70000
        assert values[19] == 60000  # October's own payment lands day 20
        assert values[30] == 60000

    def test_a_month_closes_where_the_next_one_opens(self, budget_service):
        card = _chained_card(budget_service, "Visa", 100000, apr=12.0)
        assert card.interest_rate_apr == 12.0
        september = budget_service.get_card_graph_series(
            year_month=_SEPTEMBER, today=_TODAY
        )[0].values
        october = budget_service.get_card_graph_series(
            year_month=_OCTOBER, today=_TODAY
        )[0].values
        # 1% a month: July closes 101000, August 102010; September opens there.
        assert september[0] == 102010
        assert september[-2] == 102010  # no interest until the month ends
        assert september[-1] == 103030  # the month's interest lands on its last day
        assert october[0] == 103030  # and the next month opens exactly there

    def test_the_current_month_still_opens_from_the_anchored_balance(
        self, budget_service
    ):
        _chained_card(budget_service, "Visa", 45000)
        values = budget_service.get_card_graph_series(year_month=_JULY, today=_TODAY)[
            0
        ].values
        assert values[0] == 45000

    def test_openings_for_the_current_month_are_the_anchored_opening(
        self, budget_service
    ):
        card = _chained_card(budget_service, "Visa", 12345)
        openings = card_openings_at(
            budget_service.payment_method_repo,
            budget_service.get_month_summary,
            month=_JULY,
            today_ym=_JULY,
        )
        assert openings == {card.id: 12345}

    def test_a_month_that_clears_the_card_ends_at_zero(self, budget_service):
        # Paid off in full, the card is charged no interest, so the graph's
        # last day agrees with the strip's closing balance of nothing.
        card = _chained_card(budget_service, "Visa", 100000, apr=12.0)
        budget_service.add_bill(
            bill=_bill(
                "Clear the Visa",
                100000,
                20,
                category="credit_payment",
                target_card_id=card.id,
                start=_JULY,
            )
        )
        values = budget_service.get_card_graph_series(year_month=_JULY, today=_TODAY)[
            0
        ].values
        assert values[-1] == 0

    def test_a_skipped_card_payment_does_not_move_the_card(self, budget_service):
        # The reported case: a regular card payment skipped for one month was
        # still taken off the card, because the projection read the display
        # list that keeps skipped bills.
        card = _chained_card(budget_service, "Visa", 100000)
        payment = budget_service.add_bill(
            bill=_bill(
                "Visa payment",
                10000,
                20,
                category="credit_payment",
                target_card_id=card.id,
            )
        )
        budget_service.skip_bill_for_month(bill_id=payment.id, year_month=_JULY)
        openings = card_openings_at(
            budget_service.payment_method_repo,
            budget_service.get_month_summary,
            month=_AUGUST,
            today_ym=_JULY,
        )
        assert openings == {card.id: 100000}

    def test_no_cards_yields_no_openings(self, budget_service):
        openings = card_openings_at(
            budget_service.payment_method_repo,
            budget_service.get_month_summary,
            month=_OCTOBER,
            today_ym=_JULY,
        )
        assert openings == {}
