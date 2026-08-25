"""One month exported as HTML: both renderings of the graph, plus the text.

The dialog shows one rendering at a time because the screen has room for one.
A report has room for both; they answer different questions: the bars show
what each individual day was worth, the line shows the shape of the month. So
the export carries both rather than whichever happened to be on screen when
the button was pressed, saying what each is for.

Pure string building: no Qt, no file access, no clock.
"""

from __future__ import annotations

from clear_budget.application.reporting.chart_svg import chart_svg
from clear_budget.application.reporting.curve import daily_totals
from clear_budget.application.reporting.document import document, escape, money

_X_TICK_STEP_DAYS = 5
_BACK_TEXT = "Back to the summary"

_BAR_TEXT = (
    "Each bar is the balance at the end of that day. Read it to find a "
    "particular day: the day a large bill lands or the day before payday. "
    "The curve follows the same figures through every day's real value, so "
    "it shows the shape of the month without inventing a balance the account "
    "never held."
)
_LINE_TEXT = (
    "The same figures joined day to day. Read it for the trajectory rather "
    "than for any one day: how steeply the balance falls, where it turns and "
    "whether it recovers before the month ends."
)
_ZERO_TEXT = (
    "The dashed red line is zero. Anything below it is money the account does "
    "not have, which either means an arranged overdraft or a payment that "
    "will not clear."
)


def _day_labels(days: int) -> tuple:
    """1, then every fifth day, then the last: enough to locate a day."""
    ticks = {1, days} | set(range(_X_TICK_STEP_DAYS, days, _X_TICK_STEP_DAYS))
    return tuple((day, str(day)) for day in sorted(ticks))


def _figures(totals) -> str:
    """The four numbers worth pulling out of the series."""
    opening, closing = totals[0], totals[-1]
    low = min(totals)
    low_day = totals.index(low) + 1
    change = closing - opening
    rows = (
        ("Starts at", money(opening)),
        ("Ends at", money(closing)),
        ("Change over the month", money(change)),
        (f"Lowest point (day {low_day})", money(low)),
    )
    items = "".join(
        f"<div><dt>{escape(label)}</dt><dd>{escape(value)}</dd></div>"
        for label, value in rows
    )
    return f'<dl class="figures">{items}</dl>'


def _back_to_index(home_link) -> str:
    """A link home; nothing at all when this page stands alone.

    The only outward reference a month page ever carries; it points at a
    sibling in the same folder. See `package_report` for what that costs.
    """
    if not home_link:
        return ""
    href = escape(home_link)
    return f'\n<p class="note"><a href="{href}">{escape(_BACK_TEXT)}</a></p>'


def month_report_html(
    *,
    title: str,
    subtitle: str,
    series,
    floor_pence: int = 0,
    floor_values=None,
    home_link=None,
) -> str:
    """Render one month's graph as a standalone HTML document.

    Args:
        title: Page heading, e.g. "Bank balance, March 2026".
        subtitle: A line under it saying which account or cards are plotted.
        series: The GraphSeries the dialog is showing.
        floor_pence: the arranged overdraft, so an exported bar inside it
            reads amber exactly as it does on screen. Zero means no facility.
        floor_values: the reserve floor for each day, so an exported day that
            is in credit but already spoken for reads dimmed and the floor is
            drawn across the bars, exactly as it does on screen.
        home_link: the filename of the index this page belongs to, when it is
            one page of a package rather than an export on its own. None keeps
            the page standalone, which is what a single-month export is: it
            must survive being emailed by itself, so it gets no link out.
    """
    plotted = list(series)
    back = _back_to_index(home_link)
    if not plotted or not plotted[0].values:
        body = "<section><p>There is nothing to plot for this month.</p></section>"
        return document(title=title, subtitle=subtitle, body=body + back)

    totals = daily_totals([s.values for s in plotted])
    labels = _day_labels(len(plotted[0].values))
    named = ", ".join(escape(s.label) for s in plotted)
    # The bar rendering is the only one that reads either floor: bars carry a
    # per-day fill, while the line is one stroke through every day.
    bar_svg = chart_svg(
        plotted,
        mode="bar",
        labels=labels,
        floor_pence=floor_pence,
        floor_values=floor_values,
    )
    body = (
        "<section>\n"
        f"{_figures(totals)}\n"
        f'<p class="note">Plotted: {named}.</p>\n'
        "</section>\n"
        "<section>\n<h2>Day by day</h2>\n"
        f"<p>{escape(_BAR_TEXT)}</p>\n"
        f"<figure>{bar_svg}</figure>\n"
        "</section>\n"
        "<section>\n<h2>The month's path</h2>\n"
        f"<p>{escape(_LINE_TEXT)}</p>\n"
        f'<figure>{chart_svg(plotted, mode="line", labels=labels)}</figure>\n'
        f'<p class="note">{escape(_ZERO_TEXT)}</p>\n'
        "</section>" + back
    )
    return document(title=title, subtitle=subtitle, body=body)
