"""The mid-month dip alert for SolvencyPanel - extracted for the LOC limit.

A future month can close comfortably and still go under part-way through it,
when bills fall due before the income that covers them arrives. The close
alone hides that, so this states the dip in its own line beneath the banner.

The line reads its state the same way the banner does, against the agreed
overdraft floor rather than against zero: a dip that stays inside an arranged
facility is a CAUTION, because the facility is there precisely to absorb it,
while a dip beyond the facility (or any dip at all when none is arranged) is
CRITICAL, because that is a payment bouncing. It previously said "Critical"
for every dip, so a £19.45 dip inside an arranged £25.00 overdraft was
reported in the same words as a bounced payment. That is the same defect as
heading the section "Overdraft Status" when no overdraft exists: the words
asserting something the figures do not support.

The label carries its state as a Qt property and lets the stylesheet supply
the fill, exactly as the banner does. Without that the strip stayed the fixed
danger red it had always been, which would have moved the mismatch rather
than fixing it: a line reading "Caution" on a red field.
"""

from clear_budget.ui.theme_tokens import STATE_AT_RISK, STATE_RED
from clear_budget.ui.utils.format_helpers import fmt

# Same convention as the application-layer modules, which each name this
# locally rather than sharing a constant across the layer boundary.
_BANK_PAYMENT_METHOD_ID = 1
# A bill with no stated day is assumed late in the month and income early, so
# neither is credited with helping earlier than it might.
_ASSUMED_BILL_DAY = 28
_ASSUMED_INCOME_DAY = 1
# A month whose income all lands on the 1st cannot dip before it.
_EARLIEST_MEANINGFUL_INCOME_DAY = 1


class SolvencyPanelMidmonthMixin:
    """Whether a future month dips before its income lands; how to say so."""

    @staticmethod
    def _midmonth_dip(report, summary):
        """(shortfall_pence, income_day) for a month that dips; None if it holds.

        `shortfall_pence` is positive and is how far below zero the account
        goes; `income_day` is the day the last of the month's income arrives,
        which is the day the dip ends.
        """
        income_days = [
            (i.day_of_month or _ASSUMED_INCOME_DAY, i.amount.pence)
            for i in summary.income_sources
        ]
        if not income_days:
            return None
        income_day = max(day for day, _ in income_days)
        if income_day <= _EARLIEST_MEANINGFUL_INCOME_DAY:
            return None
        # The month's opening balance: its close with the month's own income
        # taken back out and its own bank bills put back in.
        opening_pence = (
            report.balance_pence - summary.total_income.pence + summary.bank_bills.pence
        )
        early_income = sum(amt for day, amt in income_days if day < income_day)
        early_bills = sum(
            b.amount.pence
            for b in summary.bills
            if b.payment_method_id == _BANK_PAYMENT_METHOD_ID
            and (b.day_of_month or _ASSUMED_BILL_DAY) < income_day
        )
        low_point = opening_pence + early_income - early_bills
        if low_point >= 0:
            return None
        return abs(low_point), income_day

    @staticmethod
    def _midmonth_alert_text(shortfall_pence, income_day, overdraft_limit_pence):
        """(text, state) naming the dip, read against the agreed floor.

        The day is named ONCE. It used to appear twice in nine words ("before
        day-25 income - rescued day 25"); "until the day-25 income lands"
        carries the same three facts, that the account is under, until when
        and that the income ends it, without the repetition.
        """
        ends = f"until the day-{income_day} income lands"
        if shortfall_pence <= overdraft_limit_pence:
            return (
                f"Caution: using {fmt(shortfall_pence)} of your "
                f"{fmt(overdraft_limit_pence)} overdraft {ends}",
                STATE_AT_RISK,
            )
        beyond = (
            f", beyond your {fmt(overdraft_limit_pence)} overdraft"
            if overdraft_limit_pence > 0
            else ", with no overdraft arranged"
        )
        return (
            f"Critical: {fmt(shortfall_pence)} overdrawn {ends}{beyond}",
            STATE_RED,
        )
