"""A month range exported as a folder: an index plus a page per month.

The invariant these exist to police is the one the package changed. Until now
every exported report referenced nothing outside itself, which is what let a
user email one. A package cannot hold to that and still be a package, so the
rule widened by exactly one step: the FOLDER is self-contained, every outward
reference is a bare sibling filename and nothing reaches a URL, a stylesheet
or an image. That is asserted here rather than described in a docstring.
"""

from __future__ import annotations

import re

import pytest

from clear_budget.application.dto.projection_month import ProjectionMonth
from clear_budget.application.reporting.package_report import (
    INDEX_NAME,
    build_package,
    month_page_name,
    package_folder_name,
)

_DAYS = 30
_FLOOR = -20_000


class _Series:
    """The shape chart_svg reads: a label and one value per day."""

    def __init__(self, label: str, values) -> None:
        self.label = label
        self.values = tuple(values)


def _month(year: int, month: int, label: str) -> ProjectionMonth:
    return ProjectionMonth(
        year=year,
        month=month,
        label=label,
        opening_pence=100_000,
        closing_pence=120_000,
        low_pence=40_000,
        low_day=18,
        income_pence=200_000,
        bank_bills_pence=180_000,
        floor_pence=_FLOOR,
    )


@pytest.fixture()
def three_months():
    return [
        _month(2026, 3, "March 2026"),
        _month(2026, 4, "April 2026"),
        _month(2027, 1, "January 2027"),
    ]


@pytest.fixture()
def series_for(three_months):
    return {
        (m.year, m.month): [_Series("Bank balance", range(100, 100 + _DAYS))]
        for m in three_months
    }


def _by_name(files):
    return {f.name: f.html for f in files}


class TestWhatThePackageHolds:
    def test_the_index_comes_first_then_a_page_for_every_month(
        self, three_months, series_for
    ):
        files = build_package(
            title="T", months=three_months, series_by_month=series_for
        )
        assert [f.name for f in files] == [
            INDEX_NAME,
            "2026-03.html",
            "2026-04.html",
            "2027-01.html",
        ]

    def test_a_page_is_named_so_a_folder_listing_sorts_by_calendar(self):
        """The whole reason for the zero padding: December must not precede February."""
        names = sorted(month_page_name(2026, m) for m in (2, 12, 1))
        assert names == ["2026-01.html", "2026-02.html", "2026-12.html"]

    def test_the_folder_names_the_range_it_holds(self, three_months):
        assert package_folder_name(three_months) == "clearbudget-2026-03-to-2027-01"

    def test_an_empty_range_still_produces_a_readable_index(self):
        files = build_package(title="T", months=[], series_by_month={})
        assert [f.name for f in files] == [INDEX_NAME]
        assert "No months were selected." in files[0].html

    def test_an_empty_range_names_a_folder_rather_than_nothing(self):
        assert package_folder_name([]) == "clearbudget-months"


class TestHowThePagesFindEachOther:
    def test_every_month_row_leads_to_that_month_page(self, three_months, series_for):
        index = _by_name(
            build_package(title="T", months=three_months, series_by_month=series_for)
        )[INDEX_NAME]
        for month in three_months:
            name = month_page_name(month.year, month.month)
            assert f'<a href="{name}">{month.label}</a>' in index

    def test_every_month_page_leads_back_to_the_index(self, three_months, series_for):
        files = _by_name(
            build_package(title="T", months=three_months, series_by_month=series_for)
        )
        for name, html in files.items():
            if name == INDEX_NAME:
                continue
            assert f'<a href="{INDEX_NAME}">' in html

    def test_a_month_that_cannot_be_plotted_gets_a_row_but_no_dead_link(
        self, three_months, series_for
    ):
        """A link to a page that was never written is worse than no link."""
        del series_for[(2026, 4)]
        files = build_package(
            title="T", months=three_months, series_by_month=series_for
        )
        assert "2026-04.html" not in [f.name for f in files]
        index = _by_name(files)[INDEX_NAME]
        assert 'href="2026-04.html"' not in index
        assert "April 2026" in index

    def test_no_series_at_all_leaves_an_index_that_links_nowhere(self, three_months):
        files = build_package(title="T", months=three_months, series_by_month={})
        assert [f.name for f in files] == [INDEX_NAME]
        assert "href=" not in _by_name(files)[INDEX_NAME]


class TestThePackageIsSelfContained:
    """The widened invariant: siblings only, never anything off the folder."""

    def test_no_page_reaches_outside_the_folder(self, three_months, series_for):
        files = build_package(
            title="T", months=three_months, series_by_month=series_for
        )
        names = {f.name for f in files}
        for file in files:
            for href in re.findall(r'href="([^"]*)"', file.html):
                assert href in names, f"{file.name} links to {href!r}, not a sibling"

    def test_nothing_is_fetched_from_anywhere(self, three_months, series_for):
        """Styles and charts stay inline, exactly as a single report's do.

        The SVG namespace declaration is a URI and not a fetch, which is why
        this checks the places a browser would actually go rather than the
        string "http" anywhere in the markup.
        """
        for file in build_package(
            title="T", months=three_months, series_by_month=series_for
        ):
            assert "<img" not in file.html
            assert "src=" not in file.html
            assert "@import" not in file.html
            assert 'href="http' not in file.html
            assert "url(" not in file.html

    def test_every_file_is_a_whole_document(self, three_months, series_for):
        for file in build_package(
            title="T", months=three_months, series_by_month=series_for
        ):
            assert file.html.startswith("<!DOCTYPE html>")

    def test_a_page_name_can_never_climb_out_of_the_folder(self):
        """The name is built from integers, so there is nothing to escape with."""
        assert month_page_name(2026, 3) == "2026-03.html"
        assert "/" not in month_page_name(2026, 3)
        assert "\\" not in month_page_name(2026, 3)


class TestThePagesSayWhatTheyAre:
    def test_a_month_page_is_titled_with_its_month(self, three_months, series_for):
        html = _by_name(
            build_package(title="T", months=three_months, series_by_month=series_for)
        )["2026-03.html"]
        assert "<title>March 2026: bank balance by day</title>" in html

    def test_the_index_names_the_range_it_covers(self, three_months, series_for):
        index = _by_name(
            build_package(
                title="Bank balance projection",
                months=three_months,
                series_by_month=series_for,
            )
        )[INDEX_NAME]
        assert "March 2026 to January 2027" in index

    def test_the_index_still_states_the_balance_it_was_chained_from(
        self, three_months, series_for
    ):
        index = _by_name(
            build_package(
                title="T",
                months=three_months,
                series_by_month=series_for,
                recorded_balance_pence=123_456,
            )
        )[INDEX_NAME]
        assert "Chained from your recorded bank balance" in index

    def test_a_month_page_carries_the_overdraft_floor_of_its_month(
        self, three_months, series_for
    ):
        """A bar inside an arranged facility must read amber here as on screen."""
        below = [_Series("Bank balance", [-1_000] * _DAYS)]
        series_for[(2026, 3)] = below
        html = _by_name(
            build_package(title="T", months=three_months, series_by_month=series_for)
        )["2026-03.html"]
        from clear_budget.ui.theme_tokens import CHART_BAR_WITHIN_DARK

        assert CHART_BAR_WITHIN_DARK.lstrip("#") in html.lower().replace("#", "")
