"""Text emission shared by the SVG chart's frame and its legend.

The escape and the one text style used to sit in chart_svg, which is where
the grid and the day labels still call them from. The legend moved into its
own module and needs the same two, so they live here rather than in either
caller; the alternative was a second copy of the style string.
"""

from __future__ import annotations

from clear_budget.application.reporting import _chart_svg_theme as theme


def escape(text: str) -> str:
    """Escape the five characters that would otherwise break the markup."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def axis_text(x, y, anchor: str, label) -> str:
    """One piece of axis or legend text, in the chart's muted label style.

    The callers differ only in where the text sits and how it hangs off that
    point, so the style is written once.
    """
    return (
        f'<text x="{x}" y="{y}" text-anchor="{anchor}" '
        f'fill="{theme.MUTED}" font-size="{theme.AXIS_FONT}">'
        f"{escape(label)}</text>"
    )
