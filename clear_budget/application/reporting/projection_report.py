"""A range of months exported as HTML: the path of solvency over time.

Where month_report answers "how does this month go", this answers "where is
this heading". It plots two lines per month, the closing balance and the
LOWEST point reached inside that month, because those diverge in exactly the
case worth catching: a month that opens and closes in credit but bounces a
payment in the third week. A report drawn from closing balances alone would
show that month as fine.

Pure string building: no Qt, no file access, no clock.
"""

from __future__ import annotations

from clear_budget.application.dto.projection_month import (
    STATE_CAUTION,
    STATE_RED,
    STATE_SAFE,
)
from clear_budget.application.reporting.chart_svg import chart_svg
from clear_budget.application.reporting.document import document, escape, money

_CLOSING_LABEL = "Bank balance at month end"
_LOW_LABEL = "Lowest bank balance in the month"

_STATE_TEXT = {
    STATE_SAFE: "Safe",
    STATE_CAUTION: "Caution",
    STATE_RED: "Below floor",
}
_STATE_CLASS = {
    STATE_SAFE: "state-safe",
    STATE_CAUTION: "state-caution",
    STATE_RED: "state-red",
}

_INTRO = (
    "Every figure here is your bank balance. Each month is projected with the "
    "same day-by-day rules the month graph uses, starting from the balance "
    "recorded in the app and carrying forward: each month opens on the "
    "balance the month before it closed with, so opening plus net equals "
    "month end, all the way down the table."
)
_CHART_TEXT = (
    "Two lines per month. The upper one is the bank balance each month ends "
    "on; the lower one is the lowest that balance gets at any point inside "
    "the month. When they pull apart, the month has a dip in it that the "
    "closing figure hides, which is where a payment fails even though the "
    "month looks healthy on paper."
)
_STATE_TEXT_NOTE = (
    "Safe means the balance stays above zero all month. Caution means either "
    "that it dips below zero into an arranged overdraft or that the month "
    "ends lower than it started. Below floor means it goes past the agreed "
    "overdraft limit, where a payment stops clearing."
)


class _Line:
    """A labelled series of one value per month, shaped for chart_svg."""

    def __init__(self, label: str, values) -> None:
        self.label = label
        self.values = tuple(values)


def _summary_figures(months) -> str:
    closing = [m.closing_pence for m in months]
    worst = min(months, key=lambda m: m.low_pence)
    rows = (
        ("Balance at the start", money(months[0].opening_pence)),
        ("Balance at the end", money(closing[-1])),
        ("Change over the range", money(closing[-1] - months[0].opening_pence)),
        (f"Lowest it ever gets ({escape(worst.label)})", money(worst.low_pence)),
    )
    items = "".join(
        f"<div><dt>{escape(label)}</dt><dd>{escape(value)}</dd></div>"
        for label, value in rows
    )
    return f'<dl class="figures">{items}</dl>'


def _table(months) -> str:
    """Opening, net and close side by side so the chain can be checked by eye."""
    head = (
        "<thead><tr><th>Month</th><th>Opening balance</th><th>Income</th>"
        "<th>Bills</th><th>Net</th><th>Closing balance</th>"
        "<th>Lowest in month</th><th>State</th></tr></thead>"
    )
    rows = []
    for month in months:
        state = month.state
        rows.append(
            "<tr>"
            f"<td>{escape(month.label)}</td>"
            f"<td>{escape(money(month.opening_pence))}</td>"
            f"<td>{escape(money(month.income_pence))}</td>"
            f"<td>{escape(money(month.bank_bills_pence))}</td>"
            f"<td>{escape(money(month.net_pence))}</td>"
            f"<td>{escape(money(month.closing_pence))}</td>"
            f"<td>{escape(money(month.low_pence))} (day {month.low_day})</td>"
            f'<td class="state {_STATE_CLASS[state]}">'
            f"{escape(_STATE_TEXT[state])}</td>"
            "</tr>"
        )
    return f"<table>{head}<tbody>{''.join(rows)}</tbody></table>"


def _chart(months) -> str:
    lines = [
        _Line(_CLOSING_LABEL, [m.closing_pence for m in months]),
        _Line(_LOW_LABEL, [m.low_pence for m in months]),
    ]
    labels = tuple((i + 1, m.label.split(" ")[0][:3]) for i, m in enumerate(months))
    return chart_svg(lines, mode="line", labels=labels)


def projection_report_html(
    *, title: str, subtitle: str, months, recorded_balance_pence: int | None = None
) -> str:
    """Render a month range as a standalone HTML document.

    Args:
        title: Page heading, e.g. "Bank balance projection".
        subtitle: The range in words, e.g. "March 2026 to February 2027".
        months: ProjectionMonth values, ascending.
        recorded_balance_pence: The bank balance the projection was chained
            from. Stated in the report so the figures can be traced back to a
            number the user recognises rather than read as coming from
            nowhere.
    """
    projected = list(months)
    if not projected:
        body = "<section><p>No months were selected.</p></section>"
        return document(title=title, subtitle=subtitle, body=body)

    floor = projected[0].floor_pence
    floor_note = (
        f"Agreed overdraft floor: {money(floor)}."
        if floor
        else "No overdraft facility is set, so the floor is zero."
    )
    anchor_note = (
        f"Chained from your recorded bank balance of "
        f"{money(recorded_balance_pence)}."
        if recorded_balance_pence is not None
        else ""
    )
    body = (
        "<section>\n"
        f"{_summary_figures(projected)}\n"
        f"<p>{escape(_INTRO)}</p>\n"
        f'<p class="note">{escape(anchor_note)}</p>\n'
        f'<p class="note">{escape(floor_note)}</p>\n'
        "</section>\n"
        "<section>\n<h2>The path</h2>\n"
        f"<p>{escape(_CHART_TEXT)}</p>\n"
        f"<figure>{_chart(projected)}</figure>\n"
        "</section>\n"
        "<section>\n<h2>Month by month</h2>\n"
        f"{_table(projected)}\n"
        f'<p class="note">{escape(_STATE_TEXT_NOTE)}</p>\n'
        "</section>"
    )
    return document(title=title, subtitle=subtitle, body=body)
