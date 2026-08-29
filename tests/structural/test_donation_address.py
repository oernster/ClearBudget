"""The donation address has ONE home and is the address it is meant to be.

A typo here does not fail anything at runtime: the button opens, a browser
opens and a supporter's money goes somewhere that is not Oliver's. There is no
later moment at which that surfaces, so the address is asserted literally
rather than merely referenced.

The one-home scan is the same idea as `test_colour_source`: a second copy of a
value nobody can see is how two copies drift. `clear_budget/version.py` holds
it and `docs/` necessarily repeats it in the landing page's own markup, which
is a different artefact and is checked here too.
"""

from __future__ import annotations

import re
from pathlib import Path

from clear_budget.version import DONATE_URL

_REPO = Path(__file__).resolve().parents[2]
_SOURCE_OF_TRUTH = _REPO / "clear_budget" / "version.py"
_SITE_PAGE = _REPO / "docs" / "index.html"

# The address as it must be. Written out rather than derived from the constant,
# because a test that reads the value it is checking proves nothing.
_EXPECTED = "https://www.paypal.com/ncp/payment/M874QPXXJPY84"

# Stops at whitespace or a quote, so an address in HTML markup comes back
# without the attribute's closing quote attached to it.
_PAYPAL = re.compile(r"https://www\.paypal\.com/[^\s\"'<>]*")


def test_the_address_is_the_one_that_was_generated_for_clearbudget() -> None:
    """PigeonPost and Stellody carry different paths; a copied one misdirects."""
    assert DONATE_URL == _EXPECTED


def test_the_address_is_never_handed_out_over_plain_http() -> None:
    """A payment page reached over http is one a stranger can rewrite."""
    assert DONATE_URL.startswith("https://")


def test_the_package_holds_the_address_exactly_once() -> None:
    """One home. A second copy in the package is a copy that can drift."""
    hits = []
    for path in sorted((_REPO / "clear_budget").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        hits.extend((path, found) for found in _PAYPAL.findall(text))
    assert len(hits) == 1, f"expected one PayPal address, found {hits}"
    assert hits[0][0] == _SOURCE_OF_TRUTH


def test_the_landing_page_links_the_same_address() -> None:
    """The site cannot import the constant, so the two are compared instead."""
    found = _PAYPAL.findall(_SITE_PAGE.read_text(encoding="utf-8"))
    assert found, "the landing page carries no donation link"
    assert set(found) == {DONATE_URL}
