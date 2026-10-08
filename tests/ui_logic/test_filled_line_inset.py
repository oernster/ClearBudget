"""The Solvency filled lines must take their inset from contents margins.

On a word-wrapped QLabel, QSS padding or margin is taken off the width twice
when Qt sizes the wrap. A sentence that fitted with less than twice the inset
to spare was given an empty second row, so the amber banner grew taller from
one month to the next with no extra text (measured: 40px to 63px across
exactly a 20px band of widths). The inset now lives in contents margins; this
keeps any rule that names either role from putting it back in the stylesheet.
"""

import re

from clear_budget.ui._theme_labels_solvency import solvency_label_roles_qss
from clear_budget.ui.theme_tokens import THEME_DARK, state_colours_for, tokens_for

_FILLED_ROLES = ("SolvencyBanner", "SafeToSpendHeadline")
_RULE = re.compile(r"([^{}]*)\{([^{}]*)\}")
_BOX_SPACING = re.compile(r"^\s*(padding|margin)\b", re.MULTILINE)
_ANY_PX = 1


def _qss() -> str:
    return solvency_label_roles_qss(
        tokens_for(THEME_DARK),
        state_colours_for(THEME_DARK),
        section_px=_ANY_PX,
        breakdown_px=_ANY_PX,
        heading_px=_ANY_PX,
    )


def _filled_rules() -> list[tuple[str, str]]:
    rules = [(sel, body) for sel, body in _RULE.findall(_qss())]
    return [(sel, body) for sel, body in rules if any(r in sel for r in _FILLED_ROLES)]


def test_filled_roles_have_rules_to_check():
    assert _filled_rules()


def test_no_filled_role_rule_sets_padding_or_margin():
    offenders = [
        sel.strip() for sel, body in _filled_rules() if _BOX_SPACING.search(body)
    ]
    assert not offenders, offenders
