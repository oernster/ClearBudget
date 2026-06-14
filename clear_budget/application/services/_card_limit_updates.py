"""Auto-apply elapsed credit limit changes - extracted for LOC limit."""

from datetime import date

from clear_budget.domain.services.credit_limit_schedule import (
    effective_credit_limit_pence,
)


def apply_elapsed_limit_changes(payment_method_repo, *, today: date) -> None:
    """Fold any scheduled limit change whose date has passed into the card.

    A card's current limit becomes the latest change effective on or before
    `today` (same-day ties resolved to the last entered); the applied changes
    are dropped and only the still-upcoming changes are retained. So once a
    change's date passes, the displayed `Credit Limit` simply is the new value
    and the schedule holds only what is still ahead.
    """
    today_key = (today.year, today.month, today.day)
    cards = payment_method_repo.get_all_credit_cards(include_inactive=False)
    for card in cards:
        applied = [c for c in card.scheduled_limit_changes if c.sort_key <= today_key]
        if not applied:
            continue
        future = tuple(
            c for c in card.scheduled_limit_changes if c.sort_key > today_key
        )
        new_limit_pence = effective_credit_limit_pence(card=card, as_of=today)
        payment_method_repo.update_credit_card_limit(
            card_id=card.id, limit_pence=new_limit_pence
        )
        payment_method_repo.set_credit_limit_changes(card_id=card.id, changes=future)
