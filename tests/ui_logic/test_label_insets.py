"""No label takes its inset from the stylesheet.

A word-wrapped QLabel given padding or margin by a stylesheet keeps an empty
second row across a narrow band of widths, so its box grows with no extra
text (the Solvency banner was taller in one month than the next). Insets are
contents margins from ui.label_insets instead; this keeps every QLabel rule,
in both themes, from putting one back.

Checked against `widget_extras_qss`, the pure string builder that carries the
status-bar rule and every label role. The whole-sheet `build_qss` cannot run
here: it needs a live QApplication (see test_highlight_text_colour).
"""

import re

import pytest

from clear_budget.ui import label_insets, label_roles, ui_scale
from clear_budget.ui._theme_controls import widget_extras_qss
from clear_budget.ui.theme_tokens import (
    THEME_DARK,
    THEME_LIGHT,
    state_colours_for,
    tokens_for,
)

_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_RULE = re.compile(r"([^{}]*)\{([^{}]*)\}")
_BOX_SPACING = re.compile(r"(^|;)\s*(padding|margin)[\w-]*\s*:", re.MULTILINE)
_LABEL_SELECTOR = re.compile(r"(^|[\s,>])QLabel\b")


def _label_rules(theme: str) -> list[tuple[str, str]]:
    sheet = widget_extras_qss(tokens_for(theme), state_colours_for(theme))
    qss = _COMMENT.sub("", sheet)
    return [
        (" ".join(sel.split()), body)
        for sel, body in _RULE.findall(qss)
        if _LABEL_SELECTOR.search(sel)
    ]


@pytest.mark.parametrize("theme", [THEME_DARK, THEME_LIGHT])
def test_there_are_label_rules_to_check(theme):
    assert _label_rules(theme)


@pytest.mark.parametrize("theme", [THEME_DARK, THEME_LIGHT])
def test_no_label_rule_sets_padding_or_margin(theme):
    offenders = [sel for sel, body in _label_rules(theme) if _BOX_SPACING.search(body)]
    assert not offenders, offenders


def test_a_role_without_an_inset_gets_none():
    assert label_insets.inset_for(label_roles.MUTED) is None


def test_the_body_inset_follows_the_ui_scale():
    body = ui_scale.px(label_insets.BODY_PADDING_PX)
    assert label_insets.inset_for(label_roles.BODY) == (body, body, body, body)


def test_a_one_sided_inset_keeps_its_shape():
    left, top, right, bottom = label_insets.inset_for(label_roles.HINT)
    assert (top, bottom) == (0, 0)
    assert left == right > 0
