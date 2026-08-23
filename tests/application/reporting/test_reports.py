"""Tests for the two exported HTML reports.

Both are single self-contained files a user will email or print, so the two
properties that matter are that everything is inline (no external reference
that would break once the file moves) and that user text cannot inject
markup. Beyond that: the month report must carry BOTH renderings, which is
the whole reason it exists; the projection report must show the in-month
low rather than only the closing balance, which is the case it exists to
catch.
"""

import pytest

from clear_budget.application.dto.projection_month import (
    STATE_CAUTION,
    STATE_RED,
    STATE_SAFE,
    ProjectionMonth,
)
from clear_budget.application.reporting.month_report import month_report_html
from clear_budget.application.reporting.projection_report import (
    projection_report_html,
)


class _Series:
    def __init__(self, label, values):
        self.label = label
        self.values = tuple(values)


_DAYS = 28
_SERIES = _Series("Bank balance", [200_00 - 5_00 * d for d in range(_DAYS)])


def _month(**overrides):
    base = {
        "year": 2026,
        "month": 3,
        "label": "March 2026",
        "opening_pence": 200_00,
        "closing_pence": 150_00,
        "low_pence": 120_00,
        "low_day": 18,
        "income_pence": 250_00,
        "bank_bills_pence": 300_00,
        "floor_pence": -500_00,
    }
    base.update(overrides)
    return ProjectionMonth(**base)


def _report():
    return month_report_html(title="T", subtitle="S", series=[_SERIES])


# The month report carries both renderings, which the dialog cannot.
def test_the_month_report_carries_both_charts():
    html = _report()
    assert html.count("<svg") == 2


def test_the_month_report_explains_each_chart():
    html = _report()
    assert "Each bar is the balance at the end of that day" in html
    assert "The same figures joined day to day" in html


def test_the_month_report_pulls_out_the_low_and_its_day():
    html = month_report_html(title="T", subtitle="S", series=[_SERIES])
    assert f"Lowest point (day {_DAYS})" in html


def test_a_month_with_nothing_to_plot_says_so_rather_than_failing():
    html = month_report_html(title="T", subtitle="S", series=[])
    assert "nothing to plot" in html


# Both reports must survive being moved, mailed and opened offline.
@pytest.mark.parametrize(
    "html",
    [
        month_report_html(title="T", subtitle="S", series=[_SERIES]),
        projection_report_html(title="T", subtitle="S", months=[_month()]),
    ],
)
def test_a_report_references_nothing_outside_itself(html):
    """No src, href or @import: the file must stand alone."""
    assert "<img" not in html
    assert "src=" not in html
    assert "href=" not in html
    assert "@import" not in html
    assert html.startswith("<!DOCTYPE html>")


def test_user_text_cannot_inject_markup_into_a_report():
    hostile = _Series("<script>alert(1)</script>", [10] * 5)
    html = month_report_html(title="<b>T</b>", subtitle="S", series=[hostile])
    assert "<script>" not in html
    assert "<b>T</b>" not in html


# The projection report exists to show the dip a closing balance hides.
def test_the_projection_shows_the_in_month_low_not_just_the_close():
    html = projection_report_html(title="T", subtitle="S", months=[_month()])
    assert "Lowest bank balance in the month" in html
    assert "day 18" in html


def test_the_projection_says_the_figures_are_bank_balances():
    """The report was unlabelled, so the numbers read as coming from nowhere."""
    html = projection_report_html(title="T", subtitle="S", months=[_month()])
    assert "Every figure here is your bank balance" in html
    assert "Opening balance" in html
    assert "Closing balance" in html


def test_the_projection_names_the_balance_it_was_chained_from():
    html = projection_report_html(
        title="T", subtitle="S", months=[_month()], recorded_balance_pence=1234_56
    )
    assert "Chained from your recorded bank balance of" in html
    assert "1,234.56" in html


def test_the_anchor_line_is_omitted_when_no_balance_is_supplied():
    html = projection_report_html(title="T", subtitle="S", months=[_month()])
    assert "Chained from" not in html


def test_the_projection_charts_two_lines_per_month():
    html = projection_report_html(
        title="T", subtitle="S", months=[_month(), _month(label="April 2026")]
    )
    assert html.count("<polyline") == 2


@pytest.mark.parametrize(
    ("month", "expected"),
    [
        (_month(low_pence=10_00, closing_pence=300_00), "Safe"),
        (_month(low_pence=-100_00), "Caution"),
        (_month(low_pence=-600_00), "Below floor"),
    ],
)
def test_each_month_is_labelled_with_its_state(month, expected):
    html = projection_report_html(title="T", subtitle="S", months=[month])
    assert expected in html


def test_the_floor_is_stated_when_one_is_set():
    html = projection_report_html(title="T", subtitle="S", months=[_month()])
    assert "Agreed overdraft floor" in html


def test_no_facility_says_the_floor_is_zero():
    html = projection_report_html(
        title="T", subtitle="S", months=[_month(floor_pence=0)]
    )
    assert "No overdraft facility is set" in html


def test_an_empty_range_says_so_rather_than_failing():
    html = projection_report_html(title="T", subtitle="S", months=[])
    assert "No months were selected" in html


# The state rule itself.
@pytest.mark.parametrize(
    ("month", "expected"),
    [
        (_month(low_pence=10_00, closing_pence=300_00), STATE_SAFE),
        (_month(low_pence=-1, closing_pence=300_00), STATE_CAUTION),
        (_month(low_pence=10_00, closing_pence=100_00), STATE_CAUTION),
        (_month(low_pence=-500_01), STATE_RED),
    ],
)
def test_the_state_rule(month, expected):
    """Red below the floor, caution for a dip or a losing month, else safe."""
    assert month.state == expected


def test_net_is_income_less_bank_bills():
    assert _month(income_pence=250_00, bank_bills_pence=300_00).net_pence == -50_00
